# ============================================================
#  HEALIX Workflows Router — routers/workflows.py
# ============================================================

from fastapi import APIRouter, Request, Query

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models import WorkflowTriageRequest, WorkflowMitigateRequest

router = APIRouter(prefix="/api/workflows", tags=["Workflow Automation"])


@router.post("/triage")
async def triage_incident(request: Request, body: WorkflowTriageRequest):
    """Automated incident triage with AI analysis."""
    result = await request.app.state.workflow_engine.triage_incident(
        incident_id=body.incident_id,
        source=body.source,
    )
    return result


@router.post("/mitigate")
async def apply_mitigation(request: Request, body: WorkflowMitigateRequest):
    """Execute a mitigation action on a target."""
    result = await request.app.state.workflow_engine.apply_mitigation(
        action_type=body.action_type,
        target_id=body.target_id,
        target_type=body.target_type,
        reason=body.reason,
    )
    return result


@router.get("/history")
async def workflow_history(request: Request, limit: int = Query(50, le=200)):
    actions = await request.app.state.workflow_engine.get_workflow_history(limit=limit)
    return {"actions": actions, "count": len(actions)}
