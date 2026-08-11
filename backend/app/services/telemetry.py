"""OpenTelemetry / provider telemetry ingestion pipeline.

Provider → Validation → Normalization → Correlation → Aggregation → Store

Never generates synthetic telemetry when payloads are empty.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from app.models.domain import (
    ActivityEvent,
    Agent,
    AgentHealth,
    IntegrationStatus,
)
from app.services.health import health_service
from app.services.normalization import aggregate_execution, normalize_span
from app.services.optimization import optimization_service
from app.storage.store import store


class TelemetryIngestionService:
    async def ingest_otlp_spans(
        self,
        payload: dict[str, Any],
        *,
        provider: str = "otel",
        integration_id: str | None = "otel",
    ) -> dict[str, Any]:
        """Accept OTLP JSON-like or simplified span batches.

        Supported shapes:
        - { "resourceSpans": [...] }  (OTLP JSON)
        - { "spans": [...] }          (simplified)
        """
        if integration_id:
            integ = store.integrations.get(integration_id)
            if integ and not integ.enabled:
                return {
                    "accepted": False,
                    "reason": "Integration Disabled",
                    "message": f"Integration '{integration_id}' is disabled. Historical telemetry retained; new ingestion stopped.",
                    "spans_ingested": 0,
                    "executions_updated": 0,
                    "agents_registered": 0,
                }

        raw_spans = self._extract_spans(payload)
        if not raw_spans:
            return {
                "accepted": True,
                "spans_ingested": 0,
                "executions_updated": 0,
                "agents_registered": 0,
                "message": "No spans in payload. No telemetry recorded.",
            }

        normalized = [normalize_span(s, provider=provider) for s in raw_spans]
        executions_touched: set[str] = set()
        agents_registered = 0

        for span in normalized:
            store.spans[span.span_id] = span
            store.spans_by_trace.setdefault(span.trace_id, []).append(span.span_id)
            if span.execution_id:
                store.spans_by_execution.setdefault(span.execution_id, []).append(span.span_id)
                executions_touched.add(span.execution_id)

            agent_id = span.attributes.get("canonical.agent.id")
            agent_name = span.attributes.get("canonical.agent.name")
            if agent_id:
                created = await self._upsert_agent_from_span(span, integration_id)
                if created:
                    agents_registered += 1
            elif agent_name:
                # Use name-derived id only when provider gave a name but no id
                span.attributes["canonical.agent.id"] = f"name:{agent_name}"
                created = await self._upsert_agent_from_span(span, integration_id)
                if created:
                    agents_registered += 1

        for exec_id in executions_touched:
            span_ids = store.spans_by_execution.get(exec_id, [])
            spans = [store.spans[sid] for sid in span_ids if sid in store.spans]
            existing = store.executions.get(exec_id)
            execution = aggregate_execution(spans, existing)
            store.executions[exec_id] = execution

            await store.record_activity(
                ActivityEvent(
                    id=str(uuid.uuid4()),
                    timestamp=datetime.now(timezone.utc),
                    event_type="execution_updated",
                    message=f"Execution {exec_id} updated ({execution.status.value})",
                    agent_id=execution.agent_id,
                    agent_name=execution.agent_name,
                    severity="error" if execution.status.value == "failed" else "info",
                    execution_id=exec_id,
                    trace_id=execution.trace_id,
                )
            )

        now = datetime.now(timezone.utc)
        await store.touch_telemetry(now)

        if integration_id and integration_id in store.integrations:
            integ = store.integrations[integration_id]
            integ.last_telemetry_at = now
            integ.status = IntegrationStatus.TELEMETRY_ACTIVE
            integ.agents_discovered = sum(
                1 for a in store.agents.values() if a.integration_id == integration_id
            ) or None
            store.integrations[integration_id] = integ

        # Recompute derived views from live data only
        await health_service.recompute()
        await optimization_service.recompute()

        return {
            "accepted": True,
            "spans_ingested": len(normalized),
            "executions_updated": len(executions_touched),
            "agents_registered": agents_registered,
            "message": "Telemetry ingested and normalized.",
        }

    def _extract_spans(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        if not payload:
            return []
        if "spans" in payload and isinstance(payload["spans"], list):
            return [s for s in payload["spans"] if isinstance(s, dict)]

        spans: list[dict[str, Any]] = []
        for rs in payload.get("resourceSpans") or payload.get("resource_spans") or []:
            resource_attrs = self._otlp_attrs_to_dict(
                (rs.get("resource") or {}).get("attributes") or []
            )
            for ss in rs.get("scopeSpans") or rs.get("scope_spans") or []:
                for span in ss.get("spans") or []:
                    if not isinstance(span, dict):
                        continue
                    attrs = self._otlp_attrs_to_dict(span.get("attributes") or [])
                    attrs.update({f"resource.{k}": v for k, v in resource_attrs.items()})
                    spans.append(
                        {
                            "name": span.get("name"),
                            "span_id": self._bytes_id(span.get("spanId") or span.get("span_id")),
                            "trace_id": self._bytes_id(span.get("traceId") or span.get("trace_id")),
                            "parent_span_id": self._bytes_id(
                                span.get("parentSpanId") or span.get("parent_span_id")
                            ),
                            "start_time": span.get("startTimeUnixNano")
                            or span.get("start_time_unix_nano"),
                            "end_time": span.get("endTimeUnixNano") or span.get("end_time_unix_nano"),
                            "status": span.get("status"),
                            "attributes": attrs,
                        }
                    )
        return spans

    @staticmethod
    def _otlp_attrs_to_dict(attrs: list[dict[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for item in attrs:
            key = item.get("key")
            if not key:
                continue
            val = item.get("value") or {}
            for vk in (
                "stringValue",
                "string_value",
                "intValue",
                "int_value",
                "doubleValue",
                "double_value",
                "boolValue",
                "bool_value",
            ):
                if vk in val:
                    result[key] = val[vk]
                    break
        return result

    @staticmethod
    def _bytes_id(value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            return value
        return str(value)

    async def _upsert_agent_from_span(self, span, integration_id: str | None) -> bool:
        agent_id = str(span.attributes.get("canonical.agent.id"))
        created = agent_id not in store.agents
        existing = store.agents.get(agent_id)
        now = datetime.now(timezone.utc)
        agent = Agent(
            id=agent_id,
            name=str(span.attributes.get("canonical.agent.name") or (existing.name if existing else agent_id)),
            version=span.attributes.get("agent.version") or (existing.version if existing else None),
            cloud=span.attributes.get("canonical.cloud") or (existing.cloud if existing else None),
            platform=span.attributes.get("platform.name") or (existing.platform if existing else None),
            framework=span.attributes.get("canonical.framework") or (existing.framework if existing else None),
            environment=span.attributes.get("environment") or (existing.environment if existing else None),
            region=span.attributes.get("cloud.region") or (existing.region if existing else None),
            business_unit=span.attributes.get("business.unit") or (existing.business_unit if existing else None),
            application=span.attributes.get("application.id") or (existing.application if existing else None),
            primary_model=span.attributes.get("canonical.model") or (existing.primary_model if existing else None),
            telemetry_source=span.provider_raw.get("provider") if span.provider_raw else None,
            integration_id=integration_id or (existing.integration_id if existing else None),
            health=existing.health if existing else AgentHealth.UNKNOWN,
            first_seen_at=existing.first_seen_at if existing else now,
            last_execution_at=now,
            last_telemetry_at=now,
        )
        store.agents[agent_id] = agent
        if created:
            await store.record_activity(
                ActivityEvent(
                    id=str(uuid.uuid4()),
                    timestamp=now,
                    event_type="agent_discovered",
                    message=f"Agent discovered: {agent.name}",
                    agent_id=agent.id,
                    agent_name=agent.name,
                    severity="info",
                )
            )
        return created


telemetry_service = TelemetryIngestionService()
