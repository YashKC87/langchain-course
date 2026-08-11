"""API routers."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.rbac import require_permission
from app.models.domain import AppSettings, EmptyStateResponse
from app.services.integrations import integration_service
from app.services.metrics import metrics_service
from app.services.optimization import optimization_service
from app.services.telemetry import telemetry_service
from app.services.workflow import build_waterfall, build_workflow
from app.storage.store import store

router = APIRouter()


# ── Status / Live ───────────────────────────────────────────────────────


@router.get("/status")
async def status():
    return {
        "app": "Agent Metering & Observability Control Center",
        "telemetry_live": store.has_live_telemetry(),
        "last_updated": store.last_telemetry_at.isoformat() if store.last_telemetry_at else None,
        "enabled_integrations": sum(1 for i in store.integrations.values() if i.enabled),
        "agents": len(store.agents),
        "executions": len(store.executions),
    }


# ── Overview ────────────────────────────────────────────────────────────


@router.get("/overview")
async def overview(_: dict = Depends(require_permission("agents:read"))):
    result = metrics_service.overview()
    if isinstance(result, EmptyStateResponse):
        return {"empty": True, **result.model_dump()}
    return {"empty": False, "kpis": result.model_dump()}


@router.get("/overview/integration-health")
async def integration_health(_: dict = Depends(require_permission("integrations:read"))):
    return {"items": integration_service.health_panel()}


@router.get("/overview/needs-attention")
async def needs_attention(_: dict = Depends(require_permission("agents:read"))):
    if not store.attention:
        return {
            "empty": True,
            "title": "No active warnings",
            "message": "No telemetry-backed problems detected.",
            "items": [],
        }
    return {"empty": False, "items": [a.model_dump() for a in store.attention]}


@router.get("/overview/activity")
async def activity(agent: str | None = None, _: dict = Depends(require_permission("agents:read"))):
    events = store.activity
    if agent:
        events = [e for e in events if e.agent_id == agent or e.agent_name == agent]
    if not events:
        return {
            "empty": True,
            "title": "No live activity",
            "message": "Activity events appear when telemetry is ingested.",
            "items": [],
        }
    return {"empty": False, "items": [e.model_dump() for e in events[:100]]}


# ── Integrations ────────────────────────────────────────────────────────


class ConfigBody(BaseModel):
    fields: dict[str, Any] = Field(default_factory=dict)
    auth_method: str | None = None
    secret_refs: dict[str, str] | None = None


class ToggleBody(BaseModel):
    enabled: bool


@router.get("/integrations")
async def list_integrations(_: dict = Depends(require_permission("integrations:read"))):
    return {"groups": {k: [i.model_dump() for i in v] for k, v in integration_service.list_by_category().items()}}


@router.get("/integrations/{integration_id}")
async def get_integration(integration_id: str, _: dict = Depends(require_permission("integrations:read"))):
    integ = integration_service.get(integration_id)
    if not integ:
        raise HTTPException(404, f"Integration '{integration_id}' not found")
    data = integ.model_dump()
    # Never expose secret values — only refs
    data["config"]["secret_refs"] = {k: "••••••••" for k in integ.config.secret_refs}
    return data


@router.put("/integrations/{integration_id}/config")
async def save_integration_config(
    integration_id: str,
    body: ConfigBody,
    _: dict = Depends(require_permission("integrations:write")),
):
    try:
        integ = await integration_service.save_config(
            integration_id, body.fields, body.auth_method, body.secret_refs
        )
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    return integ.model_dump()


@router.post("/integrations/{integration_id}/test")
async def test_integration(integration_id: str, _: dict = Depends(require_permission("integrations:write"))):
    try:
        return await integration_service.test_connection(integration_id)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post("/integrations/{integration_id}/toggle")
async def toggle_integration(
    integration_id: str,
    body: ToggleBody,
    _: dict = Depends(require_permission("integrations:toggle")),
):
    try:
        integ = await integration_service.toggle(integration_id, body.enabled)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    return integ.model_dump()


# ── Agents ──────────────────────────────────────────────────────────────


@router.get("/agents")
async def list_agents(_: dict = Depends(require_permission("agents:read"))):
    if not store.agents:
        return {
            "empty": True,
            "title": "No agents discovered",
            "message": "Connection successful scenarios still show no agents until discovery or telemetry arrives.",
            "items": [],
        }
    return {"empty": False, "items": [a.model_dump() for a in store.agents.values()]}


@router.get("/agents/metering")
async def agent_metering(_: dict = Depends(require_permission("agents:read"))):
    result = metrics_service.agent_metering()
    if isinstance(result, EmptyStateResponse):
        return {"empty": True, **result.model_dump()}
    return {"empty": False, "items": [r.model_dump() for r in result]}


@router.get("/agents/{agent_id}")
async def get_agent(agent_id: str, _: dict = Depends(require_permission("agents:read"))):
    agent = store.agents.get(agent_id)
    if not agent:
        raise HTTPException(404, "Agent not found")
    execs = [e for e in store.executions.values() if e.agent_id == agent_id]
    score = optimization_service.efficiency_score(agent_id)
    return {
        "agent": agent.model_dump(),
        "execution_count": len(execs) if execs else None,
        "efficiency": score,
    }


@router.get("/agents/{agent_id}/telemetry-quality")
async def agent_telemetry_quality(agent_id: str, _: dict = Depends(require_permission("agents:read"))):
    agent = store.agents.get(agent_id)
    if not agent:
        raise HTTPException(404, "Agent not found")
    execs = [e for e in store.executions.values() if e.agent_id == agent_id]
    if not execs:
        return {
            "agent": agent.name,
            "dimensions": {
                "token_telemetry": "missing",
                "model_calls": "missing",
                "tool_calls": "missing",
                "mcp": "missing",
                "rag": "missing",
                "reasoning_tokens": "missing",
            },
        }

    def dim(has_any: bool, used: bool = True) -> str:
        if not used:
            return "not_used"
        return "complete" if has_any else "not_provided"

    has_tokens = any(e.total_tokens is not None for e in execs)
    has_model = any(e.model_calls is not None for e in execs)
    has_tool = any(e.tool_calls is not None for e in execs)
    has_mcp = any(e.mcp_calls is not None for e in execs)
    has_rag = any(e.rag_queries is not None for e in execs)
    has_reasoning = any(e.reasoning_tokens is not None for e in execs)
    mcp_used = has_mcp or any(
        store.spans[sid].node_type.value == "mcp"
        for e in execs
        for sid in store.spans_by_execution.get(e.execution_id, [])
        if sid in store.spans
    )

    return {
        "agent": agent.name,
        "dimensions": {
            "token_telemetry": dim(has_tokens),
            "model_calls": dim(has_model),
            "tool_calls": dim(has_tool),
            "mcp": "not_used" if not mcp_used and not has_mcp else dim(has_mcp),
            "rag": dim(has_rag),
            "reasoning_tokens": "provider_unsupported" if not has_reasoning else "complete",
        },
    }


# ── Executions ──────────────────────────────────────────────────────────


@router.get("/executions")
async def list_executions(
    status: str | None = None,
    agent: str | None = None,
    live_only: bool = False,
    _: dict = Depends(require_permission("executions:read")),
):
    items = list(store.executions.values())
    if status:
        items = [e for e in items if e.status.value == status]
    if agent:
        items = [e for e in items if e.agent_id == agent or e.agent_name == agent]
    if live_only:
        items = [e for e in items if e.status.value == "running"]
    items.sort(key=lambda e: e.start_time or e.timestamp or datetime_min(), reverse=True)
    if not items:
        return {
            "empty": True,
            "title": "No executions received",
            "message": "Executions appear when live telemetry spans are ingested.",
            "items": [],
        }
    return {"empty": False, "items": [e.model_dump() for e in items]}


def datetime_min():
    from datetime import datetime, timezone

    return datetime.min.replace(tzinfo=timezone.utc)


@router.get("/executions/{execution_id}")
async def get_execution(execution_id: str, _: dict = Depends(require_permission("executions:read"))):
    e = store.executions.get(execution_id)
    if not e:
        raise HTTPException(404, "Execution not found")
    return e.model_dump()


@router.get("/executions/{execution_id}/workflow")
async def execution_workflow(execution_id: str, _: dict = Depends(require_permission("traces:read"))):
    e = store.executions.get(execution_id)
    if not e:
        raise HTTPException(404, "Execution not found")
    span_ids = store.spans_by_execution.get(execution_id, [])
    spans = [store.spans[sid] for sid in span_ids if sid in store.spans]
    graph = build_workflow(execution_id, spans, e.status)
    return graph.model_dump()


@router.get("/executions/{execution_id}/waterfall")
async def execution_waterfall(execution_id: str, _: dict = Depends(require_permission("traces:read"))):
    if execution_id not in store.executions:
        raise HTTPException(404, "Execution not found")
    span_ids = store.spans_by_execution.get(execution_id, [])
    spans = [store.spans[sid] for sid in span_ids if sid in store.spans]
    if not spans:
        return {
            "empty": True,
            "title": "No matching traces",
            "message": "No spans available for this execution.",
            "items": [],
        }
    return {"empty": False, "items": build_waterfall(spans)}


# ── Traces ──────────────────────────────────────────────────────────────


@router.get("/traces")
async def list_traces(
    agent: str | None = None,
    trace_id: str | None = None,
    execution_id: str | None = None,
    _: dict = Depends(require_permission("traces:read")),
):
    traces = set(store.spans_by_trace.keys())
    if trace_id:
        traces = {t for t in traces if t == trace_id}
    if execution_id:
        e = store.executions.get(execution_id)
        if e and e.trace_id:
            traces = {e.trace_id}
        else:
            traces = set()
    if agent:
        agent_traces = {
            e.trace_id
            for e in store.executions.values()
            if e.trace_id and (e.agent_id == agent or e.agent_name == agent)
        }
        traces &= agent_traces

    if not traces:
        return {
            "empty": True,
            "title": "No matching traces",
            "message": "Traces appear when OpenTelemetry spans are ingested.",
            "items": [],
        }

    items = []
    for tid in traces:
        span_ids = store.spans_by_trace.get(tid, [])
        spans = [store.spans[s] for s in span_ids if s in store.spans]
        items.append(
            {
                "trace_id": tid,
                "span_count": len(spans),
                "root_name": spans[0].name if spans else None,
                "start_time": min((s.start_time for s in spans if s.start_time), default=None),
            }
        )
    return {"empty": False, "items": items}


@router.get("/traces/{trace_id}")
async def get_trace(trace_id: str, _: dict = Depends(require_permission("traces:read"))):
    span_ids = store.spans_by_trace.get(trace_id)
    if not span_ids:
        raise HTTPException(404, "Trace not found")
    spans = [store.spans[s].model_dump() for s in span_ids if s in store.spans]
    # Strip prompt/response unless content capture enabled
    if not store.settings.content_capture_enabled:
        for s in spans:
            s["attributes"] = {
                k: v
                for k, v in s.get("attributes", {}).items()
                if "prompt" not in k.lower() and "completion" not in k.lower() and "content" not in k.lower()
            }
    return {"trace_id": trace_id, "spans": spans}


# ── Models / Tools / MCP / RAG / A2A ────────────────────────────────────


@router.get("/models")
async def models(_: dict = Depends(require_permission("agents:read"))):
    result = metrics_service.models()
    if isinstance(result, EmptyStateResponse):
        return {"empty": True, **result.model_dump()}
    return {"empty": False, "items": [r.model_dump() for r in result]}


@router.get("/tools")
async def tools(_: dict = Depends(require_permission("agents:read"))):
    result = metrics_service.tools()
    if isinstance(result, EmptyStateResponse):
        return {"empty": True, **result.model_dump()}
    return {"empty": False, "items": [r.model_dump() for r in result]}


@router.get("/mcp")
async def mcp(_: dict = Depends(require_permission("agents:read"))):
    result = metrics_service.mcp()
    if isinstance(result, EmptyStateResponse):
        return {"empty": True, **result.model_dump()}
    return {"empty": False, "items": [r.model_dump() for r in result]}


@router.get("/rag")
async def rag(_: dict = Depends(require_permission("agents:read"))):
    result = metrics_service.rag()
    if isinstance(result, EmptyStateResponse):
        return {"empty": True, **result.model_dump()}
    return {"empty": False, "items": [r.model_dump() for r in result]}


@router.get("/a2a")
async def a2a(_: dict = Depends(require_permission("agents:read"))):
    result = metrics_service.a2a()
    if isinstance(result, EmptyStateResponse):
        return {"empty": True, **result.model_dump()}
    return {"empty": False, "items": [r.model_dump() for r in result]}


# ── Analytics ───────────────────────────────────────────────────────────


@router.get("/analytics/cloud")
async def cloud_dist(_: dict = Depends(require_permission("agents:read"))):
    result = metrics_service.cloud_distribution()
    if isinstance(result, EmptyStateResponse):
        return {"empty": True, **result.model_dump()}
    return {"empty": False, **result}


@router.get("/analytics/frameworks")
async def framework_dist(_: dict = Depends(require_permission("agents:read"))):
    result = metrics_service.framework_distribution()
    if isinstance(result, EmptyStateResponse):
        return {"empty": True, **result.model_dump()}
    return {"empty": False, **result}


@router.get("/analytics/cross-cloud")
async def cross_cloud(_: dict = Depends(require_permission("agents:read"))):
    result = metrics_service.cross_cloud()
    if isinstance(result, EmptyStateResponse):
        return {"empty": True, **result.model_dump()}
    return {"empty": False, **result}


# ── Optimization ────────────────────────────────────────────────────────


@router.get("/optimization")
async def optimization(_: dict = Depends(require_permission("optimization:read"))):
    if not store.optimizations:
        return {
            "empty": True,
            "title": "No optimization findings",
            "message": "Recommendations appear when enough live telemetry establishes evidence and baselines.",
            "items": [],
        }
    return {"empty": False, "items": [o.model_dump() for o in store.optimizations]}


# ── Settings ────────────────────────────────────────────────────────────


@router.get("/settings")
async def get_settings_api(_: dict = Depends(require_permission("settings:read"))):
    return store.settings.model_dump()


@router.put("/settings")
async def update_settings(body: AppSettings, _: dict = Depends(require_permission("settings:write"))):
    store.settings = body
    return store.settings.model_dump()


# ── Telemetry ingestion ─────────────────────────────────────────────────


@router.post("/telemetry/otlp")
async def ingest_otlp(
    payload: dict[str, Any],
    integration_id: str = Query(default="otel"),
    provider: str = Query(default="otel"),
):
    return await telemetry_service.ingest_otlp_spans(
        payload, provider=provider, integration_id=integration_id
    )


@router.post("/telemetry/spans")
async def ingest_spans(
    payload: dict[str, Any],
    integration_id: str | None = Query(default="otel"),
    provider: str = Query(default="otel"),
):
    """Simplified span ingestion for connectors and tests."""
    return await telemetry_service.ingest_otlp_spans(
        payload, provider=provider, integration_id=integration_id
    )
