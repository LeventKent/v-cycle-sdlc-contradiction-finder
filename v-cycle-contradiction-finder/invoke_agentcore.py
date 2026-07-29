#!/usr/bin/env python3
"""Invoke the deployed AgentCore contradiction finder."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from bedrock_agentcore_starter_toolkit.operations.runtime.invoke import (
    invoke_bedrock_agentcore,
)
from contradiction_finder import (
    ContradictionReport,
    write_json_report,
    write_markdown_report,
)

HERE = Path(__file__).resolve().parent
CONFIG_PATH = HERE.parent / ".bedrock_agentcore.yaml"
REPORT_PATH = HERE / "agent-outputs" / "contradiction-report.md"
JSON_REPORT_PATH = HERE / "agent-outputs" / "contradiction-report.json"
RUNTIME_NAME = "vcycle_contradiction_finder"


def unwrap_response(response):
    """Extract the JSON report from the toolkit's AgentCore response envelope."""
    if hasattr(response, "read"):
        response = response.read()
    if isinstance(response, bytes):
        response = response.decode("utf-8")
    if isinstance(response, str):
        return json.loads(response)
    if isinstance(response, dict) and isinstance(response.get("response"), list):
        return json.loads("".join(response["response"]))
    return response


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "document_names",
        nargs="+",
        help="One to nine exact Markdown filenames",
    )
    args = parser.parse_args()
    result = invoke_bedrock_agentcore(
        config_path=CONFIG_PATH,
        agent_name=RUNTIME_NAME,
        payload={"document_names": args.document_names},
    )
    response = unwrap_response(result.response)
    report = ContradictionReport.model_validate(response)
    markdown_path = write_markdown_report(report, REPORT_PATH)
    json_path = write_json_report(report, JSON_REPORT_PATH)
    print(json.dumps(response, indent=2))
    print(f"Markdown report written to {markdown_path}", file=sys.stderr)
    print(f"JSON report written to {json_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
