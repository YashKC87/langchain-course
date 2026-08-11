"""Tests: no fake telemetry, normalization, integrations, workflow, runaway."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app
from app.services.normalization import normalize_span, normalize_tokens, aggregate_execution
from app.services.workflow import build_workflow
from app.storage.store import ObservabilityStore, store


@pytest.fixture(autouse=True)
def reset_store():
    """Reset global store between tests — never leave synthetic data."""
    fresh = ObservabilityStore()
    store.integrations = fresh.integrations
    store.agents = {}
    store.executions = {}
    store.spans = {}
    store.spans_by_trace = {}
    store.spans_by_execution = {}
    store.activity = []
    store.attention = []
    store.optimizations = []
    store.tools = []
    store.mcp = []
    store.rag = []
    store.a2a = []
    store.models = []
    store.last_telemetry_at = None
    store.settings = fresh.settings
    yield


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ── Critical: no fake data ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_overview_empty_without_integrations(client):
    res = await client.get("/api/v1/overview")
    assert res.status_code == 200
    data = res.json()
    assert data["empty"] is True
    assert "Connect Your First Platform" in data["title"]
    assert "kpis" not in data or data.get("kpis") is None


@pytest.mark.asyncio
async def test_agents_empty_no_fake_agents(client):
    res = await client.get("/api/v1/agents")
    data = res.json()
    assert data["empty"] is True
    assert data["items"] == []


@pytest.mark.asyncio
async def test_executions_empty_no_fake_runs(client):
    res = await client.get("/api/v1/executions")
    data = res.json()
    assert data["empty"] is True
    assert data["items"] == []


@pytest.mark.asyncio
async def test_needs_attention_empty_without_telemetry(client):
    res = await client.get("/api/v1/overview/needs-attention")
    data = res.json()
    assert data["empty"] is True
    assert data["items"] == []


@pytest.mark.asyncio
async def test_optimization_empty_without_evidence(client):
    res = await client.get("/api/v1/optimization")
    data = res.json()
    assert data["empty"] is True
    assert data["items"] == []


@pytest.mark.asyncio
async def test_models_empty_no_prepopulated(client):
    res = await client.get("/api/v1/models")
    data = res.json()
    assert data["empty"] is True


@pytest.mark.asyncio
async def test_mcp_rag_a2a_empty(client):
    for path in ("/api/v1/mcp", "/api/v1/rag", "/api/v1/a2a", "/api/v1/tools"):
        data = (await client.get(path)).json()
        assert data["empty"] is True


@pytest.mark.asyncio
async def test_empty_ingest_does_not_create_agents(client):
    res = await client.post("/api/v1/telemetry/spans", json={"spans": []})
    data = res.json()
    assert data["spans_ingested"] == 0
    assert data["agents_registered"] == 0
    agents = (await client.get("/api/v1/agents")).json()
    assert agents["items"] == []


# ── Token normalization ─────────────────────────────────────────────────


def test_normalize_azure_tokens():
    result = normalize_tokens({"prompt_tokens": 10, "completion_tokens": 5})
    assert result["input_tokens"] == 10
    assert result["output_tokens"] == 5
    assert result["total_tokens"] == 15


def test_normalize_aws_tokens():
    result = normalize_tokens({"inputTokens": 20, "outputTokens": 8})
    assert result["input_tokens"] == 20
    assert result["output_tokens"] == 8


def test_normalize_google_tokens():
    result = normalize_tokens({"promptTokenCount": 7, "candidatesTokenCount": 3})
    assert result["input_tokens"] == 7
    assert result["output_tokens"] == 3


def test_missing_tokens_remain_none():
    result = normalize_tokens({})
    assert result["input_tokens"] is None
    assert result["output_tokens"] is None
    assert result["total_tokens"] is None
    assert result["reasoning_tokens"] is None


# ── Integration toggle ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_enable_unconfigured_fails_clearly(client):
    res = await client.post("/api/v1/integrations/otel/toggle", json={"enabled": True})
    data = res.json()
    assert data["enabled"] is False
    assert data["status"] in ("not_configured", "connection_failed")
    progress = data["enable_progress"]
    assert progress[0]["status"] == "failed"


@pytest.mark.asyncio
async def test_configure_and_enable_otel(client):
    await client.put(
        "/api/v1/integrations/otel/config",
        json={
            "fields": {"collector_endpoint": "http://localhost:4318", "protocol": "http/protobuf"},
            "auth_method": "none",
        },
    )
    res = await client.post("/api/v1/integrations/otel/toggle", json={"enabled": True})
    data = res.json()
    assert data["enabled"] is True
    assert data["status"] == "connected"
    # Still no fake agents
    agents = (await client.get("/api/v1/agents")).json()
    assert agents["empty"] is True


@pytest.mark.asyncio
async def test_disable_retains_message(client):
    await client.put(
        "/api/v1/integrations/otel/config",
        json={"fields": {"collector_endpoint": "http://localhost:4318", "protocol": "http/protobuf"}},
    )
    await client.post("/api/v1/integrations/otel/toggle", json={"enabled": True})
    res = await client.post("/api/v1/integrations/otel/toggle", json={"enabled": False})
    data = res.json()
    assert data["enabled"] is False
    assert data["status"] == "disabled"
    assert any("Historical telemetry retained" in str(s) for s in data["enable_progress"])


@pytest.mark.asyncio
async def test_secrets_not_returned_plaintext(client):
    await client.put(
        "/api/v1/integrations/langsmith/config",
        json={
            "fields": {"api_endpoint": "https://api.smith.langchain.com", "api_key": "super-secret-key"},
            "auth_method": "api_key",
        },
    )
    res = await client.get("/api/v1/integrations/langsmith")
    data = res.json()
    assert "super-secret-key" not in str(data)
    assert data["config"]["secret_refs"].get("api_key") == "••••••••"


# ── Telemetry → registry → workflow ─────────────────────────────────────


@pytest.mark.asyncio
async def test_ingest_creates_agent_and_workflow(client):
    await client.put(
        "/api/v1/integrations/otel/config",
        json={"fields": {"collector_endpoint": "http://localhost:4318", "protocol": "http/protobuf"}},
    )
    await client.post("/api/v1/integrations/otel/toggle", json={"enabled": True})

    payload = {
        "spans": [
            {
                "name": "agent.run",
                "span_id": "s1",
                "trace_id": "t1",
                "parent_span_id": None,
                "start_time": "2026-04-11T12:00:00+00:00",
                "end_time": "2026-04-11T12:00:02+00:00",
                "status": "ok",
                "attributes": {
                    "agent.id": "agent-device-1",
                    "agent.name": "Device Health Agent",
                    "cloud.provider": "azure",
                    "framework.name": "langgraph",
                    "gen_ai.request.model": "gpt-4o",
                    "prompt_tokens": 100,
                    "completion_tokens": 50,
                },
            },
            {
                "name": "chat gpt-4o",
                "span_id": "s2",
                "trace_id": "t1",
                "parent_span_id": "s1",
                "start_time": "2026-04-11T12:00:00.100000+00:00",
                "end_time": "2026-04-11T12:00:01+00:00",
                "status": "ok",
                "attributes": {
                    "agent.id": "agent-device-1",
                    "agent.name": "Device Health Agent",
                    "gen_ai.operation.name": "chat",
                    "gen_ai.request.model": "gpt-4o",
                    "prompt_tokens": 100,
                    "completion_tokens": 50,
                },
            },
            {
                "name": "mcp ServiceNow",
                "span_id": "s3",
                "trace_id": "t1",
                "parent_span_id": "s1",
                "start_time": "2026-04-11T12:00:01+00:00",
                "end_time": "2026-04-11T12:00:01.500000+00:00",
                "status": "ok",
                "attributes": {
                    "agent.id": "agent-device-1",
                    "mcp.server": "ServiceNow",
                    "mcp.tool": "create_incident",
                },
            },
        ]
    }
    res = await client.post("/api/v1/telemetry/spans?integration_id=otel", json=payload)
    assert res.json()["spans_ingested"] == 3
    assert res.json()["agents_registered"] == 1

    agents = (await client.get("/api/v1/agents")).json()
    assert agents["empty"] is False
    assert agents["items"][0]["name"] == "Device Health Agent"

    overview = (await client.get("/api/v1/overview")).json()
    assert overview["empty"] is False
    assert overview["kpis"]["telemetry_live"] is True
    assert overview["kpis"]["active_agents"]["available"] is True

    execs = (await client.get("/api/v1/executions")).json()
    assert execs["empty"] is False
    exec_id = execs["items"][0]["execution_id"]

    wf = (await client.get(f"/api/v1/executions/{exec_id}/workflow")).json()
    assert len(wf["nodes"]) == 3
    assert len(wf["edges"]) >= 2
    assert any(n["node_type"] == "model" for n in wf["nodes"])
    assert any(n["node_type"] == "mcp" for n in wf["nodes"])

    mcp = (await client.get("/api/v1/mcp")).json()
    assert mcp["empty"] is False


@pytest.mark.asyncio
async def test_disabled_integration_rejects_ingest(client):
    await client.put(
        "/api/v1/integrations/otel/config",
        json={"fields": {"collector_endpoint": "http://localhost:4318", "protocol": "http/protobuf"}},
    )
    # leave disabled
    res = await client.post(
        "/api/v1/telemetry/spans?integration_id=otel",
        json={"spans": [{"name": "x", "span_id": "1", "trace_id": "t", "attributes": {"agent.id": "a"}}]},
    )
    assert res.json()["accepted"] is False
    assert res.json()["spans_ingested"] == 0


def test_workflow_does_not_fabricate_nodes():
    spans = [
        normalize_span(
            {
                "name": "only-span",
                "span_id": "a",
                "trace_id": "t",
                "status": "ok",
                "attributes": {},
            }
        )
    ]
    graph = build_workflow("e1", spans)
    assert len(graph.nodes) == 1
    assert graph.edges == []


def test_aggregate_missing_fields_stay_none():
    spans = [
        normalize_span(
            {
                "name": "agent",
                "span_id": "a",
                "trace_id": "t",
                "attributes": {"agent.id": "x", "agent.name": "X"},
            }
        )
    ]
    exe = aggregate_execution(spans)
    assert exe.reasoning_tokens is None
    assert exe.cached_tokens is None
    assert exe.input_tokens is None


@pytest.mark.asyncio
async def test_runaway_detection_creates_attention(client):
    await client.put(
        "/api/v1/integrations/otel/config",
        json={"fields": {"collector_endpoint": "http://localhost:4318", "protocol": "http/protobuf"}},
    )
    await client.post("/api/v1/integrations/otel/toggle", json={"enabled": True})

    # Create many step spans to exceed critical threshold (>20)
    spans = []
    for i in range(22):
        spans.append(
            {
                "name": f"step-{i}",
                "span_id": f"s{i}",
                "trace_id": "runaway-t",
                "parent_span_id": "s0" if i else None,
                "start_time": f"2026-04-11T12:00:{i:02d}+00:00",
                "end_time": f"2026-04-11T12:00:{i:02d}.500000+00:00",
                "status": "ok",
                "attributes": {
                    "agent.id": "loop-agent",
                    "agent.name": "Loop Agent",
                    "cloud.provider": "aws",
                },
            }
        )
    await client.post("/api/v1/telemetry/spans?integration_id=otel", json={"spans": spans})
    attention = (await client.get("/api/v1/overview/needs-attention")).json()
    assert attention["empty"] is False
    conditions = [i["condition"] for i in attention["items"]]
    assert "Runaway Loop" in conditions


@pytest.mark.asyncio
async def test_waiting_for_telemetry_state(client):
    await client.put(
        "/api/v1/integrations/otel/config",
        json={"fields": {"collector_endpoint": "http://localhost:4318", "protocol": "http/protobuf"}},
    )
    await client.post("/api/v1/integrations/otel/toggle", json={"enabled": True})
    overview = (await client.get("/api/v1/overview")).json()
    assert overview["empty"] is True
    assert "Waiting for live telemetry" in overview["message"] or "No Live Telemetry" in overview["title"]
