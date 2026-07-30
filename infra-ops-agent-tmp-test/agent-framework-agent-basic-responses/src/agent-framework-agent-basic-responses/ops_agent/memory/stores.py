"""Layered memory — session, incident, knowledge, learning."""

from __future__ import annotations

from typing import Any, Optional
import copy


class SessionMemory:
    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value

    def get(self, key: str, default=None):
        return self._data.get(key, default)

    def clear(self) -> None:
        self._data.clear()


class IncidentMemory:
    def __init__(self) -> None:
        self._by_id: dict[str, dict[str, Any]] = {}

    def upsert(self, state: dict[str, Any]) -> None:
        self._by_id[state["investigation_id"]] = copy.deepcopy(state)

    def find_open_by_resource(self, resource: str) -> Optional[dict[str, Any]]:
        for rec in self._by_id.values():
            if rec.get("resource") == resource and rec.get("status") in ("InProgress", "AwaitingApproval"):
                return rec
        return None


class KnowledgeMemory:
    """Approved SOPs / KERs only — not raw chat."""

    def __init__(self) -> None:
        self._docs = {
            "endpoint_slow_perf": {
                "title": "Endpoint sustained resource pressure",
                "sop": "Disk cleanup → Teams restart → Intune sync → VPN quality check",
            }
        }

    def search(self, query: str) -> list[dict[str, Any]]:
        q = query.lower()
        return [v for k, v in self._docs.items() if q in k or q in v["title"].lower()]


class LearningMemory:
    def __init__(self) -> None:
        self._events: list[dict[str, Any]] = []

    def capture(self, outcome: dict[str, Any]) -> None:
        if not outcome.get("anonymized"):
            raise ValueError("Learning memory requires anonymized=True")
        self._events.append(outcome)


class MemoryFacade:
    def __init__(self) -> None:
        self.session = SessionMemory()
        self.incident = IncidentMemory()
        self.knowledge = KnowledgeMemory()
        self.learning = LearningMemory()
