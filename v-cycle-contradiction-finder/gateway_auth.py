"""Cognito client-credentials authentication for AgentCore Gateway."""

from __future__ import annotations

import base64
import json
import os
import urllib.parse
import urllib.request


def get_gateway_token() -> str:
    endpoint = os.environ["AGENTCORE_GATEWAY_TOKEN_URL"]
    if not endpoint.startswith("https://"):
        raise ValueError("Gateway token endpoint must use HTTPS")

    client_id = os.environ["AGENTCORE_GATEWAY_CLIENT_ID"]
    client_secret = os.environ["AGENTCORE_GATEWAY_CLIENT_SECRET"]
    scope = os.environ["AGENTCORE_GATEWAY_SCOPE"]
    basic = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    request = urllib.request.Request(
        endpoint,
        data=urllib.parse.urlencode(
            {"grant_type": "client_credentials", "scope": scope}
        ).encode(),
        headers={
            "Authorization": f"Basic {basic}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:  # nosec B310
        return json.loads(response.read())["access_token"]
