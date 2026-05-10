# ============================================================
#  HEALIX Dashboards Router — routers/dashboards.py
#  Composite endpoints that aggregate data for dashboards.
# ============================================================

from fastapi import APIRouter, Request

router = APIRouter(prefix="/api/dashboards", tags=["Dashboards"])


@router.get("/executive")
async def executive_dashboard(request: Request):
    """High-level KPIs for executive view."""
    overview = await request.app.state.monitoring_engine.get_system_overview()
    posture = await request.app.state.db.get_latest_posture()
    alert_stats = await request.app.state.db.get_alert_stats()
    healing_stats = await request.app.state.db.get_healing_stats()

    secure_score = None
    if request.app.state.defender:
        secure_score = await request.app.state.defender.get_secure_score()

    return {
        "overview": overview,
        "security_posture": posture,
        "secure_score": secure_score,
        "alerts": alert_stats,
        "healing": healing_stats,
    }


@router.get("/security")
async def security_dashboard(request: Request):
    """Security-focused: threats, incidents, posture."""
    incidents = await request.app.state.defender.get_incidents(top=10)
    alerts = await request.app.state.defender.get_security_alerts(top=10)
    risky_users = await request.app.state.entra.get_risky_users()
    posture = await request.app.state.db.get_latest_posture()
    anomalies = await request.app.state.monitoring_engine.detect_anomalies()

    return {
        "incidents": incidents[:5],
        "security_alerts": alerts[:5],
        "risky_users": risky_users[:5],
        "posture": posture,
        "anomalies": anomalies[:5],
    }


@router.get("/operations")
async def operations_dashboard(request: Request):
    """Operations-focused: alerts, healing, performance."""
    overview = await request.app.state.monitoring_engine.get_system_overview()
    active_alerts = await request.app.state.db.get_alerts(resolved=False, limit=10)
    healing = await request.app.state.db.get_healing_actions(limit=10)
    healing_stats = await request.app.state.db.get_healing_stats()
    anomalies = await request.app.state.monitoring_engine.detect_anomalies()

    return {
        "overview": overview,
        "active_alerts": active_alerts,
        "recent_healing": healing,
        "healing_stats": healing_stats,
        "anomalies": anomalies,
    }


@router.get("/compliance")
async def compliance_dashboard(request: Request):
    """Compliance-focused: scores, gaps, trends."""
    posture = await request.app.state.db.get_latest_posture()
    history = await request.app.state.db.get_posture_history(limit=14)
    gaps = await request.app.state.db.get_compliance_gaps()

    return {
        "posture": posture,
        "trend": history,
        "gaps": gaps[:10],
        "gap_count": len(gaps),
    }
