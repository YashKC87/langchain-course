"""Operations: device notification inbox, offline watch, remote access, agent download, Azure VMs, demo purge."""
import asyncio
import json
import os
import time

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel

from . import azure
from .core import ONLINE_WINDOW, Ctx

DIST = os.path.join(os.path.dirname(__file__), "..", "dist")
# events that belong in the monitored-device notification box
INBOX_KINDS = ("issue", "alert", "executed", "failed", "resolved", "enroll", "offline", "online", "conversation")
DEVICE_TABLES = ("telemetry", "issues", "actions", "notifications", "surveys", "events", "apps_current",
                 "app_samples", "alerts", "guide_deliveries", "rollups", "flow_runs")


class Deploy(BaseModel):
    resource_ids: list[str]
    server_url: str


async def watch_offline(ctx: Ctx):
    """Raise one 'offline' event when a monitored device stops reporting, and 'online' when it returns."""
    down: set[str] = set()
    while True:
        await asyncio.sleep(30)
        now = time.time()
        for d in ctx.db.q("SELECT id, hostname, last_seen FROM devices WHERE COALESCE(demo,0)=0"):
            off = not d["last_seen"] or now - d["last_seen"] > ONLINE_WINDOW
            if off and d["id"] not in down:
                down.add(d["id"])
                await ctx.event(d["id"], "offline", f"{d['hostname']} stopped reporting")
            elif not off and d["id"] in down:
                down.discard(d["id"])
                await ctx.event(d["id"], "online", f"{d['hostname']} is reporting again")


def register(app: FastAPI, ctx: Ctx, enroll_token: str):
    db = ctx.db
    who = lambda r: (getattr(r.state, "actor", "local-dev"), getattr(r.state, "role", "admin"))

    @app.on_event("startup")
    async def _start_watch():
        ctx.spawn(watch_offline(ctx))

    # ---------- notification box: monitored (non-demo) devices only ----------
    @app.get("/api/device-notifications")
    def device_notifications(after: int = 0, limit: int = 50):
        rows = db.q("SELECT e.id, e.ts, e.kind, e.message, e.device_id, d.hostname, d.kind device_kind FROM events e "
                    "JOIN devices d ON d.id=e.device_id WHERE COALESCE(d.demo,0)=0 AND e.id>? AND e.kind IN (%s) "
                    "ORDER BY e.id DESC LIMIT ?" % ",".join("?" * len(INBOX_KINDS)),
                    (after, *INBOX_KINDS, min(limit, 200)))
        return {"items": rows, "monitored": db.one("SELECT COUNT(*) n FROM devices WHERE COALESCE(demo,0)=0")["n"]}

    # ---------- remote access ----------
    def remote_options(dev: dict) -> dict:
        m = json.loads(dev["metrics"] or "{}")
        ips, az = m.get("ip_addresses") or [], m.get("azure")
        windows = dev["platform"] in ("windows", "avd", "citrix") or (az or {}).get("osType") == "Windows"
        online = bool(dev["last_seen"] and time.time() - dev["last_seen"] < ONLINE_WINDOW)
        opts = []
        if windows and dev["kind"] != "mobile":
            opts.append({"id": "rdp", "label": "Remote Desktop (RDP)", "target": ips[0] if ips else dev["hostname"],
                         "note": "Needs Remote Desktop enabled on the device and network reach (VPN/LAN) from your PC."})
            opts.append({"id": "assist", "label": "Ask the user to share their screen (Quick Assist)",
                         "note": "Sends the employee a notification; they open Quick Assist and give you the code."})
        if az and az.get("resourceId"):
            opts.append({"id": "bastion", "label": "Azure Bastion (browser)",
                         "url": f"https://portal.azure.com/#@/resource{az['resourceId']}/connect",
                         "note": "Opens the Azure portal connect page for this VM. Needs Bastion on its virtual network."})
        return {"device_id": dev["id"], "hostname": dev["hostname"], "online": online, "ip_addresses": ips,
                "options": opts,
                "unsupported": None if opts else "Remote control isn't available for this device type."}

    @app.get("/api/devices/{device_id}/remote")
    def remote(device_id: str):
        return remote_options(ctx.device(device_id))

    @app.get("/api/devices/{device_id}/remote.rdp")
    def remote_rdp(device_id: str, request: Request):
        dev = ctx.device(device_id)
        opt = next((o for o in remote_options(dev)["options"] if o["id"] == "rdp"), None)
        if not opt:
            raise HTTPException(400, "RDP isn't available for this device")
        ctx.audit(*who(request), "remote.rdp", dev["hostname"], "ok", opt["target"])
        body = f"full address:s:{opt['target']}\r\nprompt for credentials:i:1\r\nscreen mode id:i:2\r\n" \
               f"use multimon:i:0\r\nauthentication level:i:2\r\n"
        return PlainTextResponse(body, media_type="application/x-rdp",
                                 headers={"Content-Disposition": f'attachment; filename="{dev["hostname"]}.rdp"'})

    @app.post("/api/devices/{device_id}/remote/assist")
    async def remote_assist(device_id: str, request: Request):
        dev = ctx.device(device_id)
        actor, role = who(request)
        ctx.notify(device_id, f"IT ({actor}) would like to help you remotely. Press Win+Ctrl+Q to open Quick Assist, "
                              "choose 'Help someone… / Get help' and share the code IT gives you.", "message", force=True)
        await ctx.event(device_id, "remote", f"{actor} requested a remote assistance session with {dev['hostname']}")
        ctx.audit(actor, role, "remote.assist", dev["hostname"], "requested")
        return {"sent": True}

    # ---------- agent package ----------
    @app.get("/download/dwip-agent.exe")
    def agent_exe():
        path = os.path.join(DIST, "dwip-agent.exe")
        if not os.path.exists(path):
            raise HTTPException(404, "Agent package not built yet: run packaging\\build_agent.ps1 on the DWIP server")
        return FileResponse(path, filename="dwip-agent.exe", media_type="application/octet-stream")

    @app.get("/api/agent-package")
    def agent_package():
        path = os.path.join(DIST, "dwip-agent.exe")
        ok = os.path.exists(path)
        return {"available": ok, "size_mb": round(os.path.getsize(path) / 1e6, 1) if ok else None,
                "built_at": os.path.getmtime(path) if ok else None, "url": "/download/dwip-agent.exe",
                "default_token": enroll_token == "dev-token"}

    # ---------- Azure VMs ----------
    @app.get("/api/azure/vms")
    async def azure_vms():
        try:
            return {"ok": True, **await azure.list_vms(db)}
        except (RuntimeError, OSError) as e:
            return {"ok": False, "error": str(e), "vms": []}

    @app.post("/api/azure/vms/deploy")
    async def azure_deploy(d: Deploy, request: Request):
        if not d.server_url.startswith(("http://", "https://")):
            raise HTTPException(400, "server_url must be the DWIP address the VMs can reach")
        listing = await azure.list_vms(db)
        by_id = {v["id"].lower(): v for v in listing["vms"]}
        results = []
        for rid in d.resource_ids[:20]:               # batch limit
            vm = by_id.get(rid.lower())
            if not vm:
                results.append({"id": rid, "accepted": False, "detail": "VM not found in this subscription"})
                continue
            r = await azure.deploy(vm["id"], vm["os"] or "Windows", d.server_url.rstrip("/"), enroll_token)
            results.append({"id": rid, "name": vm["name"], **r})
            ctx.audit(*who(request), "azure.deploy_agent", vm["name"], "started" if r["accepted"] else "failed",
                      r["detail"][:200])
        return {"results": results}

    # ---------- remove synthetic data ----------
    @app.post("/api/admin/purge-demo")
    def purge_demo(request: Request):
        ids = [r["id"] for r in db.q("SELECT id FROM devices WHERE COALESCE(demo,0)=1")]
        if ids:
            marks = ",".join("?" * len(ids))
            db.x(f"DELETE FROM messages WHERE conversation_id IN (SELECT id FROM conversations WHERE device_id IN ({marks}))",
                 tuple(ids))
            db.x(f"DELETE FROM conversations WHERE device_id IN ({marks})", tuple(ids))
            for t in DEVICE_TABLES:
                db.x(f"DELETE FROM {t} WHERE device_id IN ({marks})", tuple(ids))
            db.x(f"DELETE FROM devices WHERE id IN ({marks})", tuple(ids))
        # fleet alerts were built from demo devices too; clear the ones no live device supports
        db.x("DELETE FROM alerts WHERE scope='fleet' AND type NOT IN "
             "(SELECT type FROM issues WHERE status='open')")
        ctx.audit(*who(request), "admin.purge_demo", f"{len(ids)} devices", "ok")
        return {"removed_devices": len(ids)}
