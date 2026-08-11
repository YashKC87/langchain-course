"""Overview KPIs, metering tables, and distribution analytics.

All values come from live telemetry. Missing → available=False, value=None.
Never interpret missing as zero.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

from app.models.domain import (
    A2ASummary,
    AgentMeteringRow,
    EmptyStateResponse,
    ExecutionStatus,
    MCPSummary,
    MetricValue,
    ModelSummary,
    OverviewKPIs,
    RAGSummary,
    ToolSummary,
    WorkflowNodeType,
)
from app.storage.store import store


def _mv(value) -> MetricValue:
    if value is None:
        return MetricValue(value=None, available=False, label="No live data")
    return MetricValue(value=value, available=True)


class MetricsService:
    def overview(self) -> OverviewKPIs | EmptyStateResponse:
        if not store.has_any_enabled_integration() and not store.has_live_telemetry():
            return EmptyStateResponse(
                title="Connect Your First Platform",
                message="Connect and enable a platform to start receiving agent telemetry.",
                actions=[
                    {"label": "Microsoft Azure", "action": "connect", "id": "azure"},
                    {"label": "AWS", "action": "connect", "id": "aws"},
                    {"label": "Google Cloud", "action": "connect", "id": "gcp"},
                    {"label": "OpenTelemetry", "action": "connect", "id": "otel"},
                ],
            )

        if store.has_any_enabled_integration() and not store.has_live_telemetry():
            enabled = [i.name for i in store.integrations.values() if i.enabled]
            return EmptyStateResponse(
                title="No Live Telemetry Available",
                message=(
                    f"Connected: {', '.join(enabled)}. Waiting for live telemetry. "
                    "Agents and metrics will populate automatically when spans arrive."
                ),
                actions=[{"label": "View Integrations", "action": "navigate", "id": "integrations"}],
            )

        # Live telemetry present
        now = datetime.now(timezone.utc)
        agents = list(store.agents.values())
        execs = list(store.executions.values())

        active = [
            a
            for a in agents
            if a.last_telemetry_at and (now - a.last_telemetry_at).total_seconds() < 300
        ]

        success_known = [e for e in execs if e.status in (ExecutionStatus.SUCCESS, ExecutionStatus.FAILED)]
        success_rate = None
        if success_known:
            success_rate = (
                sum(1 for e in success_known if e.status == ExecutionStatus.SUCCESS) / len(success_known) * 100
            )

        token_vals = [e.total_tokens for e in execs if e.total_tokens is not None]
        total_tokens = sum(token_vals) if token_vals else None

        lat_vals = [e.execution_duration_ms for e in execs if e.execution_duration_ms is not None]
        avg_lat = (sum(lat_vals) / len(lat_vals)) if lat_vals else None

        return OverviewKPIs(
            active_agents=_mv(len(active) if agents else None) if agents else MetricValue(value=None, available=False, label="No live data"),
            executions=_mv(len(execs) if execs else None),
            total_tokens=_mv(total_tokens),
            success_rate=_mv(round(success_rate, 1) if success_rate is not None else None),
            average_latency=_mv(round(avg_lat, 1) if avg_lat is not None else None),
            needs_attention=_mv(len(store.attention) if store.attention or execs else None),
            telemetry_live=True,
            last_updated=store.last_telemetry_at,
        )

    def agent_metering(self) -> list[AgentMeteringRow] | EmptyStateResponse:
        if not store.agents:
            return EmptyStateResponse(
                title="No agents discovered",
                message="Connect and enable a platform to start receiving agent telemetry.",
                actions=[{"label": "Integrations", "action": "navigate", "id": "integrations"}],
            )

        rows: list[AgentMeteringRow] = []
        for agent in store.agents.values():
            execs = [e for e in store.executions.values() if e.agent_id == agent.id]
            tokens = [e.total_tokens for e in execs if e.total_tokens is not None]
            steps = [e.agent_steps for e in execs if e.agent_steps is not None]
            lats = [e.execution_duration_ms for e in execs if e.execution_duration_ms is not None]
            known = [e for e in execs if e.status in (ExecutionStatus.SUCCESS, ExecutionStatus.FAILED)]
            success = None
            if known:
                success = sum(1 for e in known if e.status == ExecutionStatus.SUCCESS) / len(known) * 100

            def sum_field(field: str):
                vals = [getattr(e, field) for e in execs if getattr(e, field) is not None]
                return sum(vals) if vals else None

            rows.append(
                AgentMeteringRow(
                    agent_id=agent.id,
                    agent_name=agent.name,
                    cloud=agent.cloud,
                    platform=agent.platform,
                    framework=agent.framework,
                    model=agent.primary_model,
                    executions=len(execs) if execs else None,
                    tokens=sum(tokens) if tokens else None,
                    average_steps=(sum(steps) / len(steps)) if steps else None,
                    model_calls=sum_field("model_calls"),
                    tool_calls=sum_field("tool_calls"),
                    mcp_calls=sum_field("mcp_calls"),
                    rag_calls=sum_field("rag_queries"),
                    a2a_calls=sum_field("a2a_calls"),
                    average_latency_ms=(sum(lats) / len(lats)) if lats else None,
                    success_rate=round(success, 1) if success is not None else None,
                    health=agent.health,
                    last_seen=agent.last_telemetry_at,
                )
            )
        return rows

    def models(self) -> list[ModelSummary] | EmptyStateResponse:
        by_model: dict[str, list] = defaultdict(list)
        for e in store.executions.values():
            if e.model_name:
                by_model[e.model_name].append(e)
        # Also from spans
        for s in store.spans.values():
            m = s.attributes.get("canonical.model")
            if m and m not in by_model:
                by_model[m] = []

        if not by_model:
            return EmptyStateResponse(
                title="No models detected",
                message="Models appear when live telemetry includes model spans or attributes.",
            )

        rows: list[ModelSummary] = []
        for model, execs in by_model.items():
            agents = {e.agent_id for e in execs if e.agent_id}
            tokens = [e.total_tokens for e in execs if e.total_tokens is not None]
            lats = [e.average_model_latency_ms or e.execution_duration_ms for e in execs]
            lats = [x for x in lats if x is not None]
            known = [e for e in execs if e.status in (ExecutionStatus.SUCCESS, ExecutionStatus.FAILED)]
            success = (
                sum(1 for e in known if e.status == ExecutionStatus.SUCCESS) / len(known)
                if known
                else None
            )
            fb = sum(e.fallback_count or 0 for e in execs if e.fallback_count is not None)
            rows.append(
                ModelSummary(
                    model=model,
                    provider=next((e.model_provider for e in execs if e.model_provider), None),
                    cloud=next((e.cloud_provider for e in execs if e.cloud_provider), None),
                    agents_using=len(agents) if agents else None,
                    requests=len(execs) if execs else None,
                    tokens=sum(tokens) if tokens else None,
                    average_latency_ms=(sum(lats) / len(lats)) if lats else None,
                    success_rate=round(success * 100, 1) if success is not None else None,
                    failure_rate=round((1 - success) * 100, 1) if success is not None else None,
                    fallback_count=fb if any(e.fallback_count is not None for e in execs) else None,
                    last_seen=max((e.start_time for e in execs if e.start_time), default=None),
                )
            )
        return rows

    def tools(self) -> list[ToolSummary] | EmptyStateResponse:
        tool_spans = [s for s in store.spans.values() if s.node_type == WorkflowNodeType.TOOL]
        if not tool_spans:
            return EmptyStateResponse(
                title="No tool telemetry available",
                message="Tool invocations appear when agents emit tool spans.",
            )
        by_name: dict[str, list] = defaultdict(list)
        for s in tool_spans:
            name = s.attributes.get("canonical.tool") or s.name
            by_name[str(name)].append(s)
        rows = []
        for name, spans in by_name.items():
            lats = [s.duration_ms for s in spans if s.duration_ms is not None]
            fails = sum(1 for s in spans if s.error)
            rows.append(
                ToolSummary(
                    name=name,
                    tool_type=spans[0].attributes.get("tool.type"),
                    calls=len(spans),
                    success=len(spans) - fails,
                    failure=fails if fails else 0,
                    average_latency_ms=(sum(lats) / len(lats)) if lats else None,
                    last_invocation=max((s.start_time for s in spans if s.start_time), default=None),
                    health="critical" if fails == len(spans) else ("warning" if fails else "healthy"),
                )
            )
        return rows

    def mcp(self) -> list[MCPSummary] | EmptyStateResponse:
        mcp_spans = [s for s in store.spans.values() if s.node_type == WorkflowNodeType.MCP]
        if not mcp_spans:
            return EmptyStateResponse(
                title="No MCP telemetry available",
                message="MCP activity appears when agents emit MCP spans.",
            )
        by_server: dict[str, list] = defaultdict(list)
        for s in mcp_spans:
            server = s.attributes.get("canonical.mcp.server") or s.name
            by_server[str(server)].append(s)
        rows = []
        for server, spans in by_server.items():
            lats = [s.duration_ms for s in spans if s.duration_ms is not None]
            fails = sum(1 for s in spans if s.error)
            rows.append(
                MCPSummary(
                    server=server,
                    tool=spans[0].attributes.get("canonical.mcp.tool"),
                    calls=len(spans),
                    success=len(spans) - fails,
                    failure=fails,
                    average_latency_ms=(sum(lats) / len(lats)) if lats else None,
                    last_invocation=max((s.start_time for s in spans if s.start_time), default=None),
                    health="critical" if fails == len(spans) else ("warning" if fails else "healthy"),
                )
            )
        return rows

    def rag(self) -> list[RAGSummary] | EmptyStateResponse:
        rag_spans = [s for s in store.spans.values() if s.node_type == WorkflowNodeType.RAG]
        if not rag_spans:
            return EmptyStateResponse(
                title="No RAG activity detected",
                message="RAG queries appear when retrieval spans are ingested.",
            )
        by_src: dict[str, list] = defaultdict(list)
        for s in rag_spans:
            src = s.attributes.get("canonical.rag.datasource") or s.name
            by_src[str(src)].append(s)
        rows = []
        for src, spans in by_src.items():
            lats = [s.duration_ms for s in spans if s.duration_ms is not None]
            fails = sum(1 for s in spans if s.error)
            rows.append(
                RAGSummary(
                    knowledge_source=src,
                    queries=len(spans),
                    average_latency_ms=(sum(lats) / len(lats)) if lats else None,
                    failures=fails,
                    last_query=max((s.start_time for s in spans if s.start_time), default=None),
                )
            )
        return rows

    def a2a(self) -> list[A2ASummary] | EmptyStateResponse:
        a2a_spans = [s for s in store.spans.values() if s.node_type == WorkflowNodeType.A2A]
        if not a2a_spans:
            return EmptyStateResponse(
                title="No A2A activity detected",
                message="Agent-to-agent handoffs appear when A2A spans are ingested.",
            )
        by_pair: dict[tuple, list] = defaultdict(list)
        for s in a2a_spans:
            src = s.attributes.get("canonical.a2a.source") or "unknown"
            dst = s.attributes.get("canonical.a2a.destination") or s.name
            by_pair[(str(src), str(dst))].append(s)
        rows = []
        for (src, dst), spans in by_pair.items():
            lats = [s.duration_ms for s in spans if s.duration_ms is not None]
            fails = sum(1 for s in spans if s.error)
            rows.append(
                A2ASummary(
                    source_agent=src,
                    destination_agent=dst,
                    handoffs=len(spans),
                    success=len(spans) - fails,
                    failure=fails,
                    average_latency_ms=(sum(lats) / len(lats)) if lats else None,
                    last_activity=max((s.start_time for s in spans if s.start_time), default=None),
                )
            )
        return rows

    def cloud_distribution(self) -> dict | EmptyStateResponse:
        clouds: dict[str, dict] = defaultdict(lambda: {"agents": 0, "executions": 0, "tokens": None, "model_calls": None, "tool_calls": None})
        token_acc: dict[str, list] = defaultdict(list)
        model_acc: dict[str, list] = defaultdict(list)
        tool_acc: dict[str, list] = defaultdict(list)

        for a in store.agents.values():
            cloud = a.cloud or "Other"
            clouds[cloud]["agents"] += 1
        for e in store.executions.values():
            cloud = e.cloud_provider or "Other"
            clouds[cloud]["executions"] += 1
            if e.total_tokens is not None:
                token_acc[cloud].append(e.total_tokens)
            if e.model_calls is not None:
                model_acc[cloud].append(e.model_calls)
            if e.tool_calls is not None:
                tool_acc[cloud].append(e.tool_calls)

        if not clouds:
            return EmptyStateResponse(
                title="No Live Agent Telemetry",
                message="Cloud distribution appears after agents are discovered from live telemetry.",
            )

        result = []
        for cloud, data in clouds.items():
            result.append(
                {
                    "cloud": cloud,
                    "agents": data["agents"] or None,
                    "executions": data["executions"] or None,
                    "tokens": sum(token_acc[cloud]) if token_acc[cloud] else None,
                    "model_calls": sum(model_acc[cloud]) if model_acc[cloud] else None,
                    "tool_calls": sum(tool_acc[cloud]) if tool_acc[cloud] else None,
                }
            )
        return {"items": result}

    def framework_distribution(self) -> dict | EmptyStateResponse:
        frameworks: dict[str, dict] = defaultdict(lambda: {"agents": set(), "executions": 0, "tokens": [], "latency": [], "success": []})
        for a in store.agents.values():
            if a.framework:
                frameworks[a.framework]["agents"].add(a.id)
        for e in store.executions.values():
            fw = e.framework
            if not fw:
                continue
            frameworks[fw]["executions"] += 1
            if e.total_tokens is not None:
                frameworks[fw]["tokens"].append(e.total_tokens)
            if e.execution_duration_ms is not None:
                frameworks[fw]["latency"].append(e.execution_duration_ms)
            if e.status in (ExecutionStatus.SUCCESS, ExecutionStatus.FAILED):
                frameworks[fw]["success"].append(e.status == ExecutionStatus.SUCCESS)

        if not frameworks:
            return EmptyStateResponse(
                title="No frameworks detected",
                message="Framework usage appears when telemetry includes framework attributes.",
            )

        items = []
        for fw, data in frameworks.items():
            succ = data["success"]
            items.append(
                {
                    "framework": fw,
                    "agents": len(data["agents"]) or None,
                    "executions": data["executions"] or None,
                    "tokens": sum(data["tokens"]) if data["tokens"] else None,
                    "latency": (sum(data["latency"]) / len(data["latency"])) if data["latency"] else None,
                    "success_rate": (sum(succ) / len(succ) * 100) if succ else None,
                }
            )
        return {"items": items}

    def cross_cloud(self) -> dict | EmptyStateResponse:
        dist = self.cloud_distribution()
        if isinstance(dist, EmptyStateResponse):
            return dist
        # Enrich with more columns from executions
        rows = []
        for item in dist["items"]:
            cloud = item["cloud"]
            execs = [e for e in store.executions.values() if (e.cloud_provider or "Other") == cloud]
            steps = [e.agent_steps for e in execs if e.agent_steps is not None]
            lats = [e.execution_duration_ms for e in execs if e.execution_duration_ms is not None]
            known = [e for e in execs if e.status in (ExecutionStatus.SUCCESS, ExecutionStatus.FAILED)]
            errors = sum(1 for e in execs if e.status == ExecutionStatus.FAILED)
            rows.append(
                {
                    **item,
                    "mcp_calls": sum(e.mcp_calls for e in execs if e.mcp_calls is not None) or None,
                    "rag_calls": sum(e.rag_queries for e in execs if e.rag_queries is not None) or None,
                    "a2a_calls": sum(e.a2a_calls for e in execs if e.a2a_calls is not None) or None,
                    "average_steps": (sum(steps) / len(steps)) if steps else None,
                    "average_latency": (sum(lats) / len(lats)) if lats else None,
                    "success_rate": (
                        sum(1 for e in known if e.status == ExecutionStatus.SUCCESS) / len(known) * 100
                        if known
                        else None
                    ),
                    "errors": errors if execs else None,
                }
            )
        return {"items": rows}


metrics_service = MetricsService()
