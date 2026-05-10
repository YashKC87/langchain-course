# ============================================================
#  HEALIX Backend API — main.py (v2.0)
#  Enhanced with Microsoft integrations, log pipeline,
#  alert engine, compliance, monitoring, and workflows.
# ============================================================

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import pathlib

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles

# ── Configuration and Database ──────────────────────────────
from config import load_config
from database import Database
from models import ChatRequest, RemediationRequest

# ── Integration Clients ─────────────────────────────────────
from integrations.defender_client import DefenderClient
from integrations.sentinel_client import SentinelClient
from integrations.intune_client import IntuneClient
from integrations.entra_client import EntraClient
from integrations.graph_notify import NotificationService
from integrations.azure_monitor_client import AzureMonitorClient
from integrations.aws_client import AWSClient
from integrations.foundry_client import FoundryClient

# ── Processing Engines ──────────────────────────────────────
from engines.log_pipeline import LogPipeline
from engines.alert_engine import AlertEngine
from engines.compliance_engine import ComplianceEngine
from engines.monitoring_engine import MonitoringEngine
from engines.workflow_engine import WorkflowEngine
from engines.usage_analytics import UsageAnalytics

# ── API Routers ─────────────────────────────────────────────
from routers import microsoft, logs, alerts, compliance, monitoring, dashboards, usage, workflows
from routers import azure, aws, foundry, integration

# ── AI Agent ────────────────────────────────────────────────
from agent import HealIXAgent

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("healix")


# ════════════════════════════════════════════════════════════
#  APPLICATION LIFECYCLE
# ════════════════════════════════════════════════════════════

@asynccontextmanager
async def lifespan(app):
    """Startup and shutdown lifecycle manager."""
    config = load_config()
    app.state.config = config

    logger.info("=" * 60)
    logger.info("  HEALIX v2.0 — Starting up...")
    logger.info(f"  Demo mode: {config.is_demo_mode}")
    logger.info("=" * 60)

    # ── Initialize Database ──────────────────────────────────
    db = Database(config.db_path)
    await db.initialize()
    app.state.db = db

    # ── Initialize AI Agent ──────────────────────────────────
    agent = HealIXAgent(config=config)
    app.state.agent = agent

    # ── Initialize Microsoft Clients ─────────────────────────
    defender = DefenderClient(config.azure.tenant_id, config.azure.client_id, config.azure.client_secret)
    sentinel = SentinelClient(
        config.azure.tenant_id, config.azure.client_id, config.azure.client_secret,
        workspace_id=config.sentinel.workspace_id,
        subscription_id=config.sentinel.subscription_id,
        resource_group=config.sentinel.resource_group,
    )
    intune = IntuneClient(config.azure.tenant_id, config.azure.client_id, config.azure.client_secret)
    entra = EntraClient(config.azure.tenant_id, config.azure.client_id, config.azure.client_secret)

    await defender.initialize()
    await sentinel.initialize()
    await intune.initialize()
    await entra.initialize()

    app.state.defender = defender
    app.state.sentinel = sentinel
    app.state.intune = intune
    app.state.entra = entra

    logger.info(f"  Defender: {'Connected' if defender.is_available else 'Demo mode'}")
    logger.info(f"  Sentinel: {'Connected' if sentinel.is_available else 'Demo mode'}")
    logger.info(f"  Intune:   {'Connected' if intune.is_available else 'Demo mode'}")
    logger.info(f"  Entra:    {'Connected' if entra.is_available else 'Demo mode'}")

    # ── Initialize Azure Monitor (agentless VM polling) ───────
    azure_monitor = AzureMonitorClient(
        config.azure.tenant_id, config.azure.client_id, config.azure.client_secret,
        subscription_id=config.sentinel.subscription_id,
    )
    await azure_monitor.initialize()
    app.state.azure_monitor = azure_monitor

    # ── Initialize AWS Client (agentless EC2/CloudWatch) ─────
    aws_client = AWSClient(config=config.aws)
    app.state.aws = aws_client

    # ── Initialize Azure AI Foundry ───────────────────────────
    foundry_client = FoundryClient(config=config.foundry)
    app.state.foundry = foundry_client

    logger.info(f"  Azure Monitor: {'Connected' if azure_monitor.is_available else 'Demo mode'}")
    logger.info(f"  AWS EC2:       {'Connected' if aws_client.is_available else 'Demo/disabled'}")
    logger.info(f"  AI Foundry:    {'Connected' if foundry_client.is_available else 'Not configured'}")

    # ── Initialize Notification Service ──────────────────────
    notification = NotificationService(config.alert_delivery)
    app.state.notification = notification

    # ── Initialize Engines ───────────────────────────────────
    log_pipeline = LogPipeline(db, sentinel_client=sentinel, defender_client=defender, config=config)
    alert_engine = AlertEngine(db, notification_service=notification, config=config)
    compliance_engine = ComplianceEngine(db, defender_client=defender, intune_client=intune,
                                         entra_client=entra, agent=agent)
    monitoring_engine = MonitoringEngine(
        db, intune_client=intune, sentinel_client=sentinel,
        azure_monitor_client=azure_monitor, aws_client=aws_client, config=config,
    )
    workflow_engine = WorkflowEngine(db, agent=agent, defender_client=defender,
                                     intune_client=intune, entra_client=entra, alert_engine=alert_engine)
    usage_analytics = UsageAnalytics(db)

    app.state.log_pipeline = log_pipeline
    app.state.alert_engine = alert_engine
    app.state.compliance_engine = compliance_engine
    app.state.monitoring_engine = monitoring_engine
    app.state.workflow_engine = workflow_engine
    app.state.usage_analytics = usage_analytics

    # Wire alert engine to app so it can dispatch webhooks
    alert_engine.app = app

    # ── Wire agent with live data sources ──────────────────────
    agent.db = db
    agent.defender = defender
    agent.intune = intune
    agent.entra = entra
    agent.monitoring_engine = monitoring_engine

    # ── Seed demo endpoints if needed ────────────────────────
    await monitoring_engine._ensure_demo_endpoints()

    # ── Start background collection tasks ────────────────────
    bg_tasks = []
    bg_tasks.append(asyncio.create_task(
        _background_collection_loop(app, config.polling_interval)
    ))
    app.state.bg_tasks = bg_tasks

    logger.info("  HEALIX v2.0 is ready!")
    logger.info("=" * 60)

    yield

    # ── Shutdown ─────────────────────────────────────────────
    logger.info("HEALIX shutting down...")
    for task in app.state.bg_tasks:
        task.cancel()
    await defender.close()
    await sentinel.close()
    await intune.close()
    await entra.close()
    await azure_monitor.close()
    await aws_client.close()
    await notification.close()
    await db.close()


async def _background_collection_loop(app, interval: int):
    """Background loop that collects logs and evaluates alerts."""
    await asyncio.sleep(5)  # Initial delay to let startup complete
    while True:
        try:
            await app.state.log_pipeline.run_collection_cycle()
            await app.state.monitoring_engine.collect_metrics()
            await app.state.alert_engine.run_evaluation_cycle()
            await app.state.workflow_engine.process_new_alerts()
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Background collection error: {e}")
        await asyncio.sleep(interval)


# ════════════════════════════════════════════════════════════
#  CREATE THE FASTAPI APP
# ════════════════════════════════════════════════════════════

app = FastAPI(
    title="HEALIX API",
    description="Autonomous Infrastructure Healing & Security Operations Platform",
    version="2.0.0",
    lifespan=lifespan,
)

# ── CORS ─────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production: restrict to your domain
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Register all routers ────────────────────────────────────
app.include_router(microsoft.router)
app.include_router(logs.router)
app.include_router(alerts.router)
app.include_router(compliance.router)
app.include_router(monitoring.router)
app.include_router(dashboards.router)
app.include_router(usage.router)
app.include_router(workflows.router)
app.include_router(azure.router)
app.include_router(aws.router)
app.include_router(foundry.router)
app.include_router(integration.router)

# ── Static files & Dashboard UI ──────────────────────────
_PROJECT_DIR = pathlib.Path(__file__).resolve().parent
_STATIC_DIR = _PROJECT_DIR / "static"
_STATIC_DIR.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_ui():
    """Serve the HEALIX React dashboard."""
    html_path = _PROJECT_DIR / "index.html"
    return html_path.read_text(encoding="utf-8")


# ════════════════════════════════════════════════════════════
#  CORE ROUTES (v1 backward compatibility)
# ════════════════════════════════════════════════════════════

@app.get("/")
async def root():
    return {
        "status": "online",
        "product": "HEALIX",
        "version": "2.0.0",
        "message": "Autonomous Infrastructure Healing & Security Operations Platform",
    }


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "2.0.0",
        "services": {
            "defender": app.state.defender.is_available if hasattr(app.state, 'defender') else False,
            "sentinel": app.state.sentinel.is_available if hasattr(app.state, 'sentinel') else False,
            "intune": app.state.intune.is_available if hasattr(app.state, 'intune') else False,
            "entra": app.state.entra.is_available if hasattr(app.state, 'entra') else False,
            "azure_monitor": app.state.azure_monitor.is_available if hasattr(app.state, 'azure_monitor') else False,
            "aws": app.state.aws.is_available if hasattr(app.state, 'aws') else False,
            "foundry": app.state.foundry.is_available if hasattr(app.state, 'foundry') else False,
        },
    }


@app.get("/api/endpoints")
async def get_endpoints():
    """Returns live status of all monitored endpoints."""
    endpoints = await app.state.db.get_endpoints()
    if not endpoints:
        endpoints = app.state.agent.get_endpoint_status()
    return {"endpoints": endpoints, "count": len(endpoints)}



@app.get("/api/healing-actions")
async def get_healing_actions():
    """Returns the healing action log."""
    db_actions = await app.state.db.get_healing_actions(limit=50)
    if db_actions:
        stats = await app.state.db.get_healing_stats()
        return {
            "actions": db_actions,
            "total": stats.get("total", len(db_actions)),
            "success_rate": stats.get("success_rate", "N/A"),
        }
    actions = app.state.agent.get_healing_actions()
    return {"actions": actions, "total": len(actions), "success_rate": "98.4%"}


@app.post("/api/agent/chat")
async def chat_with_agent(request: ChatRequest):
    """Main AI endpoint — RAG + LLM."""
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    start = time.time()

    try:
        response = await app.state.agent.ask(
            question=request.question,
            context=request.endpoint_context
        )
        elapsed_ms = (time.time() - start) * 1000

        # Track usage
        await app.state.usage_analytics.record_event(
            metric_type="copilot_query",
            service="chat",
            action="ask",
            response_ms=elapsed_ms,
        )

        return {
            "question": request.question,
            "answer": response["answer"],
            "sources": response.get("sources", []),
            "confidence": response.get("confidence", 0.9),
            "actions_taken": response.get("actions_taken", []),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/healing/trigger")
async def trigger_healing(request: RemediationRequest):
    """Trigger auto-remediation on an endpoint."""
    result = await app.state.agent.trigger_remediation(
        endpoint_id=request.endpoint_id,
        issue_type=request.issue_type,
        triggered_by="user",
    )
    return result


@app.get("/api/predictions")
async def get_predictions():
    """ML-based failure predictions."""
    predictions = await app.state.agent.predict_failures()
    return {"predictions": predictions}


@app.get("/api/patches")
async def get_patches():
    """Patch intelligence with CVE scores."""
    patches = app.state.agent.get_patch_intelligence()
    return {"patches": patches}


# ── Run directly ────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    print("Starting HEALIX API server v2.0...")
    print("Dashboard:  http://localhost:8000/dashboard")
    print("API docs:   http://localhost:8000/docs")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
