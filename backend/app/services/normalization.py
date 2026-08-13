"""Provider-neutral telemetry normalization layer.

Maps Azure / AWS / Google / OTel / LangSmith fields into canonical dimensions.
Never invents values — missing fields remain None.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.models.domain import (
    Execution,
    ExecutionStatus,
    NormalizedSpan,
    TelemetryQuality,
    WorkflowNodeType,
)

# Pull-based telemetry (e.g. App Insights) only emits completed child spans while an
# agent run is still in flight. Keep the parent execution "running" until activity
# has been idle for this long.
IN_PROGRESS_IDLE_SECONDS = 90

# Token field aliases → canonical
INPUT_TOKEN_ALIASES = (
    "input_tokens",
    "prompt_tokens",
    "inputTokens",
    "promptTokenCount",
    "gen_ai.usage.input_tokens",
    "llm.usage.prompt_tokens",
)
OUTPUT_TOKEN_ALIASES = (
    "output_tokens",
    "completion_tokens",
    "outputTokens",
    "candidatesTokenCount",
    "gen_ai.usage.output_tokens",
    "llm.usage.completion_tokens",
)
CACHED_TOKEN_ALIASES = (
    "cached_tokens",
    "cache_read_input_tokens",
    "cachedContentTokenCount",
    "gen_ai.usage.cache_read_input_tokens",
)
REASONING_TOKEN_ALIASES = (
    "reasoning_tokens",
    "reasoningTokenCount",
    "gen_ai.usage.reasoning_tokens",
)
TOTAL_TOKEN_ALIASES = (
    "total_tokens",
    "totalTokens",
    "totalTokenCount",
    "gen_ai.usage.total_tokens",
)


def _get_first(data: dict[str, Any], keys: tuple[str, ...]) -> Any | None:
    for key in keys:
        if key in data and data[key] is not None:
            return data[key]
        # nested attribute style
        parts = key.split(".")
        cur: Any = data
        found = True
        for p in parts:
            if isinstance(cur, dict) and p in cur:
                cur = cur[p]
            else:
                found = False
                break
        if found and cur is not None and not isinstance(cur, dict):
            return cur
    return None


def _as_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, (int, float)):
        # assume ns or ms epoch
        v = float(value)
        if v > 1e18:  # ns
            return datetime.fromtimestamp(v / 1e9, tz=timezone.utc)
        if v > 1e12:  # ms
            return datetime.fromtimestamp(v / 1e3, tz=timezone.utc)
        return datetime.fromtimestamp(v, tz=timezone.utc)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def normalize_tokens(attrs: dict[str, Any]) -> dict[str, int | None]:
    input_tokens = _as_int(_get_first(attrs, INPUT_TOKEN_ALIASES))
    output_tokens = _as_int(_get_first(attrs, OUTPUT_TOKEN_ALIASES))
    cached_tokens = _as_int(_get_first(attrs, CACHED_TOKEN_ALIASES))
    reasoning_tokens = _as_int(_get_first(attrs, REASONING_TOKEN_ALIASES))
    total_tokens = _as_int(_get_first(attrs, TOTAL_TOKEN_ALIASES))

    # Only compute total if we have at least one component and no explicit total
    if total_tokens is None and any(
        v is not None for v in (input_tokens, output_tokens, cached_tokens, reasoning_tokens)
    ):
        total_tokens = sum(
            v for v in (input_tokens, output_tokens, cached_tokens, reasoning_tokens) if v is not None
        )

    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cached_tokens": cached_tokens,
        "reasoning_tokens": reasoning_tokens,
        "total_tokens": total_tokens,
    }


def infer_node_type(name: str, attrs: dict[str, Any]) -> WorkflowNodeType:
    explicit = attrs.get("node.type") or attrs.get("gen_ai.operation.name") or attrs.get("span.kind")
    if explicit:
        mapping = {
            "chat": WorkflowNodeType.MODEL,
            "completion": WorkflowNodeType.MODEL,
            "embeddings": WorkflowNodeType.MODEL,
            "execute_tool": WorkflowNodeType.TOOL,
            "invoke_agent": WorkflowNodeType.AGENT,
            "create_agent": WorkflowNodeType.AGENT,
            "retrieve": WorkflowNodeType.RAG,
            "mcp": WorkflowNodeType.MCP,
            "a2a": WorkflowNodeType.A2A,
            "router": WorkflowNodeType.ROUTER,
            "planner": WorkflowNodeType.PLANNER,
            "worker": WorkflowNodeType.WORKER,
            "guardrail": WorkflowNodeType.GUARDRAIL,
            "response": WorkflowNodeType.RESPONSE,
            "user": WorkflowNodeType.USER,
        }
        key = str(explicit).lower()
        if key in mapping:
            return mapping[key]

    lower = name.lower()
    if any(x in lower for x in ("mcp", "model context protocol")):
        return WorkflowNodeType.MCP
    if any(x in lower for x in ("rag", "retriev", "vector", "search", "knowledge")):
        return WorkflowNodeType.RAG
    if any(x in lower for x in ("a2a", "handoff", "delegate", "supervisor")):
        return WorkflowNodeType.A2A
    if any(x in lower for x in ("tool", "function", "graph.", "servicenow", "jira")):
        return WorkflowNodeType.TOOL
    if any(x in lower for x in ("llm", "model", "chat", "completion", "gpt", "claude", "nova", "gemini")):
        return WorkflowNodeType.MODEL
    if "router" in lower:
        return WorkflowNodeType.ROUTER
    if "planner" in lower:
        return WorkflowNodeType.PLANNER
    if "worker" in lower:
        return WorkflowNodeType.WORKER
    if "guard" in lower:
        return WorkflowNodeType.GUARDRAIL
    if any(x in lower for x in ("response", "final")):
        return WorkflowNodeType.RESPONSE
    if "user" in lower or "request" in lower:
        return WorkflowNodeType.USER
    if "agent" in lower:
        return WorkflowNodeType.AGENT
    if any(x in lower for x in ("sql", "database", "cosmos", "dynamodb", "postgres")):
        return WorkflowNodeType.DATABASE
    if any(x in lower for x in ("http", "api", "rest", "graphql")):
        return WorkflowNodeType.API
    return WorkflowNodeType.UNKNOWN


def normalize_status(raw: Any) -> ExecutionStatus:
    if raw is None:
        return ExecutionStatus.UNKNOWN
    s = str(raw).lower()
    if s in ("ok", "success", "succeeded", "completed", "STATUS_CODE_OK", "unset"):
        return ExecutionStatus.SUCCESS
    if s in ("error", "failed", "failure", "STATUS_CODE_ERROR"):
        return ExecutionStatus.FAILED
    if s in ("running", "in_progress", "active"):
        return ExecutionStatus.RUNNING
    if s in ("timeout", "timed_out"):
        return ExecutionStatus.TIMEOUT
    if s in ("cancelled", "canceled"):
        return ExecutionStatus.CANCELLED
    return ExecutionStatus.UNKNOWN


def normalize_span(raw: dict[str, Any], provider: str = "otel") -> NormalizedSpan:
    attrs = dict(raw.get("attributes") or raw.get("attrs") or {})
    # flatten top-level gen_ai etc into attrs for lookup
    for k, v in raw.items():
        if k not in ("attributes", "attrs", "events", "links") and k not in attrs:
            attrs[k] = v

    tokens = normalize_tokens(attrs)
    name = str(raw.get("name") or attrs.get("name") or "unnamed")
    span_id = str(raw.get("span_id") or raw.get("spanId") or attrs.get("span.id") or "")
    trace_id = str(raw.get("trace_id") or raw.get("traceId") or attrs.get("trace.id") or "")
    parent = raw.get("parent_span_id") or raw.get("parentSpanId") or attrs.get("parent.id")
    start = _parse_dt(raw.get("start_time") or raw.get("startTimeUnixNano") or raw.get("start_time_unix_nano"))
    end = _parse_dt(raw.get("end_time") or raw.get("endTimeUnixNano") or raw.get("end_time_unix_nano"))
    duration = _as_float(raw.get("duration_ms") or attrs.get("duration_ms"))
    if duration is None and start and end:
        duration = (end - start).total_seconds() * 1000

    status_raw = raw.get("status") or attrs.get("status") or attrs.get("otel.status_code")
    if isinstance(status_raw, dict):
        status_raw = status_raw.get("code") or status_raw.get("message")

    exec_id = (
        attrs.get("execution.id")
        or attrs.get("gen_ai.conversation.id")
        or attrs.get("conversation.id")
        or attrs.get("session.id")
        # Prefer shared trace/operation id so multi-step agent runs stay one execution.
        # gen_ai.response.id is per-completion and would split in-progress traces.
        or (trace_id if trace_id and trace_id != "unknown" else None)
        or attrs.get("gen_ai.response.id")
    )

    return NormalizedSpan(
        span_id=span_id or f"span-{id(raw)}",
        trace_id=trace_id or "unknown",
        parent_span_id=str(parent) if parent else None,
        execution_id=str(exec_id) if exec_id else None,
        name=name,
        node_type=infer_node_type(name, attrs),
        status=str(status_raw) if status_raw is not None else None,
        start_time=start,
        end_time=end,
        duration_ms=duration,
        tokens=tokens.get("total_tokens"),
        call_count=_as_int(attrs.get("call_count")) or 1,
        attributes={
            **{k: v for k, v in attrs.items() if not str(k).startswith("prompt") and not str(k).startswith("completion")},
            **{f"canonical.{k}": v for k, v in tokens.items()},
            "canonical.provider": provider,
            "canonical.agent.id": attrs.get("agent.id") or attrs.get("gen_ai.agent.id"),
            "canonical.agent.name": attrs.get("agent.name") or attrs.get("gen_ai.agent.name"),
            "canonical.model": attrs.get("model.name")
            or attrs.get("gen_ai.request.model")
            or attrs.get("llm.model_name"),
            "canonical.cloud": attrs.get("cloud.provider") or attrs.get("cloud"),
            "canonical.framework": attrs.get("framework.name") or attrs.get("framework"),
            "canonical.tool": attrs.get("tool.name") or attrs.get("gen_ai.tool.name"),
            "canonical.mcp.server": attrs.get("mcp.server"),
            "canonical.mcp.tool": attrs.get("mcp.tool"),
            "canonical.rag.datasource": attrs.get("rag.datasource") or attrs.get("retrieval.datasource"),
            "canonical.a2a.source": attrs.get("a2a.source_agent"),
            "canonical.a2a.destination": attrs.get("a2a.destination_agent"),
        },
        provider_raw={"provider": provider, "span_name": name},
        error=attrs.get("error.type") or attrs.get("exception.message") or raw.get("error"),
    )


def aggregate_execution(spans: list[NormalizedSpan], existing: Execution | None = None) -> Execution:
    """Aggregate normalized spans into a canonical execution record.

    Fields remain None when no span provides them — never default to 0
    unless a real zero was observed.
    """
    if not spans and existing:
        return existing

    base = existing.model_dump() if existing else {}
    first = spans[0] if spans else None
    attrs_list = [s.attributes for s in spans]

    def first_attr(key: str) -> Any:
        for a in attrs_list:
            if a.get(key) is not None:
                return a.get(key)
        return None

    starts = [s.start_time for s in spans if s.start_time]
    ends = [s.end_time for s in spans if s.end_time]
    start_time = min(starts) if starts else base.get("start_time")
    end_time = max(ends) if ends else base.get("end_time")
    duration = None
    if start_time and end_time:
        duration = (end_time - start_time).total_seconds() * 1000

    token_vals = [s.tokens for s in spans if s.tokens is not None]
    model_spans = [s for s in spans if s.node_type == WorkflowNodeType.MODEL]
    tool_spans = [s for s in spans if s.node_type == WorkflowNodeType.TOOL]
    mcp_spans = [s for s in spans if s.node_type == WorkflowNodeType.MCP]
    rag_spans = [s for s in spans if s.node_type == WorkflowNodeType.RAG]
    a2a_spans = [s for s in spans if s.node_type == WorkflowNodeType.A2A]

    statuses = [normalize_status(s.status) for s in spans]
    open_spans = [s for s in spans if s.end_time is None]
    now = datetime.now(timezone.utc)

    def _aware(dt: datetime) -> datetime:
        return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)

    activity_times = [_aware(t) for t in (*starts, *ends) if t is not None]
    latest_activity = max(activity_times) if activity_times else None
    recently_active = bool(
        latest_activity
        and (now - latest_activity).total_seconds() < IN_PROGRESS_IDLE_SECONDS
    )

    if ExecutionStatus.FAILED in statuses or ExecutionStatus.TIMEOUT in statuses:
        status = ExecutionStatus.FAILED if ExecutionStatus.FAILED in statuses else ExecutionStatus.TIMEOUT
    elif open_spans or ExecutionStatus.RUNNING in statuses or recently_active:
        # Open spans, explicit running, or fresh activity (in-progress agent pull).
        status = ExecutionStatus.RUNNING
        end_time = None
        duration = (now - _aware(start_time)).total_seconds() * 1000 if start_time else None
    elif statuses and all(st == ExecutionStatus.SUCCESS for st in statuses):
        status = ExecutionStatus.SUCCESS
    elif statuses:
        status = statuses[-1]
    else:
        status = ExecutionStatus.UNKNOWN

    input_tokens = _as_int(first_attr("canonical.input_tokens"))
    output_tokens = _as_int(first_attr("canonical.output_tokens"))
    # Prefer summing span canonical tokens when present
    in_sum = [_as_int(s.attributes.get("canonical.input_tokens")) for s in spans]
    out_sum = [_as_int(s.attributes.get("canonical.output_tokens")) for s in spans]
    if any(v is not None for v in in_sum):
        input_tokens = sum(v for v in in_sum if v is not None)
    if any(v is not None for v in out_sum):
        output_tokens = sum(v for v in out_sum if v is not None)

    total_tokens = None
    if token_vals:
        total_tokens = sum(token_vals)
    elif input_tokens is not None or output_tokens is not None:
        total_tokens = (input_tokens or 0) + (output_tokens or 0)

    exec_id = (
        (first.execution_id if first else None)
        or base.get("execution_id")
        or (first.trace_id if first else None)
        or "unknown"
    )

    quality = TelemetryQuality.PARTIAL
    if spans and total_tokens is not None and first_attr("canonical.agent.id"):
        quality = TelemetryQuality.COMPLETE
    elif not spans:
        quality = TelemetryQuality.MISSING

    retries = sum(1 for s in spans if s.attributes.get("retry") or "retry" in s.name.lower())
    fallbacks = sum(1 for s in spans if s.attributes.get("fallback") or "fallback" in s.name.lower())
    errors = sum(1 for s in spans if s.error or normalize_status(s.status) == ExecutionStatus.FAILED)

    return Execution(
        execution_id=str(exec_id),
        timestamp=start_time or datetime.now(timezone.utc),
        start_time=start_time,
        end_time=end_time,
        tenant_id=first_attr("tenant.id") or base.get("tenant_id"),
        subscription_id=first_attr("subscription.id") or base.get("subscription_id"),
        account_id=first_attr("account.id") or base.get("account_id"),
        project_id=first_attr("project.id") or base.get("project_id"),
        agent_id=first_attr("canonical.agent.id") or base.get("agent_id"),
        agent_name=first_attr("canonical.agent.name") or base.get("agent_name"),
        agent_version=first_attr("agent.version") or base.get("agent_version"),
        business_unit=first_attr("business.unit") or base.get("business_unit"),
        application=first_attr("application.id") or base.get("application"),
        cloud_provider=first_attr("canonical.cloud") or base.get("cloud_provider"),
        platform=first_attr("platform.name") or base.get("platform"),
        region=first_attr("cloud.region") or base.get("region"),
        framework=first_attr("canonical.framework") or base.get("framework"),
        environment=first_attr("environment") or base.get("environment"),
        user_id_hash=first_attr("user.id_hash") or base.get("user_id_hash"),
        session_id=first_attr("session.id") or base.get("session_id"),
        conversation_id=first_attr("conversation.id") or base.get("conversation_id"),
        trace_id=first.trace_id if first else base.get("trace_id"),
        model_provider=first_attr("model.provider") or base.get("model_provider"),
        model_name=first_attr("canonical.model") or base.get("model_name"),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cached_tokens=_as_int(first_attr("canonical.cached_tokens")),
        reasoning_tokens=_as_int(first_attr("canonical.reasoning_tokens")),
        total_tokens=total_tokens,
        model_calls=len(model_spans) if model_spans else None,
        agent_steps=len(spans) if spans else None,
        tool_calls=len(tool_spans) if tool_spans else None,
        mcp_calls=len(mcp_spans) if mcp_spans else None,
        rag_queries=len(rag_spans) if rag_spans else None,
        a2a_calls=len(a2a_spans) if a2a_spans else None,
        retry_count=retries if retries else None,
        fallback_count=fallbacks if fallbacks else None,
        execution_duration_ms=duration,
        status=status,
        error_count=errors if errors else None,
        error_type=next((s.error for s in spans if s.error), None),
        telemetry_quality=quality,
        provider_raw_reference=first.provider_raw.get("provider") if first else None,
    )
