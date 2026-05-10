# ============================================================
#  HEALIX AWS Router — routers/aws.py
#  Exposes agentless AWS EC2 / CloudWatch monitoring endpoints.
# ============================================================

from datetime import datetime, timezone
from fastapi import APIRouter, Request, HTTPException, Query

router = APIRouter(prefix="/api/aws", tags=["AWS EC2"])

try:
    import boto3
    _BOTO3_INSTALLED = True
except ImportError:
    _BOTO3_INSTALLED = False


@router.get("/status")
async def aws_status(request: Request):
    """Return AWS client availability and configuration status."""
    client = getattr(request.app.state, "aws", None)
    config = getattr(request.app.state, "config", None)

    available = client.is_available if client else False
    region = "us-east-1"
    if config and hasattr(config, "aws"):
        region = config.aws.region

    return {
        "available": available,
        "region": region,
        "demo_mode": not available,
        "boto3_installed": _BOTO3_INSTALLED,
        "timestamp": _now(),
    }


@router.get("/instances")
async def list_aws_instances(request: Request):
    """List all EC2 instances with state and health status."""
    client = getattr(request.app.state, "aws", None)
    if not client:
        raise HTTPException(status_code=503, detail="AWS client not initialized")

    instances = await client.list_instances()
    demo = any(inst.get("_demo") for inst in instances)
    clean = [{k: v for k, v in inst.items() if k != "_demo"} for inst in instances]
    return {
        "instances": clean,
        "count": len(clean),
        "demo": demo,
        "timestamp": _now(),
    }


@router.get("/instance/{instance_id}/status")
async def get_instance_status(request: Request, instance_id: str):
    """Get EC2 instance status check results."""
    client = getattr(request.app.state, "aws", None)
    if not client:
        raise HTTPException(status_code=503, detail="AWS client not initialized")

    status = await client.get_instance_status(instance_id)
    ssm_info = await client.get_ssm_instance_info(instance_id)
    return {
        "instance_id": instance_id,
        "status": status,
        "ssm": ssm_info,
        "timestamp": _now(),
    }


@router.get("/instance/{instance_id}/metrics")
async def get_instance_metrics(
    request: Request,
    instance_id: str,
    hours: int = Query(1, ge=1, le=72, description="Number of hours of metrics to return"),
):
    """Get CloudWatch performance metrics for an EC2 instance."""
    client = getattr(request.app.state, "aws", None)
    if not client:
        raise HTTPException(status_code=503, detail="AWS client not initialized")

    metrics = await client.get_instance_metrics(instance_id, hours=hours)
    return {
        "instance_id": instance_id,
        "hours": hours,
        "metrics": metrics,
        "timestamp": _now(),
    }


@router.get("/instance/{instance_id}/logs")
async def get_instance_logs(
    request: Request,
    instance_id: str,
    log_group: str = Query("/aws/ec2/user-data", description="CloudWatch log group name"),
    hours: int = Query(1, ge=1, le=72, description="Number of hours of logs to return"),
):
    """Fetch CloudWatch log events for an EC2 instance."""
    client = getattr(request.app.state, "aws", None)
    if not client:
        raise HTTPException(status_code=503, detail="AWS client not initialized")

    events = await client.get_instance_logs(instance_id, log_group=log_group, hours=hours)
    return {
        "instance_id": instance_id,
        "log_group": log_group,
        "hours": hours,
        "events": events,
        "count": len(events),
        "timestamp": _now(),
    }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
