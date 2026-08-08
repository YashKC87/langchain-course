"""Pattern 3 — Confidence Cascade for ambiguous LAPTOP-9910 incident."""

from __future__ import annotations

from typing import Any

from app.config import Settings, get_settings
from app.models.factory import build_frontier_client, build_slm_client
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

PATTERN_NAME = "Confidence Cascade"
PATTERN_ID = "confidence_cascade"
SCENARIO = "Investigate ambiguous Teams + VPN instability on LAPTOP-9910."
DEVICE_ID = "LAPTOP-9910"


class ConfidenceCascadePattern:
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
        self.threshold = self.settings.confidence_threshold

    def run(self) -> PatternResult:
        device_block = self.telemetry.device_prompt_block(DEVICE_ID)
        with self.tracer.trace(
            pattern=PATTERN_NAME,
            scenario=SCENARIO,
            device_id=DEVICE_ID,
            metadata={"pattern_id": PATTERN_ID, "threshold": self.threshold},
        ) as ctx:
            slm_diag = self.slm.structured_generate(
                prompt=(
                    "Diagnose intermittent Teams and VPN instability with conflicting telemetry.\n"
                    f"{device_block}"
                ),
                schema={
                    "hypothesis": "string",
                    "confidence": 0.0,
                    "conflicting_signals": ["string"],
                    "recommended_next_step": "string",
                },
                metadata={
                    "task": "initial_diagnosis",
                    "device_id": DEVICE_ID,
                    "force_confidence": 0.54,
                },
            )
            # Enforce scenario expectation for demo determinism
            initial_confidence = 0.54
            slm_diag.confidence = initial_confidence
            if slm_diag.structured is not None:
                slm_diag.structured["confidence"] = initial_confidence

            segments: list[SegmentResult] = [
                segment_from_generation(
                    segment="SLM Initial Diagnosis",
                    task="initial_diagnosis",
                    role=ModelRole.DIAGNOSER,
                    why="Try inexpensive local diagnosis first.",
                    result=slm_diag,
                    costs=self.costs,
                    baseline=self.baseline,
                    decision="ESCALATE" if initial_confidence < self.threshold else "COMPLETE",
                    decision_why=(
                        f"Confidence {initial_confidence:.0%} is below threshold "
                        f"{self.threshold:.0%}."
                    ),
                )
            ]
            self.tracer.record(
                ctx,
                segment="SLM Initial Diagnosis",
                model_name=slm_diag.model_name,
                model_type=slm_diag.model_type,
                model_role=ModelRole.DIAGNOSER,
                provider=slm_diag.provider,
                input_tokens=slm_diag.usage.input_tokens,
                output_tokens=slm_diag.usage.output_tokens,
                latency_ms=slm_diag.usage.latency_ms,
                confidence=initial_confidence,
                is_actual_usage=slm_diag.usage.is_actual_usage,
                metadata={"initial_confidence": initial_confidence},
            )

            evaluator = SegmentResult(
                segment="Confidence Evaluator",
                task="evaluate_confidence",
                model_name="confidence-evaluator",
                model_type=ModelType.NON_LLM,
                model_role=ModelRole.EVALUATOR,
                provider="local",
                tokens=0,
                latency_ms=5.0,
                confidence=1.0,
                why="Compare SLM confidence against configured threshold.",
                content=(
                    f"initial_confidence={initial_confidence}, threshold={self.threshold}, "
                    f"escalated={initial_confidence < self.threshold}"
                ),
                structured={
                    "initial_confidence": initial_confidence,
                    "threshold": self.threshold,
                    "escalated": initial_confidence < self.threshold,
                    "escalation_reason": "Low confidence on conflicting telemetry",
                },
                provenance="SIMULATED",
                decision="ESCALATE",
                decision_why="Ambiguous incident requires Frontier escalation.",
            )
            segments.append(evaluator)
            self.tracer.record(
                ctx,
                segment="Confidence Evaluator",
                model_name="confidence-evaluator",
                model_type=ModelType.NON_LLM,
                model_role=ModelRole.EVALUATOR,
                provider="local",
                input_tokens=0,
                output_tokens=0,
                latency_ms=5.0,
                confidence=1.0,
                metadata=evaluator.structured,
            )

            escalated = initial_confidence < self.threshold
            frontier_result = None
            if escalated:
                frontier_result = self.frontier.generate(
                    prompt=(
                        "Escalate and produce final RCA for ambiguous Teams/VPN instability.\n"
                        f"SLM hypothesis: {slm_diag.text}\nDEVICE:\n{device_block}"
                    ),
                    metadata={"task": "escalated_rca", "device_id": DEVICE_ID},
                )
                segments.append(
                    SegmentResult(
                        segment="Escalation Decision",
                        task="escalation_decision",
                        model_name="escalation-policy",
                        model_type=ModelType.NON_LLM,
                        model_role=ModelRole.EVALUATOR,
                        provider="local",
                        tokens=0,
                        latency_ms=2.0,
                        confidence=1.0,
                        why="Policy: escalate when confidence < threshold.",
                        content="ESCALATE to Frontier",
                        provenance="SIMULATED",
                        decision="ESCALATE",
                        decision_why="Confidence below threshold.",
                    )
                )
                segments.append(
                    segment_from_generation(
                        segment="FRONTIER RCA",
                        task="escalated_rca",
                        role=ModelRole.SYNTHESIZER,
                        why="Resolve ambiguity with advanced reasoning.",
                        result=frontier_result,
                        costs=self.costs,
                        baseline=self.baseline,
                        alternative_task="cascade",
                        decision="FRONTIER",
                        decision_why="Quality requirement justifies additional inference.",
                    )
                )
                self.tracer.record(
                    ctx,
                    segment="Escalation Decision",
                    model_name="escalation-policy",
                    model_type=ModelType.NON_LLM,
                    model_role=ModelRole.EVALUATOR,
                    provider="local",
                    input_tokens=0,
                    output_tokens=0,
                    latency_ms=2.0,
                    metadata={"escalated": True, "reason": "low_confidence"},
                )
                self.tracer.record(
                    ctx,
                    segment="FRONTIER RCA",
                    model_name=frontier_result.model_name,
                    model_type=frontier_result.model_type,
                    model_role=ModelRole.SYNTHESIZER,
                    provider=frontier_result.provider,
                    input_tokens=frontier_result.usage.input_tokens,
                    output_tokens=frontier_result.usage.output_tokens,
                    latency_ms=frontier_result.usage.latency_ms,
                    confidence=frontier_result.confidence,
                    is_actual_usage=frontier_result.usage.is_actual_usage,
                    metadata={
                        "escalated": True,
                        "initial_confidence": initial_confidence,
                        "threshold": self.threshold,
                        "final_confidence": frontier_result.confidence,
                    },
                )

            # Honest token accounting for cascade vs direct frontier
            slm_tokens = segments[0].tokens
            frontier_tokens = frontier_result.usage.total_tokens if frontier_result else 0
            cascade_tokens = slm_tokens + frontier_tokens
            direct_frontier = self.baseline.estimate_task("cascade")
            cascade_more_than_direct = cascade_tokens > direct_frontier["expected_tokens"]

            # Option comparisons
            option_a = {
                "name": "SLM ONLY",
                "tokens": slm_tokens,
                "latency_ms": segments[0].latency_ms,
                "confidence": initial_confidence,
                "result": "Fast and inexpensive but potentially unreliable.",
                "provenance": "SIMULATED",
            }
            option_b = {
                "name": "FRONTIER ONLY",
                "tokens": direct_frontier["expected_tokens"],
                "latency_ms": direct_frontier["expected_latency_ms"],
                "confidence": direct_frontier["expected_confidence"],
                "result": "Strong answer but uses Frontier for every incident.",
                "provenance": "ESTIMATED",
                "label": "ESTIMATED ALL-FRONTIER BASELINE",
            }
            option_c = {
                "name": "CONFIDENCE CASCADE",
                "tokens": cascade_tokens,
                "latency_ms": round(sum(s.latency_ms for s in segments), 1),
                "confidence": frontier_result.confidence if frontier_result else initial_confidence,
                "result": (
                    "SLM first; Frontier only when confidence is low. "
                    + (
                        "This individual escalation consumed more tokens than direct Frontier."
                        if cascade_more_than_direct
                        else "Cascade stayed near direct Frontier cost for this incident."
                    )
                ),
                "provenance": "SIMULATED+ESTIMATED",
                "slm_attempt_tokens": slm_tokens,
                "frontier_escalation_tokens": frontier_tokens,
            }

            # Fleet economics (illustrative deterministic)
            fleet = self._fleet_economics(slm_tokens, frontier_tokens, direct_frontier)

            llm_segments = [s for s in segments if s.model_type != ModelType.NON_LLM]
            decision = build_architect_decision(
                pattern=PATTERN_NAME,
                scenario=SCENARIO,
                segments=llm_segments,
                baseline_tasks=["cascade"],
                why="We let the SLM solve easy incidents and escalated only uncertain cases.",
                recommendation=(
                    "Use Confidence Cascade for mixed-difficulty fleets. Accept that an "
                    "individual escalation can exceed direct Frontier tokens while preserving "
                    "fleet-level savings."
                ),
                baseline=self.baseline,
                costs=self.costs,
                notes=[
                    "Primary benefit: Quality-aware escalation",
                    option_c["result"],
                ],
            )
            comparisons = summarize_token_bars(decision)
            comparisons.update(
                {
                    "options": [option_a, option_b, option_c],
                    "cascade_tokens": cascade_tokens,
                    "direct_frontier_tokens": direct_frontier["expected_tokens"],
                    "cascade_exceeds_direct_frontier": cascade_more_than_direct,
                    "callout": (
                        "This individual escalation consumed more tokens than direct Frontier."
                        if cascade_more_than_direct
                        else "Cascade did not exceed direct Frontier on this incident."
                    ),
                    "fleet_economics": fleet,
                    "initial_confidence": initial_confidence,
                    "threshold": self.threshold,
                    "escalated": escalated,
                    "final_confidence": option_c["confidence"],
                }
            )
            return PatternResult(
                pattern=PATTERN_NAME,
                pattern_id=PATTERN_ID,
                scenario=SCENARIO,
                device_id=DEVICE_ID,
                segments=segments,
                summary=frontier_result.text if frontier_result else slm_diag.text,
                findings={
                    "primary_benefit": "Quality-aware escalation",
                    "escalated": escalated,
                },
                architect_decision=decision,
                trace_id=ctx.trace_id,
                langsmith_url=ctx.langsmith_url,
                comparisons=comparisons,
            )

    def _fleet_economics(
        self, slm_tokens: int, frontier_tokens: int, direct_frontier: dict[str, Any]
    ) -> dict[str, Any]:
        incidents = 100
        solved_by_slm = 80
        escalated = 20
        all_frontier_tokens = incidents * direct_frontier["expected_tokens"]
        cascade_tokens = (
            solved_by_slm * slm_tokens + escalated * (slm_tokens + frontier_tokens)
        )
        return {
            "incidents": incidents,
            "solved_by_slm": solved_by_slm,
            "escalated_to_frontier": escalated,
            "all_frontier_tokens": all_frontier_tokens,
            "cascade_tokens": cascade_tokens,
            "frontier_tokens_avoided": max(0, all_frontier_tokens - escalated * frontier_tokens),
            "note": (
                "Fleet view: 100 × Frontier versus 80 × SLM + 20 × (SLM + Frontier). "
                "Cascade value appears at fleet scale even if one escalation is heavier."
            ),
            "provenance": "ESTIMATED",
        }

    def run_high_confidence_smoke(self) -> dict[str, Any]:
        """Test helper: high-confidence path avoids escalation."""
        result = self.slm.generate(
            "Simple CPU high on LAPTOP-3304",
            metadata={
                "task": "initial_diagnosis",
                "device_id": "LAPTOP-3304",
                "force_confidence": 0.92,
            },
        )
        result.confidence = 0.92
        escalated = result.confidence < self.threshold
        return {
            "confidence": result.confidence,
            "threshold": self.threshold,
            "escalated": escalated,
        }
