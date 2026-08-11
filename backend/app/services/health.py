"""Health derivation from live telemetry only.

An agent is never declared healthy merely because it exists in the registry.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.core.config import get_settings
from app.models.domain import (
    AgentHealth,
    AttentionItem,
    AttentionSeverity,
    ExecutionStatus,
)
from app.storage.store import store


class HealthService:
    async def recompute(self) -> None:
        settings = get_settings()
        app = store.settings
        now = datetime.now(timezone.utc)
        attention: list[AttentionItem] = []

        for agent in list(store.agents.values()):
            agent_execs = [e for e in store.executions.values() if e.agent_id == agent.id]
            last_tel = agent.last_telemetry_at
            health = AgentHealth.UNKNOWN
            reasons: list[str] = []

            if last_tel is None:
                health = AgentHealth.UNKNOWN
                reasons.append("No telemetry received for this agent.")
            else:
                age = (now - last_tel).total_seconds()
                if age > settings.telemetry_offline_seconds:
                    health = AgentHealth.OFFLINE
                    reasons.append(f"Telemetry missing for {int(age)}s.")
                    attention.append(
                        AttentionItem(
                            id=str(uuid.uuid4()),
                            condition="Agent Offline",
                            severity=AttentionSeverity.CRITICAL,
                            message=f"{agent.name} appears offline — no recent telemetry.",
                            agent_id=agent.id,
                            agent_name=agent.name,
                            evidence=f"Last telemetry at {last_tel.isoformat()}",
                            detected_at=now,
                        )
                    )
                elif age > settings.telemetry_stale_seconds:
                    health = AgentHealth.WARNING
                    reasons.append("Telemetry delayed.")
                    attention.append(
                        AttentionItem(
                            id=str(uuid.uuid4()),
                            condition="Telemetry Delayed",
                            severity=AttentionSeverity.WARNING,
                            message=f"{agent.name} telemetry is delayed.",
                            agent_id=agent.id,
                            agent_name=agent.name,
                            evidence=f"Last telemetry at {last_tel.isoformat()}",
                            detected_at=now,
                        )
                    )

            if agent_execs:
                recent = sorted(
                    agent_execs,
                    key=lambda e: e.start_time or e.timestamp or now,
                    reverse=True,
                )[:20]
                failures = [e for e in recent if e.status == ExecutionStatus.FAILED]
                running = [e for e in recent if e.status == ExecutionStatus.RUNNING]
                high_steps = [
                    e
                    for e in recent
                    if e.agent_steps is not None and e.agent_steps >= app.runaway_steps_critical
                ]
                high_retry = [
                    e
                    for e in recent
                    if e.retry_count is not None and e.retry_count >= app.runaway_retry_threshold
                ]
                high_fb = [
                    e
                    for e in recent
                    if e.fallback_count is not None and e.fallback_count >= app.runaway_fallback_threshold
                ]
                high_lat = [
                    e
                    for e in recent
                    if e.execution_duration_ms is not None
                    and e.execution_duration_ms >= app.latency_critical_ms
                ]

                if high_steps:
                    health = AgentHealth.CRITICAL
                    attention.append(
                        AttentionItem(
                            id=str(uuid.uuid4()),
                            condition="Runaway Loop",
                            severity=AttentionSeverity.CRITICAL,
                            message=f"{agent.name} exceeded critical step threshold.",
                            agent_id=agent.id,
                            agent_name=agent.name,
                            evidence=f"Execution {high_steps[0].execution_id} had {high_steps[0].agent_steps} steps",
                            related_trace=high_steps[0].trace_id,
                            detected_at=now,
                        )
                    )
                if high_retry:
                    if health not in (AgentHealth.CRITICAL, AgentHealth.OFFLINE):
                        health = AgentHealth.WARNING
                    attention.append(
                        AttentionItem(
                            id=str(uuid.uuid4()),
                            condition="Repeated Retry",
                            severity=AttentionSeverity.WARNING,
                            message=f"{agent.name} shows excessive retries.",
                            agent_id=agent.id,
                            agent_name=agent.name,
                            evidence=f"Retry count {high_retry[0].retry_count} on {high_retry[0].execution_id}",
                            related_trace=high_retry[0].trace_id,
                            detected_at=now,
                        )
                    )
                if high_fb:
                    if health not in (AgentHealth.CRITICAL, AgentHealth.OFFLINE):
                        health = AgentHealth.WARNING
                    attention.append(
                        AttentionItem(
                            id=str(uuid.uuid4()),
                            condition="Repeated Fallback",
                            severity=AttentionSeverity.WARNING,
                            message=f"{agent.name} shows excessive fallbacks.",
                            agent_id=agent.id,
                            agent_name=agent.name,
                            evidence=f"Fallback count {high_fb[0].fallback_count}",
                            related_trace=high_fb[0].trace_id,
                            detected_at=now,
                        )
                    )
                if high_lat:
                    if health not in (AgentHealth.CRITICAL, AgentHealth.OFFLINE):
                        health = AgentHealth.WARNING
                    attention.append(
                        AttentionItem(
                            id=str(uuid.uuid4()),
                            condition="High Latency",
                            severity=AttentionSeverity.WARNING,
                            message=f"{agent.name} executions exceed latency threshold.",
                            agent_id=agent.id,
                            agent_name=agent.name,
                            evidence=f"{high_lat[0].execution_duration_ms} ms on {high_lat[0].execution_id}",
                            related_trace=high_lat[0].trace_id,
                            detected_at=now,
                        )
                    )
                if failures and len(failures) >= max(1, len(recent) // 3):
                    health = AgentHealth.CRITICAL
                    attention.append(
                        AttentionItem(
                            id=str(uuid.uuid4()),
                            condition="Execution Failure",
                            severity=AttentionSeverity.CRITICAL,
                            message=f"{agent.name} has elevated failure rate.",
                            agent_id=agent.id,
                            agent_name=agent.name,
                            evidence=f"{len(failures)}/{len(recent)} recent executions failed",
                            related_trace=failures[0].trace_id,
                            detected_at=now,
                        )
                    )
                for e in running:
                    if e.start_time:
                        age_ms = (now - e.start_time).total_seconds() * 1000
                        if age_ms >= app.runaway_duration_ms_threshold:
                            health = AgentHealth.CRITICAL
                            attention.append(
                                AttentionItem(
                                    id=str(uuid.uuid4()),
                                    condition="Execution Stuck",
                                    severity=AttentionSeverity.CRITICAL,
                                    message=f"{agent.name} has a long-running execution.",
                                    agent_id=agent.id,
                                    agent_name=agent.name,
                                    evidence=f"Execution {e.execution_id} running for {int(age_ms)} ms",
                                    related_trace=e.trace_id,
                                    detected_at=now,
                                )
                            )

                if health == AgentHealth.UNKNOWN and last_tel and (now - last_tel).total_seconds() <= settings.telemetry_stale_seconds:
                    # Only healthy when recent telemetry AND no failure signals
                    if not failures and not high_steps and not high_retry:
                        health = AgentHealth.HEALTHY

            agent.health = health
            store.agents[agent.id] = agent

        # Integration failures
        for integ in store.integrations.values():
            if integ.enabled and integ.status.value == "connection_failed":
                attention.append(
                    AttentionItem(
                        id=str(uuid.uuid4()),
                        condition="Integration Failure",
                        severity=AttentionSeverity.CRITICAL,
                        message=f"{integ.name} connection failed.",
                        component=integ.id,
                        evidence=integ.error_message or "Connection failed",
                        detected_at=now,
                    )
                )
            if integ.enabled and integ.error_message and "permission" in (integ.error_message or "").lower():
                attention.append(
                    AttentionItem(
                        id=str(uuid.uuid4()),
                        condition="Permission Failure",
                        severity=AttentionSeverity.CRITICAL,
                        message=f"{integ.name}: permission issue.",
                        component=integ.id,
                        evidence=integ.error_message,
                        detected_at=now,
                    )
                )

        store.attention = attention


health_service = HealthService()
