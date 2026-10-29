"""Agentless Azure VM telemetry: Azure Monitor platform metrics for the VMs in ONE connected subscription.

Every few minutes DWIP reads each running VM's platform metrics (CPU, available memory, OS disk IOPS, network,
availability, CPU credits) and feeds them through the same pipeline as agent telemetry, so rules, thresholds,
alerts, predictions and the notification box all apply. A VM that also runs the DWIP agent keeps its agent
data (richer: apps, OS health, disk used), and the agentless sample is skipped for it.
Platform metrics have no guest view: disk space used, apps and OS events need the agent.
"""
import asyncio
import json
import re
import secrets
import time

import httpx
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel

from . import azure, connectors
from .core import Ctx

METRICS = ["Percentage CPU", "Available Memory Percentage", "OS Disk IOPS Consumed Percentage",
           "Network In Total", "Network Out Total", "VmAvailabilityMetric", "CPU Credits Remaining"]
SUB_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
AGENT_FRESH = 600     # an agent sample this recent wins over the agentless one


class MonitorIn(BaseModel):
    subscription_id: str
    enabled: bool = True
    interval_s: int = 300


def load(db) -> dict:
    row = db.one("SELECT value FROM settings WHERE key='azure_monitor'")
    return json.loads(row["value"]) if row else {"subscription_id": None, "enabled": False, "interval_s": 300}


def save(db, cfg: dict):
    db.x("INSERT OR REPLACE INTO settings(key,value) VALUES('azure_monitor',?)", (json.dumps(cfg),))


async def _get(cl, url):
    r = await cl.get(url)
    if r.status_code != 200:
        raise RuntimeError(f"Azure HTTP {r.status_code}: {r.text[:200]}")
    return r.json()


async def _vms(cl, sub):
    base = f"{azure.ARM}/subscriptions/{sub}/providers/Microsoft.Compute/virtualMachines?api-version={azure.API}"
    models, status = await asyncio.gather(_get(cl, base), _get(cl, base + "&statusOnly=true"))
    power = {}
    for v in status.get("value", []):
        sts = (v.get("properties", {}).get("instanceView") or {}).get("statuses", [])
        power[v["id"].lower()] = next((x["displayStatus"] for x in sts if x.get("code", "").startswith("PowerState/")), "unknown")
    return [(v, power.get(v["id"].lower(), "unknown")) for v in models.get("value", [])]


async def _metrics(cl, rid) -> dict:
    names = ",".join(METRICS)
    d = await _get(cl, f"{azure.ARM}{rid}/providers/Microsoft.Insights/metrics?api-version=2018-01-01"
                       f"&metricnames={names}&interval=PT5M&timespan=PT30M&aggregation=Average,Total")
    out = {}
    for m in d.get("value", []):
        pts = [p for p in (m.get("timeseries") or [{}])[0].get("data", []) if p.get("average") is not None]
        if pts:
            out[m["name"]["value"]] = pts[-1]
    return out


async def _private_ip(cl, vm) -> list[str]:
    nics = (vm.get("properties", {}).get("networkProfile") or {}).get("networkInterfaces", [])
    if not nics:
        return []
    try:
        n = await _get(cl, f"{azure.ARM}{nics[0]['id']}?api-version=2024-05-01")
    except RuntimeError:
        return []
    return [c["properties"].get("privateIPAddress") for c in n.get("properties", {}).get("ipConfigurations", [])
            if c.get("properties", {}).get("privateIPAddress")]


def to_metrics(raw: dict, vm: dict, power: str, sub: str, ips: list[str]) -> dict:
    g = lambda k, f="average": (raw.get(k) or {}).get(f)
    m = {"source": "azure-monitor", "power_state": power, "ip_addresses": ips,
         "azure": {"vmId": vm["properties"].get("vmId"), "name": vm["name"], "location": vm.get("location"),
                   "vmSize": (vm["properties"].get("hardwareProfile") or {}).get("vmSize"),
                   "resourceGroupName": vm["id"].split("/")[4], "subscriptionId": sub, "resourceId": vm["id"],
                   "osType": ((vm["properties"].get("storageProfile") or {}).get("osDisk") or {}).get("osType")},
         "metrics_ts": max((p["timeStamp"] for p in raw.values() if p.get("timeStamp")), default=None)}
    if g("Percentage CPU") is not None:
        m["cpu_pct"] = round(g("Percentage CPU"), 1)
    if g("Available Memory Percentage") is not None:
        m["mem_pct"] = round(100 - g("Available Memory Percentage"), 1)
    if g("OS Disk IOPS Consumed Percentage") is not None:
        m["os_disk_iops_pct"] = round(g("OS Disk IOPS Consumed Percentage"), 1)
    if g("Network In Total", "total") is not None:
        m["network_in_mb_5m"] = round(g("Network In Total", "total") / 1e6, 2)
    if g("Network Out Total", "total") is not None:
        m["network_out_mb_5m"] = round(g("Network Out Total", "total") / 1e6, 2)
    if g("VmAvailabilityMetric") is not None:
        m["vm_availability"] = g("VmAvailabilityMetric")
    if g("CPU Credits Remaining") is not None:
        m["cpu_credits_remaining"] = round(g("CPU Credits Remaining"), 1)
    return m


def register(app: FastAPI, ctx: Ctx, ingest, Telemetry):
    db = ctx.db
    state = {"last_run": None, "last_ok": None, "error": None, "vms": [], "running": False}

    def upsert(vm, m) -> dict:
        did = "az-" + (vm["properties"].get("vmId") or vm["name"]).lower()
        os_type = (m["azure"]["osType"] or "Windows").lower()
        if not db.one("SELECT id FROM devices WHERE id=?", (did,)):
            db.x("INSERT INTO devices(id,key,hostname,kind,platform,os_version,model,user,department,location,demo,"
                 "enrolled_at,dex,scores,metrics) VALUES(?,?,?,?,?,?,?,?,?,?,0,?,NULL,'{}','{}')",
                 (did, secrets.token_urlsafe(24), vm["name"], "vdi", os_type, "Azure VM", f"Azure VM {m['azure']['vmSize']}",
                  "", m["azure"]["resourceGroupName"], f"Azure {vm.get('location')}", time.time()))
        return db.one("SELECT * FROM devices WHERE id=?", (did,))

    async def collect() -> dict:
        cfg = load(db)
        sub = cfg.get("subscription_id")
        if not sub:
            raise RuntimeError("No subscription connected")
        state.update(running=True, last_run=time.time())
        try:
            tok, method = await azure.token()
            agents = {}
            for d in db.q("SELECT id, last_seen, metrics FROM devices WHERE id NOT LIKE 'az-%'"):
                az = json.loads(d["metrics"] or "{}").get("azure") or {}
                if az.get("vmId"):
                    agents[az["vmId"].lower()] = d
            rows = []
            async with httpx.AsyncClient(timeout=30, headers={"Authorization": f"Bearer {tok}"}) as cl:
                for vm, power in await _vms(cl, sub):
                    vid = (vm["properties"].get("vmId") or "").lower()
                    ag = agents.get(vid)
                    row = {"name": vm["name"], "power": power, "resource_group": vm["id"].split("/")[4],
                           "location": vm.get("location")}
                    if ag and ag["last_seen"] and time.time() - ag["last_seen"] < AGENT_FRESH:
                        rows.append({**row, "mode": "agent", "device_id": ag["id"]})
                        continue
                    if "running" not in power:
                        dev = db.one("SELECT id FROM devices WHERE id=?", ("az-" + vid,))
                        rows.append({**row, "mode": "stopped", "device_id": dev and dev["id"]})
                        continue
                    raw = await _metrics(cl, vm["id"])
                    m = to_metrics(raw, vm, power, sub, await _private_ip(cl, vm))
                    dev = upsert(vm, m)
                    res = await ingest(dev, Telemetry(metrics=m, apps=[]))
                    rows.append({**row, "mode": "azure-monitor", "device_id": dev["id"], "dex": res["dex"],
                                 "metrics": {k: m.get(k) for k in ("cpu_pct", "mem_pct", "os_disk_iops_pct",
                                                                   "cpu_credits_remaining", "vm_availability")}})
            state.update(vms=rows, last_ok=time.time(), error=None, auth=method)
            return {"ok": True, "vms": rows}
        except (RuntimeError, httpx.HTTPError) as e:
            state["error"] = str(e)
            raise
        finally:
            state["running"] = False

    async def loop():
        while True:
            cfg = load(db)
            if cfg.get("enabled") and cfg.get("subscription_id"):
                try:
                    await collect()
                except (RuntimeError, httpx.HTTPError):
                    pass   # state['error'] shows it on the connector card
            await asyncio.sleep(max(60, cfg.get("interval_s") or 300))

    @app.on_event("startup")
    async def _start():
        ctx.spawn(loop())

    who = lambda r: (getattr(r.state, "actor", "local-dev"), getattr(r.state, "role", "admin"))

    @app.get("/api/azure/monitor")
    def status():
        return {**load(db), **{k: v for k, v in state.items()}}

    @app.post("/api/azure/monitor")
    async def configure(c: MonitorIn, request: Request):
        if not SUB_RE.match(c.subscription_id):
            raise HTTPException(400, "subscription_id must be a GUID")
        cfg = {"subscription_id": c.subscription_id.lower(), "enabled": c.enabled,
               "interval_s": max(60, min(c.interval_s, 3600))}
        save(db, cfg)
        ctx.audit(*who(request), "azure.monitor.configure", c.subscription_id, "ok",
                  f"enabled={c.enabled} every {cfg['interval_s']}s")
        return cfg

    @app.post("/api/azure/monitor/collect")
    async def collect_now(request: Request):
        try:
            r = await collect()
        except (RuntimeError, httpx.HTTPError) as e:
            raise HTTPException(502, str(e))
        ctx.audit(*who(request), "azure.monitor.collect", load(db)["subscription_id"], "ok", f"{len(r['vms'])} VMs")
        return r

    # connector card: real status of this collector
    con = connectors.by_id("azure-vms")
    if con:
        def health(self, _db):
            cfg = load(db)
            h = connectors.Connector.health(self, db)
            h.update(status=("not_configured" if not cfg.get("subscription_id") else
                             "stale" if state["error"] else "connected" if state["last_ok"] else "configured"),
                     auth=state.get("auth") or self.auth, last_sync=state["last_ok"],
                     freshness_s=round(time.time() - state["last_ok"]) if state["last_ok"] else None,
                     volume_1h=len([v for v in state["vms"] if v.get("mode") == "azure-monitor"]) or None,
                     errors=[state["error"]] if state["error"] else [],
                     frequency=f"Every {cfg.get('interval_s', 300)} s (Azure Monitor platform metrics)",
                     note=(f"Subscription {cfg['subscription_id']}: {len(state['vms'])} VMs. Agentless: CPU, memory, "
                           "OS disk IOPS, network, availability, CPU credits. Install the agent for disk space, apps "
                           "and OS events.") if cfg.get("subscription_id") else "Connect a subscription in Devices → Azure VMs.")
            return h
        con.health = health.__get__(con)
