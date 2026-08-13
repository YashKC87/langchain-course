"""In-memory observability store — live telemetry only, never synthetic.

Historical telemetry is retained when integrations are disabled.
No fake agents, executions, KPIs, or alerts are seeded.
"""

from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from app.models.domain import (
    A2ASummary,
    ActivityEvent,
    Agent,
    AppSettings,
    AttentionItem,
    Execution,
    Integration,
    IntegrationCategory,
    IntegrationConfig,
    IntegrationStatus,
    ExecutionStatus,
    MCPSummary,
    ModelSummary,
    NormalizedSpan,
    OptimizationFinding,
    RAGSummary,
    ToolSummary,
)


LIVE_EXECUTION_WINDOW_MINUTES = 120


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def is_live_execution(
    execution: Execution,
    *,
    now: datetime | None = None,
    window_minutes: int = LIVE_EXECUTION_WINDOW_MINUTES,
) -> bool:
    """Running executions, or those that finished within the recent live window."""
    if execution.status == ExecutionStatus.RUNNING:
        return True
    moment = now or _utcnow()
    cutoff = moment.timestamp() - (window_minutes * 60)
    ref = execution.end_time or execution.start_time or execution.timestamp
    if ref is None:
        return False
    if ref.tzinfo is None:
        ref = ref.replace(tzinfo=timezone.utc)
    return ref.timestamp() >= cutoff


def _default_integrations() -> dict[str, Integration]:
    """Catalog of supported integrations — unconfigured until user connects.

    Catalog entries are NOT operational telemetry. Status is NOT_CONFIGURED
    or DISABLED until the user configures and enables them.
    """
    catalog = [
        # Cloud platforms
        ("azure", "Microsoft Azure", IntegrationCategory.CLOUD_PLATFORM, "azure"),
        ("aws", "AWS", IntegrationCategory.CLOUD_PLATFORM, "aws"),
        ("gcp", "Google Cloud", IntegrationCategory.CLOUD_PLATFORM, "gcp"),
        # Agent platforms / MVP connectors
        ("azure-foundry", "Microsoft Foundry Agent Service", IntegrationCategory.AGENT_PLATFORM, "azure"),
        ("azure-agent-framework", "Microsoft Agent Framework", IntegrationCategory.AGENT_PLATFORM, "azure"),
        ("azure-openai", "Azure OpenAI", IntegrationCategory.AGENT_PLATFORM, "azure"),
        ("copilot-studio", "Copilot Studio", IntegrationCategory.AGENT_PLATFORM, "azure"),
        ("semantic-kernel", "Semantic Kernel", IntegrationCategory.AGENT_PLATFORM, "azure"),
        ("bedrock", "Amazon Bedrock", IntegrationCategory.AGENT_PLATFORM, "aws"),
        ("bedrock-agents", "Bedrock Agents", IntegrationCategory.AGENT_PLATFORM, "aws"),
        ("agentcore", "Amazon Bedrock AgentCore", IntegrationCategory.AGENT_PLATFORM, "aws"),
        ("vertex-ai", "Vertex AI", IntegrationCategory.AGENT_PLATFORM, "gcp"),
        ("vertex-agent-engine", "Vertex AI Agent Engine", IntegrationCategory.AGENT_PLATFORM, "gcp"),
        ("google-adk", "Google Agent Development Kit", IntegrationCategory.AGENT_PLATFORM, "gcp"),
        ("langgraph", "LangGraph", IntegrationCategory.AGENT_PLATFORM, "framework"),
        ("langchain", "LangChain", IntegrationCategory.AGENT_PLATFORM, "framework"),
        ("openai-agents", "OpenAI Agents SDK", IntegrationCategory.AGENT_PLATFORM, "framework"),
        ("autogen", "AutoGen", IntegrationCategory.AGENT_PLATFORM, "framework"),
        # Observability
        ("otel", "OpenTelemetry", IntegrationCategory.OBSERVABILITY, "otel"),
        ("azure-monitor", "Azure Monitor", IntegrationCategory.OBSERVABILITY, "azure"),
        ("app-insights", "Application Insights", IntegrationCategory.OBSERVABILITY, "azure"),
        ("cloudwatch", "AWS CloudWatch", IntegrationCategory.OBSERVABILITY, "aws"),
        ("gcp-observability", "Google Cloud Observability", IntegrationCategory.OBSERVABILITY, "gcp"),
        ("langsmith", "LangSmith", IntegrationCategory.OBSERVABILITY, "langsmith"),
        ("datadog", "Datadog", IntegrationCategory.OBSERVABILITY, "datadog"),
        ("splunk", "Splunk", IntegrationCategory.OBSERVABILITY, "splunk"),
        ("grafana", "Grafana", IntegrationCategory.OBSERVABILITY, "grafana"),
        ("prometheus", "Prometheus", IntegrationCategory.OBSERVABILITY, "prometheus"),
        # Enterprise tools
        ("servicenow", "ServiceNow", IntegrationCategory.ENTERPRISE_TOOLS, "servicenow"),
        ("ms-graph", "Microsoft Graph", IntegrationCategory.ENTERPRISE_TOOLS, "azure"),
        ("jira", "Jira", IntegrationCategory.ENTERPRISE_TOOLS, "atlassian"),
        # Protocols
        ("mcp", "MCP", IntegrationCategory.PROTOCOLS, "mcp"),
        ("a2a", "A2A", IntegrationCategory.PROTOCOLS, "a2a"),
        # RAG
        ("azure-ai-search", "Azure AI Search", IntegrationCategory.RAG_DATA_SOURCES, "azure"),
        ("opensearch", "OpenSearch", IntegrationCategory.RAG_DATA_SOURCES, "aws"),
        ("pgvector", "PostgreSQL / pgvector", IntegrationCategory.RAG_DATA_SOURCES, "postgres"),
    ]
    result: dict[str, Integration] = {}
    for iid, name, category, provider in catalog:
        result[iid] = Integration(
            id=iid,
            name=name,
            category=category,
            provider=provider,
            status=IntegrationStatus.NOT_CONFIGURED,
            enabled=False,
            configured=False,
            config=IntegrationConfig(),
            agents_discovered=None,
        )
    return result


class ObservabilityStore:
    """Thread-safe in-memory store. Never seeds fake operational telemetry."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self.integrations: dict[str, Integration] = _default_integrations()
        self.agents: dict[str, Agent] = {}
        self.executions: dict[str, Execution] = {}
        self.spans: dict[str, NormalizedSpan] = {}  # span_id -> span
        self.spans_by_trace: dict[str, list[str]] = {}
        self.spans_by_execution: dict[str, list[str]] = {}
        self.activity: list[ActivityEvent] = []
        self.attention: list[AttentionItem] = []
        self.optimizations: list[OptimizationFinding] = []
        self.tools: list[ToolSummary] = []
        self.mcp: list[MCPSummary] = []
        self.rag: list[RAGSummary] = []
        self.a2a: list[A2ASummary] = []
        self.models: list[ModelSummary] = []
        self.settings = AppSettings()
        self.last_telemetry_at: datetime | None = None
        self.provider_raw: dict[str, Any] = {}  # troubleshooting refs

    def has_live_telemetry(self) -> bool:
        return self.last_telemetry_at is not None and len(self.executions) > 0

    def has_any_enabled_integration(self) -> bool:
        return any(i.enabled for i in self.integrations.values())

    def has_any_configured_integration(self) -> bool:
        return any(i.configured for i in self.integrations.values())

    async def record_activity(self, event: ActivityEvent) -> None:
        async with self._lock:
            self.activity.insert(0, event)
            self.activity = self.activity[:500]

    async def touch_telemetry(self, when: datetime | None = None) -> None:
        async with self._lock:
            self.last_telemetry_at = when or _utcnow()

    def snapshot_integrations(self) -> list[Integration]:
        return [deepcopy(i) for i in self.integrations.values()]


# Singleton store for the process
store = ObservabilityStore()
