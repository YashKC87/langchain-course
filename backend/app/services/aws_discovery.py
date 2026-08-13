"""Discover AI agents deployed in an AWS account.

Strategy (no fabricated agents):
1. Authenticate with the default AWS credential chain (IAM role, env keys, profile)
2. Validate account via STS GetCallerIdentity
3. List Amazon Bedrock Agents (bedrock-agent ListAgents)
4. List AgentCore runtimes when available (bedrock-agentcore-control ListAgentRuntimes)

Returns an empty list when none are found — never invents agents.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from typing import Any

logger = logging.getLogger("control_center.aws_discovery")

ACCOUNT_ID_RE = re.compile(r"^\d{12}$")


class AWSDiscoveryError(Exception):
    def __init__(self, message: str, *, stage: str = "discovery") -> None:
        super().__init__(message)
        self.stage = stage
        self.message = message


def _session(config: dict[str, Any]):
    """Build a boto3 Session from config + environment."""
    try:
        import boto3
    except ImportError as exc:
        raise AWSDiscoveryError(
            "AWS SDK (boto3) is not installed. Run: pip install boto3",
            stage="authenticate",
        ) from exc

    region = config.get("region") or os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION")
    if not region:
        raise AWSDiscoveryError(
            "AWS region is required for discovery. Set region in Configure or AWS_REGION in .env.",
            stage="configuration",
        )

    auth = (config.get("auth_method") or os.environ.get("AWS_AUTH_METHOD") or "").lower()
    profile = config.get("profile") or os.environ.get("AWS_PROFILE")
    role_arn = config.get("role_arn") or os.environ.get("AWS_ROLE_ARN")

    access_key = (
        config.get("access_key_id")
        or os.environ.get("AWS_ACCESS_KEY_ID")
    )
    secret_key = (
        config.get("secret_access_key")
        or os.environ.get("AWS_SECRET_ACCESS_KEY")
    )
    session_token = os.environ.get("AWS_SESSION_TOKEN")

    if "access key" in auth and access_key and secret_key:
        return boto3.Session(
            aws_access_key_id=str(access_key),
            aws_secret_access_key=str(secret_key),
            aws_session_token=session_token,
            region_name=str(region),
        )

    if profile:
        return boto3.Session(profile_name=str(profile), region_name=str(region))

    if role_arn:
        sts = boto3.client("sts", region_name=str(region))
        assumed = sts.assume_role(RoleArn=str(role_arn), RoleSessionName="agent-metering-discovery")
        creds = assumed["Credentials"]
        return boto3.Session(
            aws_access_key_id=creds["AccessKeyId"],
            aws_secret_access_key=creds["SecretAccessKey"],
            aws_session_token=creds["SessionToken"],
            region_name=str(region),
        )

    # IAM Role / IRSA / instance profile / env keys via default chain
    return boto3.Session(region_name=str(region))


def _caller_identity(session) -> dict[str, Any]:
    try:
        sts = session.client("sts")
        return sts.get_caller_identity()
    except Exception as exc:
        detail = str(exc)
        if "Unable to locate credentials" in detail or "NoCredentialsError" in detail:
            raise AWSDiscoveryError(
                "AWS credentials were not found. Configure an IAM role on this host, "
                "set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY in .env, or choose "
                "Access Key Ref / IAM Role in Configure and retry discovery.",
                stage="authenticate",
            ) from exc
        raise AWSDiscoveryError(
            f"AWS authentication failed while calling STS GetCallerIdentity: {exc}",
            stage="authenticate",
        ) from exc


def _list_bedrock_agents(session, region: str) -> tuple[list[dict[str, Any]], list[str]]:
    errors: list[str] = []
    agents: list[dict[str, Any]] = []
    try:
        from botocore.exceptions import ClientError, EndpointConnectionError
    except ImportError:
        EndpointConnectionError = Exception  # type: ignore[misc, assignment]

    try:
        client = session.client("bedrock-agent", region_name=region)
        paginator = client.get_paginator("list_agents")
        for page in paginator.paginate(PaginationConfig={"PageSize": 100}):
            agents.extend(page.get("agentSummaries") or [])
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code in ("AccessDeniedException", "UnauthorizedOperation"):
            errors.append(
                "Bedrock Agents list denied. Grant bedrock:ListAgents (and bedrock:GetAgent) "
                "to the IAM role or user used by this Control Center."
            )
        elif code == "UnrecognizedClientException":
            errors.append(
                f"Bedrock Agents API is not available in region {region}. "
                "Try a Bedrock-supported region (e.g. us-east-1)."
            )
        else:
            errors.append(f"Bedrock Agents list failed: {code}: {exc}")
    except EndpointConnectionError as exc:
        errors.append(f"Bedrock Agents endpoint unreachable in {region}: {exc}")
    except Exception as exc:  # noqa: BLE001
        errors.append(f"Bedrock Agents list failed: {exc}")

    return agents, errors


def _list_agentcore_runtimes(session, region: str) -> tuple[list[dict[str, Any]], list[str]]:
    errors: list[str] = []
    runtimes: list[dict[str, Any]] = []
    try:
        from botocore.exceptions import ClientError
    except ImportError:
        return runtimes, errors

    try:
        client = session.client("bedrock-agentcore-control", region_name=region)
        paginator = client.get_paginator("list_agent_runtimes")
        for page in paginator.paginate(PaginationConfig={"PageSize": 100}):
            runtimes.extend(page.get("agentRuntimes") or [])
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code in ("AccessDeniedException", "UnauthorizedOperation"):
            errors.append(
                "AgentCore runtime list denied. Grant bedrock-agentcore:ListAgentRuntimes "
                "to the IAM role or user (optional — only needed for AgentCore deployments)."
            )
        elif code in ("UnknownOperationException", "UnrecognizedClientException"):
            logger.info("AgentCore control plane not available in %s: %s", region, code)
        else:
            errors.append(f"AgentCore runtime list failed: {code}: {exc}")
    except Exception as exc:  # noqa: BLE001
        logger.warning("AgentCore runtime list skipped: %s", exc)

    return runtimes, errors


def _normalize_bedrock_agent(
    *,
    raw: dict[str, Any],
    account_id: str,
    region: str,
) -> dict[str, Any]:
    agent_id = str(raw.get("agentId") or "")
    name = str(raw.get("agentName") or agent_id)
    version = raw.get("latestAgentVersion")
    return {
        "id": f"aws:{account_id}:{agent_id}",
        "provider_agent_id": agent_id,
        "name": name,
        "description": raw.get("description"),
        "version": str(version) if version else None,
        "cloud": "aws",
        "platform": "bedrock-agents",
        "framework": "Amazon Bedrock Agents",
        "region": region,
        "primary_model": None,
        "environment": "aws",
        "application": name,
        "endpoint_ref": agent_id,
        "telemetry_source": "aws",
        "status": (raw.get("agentStatus") or "discovered").lower(),
        "account_id": account_id,
        "provider_raw_reference": agent_id,
    }


def _normalize_agentcore_runtime(
    *,
    raw: dict[str, Any],
    account_id: str,
    region: str,
) -> dict[str, Any]:
    runtime_id = str(raw.get("agentRuntimeId") or raw.get("agentRuntimeArn") or "")
    name = str(raw.get("agentRuntimeName") or runtime_id)
    version = raw.get("agentRuntimeVersion")
    return {
        "id": f"aws:{account_id}:agentcore:{runtime_id}",
        "provider_agent_id": runtime_id,
        "name": name,
        "description": raw.get("description"),
        "version": str(version) if version else None,
        "cloud": "aws",
        "platform": "agentcore",
        "framework": "Amazon Bedrock AgentCore",
        "region": region,
        "primary_model": None,
        "environment": "aws",
        "application": name,
        "endpoint_ref": raw.get("agentRuntimeArn") or runtime_id,
        "telemetry_source": "aws",
        "status": (raw.get("status") or "discovered").lower(),
        "account_id": account_id,
        "provider_raw_reference": runtime_id,
    }


def _discover_sync(config: dict[str, Any]) -> dict[str, Any]:
    account_id = str(config.get("account_id") or os.environ.get("AWS_ACCOUNT_ID") or "")
    region = str(config.get("region") or os.environ.get("AWS_REGION") or "")

    if not account_id:
        raise AWSDiscoveryError(
            "account_id is required for AWS discovery. Set AWS_ACCOUNT_ID in .env or Configure.",
            stage="configuration",
        )
    if not ACCOUNT_ID_RE.match(account_id):
        raise AWSDiscoveryError(
            "AWS Account ID must be a 12-digit number.",
            stage="configuration",
        )
    if not region:
        raise AWSDiscoveryError(
            "AWS region is required for discovery.",
            stage="configuration",
        )

    session = _session(config)
    identity = _caller_identity(session)
    caller_account = str(identity.get("Account") or "")
    if caller_account and caller_account != account_id:
        raise AWSDiscoveryError(
            f"Configured account_id {account_id} does not match STS caller account "
            f"{caller_account}. Update Account ID in Configure or use credentials for the "
            "correct AWS account.",
            stage="permissions",
        )

    errors: list[str] = []
    scanned: list[str] = []
    discovered: list[dict[str, Any]] = []

    bedrock_raw, bedrock_errors = _list_bedrock_agents(session, region)
    errors.extend(bedrock_errors)
    if bedrock_raw or not bedrock_errors:
        scanned.append(f"bedrock-agent:{region}")
    for item in bedrock_raw:
        discovered.append(
            _normalize_bedrock_agent(raw=item, account_id=account_id, region=region)
        )

    agentcore_raw, agentcore_errors = _list_agentcore_runtimes(session, region)
    errors.extend(agentcore_errors)
    if agentcore_raw:
        scanned.append(f"agentcore:{region}")
    for item in agentcore_raw:
        discovered.append(
            _normalize_agentcore_runtime(raw=item, account_id=account_id, region=region)
        )

    unique: dict[str, dict[str, Any]] = {}
    for agent in discovered:
        unique[agent["id"]] = agent
    agents = list(unique.values())

    if agents:
        message = (
            f"Discovered {len(agents)} agent(s) in AWS account {account_id} "
            f"(region {region})."
        )
    else:
        message = (
            f"Connection to AWS account {account_id} succeeded (region {region}). "
            f"Scanned {', '.join(scanned) if scanned else 'Bedrock / AgentCore APIs'}. "
            "No agents discovered. Confirm Bedrock Agents or AgentCore runtimes exist "
            "in this region and that the IAM principal has bedrock:ListAgents permission."
        )

    return {
        "agents": agents,
        "accounts_scanned": scanned,
        "errors": errors,
        "message": message,
        "account_id": account_id,
        "region": region,
    }


async def discover_agents_in_account(config: dict[str, Any]) -> dict[str, Any]:
    """Discover agents. Returns {agents, accounts_scanned, errors, message}."""
    return await asyncio.to_thread(_discover_sync, config)


async def validate_aws_connection(config: dict[str, Any]) -> dict[str, Any]:
    """Lightweight live validation for test connection."""
    try:
        result = await asyncio.to_thread(_validate_sync, config)
        return result
    except AWSDiscoveryError as exc:
        return {"ok": False, "message": exc.message, "stage": exc.stage}


def _validate_sync(config: dict[str, Any]) -> dict[str, Any]:
    account_id = str(config.get("account_id") or os.environ.get("AWS_ACCOUNT_ID") or "")
    region = str(config.get("region") or os.environ.get("AWS_REGION") or "")

    if not account_id or not region:
        return {
            "ok": False,
            "message": "AWS account_id and region are required.",
            "stage": "configuration",
        }

    session = _session(config)
    identity = _caller_identity(session)
    caller_account = str(identity.get("Account") or "")
    arn = str(identity.get("Arn") or "")

    if caller_account and caller_account != account_id:
        return {
            "ok": False,
            "message": (
                f"STS account {caller_account} does not match configured account {account_id}."
            ),
            "stage": "permissions",
        }

    return {
        "ok": True,
        "message": (
            f"AWS credentials validated for account {caller_account or account_id} "
            f"({arn.split('/')[-1] if arn else 'caller'}). "
            f"Region {region}. Enable the integration, then click Refresh Discovery."
        ),
        "stage": "complete",
    }
