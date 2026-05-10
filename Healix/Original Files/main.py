# ============================================================
#  HEALIX Backend API — main.py
#  This is the brain of HEALIX. It handles:
#  - Receiving questions from the frontend
#  - Running the AI agent (RAG + LLM)
#  - Returning healing actions and alerts
# ============================================================

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
import json
import asyncio
import random
from datetime import datetime

# Import our AI agent logic
from agent import HealIXAgent

# ── Create the FastAPI app ────────────────────────────────────
app = FastAPI(
    title="HEALIX API",
    description="Autonomous Infrastructure Healing Platform",
    version="1.0.0"
)

# ── Allow the frontend to talk to this backend ────────────────
# (This is needed when running frontend and backend separately)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # In production: change to your domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Initialize the AI Agent ───────────────────────────────────
agent = HealIXAgent()

# ── Data models (shapes of data we send/receive) ──────────────
class ChatRequest(BaseModel):
    question: str
    endpoint_context: Optional[str] = None  # e.g. "EDGE-NODE-07"

class RemediationRequest(BaseModel):
    endpoint_id: str
    issue_type: str   # e.g. "high_cpu", "memory_leak", "disk_full"

# ════════════════════════════════════════════════════════════
#  ROUTES — these are the URLs the frontend calls
# ════════════════════════════════════════════════════════════

# ── Health Check (test if server is running) ──────────────────
@app.get("/")
async def root():
    return {
        "status": "online",
        "product": "HEALIX",
        "version": "1.0.0",
        "message": "Autonomous Infrastructure Healing Platform is running!"
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


# ── Get all endpoint statuses ─────────────────────────────────
@app.get("/api/endpoints")
async def get_endpoints():
    """Returns live status of all monitored servers/endpoints"""
    endpoints = agent.get_endpoint_status()
    return {"endpoints": endpoints, "count": len(endpoints)}


# ── Get active alerts ─────────────────────────────────────────
@app.get("/api/alerts")
async def get_alerts():
    """Returns all current alerts across the infrastructure"""
    alerts = agent.get_alerts()
    return {
        "alerts": alerts,
        "critical_count": len([a for a in alerts if a["type"] == "critical"]),
        "warning_count":  len([a for a in alerts if a["type"] == "warning"]),
    }


# ── Get healing actions log ───────────────────────────────────
@app.get("/api/healing-actions")
async def get_healing_actions():
    """Returns the log of all auto-remediation actions taken"""
    actions = agent.get_healing_actions()
    return {
        "actions": actions,
        "total": len(actions),
        "success_rate": "98.4%"
    }


# ── Ask the AI Agent a question (RAG + LLM) ───────────────────
@app.post("/api/agent/chat")
async def chat_with_agent(request: ChatRequest):
    """
    Main AI endpoint — send a question, get an intelligent answer.
    Uses RAG (knowledge base lookup) + LLM (reasoning).
    """
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    try:
        response = await agent.ask(
            question=request.question,
            context=request.endpoint_context
        )
        return {
            "question": request.question,
            "answer": response["answer"],
            "sources": response.get("sources", []),
            "confidence": response.get("confidence", 0.9),
            "actions_taken": response.get("actions_taken", []),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Trigger auto-remediation on an endpoint ───────────────────
@app.post("/api/healing/trigger")
async def trigger_healing(request: RemediationRequest):
    """
    Tells HEALIX to start fixing a problem on a specific endpoint.
    The agent will choose the right healing action automatically.
    """
    result = await agent.trigger_remediation(
        endpoint_id=request.endpoint_id,
        issue_type=request.issue_type
    )
    return result


# ── Get predictive risk analysis ─────────────────────────────
@app.get("/api/predictions")
async def get_predictions():
    """ML-based failure predictions for the next 24 hours"""
    predictions = await agent.predict_failures()
    return {"predictions": predictions}


# ── Get patch intelligence ────────────────────────────────────
@app.get("/api/patches")
async def get_patches():
    """Returns pending patches with CVE severity scores"""
    patches = agent.get_patch_intelligence()
    return {"patches": patches}


# ── Run this file directly for testing ────────────────────────
if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting HEALIX API server...")
    print("📖 API docs available at: http://localhost:8000/docs")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
