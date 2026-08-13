"""Background telemetry sync from enabled cloud integrations."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.connectors.cloud import AzureConnector
from app.core.config import get_settings
from app.services.telemetry import telemetry_service
from app.storage.store import store

logger = logging.getLogger("control_center.telemetry_sync")


class TelemetrySyncService:
    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()

    async def start(self) -> None:
        settings = get_settings()
        if not settings.azure_telemetry_poll_enabled:
            return
        if self._task and not self._task.done():
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._run_loop())
        logger.info(
            "Azure telemetry sync started (interval=%ss)",
            settings.telemetry_poll_interval_seconds,
        )

    async def stop(self) -> None:
        self._stop.set()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _run_loop(self) -> None:
        settings = get_settings()
        while not self._stop.is_set():
            try:
                await self.sync_enabled_integrations()
            except Exception as exc:  # noqa: BLE001
                logger.warning("Telemetry sync cycle failed: %s", exc)
            try:
                await asyncio.wait_for(
                    self._stop.wait(),
                    timeout=max(5, settings.telemetry_poll_interval_seconds),
                )
            except asyncio.TimeoutError:
                continue

    async def sync_enabled_integrations(self) -> dict[str, Any]:
        results: dict[str, Any] = {}
        azure = store.integrations.get("azure")
        if azure and azure.enabled and azure.configured:
            results["azure"] = await self.sync_azure()
        return results

    async def sync_azure(self) -> dict[str, Any]:
        integ = store.integrations.get("azure")
        if not integ or not integ.configured:
            return {"ok": False, "message": "Azure is not configured."}

        connector = AzureConnector()
        cfg = {**integ.config.fields, "auth_method": integ.config.auth_method}
        raw_spans = await connector.fetch_telemetry(cfg)
        if not raw_spans:
            return {
                "ok": True,
                "spans_ingested": 0,
                "executions_updated": 0,
                "message": "No recent Application Insights agent telemetry found.",
            }

        result = await telemetry_service.ingest_otlp_spans(
            {"spans": raw_spans},
            provider="azure",
            integration_id="azure",
        )
        return {"ok": True, **result}


telemetry_sync_service = TelemetrySyncService()
