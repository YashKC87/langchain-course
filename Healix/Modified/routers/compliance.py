# ============================================================
#  HEALIX Compliance Router — routers/compliance.py
# ============================================================

from fastapi import APIRouter, Request, Query

router = APIRouter(prefix="/api/compliance", tags=["Compliance"])


@router.get("/posture")
async def get_posture(request: Request):
    """Get latest security posture scores."""
    posture = await request.app.state.db.get_latest_posture()
    if posture:
        return posture
    # Run fresh assessment if no snapshot exists
    return await request.app.state.compliance_engine.run_full_assessment()


@router.get("/posture/history")
async def get_posture_history(request: Request, limit: int = Query(30, le=365)):
    history = await request.app.state.db.get_posture_history(limit=limit)
    return {"history": history, "count": len(history)}


@router.get("/assessment")
async def run_assessment(request: Request):
    """Trigger a fresh compliance assessment."""
    scores = await request.app.state.compliance_engine.run_full_assessment()
    return scores


@router.get("/devices")
async def device_compliance(request: Request):
    findings = await request.app.state.compliance_engine.check_device_compliance()
    return {"findings": findings, "count": len(findings)}


@router.get("/identity")
async def identity_risks(request: Request):
    findings = await request.app.state.compliance_engine.check_identity_risks()
    return {"findings": findings, "count": len(findings)}


@router.get("/gaps")
async def compliance_gaps(request: Request):
    gaps = await request.app.state.db.get_compliance_gaps()
    return {"gaps": gaps, "count": len(gaps)}


@router.get("/recommendations")
async def recommendations(request: Request):
    gaps = await request.app.state.db.get_compliance_gaps()
    suggestions = await request.app.state.compliance_engine.get_remediation_suggestions(gaps)
    return {"recommendations": suggestions, "count": len(suggestions)}
