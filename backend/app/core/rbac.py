"""Enterprise RBAC roles and permission checks."""

from enum import Enum
from typing import Annotated

from fastapi import Header, HTTPException, status

from app.core.config import get_settings


class Role(str, Enum):
    PLATFORM_ADMINISTRATOR = "platform_administrator"
    OBSERVABILITY_ADMINISTRATOR = "observability_administrator"
    AGENT_OWNER = "agent_owner"
    BUSINESS_UNIT_OWNER = "business_unit_owner"
    OPERATIONS_ENGINEER = "operations_engineer"
    AUDITOR = "auditor"
    VIEWER = "viewer"


# Permissions matrix (coarse-grained for MVP)
ROLE_PERMISSIONS: dict[Role, set[str]] = {
    Role.PLATFORM_ADMINISTRATOR: {
        "integrations:read",
        "integrations:write",
        "integrations:toggle",
        "agents:read",
        "agents:write",
        "executions:read",
        "traces:read",
        "settings:read",
        "settings:write",
        "alerts:read",
        "alerts:write",
        "optimization:read",
        "content:read",
        "audit:read",
    },
    Role.OBSERVABILITY_ADMINISTRATOR: {
        "integrations:read",
        "integrations:write",
        "integrations:toggle",
        "agents:read",
        "executions:read",
        "traces:read",
        "settings:read",
        "settings:write",
        "alerts:read",
        "alerts:write",
        "optimization:read",
        "audit:read",
    },
    Role.AGENT_OWNER: {
        "integrations:read",
        "agents:read",
        "agents:write",
        "executions:read",
        "traces:read",
        "alerts:read",
        "optimization:read",
    },
    Role.BUSINESS_UNIT_OWNER: {
        "integrations:read",
        "agents:read",
        "executions:read",
        "traces:read",
        "alerts:read",
        "optimization:read",
    },
    Role.OPERATIONS_ENGINEER: {
        "integrations:read",
        "integrations:toggle",
        "agents:read",
        "executions:read",
        "traces:read",
        "alerts:read",
        "alerts:write",
        "optimization:read",
        "settings:read",
    },
    Role.AUDITOR: {
        "integrations:read",
        "agents:read",
        "executions:read",
        "traces:read",
        "settings:read",
        "alerts:read",
        "audit:read",
    },
    Role.VIEWER: {
        "integrations:read",
        "agents:read",
        "executions:read",
        "traces:read",
        "alerts:read",
        "optimization:read",
    },
}


def require_permission(permission: str):
    """FastAPI dependency factory for permission checks."""

    async def _check(
        x_role: Annotated[str | None, Header()] = None,
        x_user_id: Annotated[str | None, Header()] = None,
    ) -> dict:
        settings = get_settings()
        if not settings.auth_enabled:
            role = Role(settings.default_role)
            return {"role": role, "user_id": x_user_id or "local-dev", "permissions": ROLE_PERMISSIONS[role]}

        if not x_role:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing X-Role header. Authenticate with an enterprise identity provider.",
            )
        try:
            role = Role(x_role.lower())
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Unknown role: {x_role}",
            ) from exc

        perms = ROLE_PERMISSIONS.get(role, set())
        if permission not in perms:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{role.value}' lacks permission '{permission}'.",
            )
        return {"role": role, "user_id": x_user_id or "unknown", "permissions": perms}

    return _check
