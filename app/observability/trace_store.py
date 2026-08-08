"""In-memory / JSON-backed local trace store for LLMOps views."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from app.observability.token_metrics import TokenMetrics

STORE_PATH = Path(__file__).resolve().parents[2] / ".local_traces.json"


class TraceStore:
    def __init__(self, path: Path | None = None):
        self.path = path or STORE_PATH
        self._lock = threading.Lock()
        self._runs: list[dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            try:
                self._runs = json.loads(self.path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                self._runs = []

    def _persist(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._runs, default=str, indent=2), encoding="utf-8")

    def add(self, metrics: TokenMetrics) -> TokenMetrics:
        with self._lock:
            self._runs.append(metrics.model_dump(mode="json"))
            self._persist()
        return metrics

    def add_many(self, metrics_list: list[TokenMetrics]) -> None:
        with self._lock:
            self._runs.extend(m.model_dump(mode="json") for m in metrics_list)
            self._persist()

    def list_runs(
        self,
        *,
        pattern: str | None = None,
        model_type: str | None = None,
        device_id: str | None = None,
        escalated: bool | None = None,
        fallback: bool | None = None,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        rows = list(self._runs)
        if pattern:
            rows = [r for r in rows if r.get("pattern") == pattern]
        if model_type:
            rows = [r for r in rows if r.get("model_type") == model_type]
        if device_id:
            rows = [r for r in rows if r.get("device_id") == device_id]
        if escalated is not None:
            rows = [
                r
                for r in rows
                if bool((r.get("metadata") or {}).get("escalated")) == escalated
            ]
        if fallback is not None:
            rows = [
                r
                for r in rows
                if bool((r.get("metadata") or {}).get("fallback")) == fallback
            ]
        return rows[-limit:]

    def by_trace(self, trace_id: str) -> list[dict[str, Any]]:
        return [r for r in self._runs if r.get("trace_id") == trace_id]

    def clear(self) -> None:
        with self._lock:
            self._runs = []
            self._persist()

    def aggregates(self) -> dict[str, Any]:
        rows = self._runs
        slm = [r for r in rows if r.get("model_type") == "SLM"]
        frontier = [r for r in rows if r.get("model_type") == "FRONTIER"]
        latencies = [float(r.get("latency_ms") or 0) for r in rows]
        latencies_sorted = sorted(latencies)
        p95 = (
            latencies_sorted[int(0.95 * (len(latencies_sorted) - 1))]
            if latencies_sorted
            else 0.0
        )
        confidences = [
            float(r["confidence"])
            for r in rows
            if r.get("confidence") is not None
        ]
        escalations = sum(
            1 for r in rows if (r.get("metadata") or {}).get("escalated")
        )
        fallbacks = sum(1 for r in rows if (r.get("metadata") or {}).get("fallback"))
        return {
            "total_traces": len({r.get("trace_id") for r in rows}),
            "total_model_calls": len(rows),
            "slm_calls": len(slm),
            "frontier_calls": len(frontier),
            "slm_tokens": sum(int(r.get("total_tokens") or 0) for r in slm),
            "frontier_tokens": sum(int(r.get("total_tokens") or 0) for r in frontier),
            "total_tokens": sum(int(r.get("total_tokens") or 0) for r in rows),
            "average_latency_ms": round(sum(latencies) / len(latencies), 2) if latencies else 0,
            "p95_latency_ms": round(p95, 2),
            "average_confidence": round(sum(confidences) / len(confidences), 3)
            if confidences
            else 0,
            "escalation_rate": round(escalations / max(1, len(rows)), 3),
            "fallback_rate": round(fallbacks / max(1, len(rows)), 3),
            "estimated_cost": round(sum(float(r.get("estimated_cost") or 0) for r in rows), 6),
        }


_STORE: TraceStore | None = None


def get_trace_store() -> TraceStore:
    global _STORE
    if _STORE is None:
        _STORE = TraceStore()
    return _STORE
