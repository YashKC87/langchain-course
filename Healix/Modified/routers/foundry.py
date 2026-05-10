# ============================================================
#  HEALIX Foundry Router — routers/foundry.py
#  Exposes Azure AI Foundry status and direct chat endpoints.
# ============================================================

from datetime import datetime, timezone
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/foundry", tags=["Azure AI Foundry"])


class FoundryChatRequest(BaseModel):
    message: str
    system_prompt: Optional[str] = None


@router.get("/status")
async def foundry_status(request: Request):
    """Return Azure AI Foundry availability and agent AI provider info."""
    foundry = getattr(request.app.state, "foundry", None)
    agent = getattr(request.app.state, "agent", None)

    foundry_available = foundry.is_available if foundry else False
    model_info = foundry.get_model_info() if foundry else {}

    agent_provider = getattr(agent, "_llm_provider", "unknown") if agent else "unknown"
    agent_demo_mode = getattr(agent, "_demo_mode", True) if agent else True

    return {
        "foundry_available": foundry_available,
        "model_info": model_info,
        "agent_provider": agent_provider,
        "agent_demo_mode": agent_demo_mode,
        "timestamp": _now(),
    }


@router.get("/model-info")
async def foundry_model_info(request: Request):
    """Return metadata about the configured Azure AI Foundry model."""
    foundry = getattr(request.app.state, "foundry", None)
    if not foundry:
        raise HTTPException(status_code=503, detail="Foundry client not initialized")
    return foundry.get_model_info()


@router.post("/chat")
async def foundry_chat(request: Request, body: FoundryChatRequest):
    """Send a direct message to the Azure AI Foundry LLM (bypasses RAG)."""
    foundry = getattr(request.app.state, "foundry", None)
    if not foundry:
        raise HTTPException(status_code=503, detail="Foundry client not initialized")

    if not body.message.strip():
        raise HTTPException(status_code=400, detail="message cannot be empty")

    result = await foundry.chat(
        message=body.message,
        system_prompt=body.system_prompt,
    )
    return result


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
