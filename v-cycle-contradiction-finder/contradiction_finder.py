"""Small multi-agent contradiction finder for two Markdown documents."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from aws_bedrock_token_generator import provide_token
from dotenv import load_dotenv
from pydantic import BaseModel, Field, model_validator
from strands import Agent
from strands.models.openai_responses import OpenAIResponsesModel
from strands.tools.executors import SequentialToolExecutor


class ConfigurationError(ValueError):
    pass


class DocumentInputError(ValueError):
    pass


class Evidence(BaseModel):
    document: str
    line_start: int = Field(ge=1)
    line_end: int = Field(ge=1)
    quote: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_line_range(self) -> "Evidence":
        if self.line_end < self.line_start:
            raise ValueError("line_end must be greater than or equal to line_start")
        return self


class ReviewAssessment(BaseModel):
    candidate_id: str
    verdict: Literal["confirmed", "rejected", "needs_more_evidence"]
    confidence: Literal["high", "medium", "low"]
    rationale: str


class ReviewerResponse(BaseModel):
    reviews: list[ReviewAssessment]


class ResolutionAlternative(BaseModel):
    title: str
    change_target: str
    proposed_change: str
    tradeoffs: str


class FindingResolution(BaseModel):
    candidate_id: str
    alternatives: list[ResolutionAlternative] = Field(min_length=1, max_length=3)


class ResolverResponse(BaseModel):
    resolutions: list[FindingResolution]


class ContradictionFinding(BaseModel):
    identifier: str
    title: str
    classification: Literal["direct", "transitive", "conditional", "other"]
    explanation: str
    evidence: list[Evidence] = Field(min_length=2)
    reasoning_steps: list[str] = Field(min_length=1)
    review: ReviewAssessment
    resolutions: list[ResolutionAlternative] = Field(min_length=1, max_length=3)

    @model_validator(mode="after")
    def require_confirmed_review(self) -> "ContradictionFinding":
        if self.review.verdict != "confirmed":
            raise ValueError("final findings must be confirmed by the reviewer")
        return self


class ContradictionReport(BaseModel):
    documents_scanned: list[str]
    summary: str
    findings: list[ContradictionFinding]


@dataclass(frozen=True)
class DocumentCorpus:
    documents: tuple[str, ...]
    annotated_text: str


@dataclass(frozen=True)
class ModelSettings:
    region: str
    base_url: str
    model_id: str


def load_documents(*documents: str | Path) -> DocumentCorpus:
    """Load two or more Markdown files and add source line coordinates."""
    if len(documents) < 2:
        raise DocumentInputError("At least two Markdown documents are required")
    paths = [Path(document).expanduser().resolve() for document in documents]
    if len(set(paths)) != len(paths):
        raise DocumentInputError("Markdown documents must be unique")
    sections: list[str] = []
    names: list[str] = []

    for path in paths:
        if not path.is_file():
            raise DocumentInputError(f"Markdown document does not exist: {path}")
        if path.suffix.lower() != ".md":
            raise DocumentInputError(f"Document is not a Markdown file: {path}")

        names.append(path.name)
        lines = path.read_text(encoding="utf-8").splitlines()
        annotated = [
            f"[{path.name}:{line_number}] {line}"
            for line_number, line in enumerate(lines, start=1)
        ]
        sections.append(f"--- DOCUMENT: {path.name} ---\n" + "\n".join(annotated))

    return DocumentCorpus(
        documents=tuple(names),
        annotated_text="\n\n".join(sections),
    )


def load_model_settings() -> ModelSettings:
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    required = ("AWS_REGION", "OPENAI_BASE_URL", "MODEL_ID")
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        raise ConfigurationError(
            "Missing required environment variable(s): " + ", ".join(missing)
        )
    return ModelSettings(
        region=os.environ["AWS_REGION"],
        base_url=os.environ["OPENAI_BASE_URL"],
        model_id=os.environ["MODEL_ID"],
    )


def create_model(
    settings: ModelSettings,
    *,
    stateful: bool,
) -> OpenAIResponsesModel:
    return OpenAIResponsesModel(
        model_id=settings.model_id,
        client_args={
            "api_key": provide_token(region=settings.region),
            "base_url": settings.base_url,
        },
        stateful=stateful,
    )


REVIEWER_PROMPT = """\
You are ReviewerAgent, an independent systems-document reviewer. You receive a
batch of candidate contradictions. Review every candidate and return one
verdict per candidate_id. Confirm only statements that apply to the same scope
and cannot both be satisfied. Check direct, transitive, and temporal reasoning.
Reject omissions, stylistic issues, and mere differences in detail.
"""


RESOLVER_PROMPT = """\
You are ContradictionResolverAgent. You receive a batch of contradictions
confirmed by ReviewerAgent. For every candidate_id, return one to three concrete
alternatives that make the documents consistent. State what changes, suggested
wording or design direction, and the main tradeoff.
"""


HANDLER_PROMPT = """\
You are ContradictionHandlerAgent for V-cycle documentation. Find logical
contradictions across the two or more supplied documents and suggest resolutions.

Use this exact workflow:
1. Analyze the complete corpus. Compare all relevant document pairs and compose
   implication chains that may span three or more documents.
2. Detect and deduplicate every candidate contradiction.
3. If there are no candidates, return a report with no findings and do not call
   either specialist.
4. Otherwise, call reviewer_agent exactly once with the complete candidate
   batch, including IDs, evidence, and reasoning.
5. Keep only candidates that the reviewer confirms. If none are confirmed,
   return a report with no findings and do not call contradiction_resolver_agent.
6. Otherwise, call contradiction_resolver_agent exactly once with the complete
   batch of confirmed candidates and their review results.
7. Return the final structured report.

Every finding needs verbatim quotes and exact source line ranges. Include direct,
transitive, and conditional/temporal contradictions. Do not report missing
information or writing-style issues as contradictions.

Classify by the reasoning required to expose the conflict: use "direct" for
explicitly opposing statements, "transitive" when multiple causal implications
must be composed to derive the conflicting consequence, and "conditional" when
the conflict hinges on a state predicate or temporal window. A triggering event
does not make a multi-step implication chain conditional; classify that chain as
transitive.
"""

GATEWAY_HANDLER_PROMPT = """\
You are ContradictionHandlerAgent for V-cycle documentation. The user supplies
document filenames, not document content.

Before analysis, call the Gateway get_document and get_guideline tools once for
every requested filename. Use get_document content as the evidence baseline and
use its exact line coordinates in citations. Use the corresponding guideline to
interpret document intent and quality rules, but do not report style findings as
logical contradictions.

If any document or guideline lookup fails, stop analysis, do not call either
specialist, and return a structured report with the requested filenames in
documents_scanned, no findings, and a summary naming every failed lookup. Never
analyze an incomplete corpus or invent missing content.

After retrieval:
1. Analyze the complete corpus. Compare all relevant document pairs and compose
   implication chains that may span three or more documents.
2. Detect and deduplicate every candidate contradiction.
3. If there are no candidates, return a report with no findings and do not call
   either specialist.
4. Otherwise, call reviewer_agent exactly once with the complete candidate batch.
5. Keep only reviewer-confirmed candidates. If none are confirmed, return a
   report with no findings and do not call contradiction_resolver_agent.
6. Otherwise, call contradiction_resolver_agent exactly once with all confirmed
   candidates.
7. Return the final structured report.

Classify by the reasoning required to expose the conflict: use "direct" for
explicitly opposing statements, "transitive" when multiple causal implications
must be composed to derive the conflicting consequence, and "conditional" when
the conflict hinges on a state predicate or temporal window. A triggering event
does not make a multi-step implication chain conditional; classify that chain as
transitive.
"""


def create_contradiction_handler(
    settings: ModelSettings | None = None,
    content_tools: list[Any] | None = None,
) -> Agent:
    """Create the stateful handler with two stateless agents as tools."""
    settings = settings or load_model_settings()
    content_tools = content_tools or []
    reviewer_agent = Agent(
        name="reviewer_agent",
        description="Reviews a complete batch of candidate contradictions.",
        model=create_model(settings, stateful=False),
        system_prompt=REVIEWER_PROMPT,
        structured_output_model=ReviewerResponse,
        callback_handler=None,
    )
    resolver_agent = Agent(
        name="contradiction_resolver_agent",
        description="Suggests resolutions for a batch of confirmed contradictions.",
        model=create_model(settings, stateful=False),
        system_prompt=RESOLVER_PROMPT,
        structured_output_model=ResolverResponse,
        callback_handler=None,
    )
    return Agent(
        name="contradiction_handler_agent",
        model=create_model(settings, stateful=True),
        system_prompt=GATEWAY_HANDLER_PROMPT if content_tools else HANDLER_PROMPT,
        tools=[
            reviewer_agent.as_tool(preserve_context=False),
            resolver_agent.as_tool(preserve_context=False),
            *content_tools,
        ],
        tool_executor=SequentialToolExecutor(),
        callback_handler=None,
    )


def require_report(result: Any) -> ContradictionReport:
    report = result.structured_output
    if not isinstance(report, ContradictionReport):
        raise RuntimeError("Contradiction handler returned no structured report")
    return report


def analyze_documents(
    handler: Agent,
    corpus: DocumentCorpus,
) -> ContradictionReport:
    result = handler(
        "Analyze these documents as one corpus. Bracketed prefixes are source "
        "coordinates, not document text.\n\n" + corpus.annotated_text,
        structured_output_model=ContradictionReport,
    )
    return require_report(result)


def analyze_document_names(
    handler: Agent,
    document_names: list[str],
) -> ContradictionReport:
    result = handler(
        "Retrieve and analyze these documents and their corresponding guidelines: "
        + json.dumps(document_names),
        structured_output_model=ContradictionReport,
    )
    return require_report(result)


def render_markdown(report: ContradictionReport) -> str:
    lines = [
        "# Contradiction Report",
        "",
        report.summary,
        "",
        f"Confirmed contradictions: {len(report.findings)}",
    ]
    for finding in report.findings:
        lines.extend(
            [
                "",
                f"## {finding.identifier}: {finding.title}",
                "",
                f"**Classification:** {finding.classification}",
                "",
                finding.explanation,
                "",
                "### Evidence",
            ]
        )
        for evidence in finding.evidence:
            line_range = str(evidence.line_start)
            if evidence.line_end != evidence.line_start:
                line_range += f"-{evidence.line_end}"
            lines.append(f'- `{evidence.document}:{line_range}`: "{evidence.quote}"')

        lines.extend(["", "### Reasoning"])
        lines.extend(
            f"{index}. {step}"
            for index, step in enumerate(finding.reasoning_steps, start=1)
        )
        lines.extend(
            [
                "",
                "### Review",
                "",
                f"**Confirmed ({finding.review.confidence} confidence):** "
                f"{finding.review.rationale}",
                "",
                "### Resolution Alternatives",
            ]
        )
        for index, alternative in enumerate(finding.resolutions, start=1):
            lines.extend(
                [
                    "",
                    f"{index}. **{alternative.title}**",
                    f"   - Change target: {alternative.change_target}",
                    f"   - Proposed change: {alternative.proposed_change}",
                    f"   - Tradeoffs: {alternative.tradeoffs}",
                ]
            )
    return "\n".join(lines) + "\n"


def write_json_report(report: ContradictionReport, output_path: str | Path) -> Path:
    path = Path(output_path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report.model_dump(mode="json"), indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def write_markdown_report(
    report: ContradictionReport,
    output_path: str | Path,
) -> Path:
    path = Path(output_path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_markdown(report), encoding="utf-8")
    return path
