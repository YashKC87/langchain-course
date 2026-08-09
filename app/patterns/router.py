"""Pattern 2 — Router Pattern for 100 endpoint health requests."""

from __future__ import annotations

from typing import Any

import numpy as np

from app.config import Settings, get_settings
from app.models.factory import build_frontier_client, build_slm_client
from app.models.model_interface import LanguageModel, ModelRole, ModelType
from app.models.schemas import PatternResult, SegmentResult
from app.observability.cost_calculator import CostCalculator
from app.observability.langsmith_tracer import LangSmithTracer
from app.patterns.common import build_architect_decision, segment_from_generation, summarize_token_bars
from app.services.baseline_estimator import BaselineEstimator
from app.services.telemetry import TelemetryService

PATTERN_NAME = "Router Pattern"
PATTERN_ID = "router"
SCENARIO = "Route 100 incoming endpoint health requests between SLM and Frontier."

ROUTINE_TYPES = {
    "cpu_status",
    "disk_status",
    "compliance_status",
    "teams_crash_count",
    "vpn_disconnect_count",
    "simple_health_classification",
}
COMPLEX_TYPES = {
    "cross_domain_rca",
    "novel_problem",
    "ambiguous_telemetry",
    "complex_ux_degradation",
}


class RouterPattern:
    def __init__(
        self,
        settings: Settings | None = None,
        slm: LanguageModel | None = None,
        frontier: LanguageModel | None = None,
        telemetry: TelemetryService | None = None,
        tracer: LangSmithTracer | None = None,
    ):
        self.settings = settings or get_settings()
        self.slm = slm or build_slm_client(self.settings)
        self.frontier = frontier or build_frontier_client(self.settings)
        self.telemetry = telemetry or TelemetryService()
        self.tracer = tracer or LangSmithTracer(self.settings)
        self.costs = CostCalculator(self.settings)
        self.baseline = BaselineEstimator(self.settings)

    def _build_requests(self, n: int = 100) -> list[dict[str, Any]]:
        rng = np.random.default_rng(42)
        devices = self.telemetry.list_devices()["device_id"].tolist()
        routine = list(ROUTINE_TYPES)
        complex_types = list(COMPLEX_TYPES)
        requests = []
        for i in range(n):
            # ~85 routine / ~15 complex
            is_complex = i % 7 == 0  # 15 of 100 when i=0,7,...,98
            req_type = complex_types[i % len(complex_types)] if is_complex else routine[i % len(routine)]
            device_id = devices[i % len(devices)]
            requests.append(
                {
                    "request_id": f"REQ-{i+1:03d}",
                    "device_id": device_id,
                    "request_type": req_type,
                    "complexity": "complex" if is_complex else "routine",
                    "text": (
                        f"{req_type.replace('_', ' ')} for {device_id}. "
                        + (
                            "Cross-domain ambiguous user-experience degradation requiring RCA."
                            if is_complex
                            else "Simple status check."
                        )
                    ),
                }
            )
        # Force exact counts: 85 routine, 15 complex
        # Adjust if needed
        complex_idx = [i for i, r in enumerate(requests) if r["complexity"] == "complex"]
        routine_idx = [i for i, r in enumerate(requests) if r["complexity"] == "routine"]
        while len(complex_idx) > 15:
            idx = complex_idx.pop()
            requests[idx]["complexity"] = "routine"
            requests[idx]["request_type"] = routine[idx % len(routine)]
            requests[idx]["text"] = f"{requests[idx]['request_type'].replace('_', ' ')} for {requests[idx]['device_id']}. Simple status check."
        while len(complex_idx) < 15 and routine_idx:
            idx = routine_idx.pop()
            requests[idx]["complexity"] = "complex"
            requests[idx]["request_type"] = complex_types[idx % len(complex_types)]
            requests[idx]["text"] = (
                f"{requests[idx]['request_type'].replace('_', ' ')} for {requests[idx]['device_id']}. "
                "Cross-domain ambiguous user-experience degradation requiring RCA."
            )
            complex_idx.append(idx)
        _ = rng  # deterministic seed reserved for future jitter
        return requests

    def run(self, n: int = 100) -> PatternResult:
        requests = self._build_requests(n)
        with self.tracer.trace(
            pattern=PATTERN_NAME,
            scenario=SCENARIO,
            metadata={"pattern_id": PATTERN_ID, "request_count": n},
        ) as ctx:
            # Router non-LLM segment
            router_segment = SegmentResult(
                segment="Router",
                task="route_requests",
                model_name="rules-router",
                model_type=ModelType.NON_LLM,
                model_role=ModelRole.ROUTER,
                provider="local",
                tokens=0,
                latency_ms=12.0,
                confidence=1.0,
                why="Deterministic routing by request complexity class.",
                content="Routed routine requests to SLM and complex requests to Frontier.",
                provenance="SIMULATED",
                decision="NON_LLM",
                decision_why="Routing logic does not require an LLM.",
            )
            self.tracer.record(
                ctx,
                segment="Router",
                model_name="rules-router",
                model_type=ModelType.NON_LLM,
                model_role=ModelRole.ROUTER,
                provider="local",
                input_tokens=0,
                output_tokens=0,
                latency_ms=12.0,
                confidence=1.0,
                metadata={"slm_target": "routine", "frontier_target": "complex"},
            )

            per_request: list[dict[str, Any]] = []
            llm_segments: list[SegmentResult] = []
            examples: dict[str, Any] = {"routine": None, "complex": None}

            for req in requests:
                if req["complexity"] == "routine":
                    result = self.slm.structured_generate(
                        prompt=req["text"],
                        schema={"request_type": "string", "severity": "string", "action": "string"},
                        metadata={
                            "task": "health_classification",
                            "device_id": req["device_id"],
                            "request_type": req["request_type"],
                            "severity": "healthy",
                            "complexity": "routine",
                        },
                    )
                    selected = "SLM"
                    why = "Routine status/classification can safely run on SLM."
                    role = ModelRole.CLASSIFIER
                    task = "health_classification"
                else:
                    result = self.frontier.generate(
                        prompt=req["text"],
                        metadata={
                            "task": "complex_rca",
                            "device_id": req["device_id"],
                            "complexity": "complex",
                        },
                    )
                    selected = "FRONTIER"
                    why = "Ambiguous/cross-domain work needs Frontier reasoning quality."
                    role = ModelRole.SYNTHESIZER
                    task = "complex_rca"

                seg = segment_from_generation(
                    segment=req["request_id"],
                    task=task,
                    role=role,
                    why=why,
                    result=result,
                    costs=self.costs,
                    baseline=self.baseline,
                    decision=selected,
                    decision_why=why,
                )
                llm_segments.append(seg)
                item = {
                    "request_id": req["request_id"],
                    "device_id": req["device_id"],
                    "request_type": req["request_type"],
                    "complexity": req["complexity"],
                    "selected_model": selected,
                    "tokens": seg.tokens,
                    "latency_ms": seg.latency_ms,
                    "confidence": seg.confidence,
                    "provenance": seg.provenance,
                    "alternative": seg.alternative.model_dump() if seg.alternative else None,
                }
                per_request.append(item)
                if examples["routine"] is None and selected == "SLM":
                    examples["routine"] = item
                if examples["complex"] is None and selected == "FRONTIER":
                    examples["complex"] = item

                # Trace every request, UI aggregates by default
                self.tracer.record(
                    ctx,
                    segment=f"{req['request_id']} → {selected}",
                    model_name=result.model_name,
                    model_type=result.model_type,
                    model_role=role,
                    provider=result.provider,
                    input_tokens=result.usage.input_tokens,
                    output_tokens=result.usage.output_tokens,
                    latency_ms=result.usage.latency_ms,
                    confidence=result.confidence,
                    is_actual_usage=result.usage.is_actual_usage,
                    metadata={"request_type": req["request_type"], "complexity": req["complexity"]},
                )

            all_segments = [router_segment] + llm_segments
            decision = build_architect_decision(
                pattern=PATTERN_NAME,
                scenario=SCENARIO,
                segments=llm_segments,  # exclude NON_LLM from token math
                baseline_tasks=["routine_request"] * 85 + ["complex_rca"] * 15,
                why="We prevented routine requests from consuming Frontier capacity.",
                recommendation=(
                    "Route high-volume routine endpoint health checks to SLM and reserve "
                    "Frontier for complex/ambiguous RCA."
                ),
                baseline=self.baseline,
                costs=self.costs,
                notes=[
                    "Primary benefit: High-volume inference efficiency",
                    "ESTIMATED ALL-FRONTIER BASELINE uses benchmarks; no extra Frontier calls were made for comparison.",
                ],
            )

            slm_reqs = [r for r in per_request if r["selected_model"] == "SLM"]
            frontier_reqs = [r for r in per_request if r["selected_model"] == "FRONTIER"]
            latencies = sorted(r["latency_ms"] for r in per_request)
            p50 = latencies[len(latencies) // 2]
            p95 = latencies[int(0.95 * (len(latencies) - 1))]
            comparisons = summarize_token_bars(decision)
            comparisons.update(
                {
                    "slm_requests": len(slm_reqs),
                    "frontier_requests": len(frontier_reqs),
                    "avg_slm_tokens": round(sum(r["tokens"] for r in slm_reqs) / max(1, len(slm_reqs)), 1),
                    "avg_frontier_tokens": round(
                        sum(r["tokens"] for r in frontier_reqs) / max(1, len(frontier_reqs)), 1
                    ),
                    "p50_latency_ms": p50,
                    "p95_latency_ms": p95,
                    "frontier_calls_avoided": len(slm_reqs),
                    "frontier_avoidance_rate": round(100.0 * len(slm_reqs) / max(1, len(per_request)), 1),
                    "examples": examples,
                    "requests_preview": per_request[:10],
                    "requests_all_count": len(per_request),
                }
            )
            return PatternResult(
                pattern=PATTERN_NAME,
                pattern_id=PATTERN_ID,
                scenario=SCENARIO,
                segments=all_segments,
                summary=(
                    f"Routed {len(slm_reqs)} routine requests to SLM and "
                    f"{len(frontier_reqs)} complex requests to Frontier."
                ),
                findings={
                    "primary_benefit": "High-volume inference efficiency",
                    "routing_rule": "routine→SLM, complex→Frontier",
                },
                architect_decision=decision,
                trace_id=ctx.trace_id,
                langsmith_url=ctx.langsmith_url,
                comparisons=comparisons,
                metadata={"per_request": per_request},
            )
