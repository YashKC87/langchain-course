"""FastAPI entrypoint for the Pattern Lab."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.config import get_settings
from app.data.generator import write_datasets
from app.observability.trace_store import get_trace_store
from app.services.scenario_service import PATTERN_CATALOG, get_scenario_service
from app.services.telemetry import TelemetryService

settings = get_settings()
write_datasets()

app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="SLM + Frontier architecture pattern lab for digital workplace monitoring.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class RunRequest(BaseModel):
    failure_type: str = "http_503"
    n: int = Field(default=100, ge=1, le=100)


@app.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "demo_mode": settings.effective_demo_mode()}


@app.get("/api/v1/config")
def config_status() -> dict[str, Any]:
    return settings.public_status()


@app.get("/api/v1/patterns")
def list_patterns() -> list[dict[str, Any]]:
    return PATTERN_CATALOG


@app.get("/api/v1/devices")
def list_devices() -> dict[str, Any]:
    telemetry = TelemetryService()
    return {
        "summary": telemetry.fleet_summary(),
        "devices": telemetry.list_devices().to_dict(orient="records"),
    }


@app.get("/api/v1/devices/{device_id}")
def get_device(device_id: str) -> dict[str, Any]:
    telemetry = TelemetryService()
    try:
        device = telemetry.get_device(device_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "device": device,
        "incidents": telemetry.incidents_for(device_id),
    }


@app.post("/api/v1/patterns/{pattern_id}/run")
def run_pattern(pattern_id: str, body: RunRequest | None = None) -> dict[str, Any]:
    service = get_scenario_service()
    body = body or RunRequest()
    try:
        if pattern_id == "fallback":
            result = service.run_pattern(pattern_id, failure_type=body.failure_type)
        elif pattern_id == "router":
            result = service.run_pattern(pattern_id, n=body.n)
        else:
            result = service.run_pattern(pattern_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return result.model_dump(mode="json")


@app.post("/api/v1/patterns/run-all")
def run_all() -> dict[str, Any]:
    service = get_scenario_service()
    results = service.run_all()
    return {k: v.model_dump(mode="json") for k, v in results.items()}


@app.get("/api/v1/overview")
def overview() -> dict[str, Any]:
    service = get_scenario_service()
    return {
        "cards": service.overview_cards(),
        "patterns": PATTERN_CATALOG,
        "config": settings.public_status(),
    }


@app.get("/api/v1/mlops")
def mlops() -> dict[str, Any]:
    return get_scenario_service().mlops_dashboard()


@app.get("/api/v1/traces")
def traces(
    pattern: str | None = None,
    model_type: str | None = None,
    device_id: str | None = None,
    escalated: bool | None = None,
    fallback: bool | None = None,
    limit: int = Query(default=500, ge=1, le=5000),
) -> dict[str, Any]:
    store = get_trace_store()
    rows = store.list_runs(
        pattern=pattern,
        model_type=model_type,
        device_id=device_id,
        escalated=escalated,
        fallback=fallback,
        limit=limit,
    )
    return {"count": len(rows), "runs": rows, "aggregates": store.aggregates()}


@app.get("/api/v1/traces/{trace_id}")
def trace_detail(trace_id: str) -> dict[str, Any]:
    rows = get_trace_store().by_trace(trace_id)
    if not rows:
        raise HTTPException(status_code=404, detail="Trace not found")
    return {"trace_id": trace_id, "runs": rows}
