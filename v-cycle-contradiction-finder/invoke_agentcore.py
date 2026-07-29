#!/usr/bin/env python3
"""Invoke the deployed AgentCore contradiction finder."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from bedrock_agentcore_starter_toolkit.operations.runtime.invoke import (
    invoke_bedrock_agentcore,
)

HERE = Path(__file__).resolve().parent
CONFIG_PATH = HERE.parent / ".bedrock_agentcore.yaml"
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
        help="Two or more exact Markdown filenames",
    )
    args = parser.parse_args()
    result = invoke_bedrock_agentcore(
        config_path=CONFIG_PATH,
        agent_name=RUNTIME_NAME,
        payload={"document_names": args.document_names},
    )
    response = unwrap_response(result.response)
    print(json.dumps(response, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
