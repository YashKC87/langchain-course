"""Pattern 5 — Designing for Fallback when Frontier is unavailable."""

from __future__ import annotations

import time
from typing import Any

from app.config import Settings, get_settings
from app.models.demo_model import DemoFrontierClient, FrontierUnavailableError
from app.models.factory import build_frontier_client, build_slm_client
from app.models.frontier_client import AzureFrontierClient
from app.models.model_interface import LanguageModel, ModelRole, ModelType
from app.models.schemas import PatternResult, SegmentResult
from app.observability.cost_calculator import CostCalculator
from app.observability.langsmith_tracer import LangSmithTracer
from app.patterns.common import (
    build_architect_decision,
    segment_from_generation,
    summarize_token_bars,
)
from app.services.baseline_estimator import BaselineEstimator
from app.services.telemetry import TelemetryService

PATTERN_NAME = "Designing for Fallback"
PATTERN_ID = "fallback"
SCENARIO = (
    "A critical endpoint requires advanced RCA but the Frontier service becomes unavailable."
)
DEVICE_ID = "LAPTOP-1204"

FAILURE_MODES = {
    "http_503",
    "timeout",
    "rate_limit",
    "auth_error",
    "offline",
    "cost_guard",
}


class FallbackPattern:
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

    def run(self, failure_type: str = "http_503") -> PatternResult:
        if failure_type not in FAILURE_MODES:
            failure_type = "http_503"
        device_block = self.telemetry.device_prompt_block(DEVICE_ID)

        # Enable simulated failure on supporting clients
        if isinstance(self.frontier, (DemoFrontierClient, AzureFrontierClient)):
            self.frontier.set_failure_mode(failure_type)

        with self.tracer.trace(
            pattern=PATTERN_NAME,
            scenario=SCENARIO,
            device_id=DEVICE_ID,
            metadata={"pattern_id": PATTERN_ID, "failure_type": failure_type},
        ) as ctx:
            started = time.perf_counter()
            failure_meta: dict[str, Any] = {
                "failure_type": failure_type,
                "failed": False,
            }
            frontier_tokens = 0
            frontier_latency = 0.0
            frontier_attempt_text = ""
            try:
                _ = self.frontier.generate(
                    prompt=(
                        "Perform advanced critical RCA.\n"
                        f"{device_block}"
                    ),
                    metadata={"task": "complex_rca", "device_id": DEVICE_ID},
                )
                # If no failure raised (misconfigured), force failure semantics in demo
                raise FrontierUnavailableError(
                    "Forced fallback for demonstration",
                    code=503,
                    failure_type=failure_type,
                )
            except FrontierUnavailableError as exc:
                time_to_failure = round((time.perf_counter() - started) * 1000, 1)
                failure_meta.update(
                    {
                        "failed": True,
                        "failure_type": exc.failure_type,
                        "code": exc.code,
                        "message": str(exc),
                        "time_to_failure_ms": time_to_failure,
                        "partial_tokens": 0,
                    }
                )
                frontier_latency = time_to_failure

            frontier_attempt = SegmentResult(
                segment="FRONTIER Attempt",
                task="complex_rca",
                model_name=getattr(self.frontier, "model_name", "frontier"),
                model_type=ModelType.FRONTIER,
                model_role=ModelRole.SYNTHESIZER,
                provider=getattr(self.frontier, "provider", "unknown"),
                tokens=frontier_tokens,
                latency_ms=frontier_latency,
                confidence=0.0,
                why="Primary advanced reasoning path for critical RCA.",
                content=frontier_attempt_text or f"FAILED: {failure_meta.get('message')}",
                structured=failure_meta,
                provenance="SIMULATED",
                decision="FAILED",
                decision_why="Frontier service unavailable.",
            )
            detector = SegmentResult(
                segment="Failure Detector",
                task="detect_failure",
                model_name="failure-detector",
                model_type=ModelType.NON_LLM,
                model_role=ModelRole.EVALUATOR,
                provider="local",
                tokens=0,
                latency_ms=4.0,
                confidence=1.0,
                why="Detect Frontier transport/service failures.",
                content=str(failure_meta),
                structured=failure_meta,
                provenance="SIMULATED",
            )
            fallback_decision = SegmentResult(
                segment="Fallback Decision",
                task="fallback_route",
                model_name="fallback-router",
                model_type=ModelType.NON_LLM,
                model_role=ModelRole.ROUTER,
                provider="local",
                tokens=0,
                latency_ms=3.0,
                confidence=1.0,
                why="Route to local SLM to preserve availability.",
                content="Activate local SLM fallback",
                provenance="SIMULATED",
                decision="SLM_FALLBACK",
                decision_why="Resilience and availability.",
            )
            self.tracer.record(
                ctx,
                segment="FRONTIER Attempt",
                model_name=frontier_attempt.model_name,
                model_type=ModelType.FRONTIER,
                model_role=ModelRole.SYNTHESIZER,
                provider=frontier_attempt.provider,
                input_tokens=0,
                output_tokens=0,
                latency_ms=frontier_latency,
                metadata={**failure_meta, "fallback": True},
            )
            self.tracer.record(
                ctx,
                segment="Failure Detector",
                model_name="failure-detector",
                model_type=ModelType.NON_LLM,
                model_role=ModelRole.EVALUATOR,
                provider="local",
                input_tokens=0,
                output_tokens=0,
                latency_ms=4.0,
                metadata={**failure_meta, "fallback": True},
            )
            self.tracer.record(
                ctx,
                segment="Fallback Decision",
                model_name="fallback-router",
                model_type=ModelType.NON_LLM,
                model_role=ModelRole.ROUTER,
                provider="local",
                input_tokens=0,
                output_tokens=0,
                latency_ms=3.0,
                metadata={"fallback": True, "target": "SLM"},
            )

            slm_result = self.slm.generate(
                prompt=(
                    "Frontier unavailable. Provide degraded but usable critical RCA.\n"
                    f"{device_block}"
                ),
                metadata={"task": "fallback", "device_id": DEVICE_ID, "force_confidence": 0.72},
            )
            slm_result.confidence = 0.72
            slm_segment = segment_from_generation(
                segment="SLM Fallback",
                task="fallback",
                role=ModelRole.FALLBACK,
                why="Local SLM preserves operational capability during Frontier outage.",
                result=slm_result,
                costs=self.costs,
                baseline=self.baseline,
                decision="SLM",
                decision_why="Availability fallback with reduced reasoning quality.",
            )
            recovery_time = round(
                frontier_latency
                + detector.latency_ms
                + fallback_decision.latency_ms
                + slm_segment.latency_ms,
                1,
            )
            self.tracer.record(
                ctx,
                segment="SLM Fallback",
                model_name=slm_result.model_name,
                model_type=slm_result.model_type,
                model_role=ModelRole.FALLBACK,
                provider=slm_result.provider,
                input_tokens=slm_result.usage.input_tokens,
                output_tokens=slm_result.usage.output_tokens,
                latency_ms=slm_result.usage.latency_ms,
                confidence=slm_result.confidence,
                is_actual_usage=slm_result.usage.is_actual_usage,
                metadata={
                    "fallback": True,
                    "failure_type": failure_type,
                    "total_recovery_time_ms": recovery_time,
                },
            )

            # Reset failure mode for subsequent runs
            if isinstance(self.frontier, (DemoFrontierClient, AzureFrontierClient)):
                self.frontier.set_failure_mode(None)

            normal_frontier = self.baseline.estimate_task("complex_rca")
            segments = [frontier_attempt, detector, fallback_decision, slm_segment]
            decision = build_architect_decision(
                pattern=PATTERN_NAME,
                scenario=SCENARIO,
                segments=[slm_segment],
                baseline_tasks=["complex_rca"],
                why=(
                    "When Frontier became unavailable, the local SLM maintained service "
                    "with reduced reasoning capability."
                ),
                recommendation=(
                    "Design explicit fallback. Fallback is primarily a resiliency pattern, "
                    "not a token optimization pattern."
                ),
                baseline=self.baseline,
                costs=self.costs,
                notes=[
                    "Primary benefit: Resilience and availability",
                    "SLM fallback preserves operational capability but may provide "
                    "lower-quality reasoning than the primary Frontier model.",
                ],
            )
            comparisons = summarize_token_bars(decision)
            comparisons.update(
                {
                    "normal_frontier": {
                        "tokens": normal_frontier["expected_tokens"],
                        "latency_ms": normal_frontier["expected_latency_ms"],
                        "confidence": normal_frontier["expected_confidence"],
                        "quality": "High",
                        "provenance": "ESTIMATED",
                    },
                    "frontier_failure_slm": {
                        "failed_frontier_tokens": frontier_tokens,
                        "slm_tokens": slm_segment.tokens,
                        "fallback_latency_ms": slm_segment.latency_ms,
                        "confidence": slm_segment.confidence,
                        "quality": "Degraded but usable",
                        "availability": "Maintained",
                        "time_to_failure_ms": failure_meta.get("time_to_failure_ms"),
                        "total_recovery_time_ms": recovery_time,
                        "failure_type": failure_type,
                        "provenance": slm_segment.provenance,
                    },
                    "callout": (
                        "Fallback is NOT primarily a token optimization pattern. "
                        "PRIMARY BENEFIT: RESILIENCY + AVAILABILITY. "
                        "SLM fallback preserves operational capability but may provide "
                        "lower-quality reasoning than the primary Frontier model."
                    ),
                    "ui_controls": sorted(FAILURE_MODES),
                }
            )
            return PatternResult(
                pattern=PATTERN_NAME,
                pattern_id=PATTERN_ID,
                scenario=SCENARIO,
                device_id=DEVICE_ID,
                segments=segments,
                summary=slm_result.text,
                findings={
                    "primary_benefit": "Resilience and availability",
                    "failure_type": failure_type,
                    "availability_maintained": True,
                },
                architect_decision=decision,
                trace_id=ctx.trace_id,
                langsmith_url=ctx.langsmith_url,
                comparisons=comparisons,
                metadata={"failure": failure_meta},
            )
