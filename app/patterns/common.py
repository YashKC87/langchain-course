"""Shared helpers for pattern segment construction."""

from __future__ import annotations

from typing import Any

from app.models.model_interface import GenerationResult, ModelRole, ModelType
from app.models.schemas import AlternativeEstimate, ArchitectDecision, SegmentResult
from app.observability.cost_calculator import CostCalculator
from app.services.baseline_estimator import BaselineEstimator


def segment_from_generation(
    *,
    segment: str,
    task: str,
    role: ModelRole,
    why: str,
    result: GenerationResult,
    costs: CostCalculator,
    baseline: BaselineEstimator,
    alternative_task: str | None = None,
    decision: str = "",
    decision_why: str = "",
) -> SegmentResult:
    alt_task = alternative_task or task
    alt_raw = baseline.estimate_task(alt_task)
    # If selected is already Frontier, alternative is an SLM estimate
    if result.model_type == ModelType.FRONTIER:
        alt = AlternativeEstimate(
            model_type=ModelType.SLM,
            model_name="estimated::slm",
            expected_tokens=max(400, int(alt_raw["expected_tokens"] * 0.35)),
            expected_latency_ms=round(alt_raw["expected_latency_ms"] * 0.25, 1),
            expected_confidence=0.61 if "rca" in task or "complex" in task or "synthesis" in task or "planner" in task else 0.88,
            expected_cost=costs.estimate_total_tokens(
                ModelType.SLM, max(400, int(alt_raw["expected_tokens"] * 0.35))
            ),
            recommendation="FRONTIER" if ("rca" in task or "planner" in task or "synthesis" in task or "complex" in task) else "COMPARE",
            rationale="SLM alternative may be cheaper/faster but can lack required reasoning quality.",
        )
    else:
        alt = AlternativeEstimate(
            model_type=ModelType.FRONTIER,
            model_name=alt_raw["model_name"],
            expected_tokens=int(alt_raw["expected_tokens"]),
            expected_latency_ms=float(alt_raw["expected_latency_ms"]),
            expected_confidence=float(alt_raw["expected_confidence"]),
            expected_cost=float(alt_raw["expected_cost"]),
            recommendation="SLM",
            rationale="Frontier quality gain is often marginal for routine telemetry tasks.",
        )
        # Special callouts
        if task in {"cpu", "cpu_memory"}:
            alt.recommendation = "SLM"
            alt.rationale = (
                "The small quality improvement does not justify higher latency and "
                "Frontier consumption for this routine task."
            )
        if result.confidence < 0.85 and task in {"initial_diagnosis", "diagnose", "cascade"}:
            alt.recommendation = "FRONTIER"
            alt.rationale = "SLM confidence is below threshold; Frontier escalation is justified."

    selected_cost = costs.estimate(
        model_type=result.model_type,
        input_tokens=result.usage.input_tokens,
        output_tokens=result.usage.output_tokens,
    )
    if not decision:
        decision = result.model_type.value
    if not decision_why:
        decision_why = why

    return SegmentResult(
        segment=segment,
        task=task,
        model_name=result.model_name,
        model_type=result.model_type,
        model_role=role,
        provider=result.provider,
        tokens=result.usage.total_tokens,
        input_tokens=result.usage.input_tokens,
        output_tokens=result.usage.output_tokens,
        latency_ms=result.usage.latency_ms,
        confidence=result.confidence,
        why=why,
        content=result.text,
        structured=result.structured or {},
        is_actual_usage=result.usage.is_actual_usage,
        provenance=result.usage.provenance,
        estimated_cost=selected_cost,
        alternative=alt,
        decision=decision,
        decision_why=decision_why,
    )


def build_architect_decision(
    *,
    pattern: str,
    scenario: str,
    segments: list[SegmentResult],
    baseline_tasks: list[str],
    why: str,
    recommendation: str,
    notes: list[str] | None = None,
    baseline: BaselineEstimator | None = None,
    costs: CostCalculator | None = None,
) -> ArchitectDecision:
    baseline = baseline or BaselineEstimator()
    costs = costs or CostCalculator()
    all_frontier = baseline.estimate_all_frontier(baseline_tasks)
    slm_segments = [s for s in segments if s.model_type == ModelType.SLM]
    frontier_segments = [s for s in segments if s.model_type == ModelType.FRONTIER]
    slm_tokens = sum(s.tokens for s in slm_segments)
    frontier_tokens = sum(s.tokens for s in frontier_segments)
    total_tokens = slm_tokens + frontier_tokens
    hybrid_latency = sum(s.latency_ms for s in segments)
    hybrid_cost = round(sum(s.estimated_cost for s in segments), 6)
    hybrid_conf = round(
        sum(s.confidence for s in segments if s.confidence) / max(1, len([s for s in segments if s.confidence])),
        3,
    )
    avoided = max(0, all_frontier["total_tokens"] - frontier_tokens)
    avoided_pct = round(100.0 * avoided / max(1, all_frontier["total_tokens"]), 1)
    return ArchitectDecision(
        pattern=pattern,
        scenario=scenario,
        frontier_used_for=[s.segment for s in frontier_segments],
        slm_used_for=[s.segment for s in slm_segments],
        why_this_architecture=why,
        slm_calls=len(slm_segments),
        frontier_calls=len(frontier_segments),
        slm_tokens=slm_tokens,
        frontier_tokens=frontier_tokens,
        total_tokens=total_tokens,
        all_frontier_tokens=all_frontier["total_tokens"],
        frontier_tokens_avoided=avoided,
        frontier_tokens_avoided_pct=avoided_pct,
        hybrid_latency_ms=round(hybrid_latency, 1),
        all_frontier_latency_ms=round(all_frontier["total_latency_ms"], 1),
        hybrid_confidence=hybrid_conf,
        all_frontier_confidence=all_frontier["average_confidence"],
        hybrid_cost=hybrid_cost,
        all_frontier_cost=all_frontier["total_cost"],
        cost_avoided=round(all_frontier["total_cost"] - hybrid_cost, 6),
        recommendation=recommendation,
        notes=notes or [all_frontier["note"]],
    )


def summarize_token_bars(decision: ArchitectDecision) -> dict[str, Any]:
    return {
        "selected_hybrid": {
            "slm_tokens": decision.slm_tokens,
            "frontier_tokens": decision.frontier_tokens,
            "total_tokens": decision.total_tokens,
        },
        "estimated_all_frontier": {
            "frontier_tokens": decision.all_frontier_tokens,
            "label": "ESTIMATED ALL-FRONTIER BASELINE",
        },
        "frontier_tokens_avoided": decision.frontier_tokens_avoided,
        "frontier_tokens_avoided_pct": decision.frontier_tokens_avoided_pct,
        "cost_avoided": decision.cost_avoided,
        "latency_improvement_pct": round(
            100.0
            * (decision.all_frontier_latency_ms - decision.hybrid_latency_ms)
            / max(1.0, decision.all_frontier_latency_ms),
            1,
        ),
        "quality_difference": round(
            decision.hybrid_confidence - decision.all_frontier_confidence, 3
        ),
    }
