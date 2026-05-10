# ============================================================
#  HEALIX Monitoring Router — routers/monitoring.py
# ============================================================

from fastapi import APIRouter, Request, HTTPException, Query
from typing import Optional

router = APIRouter(prefix="/api/monitoring", tags=["Monitoring"])


@router.get("/overview")
async def system_overview(request: Request):
    """System-wide metrics summary."""
    return await request.app.state.monitoring_engine.get_system_overview()


@router.get("/endpoints")
async def list_endpoints(request: Request):
    """All endpoints with latest metrics."""
    endpoints = await request.app.state.db.get_endpoints()
    if not endpoints:
        # Fall back to demo endpoints via monitoring engine
        await request.app.state.monitoring_engine._ensure_demo_endpoints()
        endpoints = await request.app.state.db.get_endpoints()
    return {"endpoints": endpoints, "count": len(endpoints)}


@router.get("/endpoints/{endpoint_id}")
async def endpoint_detail(request: Request, endpoint_id: str):
    result = await request.app.state.monitoring_engine.get_endpoint_detail(endpoint_id)
    if not result:
        raise HTTPException(status_code=404, detail="Endpoint not found")
    return result


@router.get("/metrics/history")
async def metric_history(request: Request, endpoint: str = "",
                         metric: str = "cpu", hours: int = Query(24, le=168)):
    history = await request.app.state.monitoring_engine.get_metric_history(
        endpoint_name=endpoint, metric=metric, hours=hours
    )
    return {"history": history, "endpoint": endpoint, "metric": metric, "hours": hours}


@router.get("/anomalies")
async def anomalies(request: Request):
    return {"anomalies": await request.app.state.monitoring_engine.detect_anomalies()}


@router.get("/heartbeat")
async def heartbeat_status(request: Request):
    agents = await request.app.state.monitoring_engine.get_heartbeat_status()
    return {"agents": agents, "count": len(agents)}
