"""Invoke infra-ops-agent via Foundry Responses API (Windows path workaround)."""

from __future__ import annotations

import json
import os
import sys

import httpx
from azure.identity import DefaultAzureCredential


def main() -> int:
    endpoint = os.getenv("AGENT_INFRA_OPS_AGENT_RESPONSES_ENDPOINT") or (
        "https://cog-b6m2di3dwxwpc.services.ai.azure.com/api/projects/"
        "agent-framework-agent-basic-resp/agents/infra-ops-agent/"
        "endpoint/protocols/openai/responses?api-version=v1"
    )
    message = " ".join(sys.argv[1:]).strip()
    if not message:
        print("Usage: python scripts/invoke-responses.py <message>", file=sys.stderr)
        return 1

    token = DefaultAzureCredential().get_token("https://ai.azure.com/.default")
    payload = {"input": message, "stream": False}

    with httpx.Client(timeout=300.0) as client:
        response = client.post(
            endpoint,
            headers={
                "Authorization": f"Bearer {token.token}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        if response.status_code >= 400:
            print(f"HTTP {response.status_code}: {response.text}", file=sys.stderr)
            return 1
        print(json.dumps(response.json(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
