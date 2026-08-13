"""Pull live Foundry / Azure AI telemetry from Application Insights."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from app.services.azure_discovery import AzureDiscoveryError, _arm_list, _credential, _token

logger = logging.getLogger("control_center.azure_telemetry")

APP_INSIGHTS_QUERY = "https://api.applicationinsights.io/v1/apps"
INSIGHTS_API = "2015-05-01"
DEPENDENCIES_QUERY = """
let window = ago({hours}h);
union isfuzzy=true
(
  dependencies
  | where timestamp > window
  | where type == "AI"
      or customDimensions has "gen_ai.agent.id"
      or customDimensions has "gen_ai.operation.name"
      or customDimensions has "microsoft.foundry"
  | extend itemType = "dependency"
  | project timestamp, id, name, success, duration, operation_Id, operation_ParentId, customDimensions, customMeasurements, itemType
),
(
  requests
  | where timestamp > window
  | where customDimensions has "gen_ai.agent.id"
      or customDimensions has "gen_ai.operation.name"
      or customDimensions has "microsoft.foundry"
      or name has "agent"
      or name has "invoke"
  | extend itemType = "request"
  | project timestamp, id, name, success, duration, operation_Id, operation_ParentId, customDimensions, customMeasurements, itemType
)
| order by timestamp desc
| take {limit}
"""


class AzureTelemetryError(Exception):
    def __init__(self, message: str, *, stage: str = "telemetry") -> None:
        super().__init__(message)
        self.stage = stage
        self.message = message


def _parse_json_field(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not value:
        return {}
    try:
        parsed = json.loads(str(value))
        return parsed if isinstance(parsed, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


async def _app_insights_components(config: dict[str, Any], arm_token: str) -> list[dict[str, Any]]:
    subscription = config.get("subscription_id") or os.environ.get("AZURE_SUBSCRIPTION_ID")
    if not subscription:
        return []
    items = await _arm_list(
        f"/subscriptions/{subscription}/providers/Microsoft.Insights/components",
        arm_token,
        INSIGHTS_API,
    )
    configured = (config.get("app_insights") or os.environ.get("AZURE_APP_INSIGHTS") or "").strip()
    # Ignore placeholder names from .env.example that are not real resources.
    placeholders = {"ai-agent-metering", "app-insights", "applicationinsights"}
    if configured.lower() in placeholders:
        configured = ""
    if configured and configured.lower() not in ("__all__", "all", "*"):
        matched = [i for i in items if str(i.get("name") or "").lower() == configured.lower()]
        if matched:
            items = matched
        else:
            logger.warning(
                "Configured Application Insights '%s' was not found; scanning all %s component(s)",
                configured,
                len(items),
            )
    return items


async def _query_app_insights(app_id: str, query: str, ai_token: str) -> list[dict[str, Any]]:
    url = f"{APP_INSIGHTS_QUERY}/{app_id}/query"
    async with httpx.AsyncClient(timeout=60.0) as client:
        res = await client.get(url, params={"query": query}, headers={"Authorization": f"Bearer {ai_token}"})
    if res.status_code >= 400:
        raise AzureTelemetryError(
            f"Application Insights query failed ({res.status_code}): {res.text[:400]}",
            stage="query",
        )
    payload = res.json()
    tables = payload.get("tables") or []
    if not tables:
        return []
    columns = [c["name"] for c in tables[0].get("columns") or []]
    rows: list[dict[str, Any]] = []
    for row in tables[0].get("rows") or []:
        rows.append(dict(zip(columns, row)))
    return rows


def _row_to_span(row: dict[str, Any]) -> dict[str, Any]:
    dims = _parse_json_field(row.get("customDimensions"))
    measures = _parse_json_field(row.get("customMeasurements"))
    attrs: dict[str, Any] = {**dims, **measures}

    for key in (
        "gen_ai.usage.input_tokens",
        "gen_ai.usage.output_tokens",
        "gen_ai.usage.cached_tokens",
        "gen_ai.usage.total_tokens",
    ):
        if key in dims and dims[key] is not None:
            attrs[key] = dims[key]

    started = row.get("timestamp")
    duration_ms = row.get("duration")
    end_time = None
    start_dt = None
    if started:
        try:
            start_dt = datetime.fromisoformat(str(started).replace("Z", "+00:00"))
            if duration_ms is not None:
                end_time = (start_dt + timedelta(milliseconds=float(duration_ms))).isoformat()
            started = start_dt.isoformat()
        except (TypeError, ValueError):
            pass

    success = row.get("success")
    status = "ok"
    if str(success).lower() in ("false", "0"):
        status = "error"
    # Incomplete / in-flight rows (no duration yet) stay running so live dashboards can trace them.
    if duration_ms is None or duration_ms == "":
        status = "running"
        end_time = None

    trace_id = row.get("operation_Id") or row.get("operation_Id".lower())
    span_id = str(row.get("id") or "")
    if not span_id:
        return {}

    attrs.setdefault("cloud.provider", "azure")
    attrs.setdefault("platform.name", "Microsoft Foundry")
    attrs.setdefault("framework.name", "foundry")
    if row.get("itemType"):
        attrs["azure.item_type"] = row.get("itemType")

    return {
        "name": row.get("name") or attrs.get("gen_ai.operation.name") or "azure.dependency",
        "span_id": span_id,
        "trace_id": trace_id or span_id,
        "parent_span_id": row.get("operation_ParentId"),
        "start_time": started,
        "end_time": end_time,
        "duration_ms": duration_ms,
        "status": status,
        "attributes": attrs,
    }


async def fetch_telemetry(
    config: dict[str, Any],
    *,
    hours: int = 24,
    limit: int = 500,
) -> list[dict[str, Any]]:
    """Return simplified span payloads from Application Insights AI dependencies."""
    try:
        credential = _credential(config)
        arm_token = _token(credential, "https://management.azure.com")
        ai_token = _token(credential, "https://api.applicationinsights.io")
    except AzureDiscoveryError as exc:
        raise AzureTelemetryError(exc.message, stage=exc.stage) from exc

    components = await _app_insights_components(config, arm_token)
    if not components:
        logger.info("No Application Insights components found for telemetry pull")
        return []

    query = DEPENDENCIES_QUERY.format(hours=max(1, hours), limit=max(1, limit))
    spans: list[dict[str, Any]] = []
    seen: set[str] = set()

    for component in components:
        props = component.get("properties") or {}
        app_id = props.get("AppId") or props.get("appId")
        if not app_id:
            continue
        try:
            rows = await _query_app_insights(str(app_id), query, ai_token)
        except AzureTelemetryError as exc:
            logger.warning("Skipping App Insights %s: %s", component.get("name"), exc.message)
            continue
        for row in rows:
            span = _row_to_span(row)
            sid = span.get("span_id")
            if not sid or sid in seen:
                continue
            seen.add(str(sid))
            spans.append(span)

    logger.info("Pulled %s spans from %s Application Insights component(s)", len(spans), len(components))
    return spans
