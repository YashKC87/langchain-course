"""Scenario orchestration and aggregate MLOps views."""

from __future__ import annotations

from typing import Any

from app.config import Settings, get_settings
from app.models.schemas import PatternResult
from app.observability.trace_store import TraceStore, get_trace_store
from app.patterns import PATTERN_REGISTRY
from app.patterns.confidence_cascade import ConfidenceCascadePattern
from app.patterns.fallback import FallbackPattern
from app.patterns.planner_worker import PlannerWorkerPattern
from app.patterns.rag import RAGPattern
from app.patterns.router import RouterPattern
from app.services.telemetry import TelemetryService

PATTERN_CATALOG = [
    {
        "pattern_id": "planner_worker",
        "pattern": "Planner-Worker Hierarchy",
        "scenario": "Complete multi-domain RCA for LAPTOP-1204.",
        "slm_role": "Execute routine investigation workers",
        "frontier_role": "Plan investigation and synthesize final RCA",
        "primary_benefit": "Selective reasoning + orchestration efficiency",
    },
    {
        "pattern_id": "router",
        "pattern": "Router Pattern",
        "scenario": "Route 100 incoming endpoint health requests between SLM and Frontier.",
        "slm_role": "Routine health/status requests",
        "frontier_role": "Complex/ambiguous RCA requests",
        "primary_benefit": "High-volume inference efficiency",
    },
    {
        "pattern_id": "confidence_cascade",
        "pattern": "Confidence Cascade",
        "scenario": "Investigate ambiguous Teams + VPN instability on LAPTOP-9910.",
        "slm_role": "First-pass diagnosis",
        "frontier_role": "Escalation when confidence is low",
        "primary_benefit": "Quality-aware escalation",
    },
    {
        "pattern_id": "rag",
        "pattern": "Retrieval-Augmented Generation (RAG)",
        "scenario": "LAPTOP-1507 disk/OneDrive approved remediation via enterprise SOP.",
        "slm_role": "Grounded generation from retrieved SOPs",
        "frontier_role": "Not required for this SOP scenario",
        "primary_benefit": "Grounded enterprise knowledge with smaller model",
    },
    {
        "pattern_id": "fallback",
        "pattern": "Designing for Fallback",
        "scenario": "Critical RCA continues when Frontier becomes unavailable.",
        "slm_role": "Availability fallback with degraded quality",
        "frontier_role": "Primary advanced reasoning path",
        "primary_benefit": "Resilience and availability",
    },
]


class ScenarioService:
    def __init__(
        self,
        settings: Settings | None = None,
        store: TraceStore | None = None,
        telemetry: TelemetryService | None = None,
    ):
        self.settings = settings or get_settings()
        self.store = store or get_trace_store()
        self.telemetry = telemetry or TelemetryService()
        self._last_results: dict[str, PatternResult] = {}

    def catalog(self) -> list[dict[str, Any]]:
        return PATTERN_CATALOG

    def run_pattern(self, pattern_id: str, **kwargs: Any) -> PatternResult:
        if pattern_id not in PATTERN_REGISTRY:
            raise KeyError(f"Unknown pattern_id: {pattern_id}")
        if pattern_id == "planner_worker":
            result = PlannerWorkerPattern(settings=self.settings, telemetry=self.telemetry).run()
        elif pattern_id == "router":
            result = RouterPattern(settings=self.settings, telemetry=self.telemetry).run(
                n=int(kwargs.get("n", 100))
            )
        elif pattern_id == "confidence_cascade":
            result = ConfidenceCascadePattern(
                settings=self.settings, telemetry=self.telemetry
            ).run()
        elif pattern_id == "rag":
            result = RAGPattern(settings=self.settings, telemetry=self.telemetry).run()
        else:
            result = FallbackPattern(settings=self.settings, telemetry=self.telemetry).run(
                failure_type=str(kwargs.get("failure_type", "http_503"))
            )
        self._last_results[pattern_id] = result
        return result

    def run_all(self) -> dict[str, PatternResult]:
        results = {}
        for item in PATTERN_CATALOG:
            results[item["pattern_id"]] = self.run_pattern(item["pattern_id"])
        return results

    def overview_cards(self) -> dict[str, Any]:
        fleet = self.telemetry.fleet_summary()
        agg = self.store.aggregates()
        avoided_calls = 0
        avoided_tokens = 0
        cost_avoided = 0.0
        for result in self._last_results.values():
            if result.architect_decision:
                avoided_tokens += result.architect_decision.frontier_tokens_avoided
                cost_avoided += result.architect_decision.cost_avoided
                # approximate calls avoided from comparisons when present
                comps = result.comparisons or {}
                avoided_calls += int(comps.get("frontier_calls_avoided") or 0)
                if result.pattern_id == "planner_worker":
                    avoided_calls += result.architect_decision.slm_calls
                if result.pattern_id == "confidence_cascade":
                    fleet_econ = comps.get("fleet_economics") or {}
                    avoided_calls += int(fleet_econ.get("solved_by_slm") or 0)
        return {
            **fleet,
            "slm_calls": agg["slm_calls"],
            "frontier_calls": agg["frontier_calls"],
            "slm_tokens": agg["slm_tokens"],
            "frontier_tokens": agg["frontier_tokens"],
            "frontier_calls_avoided": avoided_calls,
            "estimated_cost_avoided": round(cost_avoided, 6),
            "total_scenarios": len(self._last_results) or len(PATTERN_CATALOG),
            "total_traces": agg["total_traces"],
            "pricing_disclaimer": self.settings.pricing_disclaimer,
        }

    def mlops_dashboard(self) -> dict[str, Any]:
        agg = self.store.aggregates()
        rows = self.store.list_runs(limit=5000)
        by_pattern: dict[str, dict[str, float]] = {}
        for row in rows:
            pattern = row.get("pattern") or "unknown"
            bucket = by_pattern.setdefault(
                pattern, {"SLM": 0, "FRONTIER": 0, "NON_LLM": 0, "latency": [], "cost": 0.0}
            )
            mt = row.get("model_type") or "NON_LLM"
            bucket[mt] = bucket.get(mt, 0) + int(row.get("total_tokens") or 0)
            bucket["latency"].append(float(row.get("latency_ms") or 0))
            bucket["cost"] += float(row.get("estimated_cost") or 0)

        efficiency = []
        for pattern_id, result in self._last_results.items():
            d = result.architect_decision
            if not d:
                continue
            efficiency.append(
                {
                    "pattern": d.pattern,
                    "scenario": d.scenario,
                    "slm_calls": d.slm_calls,
                    "frontier_calls": d.frontier_calls,
                    "slm_tokens": d.slm_tokens,
                    "frontier_tokens": d.frontier_tokens,
                    "total_tokens": d.total_tokens,
                    "all_frontier_baseline": d.all_frontier_tokens,
                    "frontier_tokens_avoided": d.frontier_tokens_avoided,
                    "actual_latency_ms": d.hybrid_latency_ms,
                    "all_frontier_estimated_latency_ms": d.all_frontier_latency_ms,
                    "confidence": d.hybrid_confidence,
                    "estimated_cost": d.hybrid_cost,
                    "primary_benefit": (result.findings or {}).get("primary_benefit"),
                }
            )
        return {
            "kpis": {
                **agg,
                "total_scenarios": len(self._last_results) or 0,
                "frontier_calls_avoided": self.overview_cards()["frontier_calls_avoided"],
                "frontier_tokens_avoided": sum(
                    (r.architect_decision.frontier_tokens_avoided if r.architect_decision else 0)
                    for r in self._last_results.values()
                ),
                "estimated_cost_avoided": self.overview_cards()["estimated_cost_avoided"],
            },
            "by_pattern": {
                k: {
                    "slm_tokens": v.get("SLM", 0),
                    "frontier_tokens": v.get("FRONTIER", 0),
                    "avg_latency_ms": round(sum(v["latency"]) / max(1, len(v["latency"])), 2),
                    "cost": round(v["cost"], 6),
                }
                for k, v in by_pattern.items()
            },
            "efficiency_table": efficiency,
            "pricing_disclaimer": self.settings.pricing_disclaimer,
            "last_results": {k: v.model_dump(mode="json") for k, v in self._last_results.items()},
        }


_SERVICE: ScenarioService | None = None


def get_scenario_service() -> ScenarioService:
    global _SERVICE
    if _SERVICE is None:
        _SERVICE = ScenarioService()
    return _SERVICE
