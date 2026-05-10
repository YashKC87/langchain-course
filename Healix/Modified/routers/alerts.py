# ============================================================
#  HEALIX Alerts Router — routers/alerts.py
# ============================================================

import json
from fastapi import APIRouter, Request, HTTPException, Query
from typing import Optional

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models import AlertResolveRequest, AlertRuleCreateRequest, AlertRuleUpdateRequest

router = APIRouter(prefix="/api/alerts", tags=["Alerts"])


@router.get("")
@router.get("/list")
async def list_alerts(request: Request, resolved: Optional[bool] = None,
                      alert_type: Optional[str] = None,
                      limit: int = Query(50, le=500)):
    alerts = await request.app.state.db.get_alerts(
        resolved=resolved, alert_type=alert_type, limit=limit
    )
    return {
        "alerts": alerts,
        "count": len(alerts),
        "critical_count": len([a for a in alerts if a.get("alert_type") == "critical"]),
        "warning_count": len([a for a in alerts if a.get("alert_type") == "warning"]),
    }


@router.get("/stats")
async def alert_stats(request: Request):
    return await request.app.state.db.get_alert_stats()


@router.get("/rules")
async def list_alert_rules(request: Request):
    rules = await request.app.state.db.get_alert_rules(enabled_only=False)
    return {"rules": rules}


@router.post("/rules")
async def create_alert_rule(request: Request, body: AlertRuleCreateRequest):
    rule_id = await request.app.state.db.insert_alert_rule(
        name=body.name,
        source=body.source,
        condition_json=json.dumps(body.condition_json),
        severity=body.severity,
        description=body.description,
        delivery_channels=json.dumps(body.delivery_channels),
        cooldown_minutes=body.cooldown_minutes,
    )
    return {"id": rule_id, "name": body.name, "status": "created"}


@router.put("/rules/{rule_id}")
async def update_alert_rule(request: Request, rule_id: int, body: AlertRuleUpdateRequest):
    updates = {}
    if body.name is not None:
        updates["name"] = body.name
    if body.description is not None:
        updates["description"] = body.description
    if body.source is not None:
        updates["source"] = body.source
    if body.condition_json is not None:
        updates["condition_json"] = json.dumps(body.condition_json)
    if body.severity is not None:
        updates["severity"] = body.severity
    if body.delivery_channels is not None:
        updates["delivery_channels"] = json.dumps(body.delivery_channels)
    if body.cooldown_minutes is not None:
        updates["cooldown_minutes"] = body.cooldown_minutes
    if body.enabled is not None:
        updates["enabled"] = 1 if body.enabled else 0

    if updates:
        await request.app.state.db.update_alert_rule(rule_id, **updates)
    return {"id": rule_id, "status": "updated"}


@router.delete("/rules/{rule_id}")
async def delete_alert_rule(request: Request, rule_id: int):
    await request.app.state.db.delete_alert_rule(rule_id)
    return {"id": rule_id, "status": "deleted"}


@router.get("/{alert_id}")
async def get_alert(request: Request, alert_id: int):
    alert = await request.app.state.db.get_alert_by_id(alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return alert


@router.post("/{alert_id}/resolve")
async def resolve_alert(request: Request, alert_id: int,
                        body: AlertResolveRequest = AlertResolveRequest()):
    alert = await request.app.state.db.get_alert_by_id(alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    await request.app.state.alert_engine.resolve_alert(alert_id, body.resolved_by)
    return {"id": alert_id, "status": "resolved", "resolved_by": body.resolved_by}
