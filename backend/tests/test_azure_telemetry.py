"""Tests for Azure Application Insights telemetry pull."""

from __future__ import annotations

import pytest

from app.services.azure_telemetry import _row_to_span


def test_row_to_span_maps_foundry_tokens():
    row = {
        "timestamp": "2026-08-13T12:34:34.1682025Z",
        "id": "a1a06fe4873418a3",
        "name": "chat gpt-5-2025-08-07",
        "success": "True",
        "duration": 5308.4227,
        "operation_Id": "b0657677e5a841ee940695fb28f536f4",
        "operation_ParentId": "141c5273128bf2cb",
        "customDimensions": (
            '{"gen_ai.agent.id":"EUC-Teams-Agent:2","gen_ai.agent.name":"EUC-Teams-Agent",'
            '"gen_ai.request.model":"gpt-5-2025-08-07","gen_ai.usage.input_tokens":"6124",'
            '"gen_ai.usage.output_tokens":"557","gen_ai.operation.name":"chat"}'
        ),
        "customMeasurements": (
            '{"gen_ai.usage.input_tokens":6124,"gen_ai.usage.output_tokens":557}'
        ),
    }
    span = _row_to_span(row)
    assert span["span_id"] == "a1a06fe4873418a3"
    assert span["trace_id"] == "b0657677e5a841ee940695fb28f536f4"
    assert span["attributes"]["gen_ai.agent.name"] == "EUC-Teams-Agent"
    assert span["attributes"]["gen_ai.usage.input_tokens"] == "6124"


@pytest.mark.asyncio
async def test_sync_azure_ingests_spans(monkeypatch):
    from app.services.telemetry_sync import telemetry_sync_service
    from app.storage.store import ObservabilityStore, store

    sample = [{
        "name": "chat gpt-5",
        "span_id": "span-sync-1",
        "trace_id": "trace-sync-1",
        "status": "ok",
        "start_time": "2026-08-13T12:34:34+00:00",
        "end_time": "2026-08-13T12:34:39+00:00",
        "attributes": {
            "gen_ai.agent.id": "agent-1",
            "gen_ai.agent.name": "Agent One",
            "gen_ai.usage.input_tokens": "100",
            "gen_ai.usage.output_tokens": "25",
            "cloud.provider": "azure",
        },
    }]

    async def fake_fetch(self, _config):
        return sample

    monkeypatch.setattr(
        "app.connectors.cloud.AzureConnector.fetch_telemetry",
        fake_fetch,
    )

    fresh = ObservabilityStore()
    store.integrations = fresh.integrations
    store.agents = {}
    store.executions = {}
    store.spans = {}
    store.spans_by_trace = {}
    store.spans_by_execution = {}
    store.last_telemetry_at = None

    azure = store.integrations["azure"]
    azure.configured = True
    azure.enabled = True
    azure.config.fields = {"tenant_id": "x", "subscription_id": "y"}

    result = await telemetry_sync_service.sync_azure()
    assert result["ok"] is True
    assert result["spans_ingested"] == 1
    assert len(store.executions) == 1
    assert store.has_live_telemetry() is True
