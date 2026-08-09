"""Shared pytest fixtures."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

# Force deterministic demo mode for all tests
os.environ["DEMO_MODE"] = "true"
os.environ["LANGSMITH_ENABLED"] = "false"
os.environ["LANGSMITH_TRACING"] = "false"
os.environ["LANGSMITH_API_KEY"] = ""

from app.config import get_settings
from app.data.generator import write_datasets
from app.observability.trace_store import TraceStore
from app.services.scenario_service import ScenarioService


@pytest.fixture(scope="session", autouse=True)
def _prepare_data() -> None:
    write_datasets(n=100, seed=42)
    get_settings.cache_clear()


@pytest.fixture()
def trace_store(tmp_path: Path) -> TraceStore:
    return TraceStore(path=tmp_path / "traces.json")


@pytest.fixture()
def scenario_service(trace_store: TraceStore) -> ScenarioService:
    get_settings.cache_clear()
    return ScenarioService(store=trace_store)
