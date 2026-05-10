# ============================================================
#  HEALIX Integration API v1 — routers/integration.py
#  Versioned REST API (/api/v1/*) for external tool integration.
#  Features: Bearer API key auth, sliding-window rate limiting,
#  standard response envelope, webhook push notifications.
# ============================================================

import asyncio
import hashlib
import hmac
import json
import logging
import os
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Optional, List, Dict

import httpx
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

logger = logging.getLogger("healix.integration")

router = APIRouter(prefix="/api/v1", tags=["Integration API v1"])

# ── Auth + Rate Limiting ─────────────────────────────────────

_security = HTTPBearer(auto_error=False)
_rate_windows: Dict[str, deque] = defaultdict(deque)


def verify_api_key(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_security),
):
    """Validate Bearer API key and enforce sliding-window rate limiting."""
    config = getattr(request.app.state, "config", None)
    configured_key = ""
    rate_limit = 100
    if config and hasattr(config, "integration_api"):
        configured_key = config.integration_api.api_key
        rate_limit = config.integration_api.rate_limit_per_minute

    # If no key configured → dev mode, skip check
    if not configured_key:
        return "unconfigured"

    if not credentials or credentials.credentials != configured_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")

    # Sliding-window rate limit (per key, per minute)
    key = credentials.credentials
    window = _rate_windows[key]
    now = datetime.now(timezone.utc).timestamp()
    # Remove timestamps older than 60 seconds
    while window and window[0] < now - 60:
        window.popleft()
    if len(window) >= rate_limit:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded: {rate_limit} requests per minute",
        )
    window.append(now)
    return key


# ── Response envelope ────────────────────────────────────────

def _envelope(data, success: bool = True) -> Dict:
    return {
        "success": success,
        "data": data,
        "timestamp": _now(),
        "version": "1.0",
    }


# ── Pydantic models ──────────────────────────────────────────

class QueryRequest(BaseModel):
    question: str
    endpoint_context: Optional[str] = None


class RemediateRequest(BaseModel):
    endpoint_id: str
    issue_type: str


class EventRequest(BaseModel):
    source: str
    severity: str = "info"
    message: str
    endpoint_name: Optional[str] = ""
    category: Optional[str] = ""
    raw_data: Optional[dict] = None


class WebhookRegisterRequest(BaseModel):
    url: str
    events: List[str] = ["all"]
    description: Optional[str] = ""
    api_key_hint: Optional[str] = ""
    secret: Optional[str] = ""


# ── Endpoints ────────────────────────────────────────────────

@router.get("/status")
async def v1_status(request: Request, _key: str = Depends(verify_api_key)):
    """Platform health and all integration statuses."""
    app = request.app

    def _avail(attr):
        c = getattr(app.state, attr, None)
        return c.is_available if c else False

    return _envelope({
        "platform": "HEALIX",
        "version": "2.0.0",
        "services": {
            "defender": _avail("defender"),
            "sentinel": _avail("sentinel"),
            "intune": _avail("intune"),
            "entra": _avail("entra"),
            "azure_monitor": _avail("azure_monitor"),
            "aws": _avail("aws"),
            "foundry": _avail("foundry"),
        },
        "agent_provider": getattr(getattr(app.state, "agent", None), "_llm_provider", "unknown"),
    })


@router.get("/endpoints")
async def v1_endpoints(request: Request, _key: str = Depends(verify_api_key)):
    """All monitored endpoints across on-prem, Azure, and AWS."""
    db = request.app.state.db
    endpoints = await db.get_endpoints()
    if not endpoints:
        agent = request.app.state.agent
        endpoints = agent.get_endpoint_status()
    return _envelope({"endpoints": endpoints, "count": len(endpoints)})


@router.get("/alerts")
async def v1_alerts(request: Request, _key: str = Depends(verify_api_key)):
    """Active alerts with recommended actions."""
    db = request.app.state.db
    agent = request.app.state.agent
    alert_engine = getattr(request.app.state, "alert_engine", None)

    db_alerts = await db.get_alerts(resolved=False, limit=50)
    if db_alerts:
        # Attach recommended action based on alert type
        for a in db_alerts:
            a["recommended_action"] = _recommended_action(a)
        return _envelope({
            "alerts": db_alerts,
            "critical_count": sum(1 for a in db_alerts if a.get("alert_type") == "critical"),
            "warning_count": sum(1 for a in db_alerts if a.get("alert_type") == "warning"),
        })

    alerts = agent.get_alerts()
    for a in alerts:
        a["recommended_action"] = _recommended_action(a)
    return _envelope({
        "alerts": alerts,
        "critical_count": sum(1 for a in alerts if a.get("type") == "critical"),
        "warning_count": sum(1 for a in alerts if a.get("type") == "warning"),
    })


@router.get("/incidents")
async def v1_incidents(request: Request, _key: str = Depends(verify_api_key)):
    """Defender and Sentinel incidents."""
    defender = getattr(request.app.state, "defender", None)
    sentinel = getattr(request.app.state, "sentinel", None)

    defender_incidents = []
    sentinel_incidents = []

    if defender and defender.is_available:
        try:
            defender_incidents = await defender.get_incidents(top=10) or []
        except Exception:
            pass

    if sentinel and sentinel.is_available:
        try:
            sentinel_incidents = await sentinel.get_incidents(limit=10) or []
        except Exception:
            pass

    return _envelope({
        "defender_incidents": defender_incidents,
        "sentinel_incidents": sentinel_incidents,
        "total": len(defender_incidents) + len(sentinel_incidents),
    })


@router.post("/query")
async def v1_query(
    request: Request,
    body: QueryRequest,
    _key: str = Depends(verify_api_key),
):
    """Ask the HEALIX AI agent a question."""
    if not body.question.strip():
        raise HTTPException(status_code=400, detail="question cannot be empty")

    agent = request.app.state.agent
    result = await agent.ask(question=body.question, context=body.endpoint_context)
    return _envelope({
        "question": body.question,
        "answer": result["answer"],
        "sources": result.get("sources", []),
        "confidence": result.get("confidence", 0.85),
        "provider": getattr(agent, "_llm_provider", "unknown"),
    })


@router.post("/remediate")
async def v1_remediate(
    request: Request,
    body: RemediateRequest,
    _key: str = Depends(verify_api_key),
):
    """Trigger auto-remediation on an endpoint."""
    agent = request.app.state.agent
    result = await agent.trigger_remediation(
        endpoint_id=body.endpoint_id,
        issue_type=body.issue_type,
    )
    return _envelope(result)


@router.post("/events")
async def v1_events(
    request: Request,
    body: EventRequest,
    _key: str = Depends(verify_api_key),
):
    """Push external events/logs into HEALIX for correlation and alerting."""
    db = request.app.state.db
    log_id = await db.insert_log(
        timestamp=_now(),
        source=body.source,
        source_service="integration_api",
        severity=body.severity,
        category=body.category or "",
        endpoint_name=body.endpoint_name or "",
        message=body.message,
        raw_data=body.raw_data,
    )
    return _envelope({"log_id": log_id, "ingested": True, "source": body.source})


@router.get("/compliance")
async def v1_compliance(request: Request, _key: str = Depends(verify_api_key)):
    """Compliance posture scores and active gaps."""
    db = request.app.state.db
    posture = await db.get_latest_posture()
    gaps = await db.get_compliance_gaps()
    return _envelope({
        "posture": posture or {"overall_score": 0, "note": "No posture data yet"},
        "gaps": gaps[:20],
        "gap_count": len(gaps),
    })


@router.post("/webhook/register")
async def v1_webhook_register(
    request: Request,
    body: WebhookRegisterRequest,
    _key: str = Depends(verify_api_key),
):
    """Register a webhook to receive push notifications for HEALIX events."""
    db = request.app.state.db
    if not body.url.startswith("https://") and not body.url.startswith("http://"):
        raise HTTPException(status_code=400, detail="URL must start with http:// or https://")

    events_json = json.dumps(body.events)
    api_key_hint = body.api_key_hint or ""
    if len(api_key_hint) > 4:
        api_key_hint = api_key_hint[:4] + "****"

    webhook_id = await db.insert_webhook(
        url=body.url,
        events=events_json,
        description=body.description or "",
        api_key_hint=api_key_hint,
        secret=body.secret or "",
    )
    return _envelope({
        "webhook_id": webhook_id,
        "url": body.url,
        "events": body.events,
        "registered": True,
    })


@router.get("/webhook/list")
async def v1_webhook_list(request: Request, _key: str = Depends(verify_api_key)):
    """List all active webhooks."""
    db = request.app.state.db
    webhooks = await db.get_webhooks(active_only=True)
    # Mask secrets before returning
    safe = []
    for w in webhooks:
        entry = dict(w)
        if entry.get("secret"):
            entry["secret"] = "****"
        safe.append(entry)
    return _envelope({"webhooks": safe, "count": len(safe)})


@router.delete("/webhook/{webhook_id}")
async def v1_webhook_delete(
    request: Request,
    webhook_id: int,
    _key: str = Depends(verify_api_key),
):
    """Deactivate (soft-delete) a registered webhook."""
    db = request.app.state.db
    await db.deactivate_webhook(webhook_id)
    return _envelope({"webhook_id": webhook_id, "deactivated": True})


# ── Webhook delivery (called by alert_engine via asyncio.create_task) ─────

async def deliver_webhooks(app, alert: Dict, event_type: str = "alert"):
    """Fire-and-forget: POST alert payload to all subscribed webhooks."""
    db = app.state.db
    try:
        webhooks = await db.get_webhooks(active_only=True)
    except Exception as e:
        logger.error(f"deliver_webhooks: failed to load webhooks: {e}")
        return

    if not webhooks:
        return

    payload = {
        "event_type": event_type,
        "alert": alert,
        "timestamp": _now(),
        "source": "healix",
        "version": "1.0",
    }
    payload_bytes = json.dumps(payload).encode()

    for webhook in webhooks:
        # Check event subscription ("all" matches everything)
        try:
            subscribed = json.loads(webhook.get("events", '["all"]'))
        except Exception:
            subscribed = ["all"]
        if "all" not in subscribed and event_type not in subscribed:
            continue

        wh_id = webhook["id"]
        alert_id = alert.get("id")
        event_id = None
        try:
            event_id = await db.insert_webhook_event(
                webhook_id=wh_id,
                alert_id=alert_id,
                event_type=event_type,
                payload=payload_bytes.decode(),
            )
        except Exception:
            pass

        # Dispatch the HTTP POST
        try:
            headers = {"Content-Type": "application/json"}
            secret = webhook.get("secret", "")
            if secret:
                sig = hmac.new(secret.encode(), payload_bytes, hashlib.sha256).hexdigest()
                headers["X-HEALIX-Signature"] = f"sha256={sig}"

            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(webhook["url"], content=payload_bytes, headers=headers)

            http_status = resp.status_code
            error_msg = "" if resp.is_success else resp.text[:200]
            logger.info(f"Webhook {wh_id} delivered: HTTP {http_status}")
        except Exception as e:
            http_status = 0
            error_msg = str(e)[:200]
            logger.warning(f"Webhook {wh_id} delivery failed: {e}")

        if event_id:
            try:
                await db.mark_webhook_delivered(event_id, http_status, error_msg)
            except Exception:
                pass


# ── Helpers ──────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _recommended_action(alert: Dict) -> str:
    severity = alert.get("alert_type") or alert.get("type", "")
    title = (alert.get("title") or "").lower()
    desc = (alert.get("description") or "").lower()

    if "cpu" in title or "cpu" in desc:
        return "Kill zombie processes and restart affected service"
    if "memory" in title or "memory" in desc or "mem" in desc:
        return "Restart service to free memory; consider scaling"
    if "disk" in title or "disk" in desc:
        return "Archive old logs and clean package cache"
    if "service" in title or "down" in title:
        return "Restart failed service and verify health check"
    if "patch" in title or "cve" in title or "vuln" in desc:
        return "Apply security patch during next maintenance window"
    if severity == "critical":
        return "Investigate immediately — critical alert"
    if severity == "warning":
        return "Monitor and prepare remediation runbook"
    return "Review alert details and take appropriate action"
