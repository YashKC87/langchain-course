"""Model client factory."""

from __future__ import annotations

from app.config import Settings, get_settings
from app.models.demo_model import DemoFrontierClient, DemoSLMClient
from app.models.frontier_client import AzureFrontierClient
from app.models.model_interface import LanguageModel
from app.models.slm_client import LocalSLMClient


def build_slm_client(settings: Settings | None = None) -> LanguageModel:
    settings = settings or get_settings()
    if settings.effective_demo_mode() or settings.slm_provider == "demo":
        return DemoSLMClient(model_name=f"demo::{settings.slm_model}")
    return LocalSLMClient(
        model_name=settings.slm_model,
        base_url=settings.slm_base_url,
        timeout_seconds=settings.slm_timeout_seconds,
    )


def build_frontier_client(settings: Settings | None = None) -> LanguageModel:
    settings = settings or get_settings()
    if settings.effective_demo_mode() or settings.frontier_provider == "demo":
        return DemoFrontierClient(model_name=f"demo::{settings.frontier_model}")
    return AzureFrontierClient(
        model_name=settings.frontier_model,
        endpoint=settings.azure_openai_endpoint,
        api_key=settings.azure_openai_api_key,
        api_version=settings.azure_openai_api_version,
        deployment=settings.azure_openai_deployment or settings.frontier_model,
        timeout_seconds=settings.slm_timeout_seconds,
    )
