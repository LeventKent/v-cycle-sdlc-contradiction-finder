from __future__ import annotations

import importlib.util
import sys
import unittest
import zipfile
from io import BytesIO
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from agentcore_runtime import validate_document_names  # noqa: E402
from deploy_agentcore import build_lambda_zip  # noqa: E402
from destroy_agentcore import destruction_plan  # noqa: E402
from invoke_agentcore import unwrap_response  # noqa: E402


def load_lambda_module():
    path = PROJECT_DIR / "gateway" / "lambda_function.py"
    spec = importlib.util.spec_from_file_location("content_lambda", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class RuntimeInputTests(unittest.TestCase):
    def test_accepts_plain_unique_markdown_names(self) -> None:
        names = ["01-System-Architecture.md", "02-System-Requirements.md"]
        self.assertEqual(validate_document_names({"document_names": names}), names)

    def test_rejects_path_traversal_and_duplicates(self) -> None:
        with self.assertRaisesRegex(ValueError, "plain Markdown"):
            validate_document_names(
                {"document_names": ["../secret.md", "02-System-Requirements.md"]}
            )
        with self.assertRaisesRegex(ValueError, "unique"):
            validate_document_names(
                {"document_names": ["same.md", "same.md"]}
            )

    def test_unwraps_chunked_agentcore_response(self) -> None:
        response = {"response": ['{"findings":', " []}"]}
        self.assertEqual(unwrap_response(response), {"findings": []})


class GatewayContentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.content = load_lambda_module()
        cls.content.DOCUMENTS = PROJECT_DIR.parent / "workshop-current-state-documentation"
        cls.content.GUIDELINES = cls.content.DOCUMENTS / "guidelines"

    def test_reads_document_with_stable_coordinates(self) -> None:
        result = self.content.get_document("01-System-Architecture.md")
        self.assertEqual(result["document_name"], "01-System-Architecture.md")
        self.assertIn("[01-System-Architecture.md:1]", result["content"])

    def test_maps_document_to_corresponding_guideline(self) -> None:
        result = self.content.get_guideline("02-System-Requirements.md")
        self.assertEqual(
            result["document_name"],
            "02-System-Requirements-Guideline.md",
        )

    def test_rejects_path_traversal(self) -> None:
        with self.assertRaisesRegex(ValueError, "plain filename"):
            self.content.get_document("../01-System-Architecture.md")


class LambdaBundleTests(unittest.TestCase):
    def test_bundle_contains_handler_and_all_content(self) -> None:
        with zipfile.ZipFile(BytesIO(build_lambda_zip())) as bundle:
            names = bundle.namelist()
        self.assertIn("lambda_function.py", names)
        self.assertEqual(
            len([name for name in names if name.startswith("documents/")]),
            9,
        )
        self.assertEqual(
            len([name for name in names if name.startswith("guidelines/")]),
            9,
        )


class DestroyPlanTests(unittest.TestCase):
    def test_plan_includes_cognito_and_shared_bucket_preservation(self) -> None:
        plan = destruction_plan(
            {
                "runtime_id": "runtime-id",
                "gateway_id": "gateway-id",
                "target_id": "target-id",
                "cognito": {
                    "domain_prefix": "domain-prefix",
                    "user_pool_id": "pool-id",
                },
            }
        )
        rendered = "\n".join(plan)
        self.assertIn("Cognito domain: domain-prefix", rendered)
        self.assertIn("Cognito user pool: pool-id", rendered)
        self.assertIn("bucket is preserved", rendered)


if __name__ == "__main__":
    unittest.main()
