"""Base connector interface — provider adapters without coupling the core model."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseConnector(ABC):
    """Platform connector contract.

    Connectors authenticate, validate telemetry access, discover agents,
    and pull or receive provider telemetry. They must never fabricate
    operational agents or metrics when the provider returns nothing.
    """

    id: str
    name: str
    provider: str

    @abstractmethod
    async def authenticate(self, config: dict[str, Any]) -> dict[str, Any]:
        """Return {ok, message}. Never log secrets."""

    @abstractmethod
    async def validate_permissions(self, config: dict[str, Any]) -> dict[str, Any]:
        ...

    @abstractmethod
    async def validate_telemetry_source(self, config: dict[str, Any]) -> dict[str, Any]:
        ...

    @abstractmethod
    async def discover_agents(self, config: dict[str, Any]) -> list[dict[str, Any]]:
        """Return discovered agent metadata only. Empty list if none found."""

    @abstractmethod
    async def fetch_telemetry(self, config: dict[str, Any]) -> list[dict[str, Any]]:
        """Return raw provider spans/events. Empty list if none available."""
