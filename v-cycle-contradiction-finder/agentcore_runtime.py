"""AgentCore Runtime entrypoint for name-based contradiction analysis."""

from __future__ import annotations

import os
from pathlib import PurePath

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from mcp.client.streamable_http import streamablehttp_client
from strands.tools.mcp.mcp_client import MCPClient

from contradiction_finder import ContradictionHandlerAgent
from gateway_auth import get_gateway_token

app = BedrockAgentCoreApp()


def validate_document_names(payload: dict) -> list[str]:
    names = payload.get("document_names")
    if not isinstance(names, list) or not 2 <= len(names) <= 9:
        raise ValueError("document_names must contain between 2 and 9 filenames")
    if any(
        not isinstance(name, str)
        or PurePath(name).name != name
        or not name.endswith(".md")
        for name in names
    ):
        raise ValueError("document_names must contain plain Markdown filenames")
    if len(set(names)) != len(names):
        raise ValueError("document_names must be unique")
    return names


@app.entrypoint
def invoke(payload: dict) -> dict:
    document_names = validate_document_names(payload)
    token = get_gateway_token()
    gateway_url = os.environ["AGENTCORE_GATEWAY_URL"]
    mcp_client = MCPClient(
        lambda: streamablehttp_client(
            gateway_url,
            headers={"Authorization": f"Bearer {token}"},
        )
    )

    with mcp_client:
        tools = mcp_client.list_tools_sync()
        content_tools = [
            tool
            for tool in tools
            if tool.tool_name.endswith("___get_document")
            or tool.tool_name.endswith("___get_guideline")
        ]
        if len(content_tools) != 2:
            raise RuntimeError(
                f"Expected two Gateway content tools, found {len(content_tools)}"
            )
        report = ContradictionHandlerAgent(
            content_tools=content_tools
        ).analyze_document_names(document_names)
        return report.model_dump(mode="json")


if __name__ == "__main__":
    app.run()
