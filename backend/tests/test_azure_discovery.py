"""Azure discovery unit tests — no live Azure calls."""

from __future__ import annotations

import pytest

from app.services.azure_discovery import (
    AzureDiscoveryError,
    _discovery_scope_rg,
    _normalize_discovered,
)


def test_discovery_scope_rg(monkeypatch):
    monkeypatch.delenv("AZURE_RESOURCE_GROUP", raising=False)
    assert _discovery_scope_rg({}) is None
    assert _discovery_scope_rg({"resource_group": ""}) is None
    assert _discovery_scope_rg({"resource_group": "__all__"}) is None
    assert _discovery_scope_rg({"resource_group": "rg-demo"}) == "rg-demo"


def test_normalize_foundry_agent():
    raw = {
        "id": "asst_123",
        "name": "Device Health Agent",
        "versions": {"latest": {"version": "1", "model": "gpt-4o"}},
    }
    agent = _normalize_discovered(
        raw=raw,
        source="azure-foundry",
        cloud_account="my-ai",
        project="agent-metering-project",
        region="eastus",
        subscription_id="7a735755-6139-4d2c-8ba4-5fccaaae24a0",
        tenant_id="c50e9e25-55e4-4e18-8ed5-4acacc035533",
        resource_group="rg-agent-metering-dev",
    )
    assert agent["id"].startswith("azure:7a735755")
    assert agent["name"] == "Device Health Agent"
    assert agent["primary_model"] == "gpt-4o"
    assert agent["cloud"] == "azure"


@pytest.mark.asyncio
async def test_discover_requires_subscription(monkeypatch):
    from app.services.azure_discovery import discover_agents_in_subscription

    monkeypatch.delenv("AZURE_SUBSCRIPTION_ID", raising=False)
    with pytest.raises(AzureDiscoveryError) as exc:
        await discover_agents_in_subscription({"tenant_id": "x", "subscription_id": None})
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
async def test_list_resource_groups_endpoint(monkeypatch):
    from httpx import ASGITransport, AsyncClient
    from app.main import create_app
    from app.services import integrations as integrations_module
    from app.storage.store import ObservabilityStore, store

    async def fake_list(_integration_id, fields_override=None):
        return {
            "ok": True,
            "subscription_id": "sub-1",
            "count": 2,
            "resource_groups": [
                {"name": "rg-a", "location": "eastus"},
                {"name": "rg-b", "location": "westus"},
            ],
            "message": "Found 2 resource group(s) in subscription sub-1.",
        }

    monkeypatch.setattr(
        integrations_module.integration_service,
        "list_resource_groups",
        fake_list,
    )

    fresh = ObservabilityStore()
    store.integrations = fresh.integrations
    azure = store.integrations["azure"]
    azure.configured = True
    azure.config.fields = {"subscription_id": "sub-1", "tenant_id": "tenant-1"}

    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post("/api/v1/integrations/azure/resource-groups")
        data = res.json()
        assert data["ok"] is True
        assert data["count"] == 2
        assert data["resource_groups"][0]["name"] == "rg-a"
