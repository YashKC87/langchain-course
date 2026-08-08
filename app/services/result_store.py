"""Persist latest pattern results for Streamlit reload across sessions."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from app.models.schemas import PatternResult

RESULT_PATH = Path(__file__).resolve().parents[2] / ".local_pattern_results.json"


class ResultStore:
    def __init__(self, path: Path | None = None):
        self.path = path or RESULT_PATH
        self._lock = threading.Lock()

    def save(self, result: PatternResult) -> None:
        with self._lock:
            data = self._read()
            data[result.pattern_id] = result.model_dump(mode="json")
            self.path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")

    def get(self, pattern_id: str) -> PatternResult | None:
        data = self._read()
        raw = data.get(pattern_id)
        if not raw:
            return None
        return PatternResult.model_validate(raw)

    def all(self) -> dict[str, PatternResult]:
        data = self._read()
        out: dict[str, PatternResult] = {}
        for key, raw in data.items():
            try:
                out[key] = PatternResult.model_validate(raw)
            except Exception:  # noqa: BLE001
                continue
        return out

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}


_RESULT_STORE: ResultStore | None = None


def get_result_store() -> ResultStore:
    global _RESULT_STORE
    if _RESULT_STORE is None:
        _RESULT_STORE = ResultStore()
    return _RESULT_STORE
