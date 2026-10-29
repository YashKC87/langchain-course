"""Console identity and role-based access.

Release 1 uses API tokens mapped to roles (env DWIP_IT_TOKENS="token:role[:name],...").
With no tokens configured the console runs in local-dev mode: everyone is admin and the UI says so.
Entra ID (OIDC) sign-in replaces tokens in a later release; the role checks below stay the same.
Devices never use these tokens: they authenticate with their own per-device key.
"""
import hashlib
import os
import secrets

ROLES = ("viewer", "analyst", "engineer", "admin")
RANK = {r: i for i, r in enumerate(ROLES)}
PERMISSIONS = {
    "viewer": "Read dashboards and ask AI Assist. Employee names are masked.",
    "analyst": "Viewer + acknowledge alerts, message employees, push guides and pulse surveys.",
    "engineer": "Analyst + approve fixes, run flows, remote access, push agents to Azure VMs, read the audit log.",
    "admin": "Engineer + change impact weights and connector settings, remove demo data.",
}
# device-facing endpoints authenticate with the device key instead
DEVICE_PATHS = ("/api/enroll", "/api/telemetry", "/api/agent/", "/api/ping")
READ_ONLY_POSTS = ("/api/assist", "/api/assistant/chat")


def load_tokens(spec: str | None = None) -> dict[str, tuple[str, str]]:
    """token -> (role, display name)."""
    spec = os.environ.get("DWIP_IT_TOKENS", "") if spec is None else spec
    out = {}
    for part in filter(None, (p.strip() for p in spec.split(","))):
        bits = part.split(":")
        if len(bits) >= 2 and bits[0] and bits[1] in RANK:
            name = bits[2] if len(bits) > 2 else f"{bits[1]}-{hashlib.sha256(bits[0].encode()).hexdigest()[:6]}"
            out[bits[0]] = (bits[1], name)
    return out


def resolve(tokens: dict, presented: str | None) -> tuple[str, str] | None:
    for tok, who in tokens.items():
        if presented and secrets.compare_digest(tok, presented):
            return who
    return None


def required_role(method: str, path: str) -> str:
    if path.startswith("/api/audit"):
        return "engineer"
    if path.startswith("/api/actions/"):
        return "engineer"
    if method != "GET" and path.startswith("/api/flows"):   # flows can queue remediation
        return "engineer"
    if method != "GET" and path.startswith(("/api/scripts", "/api/script-runs", "/api/thresholds")):
        return "engineer"
    if path.startswith("/api/admin/"):
        return "admin"
    if "/remote" in path or (method != "GET" and path.startswith("/api/azure")):   # remote access, agent pushes
        return "engineer"
    if method != "GET" and path.startswith(("/api/impact/config", "/api/connectors")):
        return "admin"
    if method == "GET" or path in READ_ONLY_POSTS:
        return "viewer"
    return "analyst"


def allowed(role: str, need: str) -> bool:
    return RANK.get(role, -1) >= RANK[need]
