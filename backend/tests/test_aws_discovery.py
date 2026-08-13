"""AWS discovery unit tests — no live AWS calls."""

from __future__ import annotations

import pytest

from app.services.aws_discovery import (
    AWSDiscoveryError,
    _normalize_agentcore_runtime,
    _normalize_bedrock_agent,
)


def test_normalize_bedrock_agent():
    raw = {
        "agentId": "ABCDEF1234",
        "agentName": "Support Agent",
        "agentStatus": "PREPARED",
        "latestAgentVersion": "DRAFT",
        "description": "Handles tier-1 support",
    }
    agent = _normalize_bedrock_agent(
        raw=raw,
        account_id="123456789012",
        region="us-east-1",
    )
    assert agent["id"] == "aws:123456789012:ABCDEF1234"
    assert agent["name"] == "Support Agent"
    assert agent["cloud"] == "aws"
    assert agent["platform"] == "bedrock-agents"
    assert agent["framework"] == "Amazon Bedrock Agents"


def test_normalize_agentcore_runtime():
    raw = {
        "agentRuntimeId": "runtime-abc",
        "agentRuntimeName": "My AgentCore Runtime",
        "agentRuntimeVersion": "1",
        "status": "ACTIVE",
        "agentRuntimeArn": "arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/runtime-abc",
    }
    agent = _normalize_agentcore_runtime(
        raw=raw,
        account_id="123456789012",
        region="us-east-1",
    )
    assert agent["id"] == "aws:123456789012:agentcore:runtime-abc"
    assert agent["name"] == "My AgentCore Runtime"
    assert agent["platform"] == "agentcore"


@pytest.mark.asyncio
async def test_discover_requires_account_id(monkeypatch):
    from app.services.aws_discovery import discover_agents_in_account

    monkeypatch.delenv("AWS_ACCOUNT_ID", raising=False)
    with pytest.raises(AWSDiscoveryError) as exc:
        await discover_agents_in_account({"region": "us-east-1", "account_id": None})
    assert exc.value.stage == "configuration"


@pytest.mark.asyncio
async def test_discover_endpoint_requires_enabled():
    from httpx import ASGITransport, AsyncClient
    from app.main import create_app
    from app.storage.store import ObservabilityStore, store

    fresh = ObservabilityStore()
    store.integrations = fresh.integrations
    store.agents = {}

    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post("/api/v1/integrations/aws/discover")
        data = res.json()
        assert data["ok"] is False
        assert "Configure" in data["message"] or "Enable" in data["message"]


@pytest.mark.asyncio
async def test_discover_lists_bedrock_agents(monkeypatch):
    from app.services import aws_discovery

    class FakePaginator:
        def paginate(self, **_kwargs):
            return [
                {
                    "agentSummaries": [
                        {
                            "agentId": "AGENT1",
                            "agentName": "Demo Agent",
                            "agentStatus": "PREPARED",
                        }
                    ]
                }
            ]

    class FakeBedrockClient:
        def get_paginator(self, name):
            assert name == "list_agents"
            return FakePaginator()

    class FakeSession:
        def client(self, service, region_name=None):
            if service == "sts":
                return FakeSTS()
            if service == "bedrock-agent":
                return FakeBedrockClient()
            if service == "bedrock-agentcore-control":
                return FakeAgentCoreClient()
            raise AssertionError(f"unexpected service {service}")

    class FakeSTS:
        def get_caller_identity(self):
            return {"Account": "123456789012", "Arn": "arn:aws:iam::123456789012:role/test"}

    class FakeAgentCoreClient:
        def get_paginator(self, name):
            return FakeEmptyPaginator()

    class FakeEmptyPaginator:
        def paginate(self, **_kwargs):
            return [{"agentRuntimes": []}]

    monkeypatch.setattr(aws_discovery, "_session", lambda _cfg: FakeSession())

    result = await aws_discovery.discover_agents_in_account(
        {"account_id": "123456789012", "region": "us-east-1"}
    )
    assert len(result["agents"]) == 1
    assert result["agents"][0]["name"] == "Demo Agent"
    assert result["account_id"] == "123456789012"
