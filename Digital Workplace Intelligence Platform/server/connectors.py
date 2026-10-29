"""Enterprise connector framework.

Every connector reports the same health fields: status, auth method, capabilities, last successful sync,
freshness, collection errors, rate-limit state and ingestion volume. Nothing here invents values:
a connector without credentials reports "not_configured", and one with credentials but no collector in this
release reports "configured" with an authentication test only. Secrets come from environment variables
(or a secret store that populates them) and are never returned by the API.
"""
import os
import time

import httpx

ONLINE = 90


class Connector:
    id = name = domain = auth = ""
    capabilities: list[str] = []
    env: list[str] = []          # required settings
    frequency = "n/a"

    def configured(self) -> bool:
        return all(os.environ.get(k) for k in self.env)

    def health(self, db) -> dict:
        ok = self.configured()
        return {"id": self.id, "name": self.name, "domain": self.domain, "auth": self.auth,
                "capabilities": self.capabilities, "frequency": self.frequency,
                "status": "configured" if ok else "not_configured",
                "missing_settings": [k for k in self.env if not os.environ.get(k)],
                "last_sync": None, "freshness_s": None, "errors": [], "rate_limit": None, "volume_1h": None,
                "note": ("Credentials present. Data collection arrives in a later release; use Test to check sign-in."
                         if ok else "Not configured: no data is shown for this source.")}

    async def test(self) -> dict:
        return {"ok": False, "detail": "No test available"}


class DWIPAgents(Connector):
    id, name, domain, auth = "dwip-agent", "DWIP endpoint agent", "Endpoint", "Per-device key"
    capabilities = ["Device vitals", "Apps", "OS health", "VDI session", "Surveys", "Remediation"]
    frequency = "Every 15-60 s (push)"
    demo = 0

    def configured(self):
        return True

    def health(self, db):
        h = super().health(db)
        now = time.time()
        r = db.one("SELECT COUNT(*) n, MAX(last_seen) last, SUM(last_seen>?) online FROM devices WHERE "
                   "COALESCE(demo,0)=?", (now - ONLINE, self.demo))
        vol = db.one("SELECT COUNT(*) n FROM telemetry t JOIN devices d ON d.id=t.device_id WHERE t.ts>? AND "
                     "COALESCE(d.demo,0)=?", (now - 3600, self.demo))["n"]
        stale = r["n"] - (r["online"] or 0)
        h.update(status="connected" if r["online"] else ("stale" if r["n"] else "no_data"),
                 last_sync=r["last"], freshness_s=round(now - r["last"]) if r["last"] else None,
                 volume_1h=vol, devices=r["n"],
                 errors=[f"{stale} device(s) not reporting for over {ONLINE}s"] if stale else [],
                 note="Live telemetry pushed by enrolled devices.")
        return h


class DWIPSimulator(DWIPAgents):
    id, name = "dwip-simulator", "DWIP simulator (demo data)"
    capabilities = ["Synthetic fleet for testing"]
    frequency = "Every 3 s (push)"
    demo = 1

    def health(self, db):
        h = super().health(db)
        h["note"] = "Synthetic devices. Shown with a DEMO badge and excluded by the 'Live only' filter."
        return h


class MicrosoftGraph(Connector):
    """Shared Entra ID app registration (client credentials) used by Intune, M365, Teams and OneDrive."""
    auth = "Entra ID app (client credentials)"
    env = ["DWIP_ENTRA_TENANT_ID", "DWIP_ENTRA_CLIENT_ID", "DWIP_ENTRA_CLIENT_SECRET"]
    scope = "https://graph.microsoft.com/.default"

    async def test(self):
        if not self.configured():
            return {"ok": False, "detail": "Missing settings: " + ", ".join(self.health(None)["missing_settings"])}
        url = f"https://login.microsoftonline.com/{os.environ['DWIP_ENTRA_TENANT_ID']}/oauth2/v2.0/token"
        try:
            async with httpx.AsyncClient(timeout=15) as c:
                r = await c.post(url, data={"grant_type": "client_credentials", "scope": self.scope,
                                            "client_id": os.environ["DWIP_ENTRA_CLIENT_ID"],
                                            "client_secret": os.environ["DWIP_ENTRA_CLIENT_SECRET"]})
            return {"ok": r.status_code == 200, "detail": "Token issued" if r.status_code == 200
                    else f"Sign-in failed (HTTP {r.status_code})"}
        except httpx.HTTPError as e:
            return {"ok": False, "detail": f"Network error: {type(e).__name__}"}


def _graph(id_, name, domain, caps, freq="Scheduled pull (planned: 15 min)"):
    return type(id_, (MicrosoftGraph,), {"id": id_, "name": name, "domain": domain, "capabilities": caps,
                                         "frequency": freq})()


class ServiceNow(Connector):
    id, name, domain, auth = "servicenow", "ServiceNow", "ITSM", "Basic auth or OAuth"
    capabilities = ["Incidents", "Change requests", "Create/update incidents (Release 3)"]
    env = ["DWIP_SNOW_INSTANCE", "DWIP_SNOW_USER", "DWIP_SNOW_PASSWORD"]
    frequency = "Scheduled pull (planned: 5 min)"

    async def test(self):
        if not self.configured():
            return {"ok": False, "detail": "Missing settings"}
        url = f"https://{os.environ['DWIP_SNOW_INSTANCE']}/api/now/table/incident?sysparm_limit=1"
        try:
            async with httpx.AsyncClient(timeout=15) as c:
                r = await c.get(url, auth=(os.environ["DWIP_SNOW_USER"], os.environ["DWIP_SNOW_PASSWORD"]))
            return {"ok": r.status_code == 200, "detail": f"HTTP {r.status_code}"}
        except httpx.HTTPError as e:
            return {"ok": False, "detail": f"Network error: {type(e).__name__}"}


def _plain(id_, name, domain, auth, env, caps, freq="Scheduled pull"):
    return type(id_, (Connector,), {"id": id_, "name": name, "domain": domain, "auth": auth, "env": env,
                                    "capabilities": caps, "frequency": freq})()


REGISTRY: list[Connector] = [
    DWIPAgents(),
    DWIPSimulator(),
    _graph("intune", "Microsoft Intune", "Endpoint management",
           ["Compliance state", "BitLocker status", "Device sync", "Inventory"]),
    _graph("m365", "Microsoft 365 service health", "Cloud services", ["Service incidents", "Advisories"]),
    _graph("teams", "Microsoft Teams call quality", "Application", ["Call quality records (CQD)"]),
    _graph("onedrive", "OneDrive", "Application", ["Sync health reports"]),
    type("azmon", (MicrosoftGraph,), {"id": "azure-monitor", "name": "Azure Monitor / Log Analytics (AVD)",
                                      "domain": "Virtual desktop", "scope": "https://api.loganalytics.io/.default",
                                      "env": MicrosoftGraph.env + ["DWIP_LA_WORKSPACE_ID"],
                                      "capabilities": ["AVD connections", "Session host metrics", "FSLogix events"],
                                      "frequency": "Scheduled query (planned: 5 min)"})(),
    type("azvm", (Connector,), {"id": "azure-vms", "name": "Azure virtual machines", "domain": "Virtual machines",
                               "auth": "Entra ID app or Azure CLI (az login)", "env": [],
                               "capabilities": ["Discover VMs", "Power state", "Push the DWIP agent (Run Command)"],
                               "frequency": "On demand (Devices → Azure VMs)",
                               "health": lambda self, db: {**Connector.health(self, db), "status": "configured",
                                                           "note": "Open Devices → Azure VMs to list and onboard VMs. "
                                                                   "Uses DWIP_ENTRA_* or the server's az login."}})(),
    ServiceNow(),
    _plain("sccm", "MECM / SCCM", "Endpoint management", "SQL or AdminService (Windows auth)",
           ["DWIP_SCCM_ADMINSERVICE_URL"], ["Deployments", "Software updates", "Collections"]),
    _plain("nexthink", "Nexthink", "DEX platform", "API credentials (authorised access only)",
           ["DWIP_NEXTHINK_URL", "DWIP_NEXTHINK_CLIENT_ID", "DWIP_NEXTHINK_CLIENT_SECRET"],
           ["NQL query export"]),
    _plain("splunk", "Splunk", "Observability", "HEC / search token", ["DWIP_SPLUNK_URL", "DWIP_SPLUNK_TOKEN"],
           ["Event search", "Forward DWIP events"]),
]


def by_id(cid: str) -> Connector | None:
    return next((c for c in REGISTRY if c.id == cid), None)
