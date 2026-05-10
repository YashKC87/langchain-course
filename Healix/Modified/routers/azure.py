# ============================================================
#  HEALIX Azure VM Router — routers/azure.py
#  Exposes agentless Azure VM monitoring via ARM API.
# ============================================================

from datetime import datetime, timezone
from fastapi import APIRouter, Request, HTTPException, Query
from typing import Optional

router = APIRouter(prefix="/api/azure", tags=["Azure Monitor"])


@router.get("/status")
async def azure_status(request: Request):
    """Return Azure Monitor client availability."""
    client = getattr(request.app.state, "azure_monitor", None)
    config = getattr(request.app.state, "config", None)

    available = client.is_available if client else False
    sub_id = ""
    if config and hasattr(config, "sentinel"):
        sub_id = config.sentinel.subscription_id

    return {
        "available": available,
        "subscription_id": sub_id or "(not configured)",
        "demo_mode": not available,
        "timestamp": _now(),
    }


@router.get("/vms")
async def list_azure_vms(request: Request):
    """List all Azure VMs with power state and health status."""
    client = getattr(request.app.state, "azure_monitor", None)
    if not client:
        raise HTTPException(status_code=503, detail="Azure Monitor client not initialized")

    vms = await client.list_vms()
    demo = any(vm.get("_demo") for vm in vms)
    # Strip internal _demo flag before returning
    clean = [{k: v for k, v in vm.items() if k != "_demo"} for vm in vms]
    return {
        "vms": clean,
        "count": len(clean),
        "demo": demo,
        "timestamp": _now(),
    }


@router.get("/vm/{vm_name}/status")
async def get_vm_status(
    request: Request,
    vm_name: str,
    resource_group: str = Query(..., description="Azure resource group name"),
):
    """Get instance view and power state for a single Azure VM."""
    client = getattr(request.app.state, "azure_monitor", None)
    if not client:
        raise HTTPException(status_code=503, detail="Azure Monitor client not initialized")

    result = await client.get_vm_status(resource_group=resource_group, vm_name=vm_name)
    return result


@router.get("/vm/{vm_name}/metrics")
async def get_vm_metrics(
    request: Request,
    vm_name: str,
    resource_group: str = Query(..., description="Azure resource group name"),
    hours: int = Query(1, ge=1, le=72, description="Number of hours of metrics to return"),
):
    """Get Azure Monitor performance metrics for a VM."""
    client = getattr(request.app.state, "azure_monitor", None)
    if not client:
        raise HTTPException(status_code=503, detail="Azure Monitor client not initialized")

    metrics = await client.get_vm_metrics(
        resource_group=resource_group, vm_name=vm_name, hours=hours
    )
    return {
        "vm_name": vm_name,
        "resource_group": resource_group,
        "hours": hours,
        "metrics": metrics,
        "timestamp": _now(),
    }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
