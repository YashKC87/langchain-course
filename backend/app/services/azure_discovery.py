"""Discover AI agents deployed in an Azure subscription.

Strategy (no fabricated agents):
1. Authenticate with Azure Identity (Managed Identity / Service Principal / DefaultAzureCredential)
2. List AI / Cognitive Services / ML workspaces in the subscription (ARM)
3. For each Foundry / AI Services project endpoint, list agents via Foundry Agents API
4. Optionally list classic Azure OpenAI Assistants on OpenAI accounts

Returns an empty list when none are found — never invents agents.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger("control_center.azure_discovery")

ARM = "https://management.azure.com"
AI_AUDIENCE = "https://ai.azure.com"
ARM_API = "2021-04-01"
RG_API = "2021-04-01"
COG_API = "2023-05-01"
FOUNDRY_API = "v1"
OPENAI_ASSISTANTS_API = "2024-05-01-preview"


class AzureDiscoveryError(Exception):
    def __init__(self, message: str, *, stage: str = "discovery") -> None:
        super().__init__(message)
        self.stage = stage
        self.message = message


def _credential(config: dict[str, Any]):
    """Build an Azure credential from config + environment."""
    try:
        from azure.identity import (
            ClientSecretCredential,
            DefaultAzureCredential,
            ManagedIdentityCredential,
        )
    except ImportError as exc:
        raise AzureDiscoveryError(
            "Azure Identity SDK is not installed. Run: pip install azure-identity",
            stage="authenticate",
        ) from exc

    auth = (config.get("auth_method") or os.environ.get("AZURE_AUTH_METHOD") or "").lower()
    tenant = config.get("tenant_id") or os.environ.get("AZURE_TENANT_ID")
    client_id = config.get("client_id") or os.environ.get("AZURE_CLIENT_ID")
    client_secret = (
        config.get("client_secret")
        or os.environ.get("AZURE_CLIENT_SECRET")
        or os.environ.get("AZURE_CLIENT_SECRET_VALUE")
    )

    if "service principal" in auth or (tenant and client_id and client_secret):
        if not (tenant and client_id and client_secret):
            raise AzureDiscoveryError(
                "Service Principal discovery requires Tenant ID, Application (Client) ID, "
                "and Client Secret. Add AZURE_CLIENT_ID and AZURE_CLIENT_SECRET to .env "
                "(or enter them in Configure), then retry discovery.",
                stage="authenticate",
            )
        return ClientSecretCredential(
            tenant_id=str(tenant),
            client_id=str(client_id),
            client_secret=str(client_secret),
        )

    if "managed identity" in auth:
        mi_client = client_id or os.environ.get("AZURE_CLIENT_ID")
        # If a client secret is present, prefer Service Principal even when
        # the UI still says Managed Identity (common in local/dev).
        if tenant and client_id and client_secret:
            return ClientSecretCredential(
                tenant_id=str(tenant),
                client_id=str(client_id),
                client_secret=str(client_secret),
            )
        try:
            if mi_client:
                return ManagedIdentityCredential(client_id=str(mi_client))
            return ManagedIdentityCredential()
        except Exception:
            pass

    # DefaultAzureCredential covers az login / VS Code / env SP
    if tenant and client_id and client_secret:
        return ClientSecretCredential(
            tenant_id=str(tenant),
            client_id=str(client_id),
            client_secret=str(client_secret),
        )

    return DefaultAzureCredential(exclude_interactive_browser_credential=True)


def _token(credential: Any, audience: str) -> str:
    try:
        token = credential.get_token(f"{audience}/.default")
        return token.token
    except Exception as exc:
        detail = str(exc)
        if "IMDS" in detail or "ManagedIdentityCredential" in detail:
            raise AzureDiscoveryError(
                "Managed Identity is not available on this host (no Azure IMDS endpoint). "
                "Switch Auth Method to Service Principal, then set AZURE_CLIENT_ID and "
                "AZURE_CLIENT_SECRET in .env (or enter Client ID + Client Secret in Configure). "
                "Grant the app Reader on the subscription and Azure AI User on the Foundry account, "
                "restart the backend, and click Refresh Discovery.",
                stage="authenticate",
            ) from exc
        raise AzureDiscoveryError(
            "Azure authentication failed while acquiring a token for "
            f"{audience}. If you are not running on Azure with Managed Identity, "
            "configure a Service Principal (AZURE_CLIENT_ID + AZURE_CLIENT_SECRET) "
            "with Reader on the subscription and Azure AI User / Cognitive Services "
            f"User on the Foundry account. Details: {exc}",
            stage="authenticate",
        ) from exc


async def _arm_get(path: str, arm_token: str, api_version: str) -> dict[str, Any]:
    url = f"{ARM}{path}"
    params = {"api-version": api_version}
    async with httpx.AsyncClient(timeout=60.0) as client:
        res = await client.get(
            url,
            params=params,
            headers={"Authorization": f"Bearer {arm_token}"},
        )
        if res.status_code == 401:
            raise AzureDiscoveryError(
                "ARM returned 401 Unauthorized. Verify the identity has Reader "
                "on the subscription.",
                stage="permissions",
            )
        if res.status_code == 403:
            raise AzureDiscoveryError(
                "ARM returned 403 Forbidden. Grant Reader (or higher) on subscription "
                f"{path.split('/')[2] if '/subscriptions/' in path else ''} "
                "to the Managed Identity / Service Principal.",
                stage="permissions",
            )
        if res.status_code >= 400:
            raise AzureDiscoveryError(
                f"ARM request failed ({res.status_code}) for {path}: {res.text[:400]}",
                stage="arm",
            )
        return res.json()


def _discovery_scope_rg(config: dict[str, Any]) -> str | None:
    """Return a resource group name when discovery should be RG-scoped, else None (full subscription)."""
    rg = config.get("resource_group") or os.environ.get("AZURE_RESOURCE_GROUP")
    if rg is None:
        return None
    normalized = str(rg).strip()
    if not normalized or normalized.lower() in ("__all__", "all", "*"):
        return None
    return normalized


async def _arm_list(path: str, arm_token: str, api_version: str) -> list[dict[str, Any]]:
    """Paginated ARM list returning all value entries."""
    items: list[dict[str, Any]] = []
    url = f"{ARM}{path}"
    params: dict[str, Any] = {"api-version": api_version}
    async with httpx.AsyncClient(timeout=60.0) as client:
        while url:
            res = await client.get(
                url,
                params=params if url.startswith(ARM) else None,
                headers={"Authorization": f"Bearer {arm_token}"},
            )
            if res.status_code == 401:
                raise AzureDiscoveryError(
                    "ARM returned 401 Unauthorized. Verify the identity has Reader "
                    "on the subscription.",
                    stage="permissions",
                )
            if res.status_code == 403:
                raise AzureDiscoveryError(
                    "ARM returned 403 Forbidden. Grant Reader (or higher) on the subscription "
                    "to list resource groups and Cognitive Services accounts.",
                    stage="permissions",
                )
            if res.status_code >= 400:
                raise AzureDiscoveryError(
                    f"ARM request failed ({res.status_code}) for {path}: {res.text[:400]}",
                    stage="arm",
                )
            payload = res.json()
            items.extend(payload.get("value") or [])
            next_link = payload.get("nextLink")
            if next_link:
                url = next_link
                params = {}
            else:
                break
    return items


async def list_resource_groups_in_subscription(config: dict[str, Any]) -> dict[str, Any]:
    """List resource groups in the configured subscription."""
    subscription = config.get("subscription_id") or os.environ.get("AZURE_SUBSCRIPTION_ID")
    if not subscription:
        raise AzureDiscoveryError(
            "subscription_id is required to list resource groups.",
            stage="configuration",
        )

    credential = _credential(config)
    arm_token = _token(credential, "https://management.azure.com")
    raw_groups = await _arm_list(
        f"/subscriptions/{subscription}/resourcegroups",
        arm_token,
        RG_API,
    )
    groups: list[dict[str, Any]] = []
    for item in raw_groups:
        name = item.get("name")
        if not name:
            continue
        props = item.get("properties") or {}
        groups.append(
            {
                "name": str(name),
                "location": item.get("location"),
                "id": item.get("id"),
                "provisioning_state": props.get("provisioningState"),
            }
        )
    groups.sort(key=lambda g: g["name"].lower())

    return {
        "subscription_id": subscription,
        "resource_groups": groups,
        "count": len(groups),
        "message": f"Found {len(groups)} resource group(s) in subscription {subscription}.",
    }


async def list_ai_accounts(config: dict[str, Any], arm_token: str) -> list[dict[str, Any]]:
    subscription = config["subscription_id"]
    rg = _discovery_scope_rg(config)

    if rg:
        path = f"/subscriptions/{subscription}/resourceGroups/{rg}/providers/Microsoft.CognitiveServices/accounts"
        try:
            data = await _arm_get(path, arm_token, COG_API)
        except AzureDiscoveryError as exc:
            if "404" in exc.message:
                raise AzureDiscoveryError(
                    f"Resource group '{rg}' was not found in subscription {subscription}. "
                    "Load resource groups and select a valid group, or choose "
                    "'All resource groups' for a full subscription scan.",
                    stage="configuration",
                ) from exc
            raise
        return list(data.get("value") or [])

    path = f"/subscriptions/{subscription}/providers/Microsoft.CognitiveServices/accounts"
    data = await _arm_get(path, arm_token, COG_API)
    return list(data.get("value") or [])


async def _list_foundry_agents(
    *,
    account_name: str,
    project_name: str,
    ai_token: str,
) -> list[dict[str, Any]]:
    base = f"https://{account_name}.services.ai.azure.com/api/projects/{project_name}"
    url = f"{base}/agents"
    agents: list[dict[str, Any]] = []
    params: dict[str, Any] = {"api-version": FOUNDRY_API, "limit": 100}
    async with httpx.AsyncClient(timeout=60.0) as client:
        while True:
            res = await client.get(
                url,
                params=params,
                headers={"Authorization": f"Bearer {ai_token}"},
            )
            if res.status_code in (401, 403):
                logger.warning(
                    "Foundry agents list denied for %s/%s: %s",
                    account_name,
                    project_name,
                    res.status_code,
                )
                break
            if res.status_code == 404:
                # Try legacy assistants path used by some Foundry builds
                break
            if res.status_code >= 400:
                logger.warning(
                    "Foundry agents list failed for %s/%s: %s %s",
                    account_name,
                    project_name,
                    res.status_code,
                    res.text[:300],
                )
                break
            payload = res.json()
            for item in payload.get("data") or payload.get("value") or []:
                agents.append(item)
            after = payload.get("last_id") or payload.get("next_cursor")
            if not after or not (payload.get("has_more") or payload.get("nextLink")):
                # also support after cursor style
                if payload.get("has_more") and after:
                    params["after"] = after
                    continue
                break
            params["after"] = after
    return agents


async def _list_openai_assistants(*, endpoint: str, ai_token: str) -> list[dict[str, Any]]:
    """Legacy Assistants API on Azure OpenAI / AI Services endpoints."""
    endpoint = endpoint.rstrip("/")
    url = f"{endpoint}/openai/assistants"
    async with httpx.AsyncClient(timeout=60.0) as client:
        res = await client.get(
            url,
            params={"api-version": OPENAI_ASSISTANTS_API},
            headers={"Authorization": f"Bearer {ai_token}"},
        )
        if res.status_code >= 400:
            return []
        payload = res.json()
        return list(payload.get("data") or [])


def _normalize_discovered(
    *,
    raw: dict[str, Any],
    source: str,
    cloud_account: str | None,
    project: str | None,
    region: str | None,
    subscription_id: str,
    tenant_id: str | None,
    resource_group: str | None,
) -> dict[str, Any]:
    agent_id = str(
        raw.get("id")
        or raw.get("name")
        or raw.get("assistant_id")
        or ""
    )
    meta = raw.get("metadata") if isinstance(raw.get("metadata"), dict) else {}
    name = str(
        raw.get("name")
        or raw.get("display_name")
        or meta.get("name")
        or agent_id
    )
    model = None
    if isinstance(raw.get("model"), str):
        model = raw["model"]
    elif isinstance(raw.get("versions"), dict):
        latest = raw["versions"].get("latest") or {}
        if isinstance(latest, dict):
            model = latest.get("model") or (latest.get("definition") or {}).get("model")

    version = None
    if isinstance(raw.get("versions"), dict):
        latest = raw["versions"].get("latest")
        if isinstance(latest, dict):
            version = str(latest.get("version") or latest.get("id") or "") or None

    return {
        "id": f"azure:{subscription_id}:{agent_id}",
        "provider_agent_id": agent_id,
        "name": name or agent_id,
        "description": raw.get("description") or raw.get("instructions"),
        "version": version,
        "cloud": "azure",
        "platform": source,
        "framework": "Microsoft Foundry Agent Service" if "foundry" in source else "Azure OpenAI Assistants",
        "region": region,
        "primary_model": model,
        "environment": "azure",
        "application": project,
        "endpoint_ref": cloud_account,
        "telemetry_source": "azure",
        "status": raw.get("status") or "discovered",
        "subscription_id": subscription_id,
        "tenant_id": tenant_id,
        "resource_group": resource_group,
        "provider_raw_reference": raw.get("id") or agent_id,
    }


async def discover_agents_in_subscription(config: dict[str, Any]) -> dict[str, Any]:
    """Discover agents. Returns {agents, accounts_scanned, errors, message}."""
    subscription = config.get("subscription_id") or os.environ.get("AZURE_SUBSCRIPTION_ID")
    tenant = config.get("tenant_id") or os.environ.get("AZURE_TENANT_ID")
    rg = _discovery_scope_rg(config)
    project = config.get("foundry_project") or os.environ.get("AZURE_FOUNDRY_PROJECT") or "_project"

    if not subscription:
        raise AzureDiscoveryError("subscription_id is required for Azure discovery.", stage="configuration")

    credential = _credential(config)
    arm_token = _token(credential, "https://management.azure.com")
    ai_token = _token(credential, AI_AUDIENCE)

    accounts = await list_ai_accounts(config, arm_token)
    errors: list[str] = []
    discovered: list[dict[str, Any]] = []
    scanned: list[str] = []

    # If user named a Foundry account separately, also probe it
    preferred_names: list[str] = []
    for key in ("foundry_account", "ai_services_account", "account_name"):
        if config.get(key):
            preferred_names.append(str(config[key]))

    account_entries: list[dict[str, Any]] = list(accounts)
    for name in preferred_names:
        if not any((a.get("name") == name) for a in account_entries):
            account_entries.append(
                {
                    "name": name,
                    "location": config.get("region"),
                    "properties": {"endpoint": f"https://{name}.services.ai.azure.com"},
                    "id": f"/subscriptions/{subscription}/resourceGroups/{rg or config.get('resource_group') or 'unknown'}/providers/Microsoft.CognitiveServices/accounts/{name}",
                }
            )

    if not account_entries:
        if rg:
            errors.append(
                f"No Microsoft.CognitiveServices accounts were found in resource group '{rg}'. "
                "Try another resource group or choose 'All resource groups'."
            )
        elif project:
            errors.append(
                "No Microsoft.CognitiveServices accounts were found in the subscription. "
                "If agents live under a Foundry account outside the configured resource group, "
                "add foundry_account / AI Services account name in Configure."
            )

    for acct in account_entries:
        name = acct.get("name")
        if not name:
            continue
        scanned.append(str(name))
        props = acct.get("properties") or {}
        endpoint = props.get("endpoint")
        location = acct.get("location")
        kind = (acct.get("kind") or props.get("publicNetworkAccess") or "").lower()
        rg_from_id = None
        acct_id = str(acct.get("id") or "")
        if "/resourceGroups/" in acct_id:
            try:
                rg_from_id = acct_id.split("/resourceGroups/")[1].split("/")[0]
            except IndexError:
                rg_from_id = rg

        # Foundry agents (project data plane)
        for proj in {project, "_project"}:
            try:
                items = await _list_foundry_agents(
                    account_name=str(name),
                    project_name=str(proj),
                    ai_token=ai_token,
                )
                for item in items:
                    discovered.append(
                        _normalize_discovered(
                            raw=item,
                            source="azure-foundry",
                            cloud_account=str(name),
                            project=str(proj),
                            region=location,
                            subscription_id=str(subscription),
                            tenant_id=str(tenant) if tenant else None,
                            resource_group=rg_from_id or rg,
                        )
                    )
            except Exception as exc:  # noqa: BLE001
                errors.append(f"Foundry list failed for {name}/{proj}: {exc}")

        # Classic assistants on the account endpoint
        if endpoint:
            try:
                assistants = await _list_openai_assistants(endpoint=str(endpoint), ai_token=ai_token)
                for item in assistants:
                    discovered.append(
                        _normalize_discovered(
                            raw=item,
                            source="azure-openai-assistants",
                            cloud_account=str(name),
                            project=None,
                            region=location,
                            subscription_id=str(subscription),
                            tenant_id=str(tenant) if tenant else None,
                            resource_group=rg_from_id or rg,
                        )
                    )
            except Exception as exc:  # noqa: BLE001
                errors.append(f"Assistants list failed for {name}: {exc}")
        _ = kind  # reserved for future filtering

    # De-dupe by id
    unique: dict[str, dict[str, Any]] = {}
    for a in discovered:
        unique[a["id"]] = a
    agents = list(unique.values())

    scope_label = f"resource group {rg}" if rg else f"subscription {subscription}"

    if agents:
        message = (
            f"Discovered {len(agents)} agent(s) across {len(scanned)} AI account(s) "
            f"in {scope_label}."
        )
    else:
        message = (
            f"Connection to {scope_label} succeeded. "
            f"Scanned {len(scanned)} Cognitive Services / AI account(s). "
            "No agents discovered. Confirm the Foundry project name, account, "
            "and that agents exist in Azure AI Foundry."
        )

    return {
        "agents": agents,
        "accounts_scanned": scanned,
        "errors": errors,
        "message": message,
        "subscription_id": subscription,
        "resource_group": rg,
        "foundry_project": project,
        "scope": "resource_group" if rg else "subscription",
    }
