"""Convert normalized spans into a workflow graph.

Does not fabricate missing relationships. Unknown edges are marked clearly.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.models.domain import (
    ExecutionStatus,
    NormalizedSpan,
    WorkflowEdge,
    WorkflowEdgeType,
    WorkflowGraph,
    WorkflowNode,
    WorkflowNodeType,
)
from app.services.normalization import normalize_status as _normalize_status


def _edge_type_for(parent: NormalizedSpan, child: NormalizedSpan) -> tuple[WorkflowEdgeType, str]:
    if child.node_type == WorkflowNodeType.MODEL:
        if "fallback" in child.name.lower() or child.attributes.get("fallback"):
            return WorkflowEdgeType.FALLS_BACK, "Fallback"
        return WorkflowEdgeType.CALLS, "Model Call"
    if child.node_type == WorkflowNodeType.TOOL:
        return WorkflowEdgeType.CALLS, "Tool Call"
    if child.node_type == WorkflowNodeType.MCP:
        return WorkflowEdgeType.CALLS, "MCP Call"
    if child.node_type == WorkflowNodeType.RAG:
        return WorkflowEdgeType.RETRIEVES, "RAG Query"
    if child.node_type == WorkflowNodeType.A2A:
        return WorkflowEdgeType.HANDS_OFF, "A2A Handoff"
    if child.node_type in (WorkflowNodeType.WORKER, WorkflowNodeType.PLANNER):
        return WorkflowEdgeType.DELEGATES, "Delegation"
    if child.node_type == WorkflowNodeType.ROUTER:
        return WorkflowEdgeType.ROUTES, "Route"
    if "retry" in child.name.lower():
        return WorkflowEdgeType.RETRIES, "Retry"
    if child.node_type == WorkflowNodeType.RESPONSE:
        return WorkflowEdgeType.RETURNS, "Response"
    if parent.node_type == WorkflowNodeType.AGENT:
        return WorkflowEdgeType.INVOKES, "Invokes"
    return WorkflowEdgeType.UNKNOWN, "Related"


def build_workflow(execution_id: str, spans: list[NormalizedSpan], status: ExecutionStatus | None = None) -> WorkflowGraph:
    if not spans:
        return WorkflowGraph(
            execution_id=execution_id,
            nodes=[],
            edges=[],
            status=status or ExecutionStatus.UNKNOWN,
        )

    # Deduplicate by span_id — re-ingest polls can append the same span many times.
    unique: dict[str, NormalizedSpan] = {}
    for s in spans:
        if s.span_id:
            unique[s.span_id] = s
    spans = list(unique.values())

    nodes: list[WorkflowNode] = []
    edges: list[WorkflowEdge] = []
    by_id = {s.span_id: s for s in spans}

    # Determine live node: running status with no end, or latest span while execution is live
    live_ids: set[str] = set()
    for s in spans:
        st = _normalize_status(s.status)
        if st == ExecutionStatus.RUNNING or (s.start_time and not s.end_time and st != ExecutionStatus.SUCCESS):
            live_ids.add(s.span_id)
    if not live_ids and status == ExecutionStatus.RUNNING and spans:
        # Fresh pull-based runs: highlight the most recent span as in progress
        latest = max(
            spans,
            key=lambda s: s.end_time or s.start_time or datetime.min.replace(tzinfo=timezone.utc),
        )
        live_ids.add(latest.span_id)

    for s in spans:
        st = _normalize_status(s.status)
        status_label = None
        if s.span_id in live_ids:
            status_label = "running"
        elif st == ExecutionStatus.SUCCESS:
            status_label = "success"
        elif st == ExecutionStatus.FAILED:
            status_label = "failed"
        elif s.error:
            status_label = "failed"
        elif st == ExecutionStatus.UNKNOWN:
            status_label = "unknown"
        else:
            status_label = st.value

        nodes.append(
            WorkflowNode(
                id=s.span_id,
                name=s.name,
                node_type=s.node_type,
                status=status_label,
                duration_ms=s.duration_ms,
                tokens=s.tokens,
                call_count=s.call_count,
                timestamp=s.start_time,
                is_live=s.span_id in live_ids,
                span_id=s.span_id,
                attributes={
                    k: v
                    for k, v in s.attributes.items()
                    if k.startswith("canonical.") or k in ("tool.name", "mcp.server", "error.type")
                },
            )
        )

    for s in spans:
        if s.parent_span_id and s.parent_span_id in by_id:
            parent = by_id[s.parent_span_id]
            edge_type, label = _edge_type_for(parent, s)
            edges.append(
                WorkflowEdge(
                    id=f"{s.parent_span_id}->{s.span_id}",
                    source=s.parent_span_id,
                    target=s.span_id,
                    edge_type=edge_type,
                    label=label,
                )
            )
        elif s.parent_span_id:
            # Parent missing — mark unknown relationship without fabricating parent
            edges.append(
                WorkflowEdge(
                    id=f"unknown->{s.span_id}",
                    source=f"unresolved:{s.parent_span_id}",
                    target=s.span_id,
                    edge_type=WorkflowEdgeType.UNKNOWN,
                    label="Unknown parent",
                )
            )
            if not any(n.id == f"unresolved:{s.parent_span_id}" for n in nodes):
                nodes.append(
                    WorkflowNode(
                        id=f"unresolved:{s.parent_span_id}",
                        name="Unresolved parent",
                        node_type=WorkflowNodeType.UNKNOWN,
                        status="unknown",
                    )
                )

    # Order nodes roughly by start time
    nodes.sort(key=lambda n: (n.timestamp is None, n.timestamp or 0))

    overall = status
    if overall is None:
        if live_ids:
            overall = ExecutionStatus.RUNNING
        elif any(n.status == "failed" for n in nodes):
            overall = ExecutionStatus.FAILED
        elif nodes and all(n.status == "success" for n in nodes):
            overall = ExecutionStatus.SUCCESS
        else:
            overall = ExecutionStatus.UNKNOWN

    return WorkflowGraph(
        execution_id=execution_id,
        trace_id=spans[0].trace_id if spans else None,
        nodes=nodes,
        edges=edges,
        status=overall,
    )


def build_waterfall(spans: list[NormalizedSpan]) -> list[dict]:
    """Alternative waterfall view — ordered by start time, no fabricated spans."""
    unique: dict[str, NormalizedSpan] = {}
    for s in spans:
        if s.span_id:
            unique[s.span_id] = s
    ordered = sorted(unique.values(), key=lambda s: (s.start_time is None, s.start_time or 0))
    rows = []
    origin = next((s.start_time for s in ordered if s.start_time), None)
    for s in ordered:
        offset_ms = None
        if origin and s.start_time:
            offset_ms = (s.start_time - origin).total_seconds() * 1000
        rows.append(
            {
                "span_id": s.span_id,
                "name": s.name,
                "node_type": s.node_type.value,
                "offset_ms": offset_ms,
                "duration_ms": s.duration_ms,
                "tokens": s.tokens,
                "status": s.status,
                "parent_span_id": s.parent_span_id,
                "error": s.error,
                "attributes": {
                    k: v for k, v in s.attributes.items() if k.startswith("canonical.")
                },
            }
        )
    return rows
