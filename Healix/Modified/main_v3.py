# ============================================================
#  HEALIX — main.py (Intune + ManageEngine Edition)
# ============================================================

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import asyncio
from datetime import datetime

from agent import HealIXAgent
from device_monitor import DeviceManager, DEVICE_CONFIG
from intune_connector import IntuneConnector
from manageengine_connector import ManageEngineConnector

app = FastAPI(
    title="HEALIX API",
    description="Autonomous Infrastructure Healing — Intune + ManageEngine Edition",
    version="3.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Initialize all systems ────────────────────────────────────
print("\n" + "="*55)
print("  HEALIX v3.0 — Initializing all connectors...")
print("="*55)

agent         = HealIXAgent()
device_mgr    = DeviceManager(DEVICE_CONFIG)
intune        = IntuneConnector()
manage_engine = ManageEngineConnector()

print("="*55 + "\n")

# ── Request models ────────────────────────────────────────────
class ChatRequest(BaseModel):
    question: str
    endpoint_context: Optional[str] = None

class RemediationRequest(BaseModel):
    endpoint_id: str
    issue_type: str

class PatchDeployRequest(BaseModel):
    patch_id: str
    computer_ids: List[str]
    schedule_time: Optional[str] = None  # "2024-12-01 02:00:00"

class RemoteScriptRequest(BaseModel):
    computer_id: str
    script: str
    script_type: str = "powershell"   # "powershell" or "batch"

class ServiceDeskTicketRequest(BaseModel):
    subject: str
    description: str
    device_name: Optional[str] = None
    priority: str = "High"
    category: str = "Software"

class AddDeviceRequest(BaseModel):
    id: str
    name: str
    type: str
    group: Optional[str] = "Default"
    tags: Optional[List[str]] = []
    host: Optional[str] = None
    port: Optional[int] = 22
    username: Optional[str] = None
    password: Optional[str] = None
    sim_profile: Optional[str] = "healthy"

# ════════════════════════════════════════════════════════════
#  GENERAL ROUTES
# ════════════════════════════════════════════════════════════

@app.get("/")
async def root():
    return {
        "product":  "HEALIX",
        "version":  "3.0.0",
        "status":   "online",
        "connectors": {
            "intune":        "connected" if intune.connected        else "disconnected",
            "manageengine":  "connected" if manage_engine.connected else "disconnected",
            "local_devices": len(device_mgr.device_configs),
        },
        "docs": "http://localhost:8000/docs"
    }

@app.get("/health")
async def health():
    return {
        "status":          "healthy",
        "intune":          intune.connected,
        "manageengine":    manage_engine.connected,
        "timestamp":       datetime.utcnow().isoformat()
    }

# ════════════════════════════════════════════════════════════
#  UNIFIED DASHBOARD — ALL sources in one call
# ════════════════════════════════════════════════════════════

@app.get("/api/dashboard")
async def get_full_dashboard():
    """
    Single endpoint that returns EVERYTHING for the dashboard.
    Combines Intune + ManageEngine + local devices + AI alerts.
    This is the main endpoint your frontend should call.
    """
    loop = asyncio.get_event_loop()

    # Run all data fetches concurrently (much faster than one by one)
    local_task   = device_mgr.collect_all_async()
    intune_task  = loop.run_in_executor(None, intune.get_all_devices)
    me_cpu_task  = loop.run_in_executor(None, manage_engine.get_cpu_report)
    me_mem_task  = loop.run_in_executor(None, manage_engine.get_memory_report)
    me_disk_task = loop.run_in_executor(None, manage_engine.get_disk_report)

    (local_devices, intune_raw,
     me_cpu, me_mem, me_disk) = await asyncio.gather(
        local_task, intune_task, me_cpu_task, me_mem_task, me_disk_task
    )

    # Normalize each source to HEALIX format
    intune_devices = intune.normalize_devices(intune_raw)
    me_raw         = await loop.run_in_executor(None, manage_engine.get_all_computers)
    me_devices     = manage_engine.normalize_computers(me_raw, me_cpu, me_mem, me_disk)

    # Merge all devices from all sources
    all_devices = local_devices + intune_devices + me_devices

    # Generate alerts from each source
    intune_alerts = intune.generate_alerts(intune_devices)
    me_alerts     = manage_engine.generate_alerts(me_devices)
    agent_alerts  = agent.get_alerts()
    all_alerts    = agent_alerts + intune_alerts + me_alerts

    # Build summary
    summary = device_mgr.get_summary(all_devices)
    summary["by_source"] = {
        "local":         len(local_devices),
        "intune":        len(intune_devices),
        "manageengine":  len(me_devices),
    }

    return {
        "summary":        summary,
        "devices":        all_devices,
        "active_alerts":  [a for a in all_alerts if not a.get("resolved", False)],
        "healing_actions":agent.get_healing_actions()[:5],
        "timestamp":      datetime.utcnow().isoformat(),
    }


# ════════════════════════════════════════════════════════════
#  MICROSOFT INTUNE ROUTES
# ════════════════════════════════════════════════════════════

@app.get("/api/intune/devices")
async def intune_get_devices(
    os_filter: Optional[str] = Query(None, description="Filter by OS: windows, ios, android, macos"),
    compliance: Optional[str] = Query(None, description="Filter: compliant, noncompliant, unknown"),
    stale_only: bool = Query(False, description="Show only devices not synced in 7+ days")
):
    """
    Get all Intune-managed devices with optional filtering.

    Examples:
    - /api/intune/devices?os_filter=windows
    - /api/intune/devices?compliance=noncompliant
    - /api/intune/devices?stale_only=true
    """
    if not intune.connected:
        raise HTTPException(status_code=503,
            detail="Intune not connected. Check INTUNE_* vars in .env file.")

    loop     = asyncio.get_event_loop()
    raw      = await loop.run_in_executor(None, intune.get_all_devices)
    devices  = intune.normalize_devices(raw)

    # Apply filters
    if os_filter:
        devices = [d for d in devices if os_filter.lower() in " ".join(d.get("tags",[])).lower()]
    if compliance:
        devices = [d for d in devices if d.get("compliance") == compliance]
    if stale_only:
        devices = [d for d in devices if d.get("days_since_sync", 0) > 7]

    summary = intune.get_summary_stats(devices)
    return {
        "devices":  devices,
        "count":    len(devices),
        "summary":  summary,
        "filters_applied": {
            "os": os_filter, "compliance": compliance, "stale_only": stale_only
        }
    }

@app.get("/api/intune/devices/{intune_device_id}")
async def intune_get_device(intune_device_id: str):
    """Get full detail for one Intune device (raw Graph API data)"""
    if not intune.connected:
        raise HTTPException(status_code=503, detail="Intune not connected")
    loop = asyncio.get_event_loop()
    detail = await loop.run_in_executor(None, intune.get_device_detail, intune_device_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Device not found in Intune")
    return detail

@app.get("/api/intune/compliance")
async def intune_compliance_report():
    """Get full compliance report — which devices are compliant/non-compliant"""
    if not intune.connected:
        raise HTTPException(status_code=503, detail="Intune not connected")
    loop    = asyncio.get_event_loop()
    raw     = await loop.run_in_executor(None, intune.get_all_devices)
    devices = intune.normalize_devices(raw)

    compliant     = [d for d in devices if d.get("compliance") == "compliant"]
    non_compliant = [d for d in devices if d.get("compliance") == "noncompliant"]
    unknown       = [d for d in devices if d.get("compliance") not in ["compliant","noncompliant"]]

    return {
        "total":          len(devices),
        "compliant":       {"count": len(compliant),     "devices": compliant},
        "non_compliant":   {"count": len(non_compliant), "devices": non_compliant},
        "unknown":         {"count": len(unknown),       "devices": unknown},
        "compliance_pct":  round(len(compliant) / len(devices) * 100, 1) if devices else 0,
    }

@app.get("/api/intune/alerts")
async def intune_alerts():
    """Get all alerts generated from Intune device data"""
    if not intune.connected:
        raise HTTPException(status_code=503, detail="Intune not connected")
    loop    = asyncio.get_event_loop()
    raw     = await loop.run_in_executor(None, intune.get_all_devices)
    devices = intune.normalize_devices(raw)
    alerts  = intune.generate_alerts(devices)
    return {
        "alerts":    alerts,
        "count":     len(alerts),
        "critical":  len([a for a in alerts if a["type"] == "critical"]),
        "warning":   len([a for a in alerts if a["type"] == "warning"]),
    }

@app.get("/api/intune/whfb/{device_id}")
async def intune_whfb_status(device_id: str):
    """
    Get Windows Hello for Business status for a specific device.
    Useful for your WHFB deployment troubleshooting!
    """
    if not intune.connected:
        raise HTTPException(status_code=503, detail="Intune not connected")
    loop   = asyncio.get_event_loop()
    status = await loop.run_in_executor(None, intune.get_whfb_status, device_id)
    return {"device_id": device_id, "whfb_status": status}

@app.get("/api/intune/stale-devices")
async def intune_stale_devices(days: int = Query(7, description="Days since last sync")):
    """Find devices that haven't checked in for N days"""
    if not intune.connected:
        raise HTTPException(status_code=503, detail="Intune not connected")
    loop    = asyncio.get_event_loop()
    raw     = await loop.run_in_executor(None, intune.get_all_devices)
    devices = intune.normalize_devices(raw)
    stale   = [d for d in devices if d.get("days_since_sync", 0) > days]
    return {
        "threshold_days": days,
        "stale_count":    len(stale),
        "stale_devices":  stale
    }

@app.get("/api/intune/summary")
async def intune_summary():
    """High-level Intune stats for the dashboard header"""
    if not intune.connected:
        raise HTTPException(status_code=503, detail="Intune not connected")
    loop    = asyncio.get_event_loop()
    raw     = await loop.run_in_executor(None, intune.get_all_devices)
    devices = intune.normalize_devices(raw)
    return intune.get_summary_stats(devices)


# ════════════════════════════════════════════════════════════
#  MANAGEENGINE ROUTES
# ════════════════════════════════════════════════════════════

@app.get("/api/manageengine/devices")
async def me_get_devices():
    """Get all computers managed by ManageEngine with live metrics"""
    if not manage_engine.connected:
        raise HTTPException(status_code=503,
            detail="ManageEngine not connected. Check ME_BASE_URL and ME_API_KEY in .env")

    loop      = asyncio.get_event_loop()
    computers = await loop.run_in_executor(None, manage_engine.get_all_computers)
    cpu_data  = await loop.run_in_executor(None, manage_engine.get_cpu_report)
    mem_data  = await loop.run_in_executor(None, manage_engine.get_memory_report)
    disk_data = await loop.run_in_executor(None, manage_engine.get_disk_report)

    devices   = manage_engine.normalize_computers(computers, cpu_data, mem_data, disk_data)
    return {"devices": devices, "count": len(devices)}

@app.get("/api/manageengine/devices/{computer_id}")
async def me_get_device(computer_id: str):
    """Get detailed info for one ManageEngine-managed computer"""
    if not manage_engine.connected:
        raise HTTPException(status_code=503, detail="ManageEngine not connected")
    loop   = asyncio.get_event_loop()
    detail = await loop.run_in_executor(None, manage_engine.get_computer_detail, computer_id)
    return detail

@app.get("/api/manageengine/patches")
async def me_patch_report(
    severity: Optional[str] = Query(None, description="critical | important | moderate | low")
):
    """Get patch compliance report from ManageEngine"""
    if not manage_engine.connected:
        raise HTTPException(status_code=503, detail="ManageEngine not connected")
    loop    = asyncio.get_event_loop()
    missing = await loop.run_in_executor(
        None, manage_engine.get_missing_patches, severity
    )
    return {
        "missing_patches": missing,
        "count":           len(missing),
        "severity_filter": severity
    }

@app.post("/api/manageengine/patches/deploy")
async def me_deploy_patch(request: PatchDeployRequest):
    """
    Deploy a patch to a list of computers via ManageEngine.
    Optionally schedule for a specific time (e.g. maintenance window).
    """
    if not manage_engine.connected:
        raise HTTPException(status_code=503, detail="ManageEngine not connected")
    loop   = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        manage_engine.deploy_patch,
        request.patch_id,
        request.computer_ids,
        request.schedule_time
    )
    return result

@app.post("/api/manageengine/remote/script")
async def me_run_script(request: RemoteScriptRequest):
    """
    Run a PowerShell or batch script on a remote Windows device.
    Used by HEALIX auto-remediation engine.

    Example body:
    {
      "computer_id": "123",
      "script": "Restart-Service W3SVC",
      "script_type": "powershell"
    }
    """
    if not manage_engine.connected:
        raise HTTPException(status_code=503, detail="ManageEngine not connected")
    loop   = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        manage_engine.run_remote_script,
        request.computer_id,
        request.script,
        request.script_type
    )
    return result

@app.get("/api/manageengine/vulnerabilities")
async def me_vulnerabilities(computer_id: Optional[str] = None):
    """Get CVE vulnerability report from ManageEngine"""
    if not manage_engine.connected:
        raise HTTPException(status_code=503, detail="ManageEngine not connected")
    loop  = asyncio.get_event_loop()
    vulns = await loop.run_in_executor(
        None, manage_engine.get_vulnerabilities, computer_id
    )
    return {"vulnerabilities": vulns, "count": len(vulns)}

@app.post("/api/manageengine/servicedesk/ticket")
async def me_create_ticket(request: ServiceDeskTicketRequest):
    """Create a ServiceDesk Plus ticket for a detected issue"""
    loop   = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        manage_engine.create_ticket,
        request.subject,
        request.description,
        request.category,
        request.priority,
        request.device_name
    )
    return result

@app.get("/api/manageengine/alerts")
async def me_alerts():
    """Get alerts generated from ManageEngine live metrics"""
    if not manage_engine.connected:
        raise HTTPException(status_code=503, detail="ManageEngine not connected")

    loop      = asyncio.get_event_loop()
    computers = await loop.run_in_executor(None, manage_engine.get_all_computers)
    cpu_data  = await loop.run_in_executor(None, manage_engine.get_cpu_report)
    mem_data  = await loop.run_in_executor(None, manage_engine.get_memory_report)
    disk_data = await loop.run_in_executor(None, manage_engine.get_disk_report)

    devices   = manage_engine.normalize_computers(computers, cpu_data, mem_data, disk_data)
    alerts    = manage_engine.generate_alerts(devices)
    return {"alerts": alerts, "count": len(alerts)}


# ════════════════════════════════════════════════════════════
#  AI AGENT ROUTES (unchanged from before)
# ════════════════════════════════════════════════════════════

@app.post("/api/agent/chat")
async def chat_with_agent(request: ChatRequest):
    """Ask the AI agent a question — uses RAG + LLM"""
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    try:
        response = await agent.ask(
            question=request.question,
            context=request.endpoint_context
        )
        return {
            "question":      request.question,
            "answer":        response["answer"],
            "sources":       response.get("sources", []),
            "confidence":    response.get("confidence", 0.9),
            "actions_taken": response.get("actions_taken", []),
            "timestamp":     datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/healing/trigger")
async def trigger_healing(request: RemediationRequest):
    return await agent.trigger_remediation(
        endpoint_id=request.endpoint_id,
        issue_type=request.issue_type
    )

@app.get("/api/predictions")
async def get_predictions():
    predictions = await agent.predict_failures()
    return {"predictions": predictions}

@app.get("/api/patches")
async def get_patches():
    return {"patches": agent.get_patch_intelligence()}

# ── Local device routes ───────────────────────────────────────

@app.get("/api/devices")
async def get_local_devices():
    devices = await device_mgr.collect_all_async()
    return {"devices": devices, "count": len(devices)}

@app.post("/api/devices/add")
async def add_device(request: AddDeviceRequest):
    device_mgr.add_device(request.dict(exclude_none=True))
    return {"status": "added", "device": request.name}

# ── Run ───────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    print("\n" + "="*60)
    print("  HEALIX v3.0 — Intune + ManageEngine Monitoring")
    print("="*60)
    print(f"  Intune:        {'✅ Connected' if intune.connected else '⚠️  Not configured'}")
    print(f"  ManageEngine:  {'✅ Connected' if manage_engine.connected else '⚠️  Not configured'}")
    print(f"  Local devices: {len(device_mgr.device_configs)} configured")
    print("="*60)
    print("  API Docs  →  http://localhost:8000/docs")
    print("  Dashboard →  http://localhost:8000/api/dashboard")
    print("="*60 + "\n")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
