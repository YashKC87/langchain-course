"""FastAPI application entrypoint."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import get_settings
from app.services.integrations import integration_service
from app.services.telemetry_sync import telemetry_sync_service
from app.storage.persistence import apply_env_defaults, apply_saved_config, auto_enable_integrations
from app.storage.store import store

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("control_center")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    apply_saved_config(store.integrations)
    apply_env_defaults(store.integrations)
    auto_enabled = auto_enable_integrations(store.integrations)
    if auto_enabled:
        logger.info("Auto-enabled integrations: %s", ", ".join(auto_enabled))
    if settings.azure_auto_enable:
        azure = store.integrations.get("azure")
        if azure and azure.configured and not azure.enabled:
            try:
                await integration_service.enable("azure")
                logger.info("Auto-enabled Azure integration (discovery on startup)")
            except Exception as exc:  # noqa: BLE001
                logger.warning("Azure auto-enable failed: %s", exc)
    logger.info("Starting %s (env=%s)", settings.app_name, settings.app_env)
    logger.info(
        "Content capture default: %s | No synthetic telemetry will be seeded",
        settings.content_capture_enabled,
    )
    configured = [i.name for i in store.integrations.values() if i.configured]
    if configured:
        logger.info("Loaded integration config: %s", ", ".join(configured[:8]))
    await telemetry_sync_service.start()
    yield
    await telemetry_sync_service.stop()
    logger.info("Shutting down Control Center")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        lifespan=lifespan,
        description=(
            "One live control center to discover, meter, observe, trace, and optimize "
            "AI agents across Azure, AWS, Google Cloud, and agent frameworks. "
            "Live telemetry only — no synthetic operational data."
        ),
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router, prefix=settings.api_prefix)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app


app = create_app()
