# ============================================================
#  HEALIX — ManageEngine Connector (manageengine_connector.py)
#
#  Integrates with ManageEngine Endpoint Central (formerly
#  Desktop Central) and ManageEngine ServiceDesk Plus.
#
#  What it fetches:
#  ✅ All managed computers with live CPU, RAM, Disk
#  ✅ Patch compliance status per device
#  ✅ Software inventory
#  ✅ Vulnerability scan results
#  ✅ Remote control / remediation triggers
#  ✅ Scheduled patch deployment
#  ✅ ServiceDesk Plus tickets (if configured)
#
#  Supports both:
#  - ManageEngine Cloud (https://endpointcentral.manageengine.com)
#  - ManageEngine On-Premise (your internal server URL)
#
#  SETUP GUIDE: See comments below.
# ============================================================

import os
import requests
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

# ════════════════════════════════════════════════════════════
#  SETUP GUIDE — ManageEngine Endpoint Central
# ════════════════════════════════════════════════════════════
#
#  For CLOUD edition:
#  ──────────────────
#  1. Log in to https://endpointcentral.manageengine.com
#  2. Go to Admin → API → Generate API Key
#  3. Copy the API key
#  4. Add to .env:
#       ME_BASE_URL=https://endpointcentral.manageengine.com
#       ME_API_KEY=your-api-key-here
#       ME_PRODUCT=endpoint_central
#
#  For ON-PREMISE edition:
#  ────────────────────────
#  1. Log in to your ManageEngine server (e.g. http://your-server:8020)
#  2. Go to Admin → API → Generate API Key
#  3. Add to .env:
#       ME_BASE_URL=http://your-server:8020
#       ME_API_KEY=your-api-key-here
#       ME_PRODUCT=endpoint_central
#
#  For ServiceDesk Plus (ticket integration):
#  ───────────────────────────────────────────
#       ME_SERVICEDESK_URL=http://your-servicedesk:8080
#       ME_SERVICEDESK_API_KEY=your-servicedesk-key
#
#  API Documentation:
#  https://www.manageengine.com/products/desktop-central/api/
#
# ════════════════════════════════════════════════════════════


class ManageEngineConnector:
    """
    Connects to ManageEngine Endpoint Central (Desktop Central)
    and optionally ServiceDesk Plus.
    """

    # API endpoints inside ManageEngine
    API_PATHS = {
        # Computer inventory
        "computers":          "/api/1.4/desktop/computers",
        "computer_detail":    "/api/1.4/desktop/computers/{computer_id}",
        # Hardware/software
        "hardware_detail":    "/api/1.4/desktop/hardwaredetails",
        "software_detail":    "/api/1.4/desktop/softwaredetails",
        # Patch management
        "patch_summary":      "/api/1.4/patch/viewpatchdetails",
        "missing_patches":    "/api/1.4/patch/computerswithpatchstatus",
        "patch_status":       "/api/1.4/patch/computerpatchstatus",
        "deploy_patch":       "/api/1.4/patch/deploypatches",
        # Remote tools
        "remote_shutdown":    "/api/1.4/desktop/remotecommands",
        "run_script":         "/api/1.4/desktop/runscript",
        # Vulnerability
        "vulnerabilities":    "/api/1.4/cve/details",
        # Reports
        "disk_report":        "/api/1.4/reports/diskspacereport",
        "memory_report":      "/api/1.4/reports/memorydetails",
        "cpu_report":         "/api/1.4/reports/cpudetails",
    }

    def __init__(self):
        self.base_url        = os.getenv("ME_BASE_URL", "").rstrip("/")
        self.api_key         = os.getenv("ME_API_KEY", "")
        self.product         = os.getenv("ME_PRODUCT", "endpoint_central")
        self.sd_url          = os.getenv("ME_SERVICEDESK_URL", "").rstrip("/")
        self.sd_api_key      = os.getenv("ME_SERVICEDESK_API_KEY", "")
        self.connected       = False
        self._test_connection()

    def _test_connection(self):
        """Verify ManageEngine credentials work"""
        if not self.base_url or not self.api_key:
            print("⚠️  ManageEngine: Missing credentials in .env file.")
            print("   Add ME_BASE_URL and ME_API_KEY")
            self.connected = False
            return

        try:
            # Quick test — fetch 1 computer
            resp = self._get(self.API_PATHS["computers"], params={"pagelimit": 1})
            if resp.get("message_response"):
                self.connected = True
                total = resp.get("message_response", {}).get("computers", {}).get("totalcount", 0)
                print(f"✅ ManageEngine: Connected. {total} computers managed.")
            else:
                self.connected = False
                print("❌ ManageEngine: Connected but unexpected response format.")
        except Exception as e:
            self.connected = False
            print(f"❌ ManageEngine: Connection failed — {e}")

    # ── Core HTTP Helper ──────────────────────────────────────

    def _get(self, path: str, params: dict = None) -> dict:
        """GET request to ManageEngine API"""
        url = f"{self.base_url}{path}"
        headers = {
            "Authorization": f"Basic {self.api_key}",  # ManageEngine uses Basic auth
        }
        all_params = {"Authorization": self.api_key}
        if params:
            all_params.update(params)

        resp = requests.get(url, headers=headers, params=all_params, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def _post(self, path: str, data: dict = None) -> dict:
        """POST request to ManageEngine API"""
        url = f"{self.base_url}{path}"
        headers = {
            "Authorization": f"Basic {self.api_key}",
            "Content-Type":  "application/json",
        }
        params = {"Authorization": self.api_key}
        resp = requests.post(url, headers=headers, params=params,
                             json=data or {}, timeout=30)
        resp.raise_for_status()
        return resp.json()

    # ── Device / Computer Fetchers ────────────────────────────

    def get_all_computers(self, page: int = 1, page_limit: int = 200) -> list:
        """
        Fetch all managed computers from ManageEngine.
        Paginates automatically to get all devices.
        """
        if not self.connected:
            return []

        all_computers = []
        current_page  = page
        total_fetched  = 0

        while True:
            try:
                resp = self._get(
                    self.API_PATHS["computers"],
                    params={
                        "pagenumber": current_page,
                        "pagelimit":  page_limit,
                    }
                )
                msg   = resp.get("message_response", {})
                comps = msg.get("computers", {})

                batch = comps.get("computer", [])
                if not batch:
                    break

                all_computers.extend(batch)
                total_fetched += len(batch)

                # Check if there are more pages
                total_count = int(comps.get("totalcount", 0))
                if total_fetched >= total_count:
                    break
                current_page += 1

            except Exception as e:
                print(f"ManageEngine: Error fetching page {current_page}: {e}")
                break

        return all_computers

    def get_computer_detail(self, computer_id: str) -> dict:
        """Get full hardware + software detail for one computer"""
        if not self.connected:
            return {}
        try:
            path = self.API_PATHS["computer_detail"].format(computer_id=computer_id)
            resp = self._get(path)
            return resp.get("message_response", {}).get("computerdetails", {})
        except Exception as e:
            return {"error": str(e)}

    def get_hardware_details(self, computer_id: str) -> dict:
        """Get CPU, RAM, disk details for a specific computer"""
        if not self.connected:
            return {}
        try:
            resp = self._get(
                self.API_PATHS["hardware_detail"],
                params={"computerid": computer_id}
            )
            return resp.get("message_response", {}).get("hardwaredetails", {})
        except Exception:
            return {}

    def get_cpu_report(self) -> list:
        """Get CPU utilization report across all devices"""
        if not self.connected:
            return []
        try:
            resp = self._get(self.API_PATHS["cpu_report"])
            return resp.get("message_response", {}).get("cpudetails", [])
        except Exception:
            return []

    def get_memory_report(self) -> list:
        """Get RAM usage report across all devices"""
        if not self.connected:
            return []
        try:
            resp = self._get(self.API_PATHS["memory_report"])
            return resp.get("message_response", {}).get("memorydetails", [])
        except Exception:
            return []

    def get_disk_report(self) -> list:
        """Get disk space report across all devices"""
        if not self.connected:
            return []
        try:
            resp = self._get(self.API_PATHS["disk_report"])
            return resp.get("message_response", {}).get("diskspacereport", [])
        except Exception:
            return []

    # ── Patch Management ──────────────────────────────────────

    def get_patch_status(self, computer_id: str = None) -> dict:
        """
        Get patch compliance status.
        If computer_id provided: status for that device.
        Otherwise: summary across all devices.
        """
        if not self.connected:
            return {}
        try:
            params = {}
            if computer_id:
                params["computerid"] = computer_id
            resp = self._get(self.API_PATHS["patch_status"], params=params)
            return resp.get("message_response", {})
        except Exception as e:
            return {"error": str(e)}

    def get_missing_patches(self, severity: str = None) -> list:
        """
        Get list of computers with missing patches.
        severity: "critical", "important", "moderate", "low"
        """
        if not self.connected:
            return []
        try:
            params = {"status": "missing"}
            if severity:
                params["severity"] = severity
            resp = self._get(self.API_PATHS["missing_patches"], params=params)
            return resp.get("message_response", {}).get("computers", [])
        except Exception:
            return []

    def deploy_patch(self, patch_id: str, computer_ids: list,
                     schedule_time: str = None) -> dict:
        """
        Deploy a specific patch to a list of computers.
        schedule_time format: "2024-12-01 02:00:00"
        If schedule_time is None, deploys immediately.
        """
        if not self.connected:
            return {"error": "Not connected"}
        try:
            payload = {
                "patchid":     patch_id,
                "computerids": computer_ids,
            }
            if schedule_time:
                payload["scheduledtime"] = schedule_time

            resp = self._post(self.API_PATHS["deploy_patch"], data=payload)
            return resp.get("message_response", {})
        except Exception as e:
            return {"error": str(e)}

    # ── Remote Actions ────────────────────────────────────────

    def run_remote_script(self, computer_id: str, script: str,
                          script_type: str = "powershell") -> dict:
        """
        Run a PowerShell or batch script on a remote Windows device.
        Great for remediation actions!

        Example — kill a process:
        run_remote_script("123", "Stop-Process -Name 'myapp' -Force", "powershell")

        Example — restart a service:
        run_remote_script("123", "Restart-Service W3SVC", "powershell")
        """
        if not self.connected:
            return {"error": "Not connected"}
        try:
            payload = {
                "computerid":  computer_id,
                "script":      script,
                "scripttype":  script_type,   # "powershell" or "batch"
            }
            resp = self._post(self.API_PATHS["run_script"], data=payload)
            return resp.get("message_response", {})
        except Exception as e:
            return {"error": str(e)}

    def get_vulnerabilities(self, computer_id: str = None) -> list:
        """Get CVE vulnerability details"""
        if not self.connected:
            return []
        try:
            params = {}
            if computer_id:
                params["computerid"] = computer_id
            resp = self._get(self.API_PATHS["vulnerabilities"], params=params)
            return resp.get("message_response", {}).get("cvedetails", [])
        except Exception:
            return []

    # ── ServiceDesk Plus Integration ──────────────────────────

    def create_ticket(self, subject: str, description: str,
                      category: str = "Software", priority: str = "High",
                      device_name: str = None) -> dict:
        """
        Create a ServiceDesk Plus ticket for a detected issue.
        Automatically triggered when HEALIX detects critical problems.
        """
        if not self.sd_url or not self.sd_api_key:
            return {"error": "ServiceDesk Plus not configured"}

        url = f"{self.sd_url}/api/v3/requests"
        headers = {"TECHNICIAN_KEY": self.sd_api_key}

        ticket_data = {
            "request": {
                "subject":     subject,
                "description": f"{description}\n\nDetected by: HEALIX Autonomous Monitor\n"
                               f"Device: {device_name or 'N/A'}\n"
                               f"Time: {datetime.utcnow().isoformat()} UTC",
                "category":    {"name": category},
                "priority":    {"name": priority},
                "status":      {"name": "Open"},
            }
        }

        try:
            resp = requests.post(url, headers=headers, json=ticket_data, timeout=15)
            resp.raise_for_status()
            result = resp.json()
            ticket_id = result.get("request", {}).get("id")
            print(f"✅ ServiceDesk ticket created: #{ticket_id} — {subject}")
            return {"ticket_id": ticket_id, "status": "created"}
        except Exception as e:
            return {"error": str(e)}

    # ── Normalize to HEALIX format ────────────────────────────

    def normalize_computers(self, raw_computers: list,
                             cpu_data: list = None,
                             mem_data: list = None,
                             disk_data: list = None) -> list:
        """Convert ManageEngine computer list → HEALIX format"""

        # Build lookup maps for performance data
        cpu_map  = {str(c.get("computerid")): c for c in (cpu_data  or [])}
        mem_map  = {str(c.get("computerid")): c for c in (mem_data  or [])}
        disk_map = {str(c.get("computerid")): c for c in (disk_data or [])}

        return [self._normalize_one(c, cpu_map, mem_map, disk_map)
                for c in raw_computers]

    def _normalize_one(self, c: dict, cpu_map: dict,
                       mem_map: dict, disk_map: dict) -> dict:
        """Normalize one ManageEngine computer record"""
        comp_id   = str(c.get("computerid", ""))
        comp_name = c.get("computername", "Unknown")

        # ── Performance data from reports ────────────────────
        cpu_info  = cpu_map.get(comp_id,  {})
        mem_info  = mem_map.get(comp_id,  {})
        disk_info = disk_map.get(comp_id, {})

        cpu_pct   = float(cpu_info.get("cpuutilization", 0) or 0)
        mem_pct   = float(mem_info.get("memoryutilization", 0) or 0)
        disk_pct  = float(disk_info.get("diskutilization", 0) or 0)

        mem_total = float(mem_info.get("totalram", 0) or 0) / 1024   # MB → GB
        mem_used  = float(mem_info.get("usedram",  0) or 0) / 1024
        disk_total= float(disk_info.get("totaldisk",0) or 0) / 1024
        disk_used = float(disk_info.get("useddisk", 0) or 0) / 1024

        # ── Status from health + resource data ───────────────
        me_health = c.get("health", "").lower()
        status    = self._determine_status(cpu_pct, mem_pct, disk_pct, me_health)

        # ── Last seen ────────────────────────────────────────
        last_seen = c.get("lastseen", "")

        # ── OS ───────────────────────────────────────────────
        os_name   = c.get("osname",    "")
        os_ver    = c.get("osversion", "")
        os_full   = f"{os_name} {os_ver}".strip()

        # ── Patch status ─────────────────────────────────────
        patch_status = c.get("patchstatus", "")

        # ── Tags ─────────────────────────────────────────────
        tags = ["manageengine"]
        if os_name:
            if "windows" in os_name.lower(): tags.append("windows")
            elif "linux"  in os_name.lower(): tags.append("linux")
            elif "mac"    in os_name.lower(): tags.append("macos")
        if patch_status == "missing":   tags.append("patch-missing")
        if patch_status == "installed": tags.append("patch-ok")

        return {
            # ── Identity ─────────────────────────────────────
            "id":              f"ME-{comp_id}",
            "me_computer_id":  comp_id,
            "name":            comp_name,
            "source":          "manageengine",
            "type":            "me_managed",
            "group":           c.get("domain", c.get("group", "Managed")),

            # ── OS & Hardware ─────────────────────────────────
            "os":              os_full or "Unknown",
            "manufacturer":    c.get("manufacturer", ""),
            "model":           c.get("model", ""),
            "serial_number":   c.get("serialnumber", ""),
            "ip":              c.get("ipaddress", ""),
            "mac_address":     c.get("macaddress", ""),

            # ── Status ───────────────────────────────────────
            "status":          status,
            "health":          me_health,
            "patch_status":    patch_status,
            "agent_version":   c.get("agentversion", ""),

            # ── Performance ──────────────────────────────────
            "cpu_percent":     round(cpu_pct, 1),
            "memory": {
                "percent":     round(mem_pct, 1),
                "used_gb":     round(mem_used, 1),
                "total_gb":    round(mem_total, 1),
            },
            "disk": {
                "percent":     round(disk_pct, 1),
                "used_gb":     round(disk_used, 1),
                "total_gb":    round(disk_total, 1),
            },

            # ── Timing ───────────────────────────────────────
            "last_sync":       last_seen,
            "last_updated":    datetime.utcnow().isoformat(),
            "collection_type": "real",
            "tags":            tags,
        }

    def _determine_status(self, cpu: float, mem: float,
                          disk: float, health: str) -> str:
        if health in ["red", "critical"]:   return "critical"
        if health in ["yellow", "warning"]: return "warning"
        if cpu > 90 or mem > 90 or disk > 95: return "critical"
        if cpu > 75 or mem > 80 or disk > 85: return "warning"
        return "healthy"

    # ── Alerts from ManageEngine data ─────────────────────────

    def generate_alerts(self, devices: list) -> list:
        """Generate HEALIX alerts from ManageEngine device data"""
        alerts  = []
        alert_id = 100  # Start at 100 to avoid collision with Intune alerts

        for d in devices:
            name = d.get("name", "Unknown")
            cpu  = d.get("cpu_percent", 0) or 0
            mem  = d.get("memory", {}).get("percent", 0) or 0
            disk = d.get("disk", {}).get("percent", 0) or 0

            if cpu > 85:
                alerts.append({
                    "id":       alert_id,
                    "source":   "manageengine",
                    "time":     datetime.utcnow().strftime("%H:%M:%S"),
                    "type":     "critical" if cpu > 95 else "warning",
                    "endpoint": name,
                    "msg":      f"High CPU usage: {cpu}%. ManageEngine agent reporting.",
                    "resolved": False,
                    "action":   "Run HEALIX auto-remediation → kill zombie processes"
                })
                alert_id += 1

            if mem > 85:
                alerts.append({
                    "id":       alert_id,
                    "source":   "manageengine",
                    "time":     datetime.utcnow().strftime("%H:%M:%S"),
                    "type":     "critical" if mem > 95 else "warning",
                    "endpoint": name,
                    "msg":      f"High memory usage: {mem}%. "
                                f"Used: {d.get('memory',{}).get('used_gb','?')} GB",
                    "resolved": False,
                    "action":   "Restart non-critical services"
                })
                alert_id += 1

            if d.get("patch_status") == "missing":
                alerts.append({
                    "id":       alert_id,
                    "source":   "manageengine",
                    "time":     datetime.utcnow().strftime("%H:%M:%S"),
                    "type":     "warning",
                    "endpoint": name,
                    "msg":      "Missing security patches detected by ManageEngine.",
                    "resolved": False,
                    "action":   "Deploy patches via ManageEngine patch management"
                })
                alert_id += 1

        return alerts
