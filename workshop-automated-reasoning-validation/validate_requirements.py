#!/usr/bin/env python3
"""Validate OpenMower requirements docs against guideline-derived guardrails.

For each (requirements doc, guardrail) pair below, sends the doc's prose
paragraphs to bedrock-runtime ApplyGuardrail (source=OUTPUT) and reports the
Automated Reasoning findings: which claims are logically valid against the
guideline, which are invalid/impossible (real contradictions), and which are
ambiguous or too complex to translate.

Automated Reasoning translates natural-language prose into formal logic, so
fenced code blocks are stripped and the doc is split into paragraphs before
validation -- sending an entire markdown doc (headers, tables, code, ASCII
diagrams) as one blob overwhelms translation and yields only `noTranslations`.

Exits non-zero if any invalid/impossible finding is found across all docs,
so this can double as a CI-style gate.
"""
import json
import re
import sys
from pathlib import Path

import boto3

REGION = "us-west-2"
REQUIREMENTS_DIR = Path(__file__).resolve().parent.parent / "workshop-current-state-requirements"
STATE_FILE = Path(__file__).resolve().parent / "policies.json"

DOC_TO_GUIDELINE_KEY = {
    "07-Software-Architecture.md": "software-architecture",
    "09-Safety-Systems.md": "safety-systems",
    "10-State-Machine-Design.md": "state-machine",
}

FINDING_TYPES = [
    "valid",
    "invalid",
    "satisfiable",
    "impossible",
    "translationAmbiguous",
    "tooComplex",
    "noTranslations",
]

VIOLATION_TYPES = {"invalid", "impossible"}

MIN_PARAGRAPH_CHARS = 30


def load_state():
    if not STATE_FILE.exists():
        print(f"No {STATE_FILE} found. Run setup_policies.py first.", file=sys.stderr)
        sys.exit(1)
    return json.loads(STATE_FILE.read_text())


def extract_paragraphs(doc_text):
    text = re.sub(r"```.*?```", "", doc_text, flags=re.S)
    paragraphs = [p.strip() for p in text.split("\n\n")]
    return [p for p in paragraphs if len(p) >= MIN_PARAGRAPH_CHARS]


def finding_type(finding):
    for t in FINDING_TYPES:
        if t in finding:
            return t
    return "unknown"


def describe_translation(finding, ftype):
    body = finding.get(ftype, {})
    translation = body.get("translation", {})
    lines = []
    for claim in translation.get("claims", []):
        nl = claim.get("naturalLanguage") or claim.get("logic", "")
        if nl:
            lines.append(f"claim: {nl}")
    for premise in translation.get("premises", []):
        nl = premise.get("naturalLanguage") or premise.get("logic", "")
        if nl:
            lines.append(f"premise: {nl}")
    return lines


def validate_paragraph(runtime, guardrail_id, guardrail_version, paragraph):
    resp = runtime.apply_guardrail(
        guardrailIdentifier=guardrail_id,
        guardrailVersion=guardrail_version,
        source="OUTPUT",
        content=[{"text": {"text": paragraph}}],
    )
    findings = []
    for assessment in resp.get("assessments", []):
        ar = assessment.get("automatedReasoningPolicy", {})
        findings.extend(ar.get("findings", []))
    return findings


def validate_doc(runtime, doc_name, guardrail_id, guardrail_version):
    doc_path = REQUIREMENTS_DIR / doc_name
    paragraphs = extract_paragraphs(doc_path.read_text())

    counts = {t: 0 for t in FINDING_TYPES}
    counts["unknown"] = 0
    violations = []

    for paragraph in paragraphs:
        for finding in validate_paragraph(runtime, guardrail_id, guardrail_version, paragraph):
            ftype = finding_type(finding)
            counts[ftype] = counts.get(ftype, 0) + 1
            if ftype in VIOLATION_TYPES:
                violations.append((ftype, paragraph, describe_translation(finding, ftype)))

    return len(paragraphs), counts, violations


def main():
    state = load_state()
    runtime = boto3.client("bedrock-runtime", region_name=REGION)

    any_violations = False

    for doc_name, key in DOC_TO_GUIDELINE_KEY.items():
        entry = state.get(key)
        print(f"\n=== {doc_name}  (guideline: {key}) ===")
        if not entry or not entry.get("guardrail_id") or not entry.get("guardrail_version"):
            print("  no provisioned guardrail found for this guideline, skipping", file=sys.stderr)
            continue

        num_paragraphs, counts, violations = validate_doc(
            runtime, doc_name, entry["guardrail_id"], entry["guardrail_version"]
        )

        print(f"  paragraphs checked: {num_paragraphs}")
        print(f"  finding counts: {counts}")

        if violations:
            any_violations = True
            print(f"  VIOLATIONS ({len(violations)}):")
            for ftype, paragraph, lines in violations:
                print(f"    [{ftype.upper()}] in paragraph: {paragraph[:80]!r}")
                for line in lines:
                    print(f"      - {line}")
        else:
            print("  no logical violations found")

    if any_violations:
        print("\nResult: violations detected against one or more guidelines.")
        sys.exit(1)
    else:
        print("\nResult: all requirements docs are consistent with the guidelines checked.")
        sys.exit(0)


if __name__ == "__main__":
    main()
