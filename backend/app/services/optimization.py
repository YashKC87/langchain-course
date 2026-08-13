"""Telemetry-backed optimization recommendations.

Never generates findings without evidence from live executions.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import datetime, timezone

from app.models.domain import (
    AttentionSeverity,
    OptimizationFinding,
    WorkflowNodeType,
)
from app.storage.store import store


class OptimizationService:
    async def recompute(self) -> None:
        findings: list[OptimizationFinding] = []
        now = datetime.now(timezone.utc)
        app = store.settings

        # Group executions by agent
        by_agent: dict[str, list] = defaultdict(list)
        for e in store.executions.values():
            if e.agent_id:
                by_agent[e.agent_id].append(e)

        for agent_id, execs in by_agent.items():
            if len(execs) < 3:
                # Not enough history for baselines
                continue

            step_vals = [e.agent_steps for e in execs if e.agent_steps is not None]
            if len(step_vals) >= 3:
                baseline = sum(step_vals) / len(step_vals)
                latest = execs[-1]
                if (
                    latest.agent_steps is not None
                    and baseline >= 1
                    and latest.agent_steps >= max(app.runaway_steps_warning, baseline * 1.8)
                ):
                    agent = store.agents.get(agent_id)
                    findings.append(
                        OptimizationFinding(
                            id=str(uuid.uuid4()),
                            observation=(
                                f"Agent averages {latest.agent_steps} steps while its "
                                f"normal baseline is {baseline:.1f}."
                            ),
                            evidence=f"Based on {len(step_vals)} executions with step telemetry.",
                            affected_agent=agent.name if agent else agent_id,
                            affected_component="agent_steps",
                            recommendation=(
                                "Inspect planner/worker loops and tool retry policies. "
                                "Review the related trace for circular step patterns."
                            ),
                            confidence=min(0.95, 0.5 + len(step_vals) * 0.05),
                            severity=AttentionSeverity.WARNING
                            if latest.agent_steps < app.runaway_steps_critical
                            else AttentionSeverity.CRITICAL,
                            related_trace=latest.trace_id,
                            detected_at=now,
                        )
                    )

            # Retry patterns
            retry_execs = [e for e in execs if e.retry_count and e.retry_count > 0]
            if retry_execs and len(retry_execs) / len(execs) >= 0.3:
                agent = store.agents.get(agent_id)
                findings.append(
                    OptimizationFinding(
                        id=str(uuid.uuid4()),
                        observation="The same model or tool request is retried multiple times.",
                        evidence=(
                            f"{len(retry_execs)}/{len(execs)} executions include retries "
                            f"(threshold {app.runaway_retry_threshold})."
                        ),
                        affected_agent=agent.name if agent else agent_id,
                        affected_component="retries",
                        recommendation="Investigate transient vs systematic failures on model/tool calls.",
                        confidence=0.7,
                        severity=AttentionSeverity.WARNING,
                        related_trace=retry_execs[-1].trace_id,
                        detected_at=now,
                    )
                )

            # Fallback patterns
            fb_execs = [e for e in execs if e.fallback_count and e.fallback_count > 0]
            if fb_execs and len(fb_execs) / len(execs) >= 0.25:
                agent = store.agents.get(agent_id)
                findings.append(
                    OptimizationFinding(
                        id=str(uuid.uuid4()),
                        observation="High SLM-to-Frontier fallback rate detected."
                        if any(
                            e.model_name and "frontier" in (e.model_name or "").lower()
                            for e in fb_execs
                        )
                        else "Frontier / fallback model is frequently invoked.",
                        evidence=f"{len(fb_execs)}/{len(execs)} executions triggered fallbacks.",
                        affected_agent=agent.name if agent else agent_id,
                        affected_component="model_routing",
                        recommendation=(
                            "Review routing criteria for simple deterministic requests "
                            "before escalating to frontier models."
                        ),
                        confidence=0.65,
                        severity=AttentionSeverity.WARNING,
                        related_trace=fb_execs[-1].trace_id,
                        detected_at=now,
                    )
                )

            # MCP latency baseline
            mcp_lats = [e.mcp_latency_ms for e in execs if e.mcp_latency_ms is not None]
            if len(mcp_lats) >= 5:
                baseline = sum(mcp_lats[:-1]) / (len(mcp_lats) - 1)
                latest_lat = mcp_lats[-1]
                if baseline > 0 and latest_lat > baseline * 2:
                    agent = store.agents.get(agent_id)
                    findings.append(
                        OptimizationFinding(
                            id=str(uuid.uuid4()),
                            observation=(
                                "MCP response latency has increased substantially "
                                "relative to its recent baseline."
                            ),
                            evidence=f"Latest {latest_lat:.0f} ms vs baseline {baseline:.0f} ms.",
                            affected_agent=agent.name if agent else agent_id,
                            affected_component="mcp",
                            recommendation="Check MCP server health and network path.",
                            confidence=0.75,
                            severity=AttentionSeverity.WARNING,
                            related_trace=execs[-1].trace_id,
                            detected_at=now,
                        )
                    )

        # Repeated tool calls within same execution (from spans)
        for exec_id, span_ids in store.spans_by_execution.items():
            spans = [store.spans[s] for s in span_ids if s in store.spans]
            tool_spans = [s for s in spans if s.node_type == WorkflowNodeType.TOOL]
            if len(tool_spans) < 4:
                continue
            names = [s.name for s in tool_spans]
            repeats = len(names) - len(set(names))
            if repeats / len(names) >= 0.4:
                e = store.executions.get(exec_id)
                findings.append(
                    OptimizationFinding(
                        id=str(uuid.uuid4()),
                        observation="Repeated tool calls detected within the same execution.",
                        evidence=f"{repeats}/{len(names)} tool calls are repeats in {exec_id}.",
                        affected_agent=e.agent_name if e else None,
                        affected_component="tools",
                        recommendation="Add idempotency / result caching for repeated tool invocations.",
                        confidence=0.8,
                        severity=AttentionSeverity.WARNING,
                        related_trace=e.trace_id if e else None,
                        detected_at=now,
                    )
                )

            # A2A circular handoffs
            a2a = [s for s in spans if s.node_type == WorkflowNodeType.A2A]
            if len(a2a) >= 4:
                pairs = [
                    (
                        s.attributes.get("canonical.a2a.source"),
                        s.attributes.get("canonical.a2a.destination"),
                    )
                    for s in a2a
                ]
                if len(pairs) != len(set(pairs)) or len(a2a) >= app.runaway_steps_warning:
                    e = store.executions.get(exec_id)
                    findings.append(
                        OptimizationFinding(
                            id=str(uuid.uuid4()),
                            observation="Repeated routing between agents detected.",
                            evidence=f"{len(a2a)} A2A handoffs in execution {exec_id}.",
                            affected_agent=e.agent_name if e else None,
                            affected_component="a2a",
                            recommendation="Inspect supervisor-worker termination conditions.",
                            confidence=0.7,
                            severity=AttentionSeverity.WARNING,
                            related_trace=e.trace_id if e else None,
                            detected_at=now,
                        )
                    )

        store.optimizations = findings

    def efficiency_score(self, agent_id: str) -> dict | None:
        """Optional non-financial efficiency score with transparent calculation."""
        execs = [e for e in store.executions.values() if e.agent_id == agent_id]
        if not execs:
            return None

        weights = store.settings.efficiency_weights
        factors: dict[str, float | None] = {}

        # Success rate
        known = [e for e in execs if e.status.value in ("success", "failed")]
        if known:
            factors["success_rate"] = sum(1 for e in known if e.status.value == "success") / len(known)
        else:
            factors["success_rate"] = None

        # Step efficiency: closer to 1–7 is better
        steps = [e.agent_steps for e in execs if e.agent_steps is not None]
        if steps:
            avg = sum(steps) / len(steps)
            factors["step_count"] = max(0.0, min(1.0, 1.0 - (max(0, avg - 7) / 20)))
        else:
            factors["step_count"] = None

        # Retry / fallback (lower better)
        retries = [e.retry_count or 0 for e in execs if e.retry_count is not None]
        factors["retry_rate"] = (
            max(0.0, 1.0 - (sum(retries) / max(1, len(retries)) / 5)) if retries else None
        )
        fallbacks = [e.fallback_count or 0 for e in execs if e.fallback_count is not None]
        factors["fallback_rate"] = (
            max(0.0, 1.0 - (sum(fallbacks) / max(1, len(fallbacks)) / 3)) if fallbacks else None
        )

        # Latency
        lats = [e.execution_duration_ms for e in execs if e.execution_duration_ms is not None]
        if lats:
            avg_lat = sum(lats) / len(lats)
            factors["latency"] = max(0.0, min(1.0, 1.0 - (avg_lat / 30000)))
        else:
            factors["latency"] = None

        # Token efficiency — without a baseline, mark unavailable
        factors["token_efficiency"] = None
        factors["tool_efficiency"] = None
        factors["mcp_efficiency"] = None
        factors["rag_efficiency"] = None
        factors["a2a_efficiency"] = None
        factors["error_rate"] = factors["success_rate"]  # inverse already in success

        usable = {k: v for k, v in factors.items() if v is not None and k in weights}
        if not usable:
            return {
                "score": None,
                "classification": None,
                "message": "Baseline not yet established — insufficient telemetry factors.",
                "factors": factors,
                "weights": weights,
            }

        total_w = sum(weights[k] for k in usable)
        score = 100 * sum(usable[k] * weights[k] for k in usable) / total_w
        if score >= 90:
            classification = "Excellent"
        elif score >= 75:
            classification = "Good"
        elif score >= 60:
            classification = "Needs Optimization"
        else:
            classification = "Inefficient"

        return {
            "score": round(score, 1),
            "classification": classification,
            "factors": factors,
            "weights_used": {k: weights[k] for k in usable},
            "weights_all": weights,
            "message": "Score derived only from available live telemetry factors.",
        }


optimization_service = OptimizationService()
