"""Agent registry helpers — register discovered agents without fabricating data."""

from __future__ import annotations

from datetime import datetime, timezone

from app.models.domain import Agent, AgentHealth, IntegrationStatus
from app.storage.store import store


def register_discovered_agents(
    agents: list[dict],
    *,
    integration_id: str,
) -> dict:
    """Upsert discovered agents into the registry. Returns counts."""
    now = datetime.now(timezone.utc)
    created = 0
    updated = 0
    for raw in agents:
        agent_id = str(raw.get("id") or "")
        if not agent_id:
            continue
        existing = store.agents.get(agent_id)
        agent = Agent(
            id=agent_id,
            name=str(raw.get("name") or agent_id),
            description=raw.get("description"),
            version=raw.get("version"),
            cloud=raw.get("cloud") or "azure",
            platform=raw.get("platform"),
            framework=raw.get("framework"),
            environment=raw.get("environment"),
            region=raw.get("region"),
            application=raw.get("application"),
            primary_model=raw.get("primary_model"),
            endpoint_ref=raw.get("endpoint_ref"),
            telemetry_source=raw.get("telemetry_source") or "azure",
            integration_id=integration_id,
            status=raw.get("status") or "discovered",
            health=existing.health if existing else AgentHealth.UNKNOWN,
            first_seen_at=existing.first_seen_at if existing else now,
            last_execution_at=existing.last_execution_at if existing else None,
            last_telemetry_at=existing.last_telemetry_at if existing else None,
        )
        if existing:
            updated += 1
        else:
            created += 1
        store.agents[agent_id] = agent

    if integration_id in store.integrations:
        integ = store.integrations[integration_id]
        count = sum(1 for a in store.agents.values() if a.integration_id == integration_id)
        integ.agents_discovered = count if count else None
        if integ.enabled and integ.status in (
            IntegrationStatus.CONNECTED,
            IntegrationStatus.TELEMETRY_ACTIVE,
            IntegrationStatus.DISABLED,
        ):
            # Keep telemetry_active if already receiving; else connected
            if integ.status != IntegrationStatus.TELEMETRY_ACTIVE:
                integ.status = IntegrationStatus.CONNECTED
        store.integrations[integration_id] = integ

    return {"created": created, "updated": updated, "total": created + updated}
