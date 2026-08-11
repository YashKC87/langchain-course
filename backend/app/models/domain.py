"""Canonical domain models — provider-neutral, no financial fields."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ── Enums ──────────────────────────────────────────────────────────────


class IntegrationCategory(str, Enum):
    CLOUD_PLATFORM = "cloud_platforms"
    AGENT_PLATFORM = "agent_platforms"
    OBSERVABILITY = "observability"
    ENTERPRISE_TOOLS = "enterprise_tools"
    PROTOCOLS = "protocols"
    RAG_DATA_SOURCES = "rag_data_sources"


class IntegrationStatus(str, Enum):
    CONNECTED = "connected"
    TELEMETRY_ACTIVE = "telemetry_active"
    WARNING = "warning"
    CONNECTION_FAILED = "connection_failed"
    DISABLED = "disabled"
    NOT_CONFIGURED = "not_configured"


class AgentHealth(str, Enum):
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    OFFLINE = "offline"
    UNKNOWN = "unknown"
    PAUSED = "paused"


class ExecutionStatus(str, Enum):
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


class TelemetryQuality(str, Enum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    DELAYED = "delayed"
    MISSING = "missing"
    PROVIDER_UNSUPPORTED = "provider_unsupported"
    NOT_USED = "not_used"
    NOT_PROVIDED = "not_provided"


class WorkflowNodeType(str, Enum):
    USER = "user"
    AGENT = "agent"
    ROUTER = "router"
    PLANNER = "planner"
    WORKER = "worker"
    MODEL = "model"
    TOOL = "tool"
    MCP = "mcp"
    RAG = "rag"
    DATABASE = "database"
    API = "api"
    A2A = "a2a"
    GUARDRAIL = "guardrail"
    RESPONSE = "response"
    UNKNOWN = "unknown"


class WorkflowEdgeType(str, Enum):
    INVOKES = "invokes"
    DELEGATES = "delegates"
    ROUTES = "routes"
    RETRIEVES = "retrieves"
    CALLS = "calls"
    RETRIES = "retries"
    FALLS_BACK = "falls_back"
    HANDS_OFF = "hands_off"
    RETURNS = "returns"
    UNKNOWN = "unknown"


class AttentionSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


# ── Integration ─────────────────────────────────────────────────────────


class IntegrationConfig(BaseModel):
    """Non-secret configuration fields. Secrets referenced by key only."""

    fields: dict[str, Any] = Field(default_factory=dict)
    secret_refs: dict[str, str] = Field(default_factory=dict)
    auth_method: str | None = None


class Integration(BaseModel):
    id: str
    name: str
    category: IntegrationCategory
    provider: str
    status: IntegrationStatus = IntegrationStatus.NOT_CONFIGURED
    enabled: bool = False
    configured: bool = False
    config: IntegrationConfig = Field(default_factory=IntegrationConfig)
    last_telemetry_at: datetime | None = None
    agents_discovered: int | None = None  # None = unknown / N/A, never fake 0
    connection_health: str | None = None
    auth_state: str | None = None
    error_message: str | None = None
    enable_progress: list[dict[str, Any]] = Field(default_factory=list)


class IntegrationEnableStage(BaseModel):
    name: str
    status: str  # pending | running | success | failed | skipped
    message: str | None = None


# ── Agent Registry ──────────────────────────────────────────────────────


class Agent(BaseModel):
    id: str
    name: str
    description: str | None = None
    version: str | None = None
    cloud: str | None = None
    platform: str | None = None
    framework: str | None = None
    environment: str | None = None
    region: str | None = None
    owner: str | None = None
    business_unit: str | None = None
    application: str | None = None
    primary_model: str | None = None
    fallback_model: str | None = None
    endpoint_ref: str | None = None
    telemetry_source: str | None = None
    integration_id: str | None = None
    status: str | None = None
    health: AgentHealth = AgentHealth.UNKNOWN
    first_seen_at: datetime | None = None
    last_execution_at: datetime | None = None
    last_telemetry_at: datetime | None = None


# ── Normalized Execution ────────────────────────────────────────────────


class Execution(BaseModel):
    execution_id: str
    timestamp: datetime | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    tenant_id: str | None = None
    subscription_id: str | None = None
    account_id: str | None = None
    project_id: str | None = None
    agent_id: str | None = None
    agent_name: str | None = None
    agent_version: str | None = None
    business_unit: str | None = None
    application: str | None = None
    cloud_provider: str | None = None
    platform: str | None = None
    region: str | None = None
    framework: str | None = None
    environment: str | None = None
    user_id_hash: str | None = None
    session_id: str | None = None
    conversation_id: str | None = None
    trace_id: str | None = None
    model_provider: str | None = None
    model_name: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cached_tokens: int | None = None
    reasoning_tokens: int | None = None
    total_tokens: int | None = None
    model_calls: int | None = None
    agent_steps: int | None = None
    tool_calls: int | None = None
    mcp_calls: int | None = None
    api_calls: int | None = None
    rag_queries: int | None = None
    vector_queries: int | None = None
    database_calls: int | None = None
    retrieval_count: int | None = None
    a2a_calls: int | None = None
    handoff_count: int | None = None
    retry_count: int | None = None
    fallback_count: int | None = None
    execution_duration_ms: float | None = None
    first_token_latency_ms: float | None = None
    average_model_latency_ms: float | None = None
    tool_latency_ms: float | None = None
    mcp_latency_ms: float | None = None
    rag_latency_ms: float | None = None
    status: ExecutionStatus = ExecutionStatus.UNKNOWN
    outcome: str | None = None
    error_count: int | None = None
    error_type: str | None = None
    telemetry_quality: TelemetryQuality = TelemetryQuality.PARTIAL
    provider_raw_reference: str | None = None


# ── Spans / Workflow ────────────────────────────────────────────────────


class NormalizedSpan(BaseModel):
    span_id: str
    trace_id: str
    parent_span_id: str | None = None
    execution_id: str | None = None
    name: str
    node_type: WorkflowNodeType = WorkflowNodeType.UNKNOWN
    status: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    duration_ms: float | None = None
    tokens: int | None = None
    call_count: int | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)
    provider_raw: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class WorkflowNode(BaseModel):
    id: str
    name: str
    node_type: WorkflowNodeType
    status: str | None = None
    duration_ms: float | None = None
    tokens: int | None = None
    call_count: int | None = None
    timestamp: datetime | None = None
    is_live: bool = False
    span_id: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)


class WorkflowEdge(BaseModel):
    id: str
    source: str
    target: str
    edge_type: WorkflowEdgeType = WorkflowEdgeType.UNKNOWN
    label: str | None = None


class WorkflowGraph(BaseModel):
    execution_id: str
    trace_id: str | None = None
    nodes: list[WorkflowNode] = Field(default_factory=list)
    edges: list[WorkflowEdge] = Field(default_factory=list)
    status: ExecutionStatus = ExecutionStatus.UNKNOWN


# ── Activity / Attention / Optimization ─────────────────────────────────


class ActivityEvent(BaseModel):
    id: str
    timestamp: datetime
    event_type: str
    message: str
    agent_id: str | None = None
    agent_name: str | None = None
    severity: str = "info"
    execution_id: str | None = None
    trace_id: str | None = None


class AttentionItem(BaseModel):
    id: str
    condition: str
    severity: AttentionSeverity
    message: str
    agent_id: str | None = None
    agent_name: str | None = None
    component: str | None = None
    evidence: str | None = None
    related_trace: str | None = None
    detected_at: datetime


class OptimizationFinding(BaseModel):
    id: str
    observation: str
    evidence: str
    affected_agent: str | None = None
    affected_component: str | None = None
    recommendation: str
    confidence: float  # 0–1
    severity: AttentionSeverity
    related_trace: str | None = None
    detected_at: datetime


# ── Overview KPIs ───────────────────────────────────────────────────────


class MetricValue(BaseModel):
    """Nullable metric — None means no live data, never fabricate zero."""

    value: float | int | None = None
    available: bool = False
    label: str | None = None
    unit: str | None = None


class OverviewKPIs(BaseModel):
    active_agents: MetricValue = Field(default_factory=MetricValue)
    executions: MetricValue = Field(default_factory=MetricValue)
    total_tokens: MetricValue = Field(default_factory=MetricValue)
    success_rate: MetricValue = Field(default_factory=MetricValue)
    average_latency: MetricValue = Field(default_factory=MetricValue)
    needs_attention: MetricValue = Field(default_factory=MetricValue)
    telemetry_live: bool = False
    last_updated: datetime | None = None


# ── Filters / Settings ──────────────────────────────────────────────────


class GlobalFilters(BaseModel):
    cloud: str | None = None
    platform: str | None = None
    tenant: str | None = None
    business_unit: str | None = None
    environment: str | None = None
    agent: str | None = None
    framework: str | None = None
    model: str | None = None
    status: str | None = None
    time_range: str = "1h"


class AppSettings(BaseModel):
    telemetry_retention_days: int = 30
    auto_refresh_seconds: int = 30
    runaway_steps_warning: int = 8
    runaway_steps_high: int = 13
    runaway_steps_critical: int = 21
    runaway_retry_threshold: int = 5
    runaway_fallback_threshold: int = 3
    runaway_duration_ms_threshold: int = 300_000
    latency_warning_ms: int = 2_000
    latency_critical_ms: int = 10_000
    content_capture_enabled: bool = False
    pii_redaction_enabled: bool = True
    telemetry_sampling_rate: float = 1.0
    efficiency_weights: dict[str, float] = Field(
        default_factory=lambda: {
            "token_efficiency": 0.15,
            "latency": 0.15,
            "step_count": 0.15,
            "retry_rate": 0.10,
            "fallback_rate": 0.10,
            "success_rate": 0.15,
            "tool_efficiency": 0.05,
            "mcp_efficiency": 0.05,
            "rag_efficiency": 0.05,
            "a2a_efficiency": 0.025,
            "error_rate": 0.025,
        }
    )
    agent_discovery_schedule_minutes: int = 15


# ── Tool / MCP / RAG / A2A / Model summaries ────────────────────────────


class ToolSummary(BaseModel):
    name: str
    tool_type: str | None = None
    agent_id: str | None = None
    agent_name: str | None = None
    calls: int | None = None
    success: int | None = None
    failure: int | None = None
    average_latency_ms: float | None = None
    retries: int | None = None
    last_invocation: datetime | None = None
    health: str | None = None


class MCPSummary(BaseModel):
    server: str
    tool: str | None = None
    connected_agents: int | None = None
    calls: int | None = None
    success: int | None = None
    failure: int | None = None
    timeouts: int | None = None
    auth_errors: int | None = None
    average_latency_ms: float | None = None
    retries: int | None = None
    last_invocation: datetime | None = None
    health: str | None = None


class RAGSummary(BaseModel):
    knowledge_source: str
    agent_id: str | None = None
    agent_name: str | None = None
    queries: int | None = None
    search_type: str | None = None
    documents_retrieved: int | None = None
    chunks_retrieved: int | None = None
    average_latency_ms: float | None = None
    empty_retrievals: int | None = None
    failures: int | None = None
    retries: int | None = None
    last_query: datetime | None = None


class A2ASummary(BaseModel):
    source_agent: str
    destination_agent: str
    protocol: str | None = None
    handoffs: int | None = None
    success: int | None = None
    failure: int | None = None
    average_latency_ms: float | None = None
    tokens: int | None = None
    retries: int | None = None
    last_activity: datetime | None = None


class ModelSummary(BaseModel):
    model: str
    provider: str | None = None
    cloud: str | None = None
    agents_using: int | None = None
    requests: int | None = None
    tokens: int | None = None
    average_latency_ms: float | None = None
    success_rate: float | None = None
    failure_rate: float | None = None
    fallback_count: int | None = None
    last_seen: datetime | None = None


class AgentMeteringRow(BaseModel):
    agent_id: str
    agent_name: str
    cloud: str | None = None
    platform: str | None = None
    framework: str | None = None
    model: str | None = None
    executions: int | None = None
    tokens: int | None = None
    average_steps: float | None = None
    model_calls: int | None = None
    tool_calls: int | None = None
    mcp_calls: int | None = None
    rag_calls: int | None = None
    a2a_calls: int | None = None
    average_latency_ms: float | None = None
    success_rate: float | None = None
    health: AgentHealth = AgentHealth.UNKNOWN
    last_seen: datetime | None = None


class EmptyStateResponse(BaseModel):
    empty: bool = True
    title: str
    message: str
    actions: list[dict[str, str]] = Field(default_factory=list)
