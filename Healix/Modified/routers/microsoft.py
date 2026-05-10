# ============================================================
#  HEALIX Microsoft Router — routers/microsoft.py
#  Endpoints for Defender XDR, Sentinel, Intune, and Entra.
# ============================================================

from fastapi import APIRouter, Request, HTTPException, Query
from typing import Optional

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models import KQLQueryRequest, DeviceActionRequest, IncidentUpdateRequest

router = APIRouter(prefix="/api/microsoft", tags=["Microsoft Integration"])


@router.get("/status")
async def microsoft_status(request: Request):
    """Check which Microsoft services are connected."""
    return {
        "defender": request.app.state.defender.is_available if hasattr(request.app.state, 'defender') else False,
        "sentinel": request.app.state.sentinel.is_available if hasattr(request.app.state, 'sentinel') else False,
        "intune": request.app.state.intune.is_available if hasattr(request.app.state, 'intune') else False,
        "entra": request.app.state.entra.is_available if hasattr(request.app.state, 'entra') else False,
        "demo_mode": request.app.state.config.is_demo_mode,
    }


# ── Defender XDR ────────────────────────────────────────────

@router.get("/defender/incidents")
async def defender_incidents(request: Request, status: Optional[str] = None,
                             top: int = Query(50, le=200)):
    return {"incidents": await request.app.state.defender.get_incidents(top=top, status=status)}


@router.get("/defender/incidents/{incident_id}")
async def defender_incident_detail(request: Request, incident_id: str):
    result = await request.app.state.defender.get_incident_details(incident_id)
    if not result:
        raise HTTPException(status_code=404, detail="Incident not found")
    return result


@router.get("/defender/alerts")
async def defender_alerts(request: Request, severity: Optional[str] = None,
                          top: int = Query(100, le=500)):
    return {"alerts": await request.app.state.defender.get_security_alerts(severity=severity, top=top)}


@router.post("/defender/hunt")
async def defender_hunt(request: Request, body: KQLQueryRequest):
    result = await request.app.state.defender.run_hunting_query(body.query)
    return result or {"error": "Hunting query failed"}


@router.get("/defender/secure-score")
async def defender_secure_score(request: Request):
    return await request.app.state.defender.get_secure_score()


# ── Sentinel ────────────────────────────────────────────────

@router.get("/sentinel/incidents")
async def sentinel_incidents(request: Request, top: int = Query(50, le=200)):
    return {"incidents": await request.app.state.sentinel.get_sentinel_incidents(top=top)}


@router.post("/sentinel/query")
async def sentinel_query(request: Request, body: KQLQueryRequest):
    result = await request.app.state.sentinel.query_logs(body.query, body.timespan)
    return result or {"error": "Query returned no results"}


@router.get("/sentinel/alert-rules")
async def sentinel_alert_rules(request: Request):
    return {"rules": await request.app.state.sentinel.get_alert_rules()}


# ── Intune ──────────────────────────────────────────────────

@router.get("/intune/devices")
async def intune_devices(request: Request, top: int = Query(100, le=500)):
    return {"devices": await request.app.state.intune.list_managed_devices(top=top)}


@router.get("/intune/devices/{device_id}")
async def intune_device_detail(request: Request, device_id: str):
    result = await request.app.state.intune.get_device(device_id)
    if not result:
        raise HTTPException(status_code=404, detail="Device not found")
    return result


@router.post("/intune/devices/{device_id}/action")
async def intune_device_action(request: Request, device_id: str, body: DeviceActionRequest):
    return await request.app.state.intune.trigger_device_action(device_id, body.action)


@router.get("/intune/compliance")
async def intune_compliance(request: Request):
    return {"policies": await request.app.state.intune.get_compliance_policies()}


# ── Entra ID ────────────────────────────────────────────────

@router.get("/entra/risky-users")
async def entra_risky_users(request: Request, risk_level: Optional[str] = None):
    return {"users": await request.app.state.entra.get_risky_users(risk_level=risk_level)}


@router.get("/entra/risk-detections")
async def entra_risk_detections(request: Request, top: int = Query(50, le=200)):
    return {"detections": await request.app.state.entra.get_risk_detections(top=top)}


@router.get("/entra/sign-ins")
async def entra_sign_ins(request: Request, top: int = Query(100, le=500)):
    return {"signIns": await request.app.state.entra.get_sign_in_logs(top=top)}


@router.get("/entra/conditional-access")
async def entra_conditional_access(request: Request):
    return {"policies": await request.app.state.entra.get_conditional_access_policies()}
