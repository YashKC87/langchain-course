"""Azure virtual machines: discover VMs in a subscription, show which report to DWIP, and push the agent.

Credentials, in order:
1. Entra ID app (client credentials): DWIP_ENTRA_TENANT_ID / DWIP_ENTRA_CLIENT_ID / DWIP_ENTRA_CLIENT_SECRET
2. the Azure CLI's signed-in account (`az login`) on the DWIP server
Subscription: DWIP_AZURE_SUBSCRIPTION_ID, else the CLI's default subscription.
The identity needs Reader to list VMs and "Virtual Machine Contributor" to run the agent install command.
"""
import asyncio
import json
import os
import shutil
import subprocess
import time

import httpx

ARM = "https://management.azure.com"
API = "2024-07-01"
_token: tuple[float, str, str] = (0.0, "", "")   # expires_at, token, method


def _cli(*args) -> str | None:
    az = shutil.which("az") or shutil.which("az.cmd")
    if not az:
        return None
    r = subprocess.run([az, *args, "-o", "json"], capture_output=True, text=True, timeout=60)
    return r.stdout if r.returncode == 0 else None


async def token() -> tuple[str, str]:
    """(bearer token, method) or raises RuntimeError with what is missing."""
    global _token
    if _token[0] > time.time() + 60:
        return _token[1], _token[2]
    t, c, s = (os.environ.get(k) for k in ("DWIP_ENTRA_TENANT_ID", "DWIP_ENTRA_CLIENT_ID", "DWIP_ENTRA_CLIENT_SECRET"))
    if t and c and s:
        async with httpx.AsyncClient(timeout=20) as cl:
            r = await cl.post(f"https://login.microsoftonline.com/{t}/oauth2/v2.0/token",
                              data={"grant_type": "client_credentials", "scope": f"{ARM}/.default",
                                    "client_id": c, "client_secret": s})
        if r.status_code != 200:
            raise RuntimeError(f"Entra ID sign-in failed (HTTP {r.status_code})")
        d = r.json()
        _token = (time.time() + int(d.get("expires_in", 3000)), d["access_token"], "Entra ID app")
        return _token[1], _token[2]
    out = await asyncio.to_thread(_cli, "account", "get-access-token", "--resource", ARM)
    if not out:
        raise RuntimeError("No Azure credentials: set DWIP_ENTRA_* or run 'az login' on the DWIP server")
    d = json.loads(out)
    _token = (d.get("expires_on") or time.time() + 1800, d["accessToken"], "Azure CLI (az login)")
    return _token[1], _token[2]


async def subscription() -> str:
    sub = os.environ.get("DWIP_AZURE_SUBSCRIPTION_ID")
    if sub:
        return sub
    out = await asyncio.to_thread(_cli, "account", "show")
    if not out:
        raise RuntimeError("Set DWIP_AZURE_SUBSCRIPTION_ID or run 'az login'")
    return json.loads(out)["id"]


async def list_vms(db) -> dict:
    tok, method = await token()
    sub = await subscription()
    base = f"{ARM}/subscriptions/{sub}/providers/Microsoft.Compute/virtualMachines?api-version={API}"

    async def pages(cl, url):
        out = []
        while url:   # ARM pages with nextLink
            r = await cl.get(url)
            if r.status_code != 200:
                raise RuntimeError(f"Azure returned HTTP {r.status_code}: {r.text[:200]}")
            d = r.json()
            out += d.get("value", [])
            url = d.get("nextLink")
        return out
    async with httpx.AsyncClient(timeout=30, headers={"Authorization": f"Bearer {tok}"}) as cl:
        # the model listing has size and OS; the status-only listing has power state
        vms, status = await asyncio.gather(pages(cl, base), pages(cl, base + "&statusOnly=true"))
    power_by_id = {}
    for v in status:
        sts = (v.get("properties", {}).get("instanceView") or {}).get("statuses", [])
        power_by_id[v["id"].lower()] = next((x["displayStatus"] for x in sts if x.get("code", "").startswith("PowerState/")),
                                            "unknown")
    known = {}
    for dev in db.q("SELECT id, hostname, last_seen, dex, metrics FROM devices"):
        az = json.loads(dev["metrics"] or "{}").get("azure") or {}
        if az.get("vmId"):
            known[az["vmId"].lower()] = dev
    out = []
    for v in vms:
        p = v.get("properties", {})
        power = power_by_id.get(v["id"].lower(), "unknown")
        dev = known.get((p.get("vmId") or "").lower())
        out.append({"id": v["id"], "name": v["name"], "location": v.get("location"),
                    "resource_group": v["id"].split("/")[4], "size": (p.get("hardwareProfile") or {}).get("vmSize"),
                    "os": (p.get("storageProfile", {}).get("osDisk") or {}).get("osType"), "power": power,
                    "vm_id": p.get("vmId"), "device_id": dev and dev["id"], "dex": dev and dev["dex"],
                    "last_seen": dev and dev["last_seen"]})
    return {"subscription": sub, "auth": method, "vms": sorted(out, key=lambda x: x["name"].lower())}


def install_script(os_type: str, server: str, enroll_token: str) -> list[str]:
    if os_type == "Windows":
        return [
            "$ErrorActionPreference = 'Stop'",
            "New-Item -ItemType Directory -Force C:\\ProgramData\\DWIP | Out-Null",
            f"Invoke-WebRequest -UseBasicParsing '{server}/download/dwip-agent.exe' -OutFile C:\\ProgramData\\DWIP\\dwip-agent-setup.exe",
            f"& C:\\ProgramData\\DWIP\\dwip-agent-setup.exe install --server '{server}' --token '{enroll_token}'",
        ]
    return ["echo 'DWIP agent install via Run Command is Windows-only in this release'", "exit 1"]


async def deploy(resource_id: str, os_type: str, server: str, enroll_token: str) -> dict:
    """Start an Azure Run Command that downloads and installs the agent. Returns once Azure accepts it."""
    tok, _ = await token()
    cmd = "RunPowerShellScript" if os_type == "Windows" else "RunShellScript"
    async with httpx.AsyncClient(timeout=30, headers={"Authorization": f"Bearer {tok}"}) as cl:
        r = await cl.post(f"{ARM}{resource_id}/runCommand?api-version={API}",
                          json={"commandId": cmd, "script": install_script(os_type, server, enroll_token)})
    return {"accepted": r.status_code in (200, 202), "status": r.status_code,
            "detail": "Install started; the VM appears in DWIP within a few minutes" if r.status_code in (200, 202)
            else r.text[:300]}
