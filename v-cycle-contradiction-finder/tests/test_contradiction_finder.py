from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from contradiction_finder import (  # noqa: E402
    ConfigurationError,
    ContradictionFinding,
    ContradictionReport,
    DocumentInputError,
    Evidence,
    ResolutionAlternative,
    ReviewAssessment,
    load_documents,
    load_model_settings,
    render_markdown,
    write_json_report,
)
from pydantic import ValidationError  # noqa: E402


def make_finding() -> ContradictionFinding:
    return ContradictionFinding(
        identifier="C1",
        title="Conflicting route",
        classification="direct",
        explanation="The same route is required and forbidden.",
        evidence=[
            Evidence(
                document="architecture.md",
                line_start=10,
                line_end=10,
                quote="The adapter must not call the service.",
            ),
            Evidence(
                document="requirements.md",
                line_start=20,
                line_end=20,
                quote="The adapter shall call the service.",
            ),
        ],
        reasoning_steps=["Both statements govern the same command."],
        review=ReviewAssessment(
            candidate_id="C1",
            verdict="confirmed",
            confidence="high",
            rationale="Both obligations cannot be satisfied.",
        ),
        resolutions=[
            ResolutionAlternative(
                title="Change the requirement",
                change_target="requirements.md",
                proposed_change="Route through the controller.",
                tradeoffs="Removes direct control.",
            )
        ],
    )


class DocumentLoadingTests(unittest.TestCase):
    def test_loads_exactly_two_files_with_line_coordinates(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            architecture = root / "architecture.md"
            requirements = root / "requirements.md"
            architecture.write_text("Architecture\nRule\n", encoding="utf-8")
            requirements.write_text("Requirements\nConflict\n", encoding="utf-8")

            corpus = load_documents(architecture, requirements)

            self.assertEqual(
                corpus.documents,
                ("architecture.md", "requirements.md"),
            )
            self.assertIn("[architecture.md:2] Rule", corpus.annotated_text)
            self.assertIn("[requirements.md:2] Conflict", corpus.annotated_text)

    def test_rejects_missing_file(self) -> None:
        with self.assertRaisesRegex(DocumentInputError, "does not exist"):
            load_documents("/missing/architecture.md", "/missing/requirements.md")


class SchemaAndRenderingTests(unittest.TestCase):
    def test_final_finding_requires_confirmed_review(self) -> None:
        data = make_finding().model_dump()
        data["review"]["verdict"] = "rejected"
        with self.assertRaisesRegex(ValidationError, "must be confirmed"):
            ContradictionFinding.model_validate(data)

    def test_renders_markdown_and_json(self) -> None:
        report = ContradictionReport(
            documents_scanned=["architecture.md", "requirements.md"],
            summary="One contradiction confirmed.",
            findings=[make_finding()],
        )
        self.assertIn("C1: Conflicting route", render_markdown(report))

        with tempfile.TemporaryDirectory() as temporary_directory:
            path = write_json_report(
                report,
                Path(temporary_directory) / "report.json",
            )
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(data["findings"][0]["identifier"], "C1")


class ConfigurationTests(unittest.TestCase):
    def test_reports_missing_environment_variables(self) -> None:
        with (
            patch.dict(os.environ, {}, clear=True),
            patch("contradiction_finder.load_dotenv"),
        ):
            with self.assertRaisesRegex(ConfigurationError, "AWS_REGION"):
                load_model_settings()


if __name__ == "__main__":
    unittest.main()
