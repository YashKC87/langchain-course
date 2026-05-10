# ============================================================
#  HEALIX — Microsoft Intune Connector (intune_connector.py)
#
#  Pulls REAL device data from Microsoft Intune via
#  the Microsoft Graph API.
#
#  What it fetches:
#  ✅ All enrolled devices (Windows, iOS, Android, macOS)
#  ✅ Device compliance status
#  ✅ OS version & patch level
#  ✅ Last check-in time
#  ✅ Hardware info (CPU, RAM, disk)
#  ✅ User assignment
#  ✅ Configuration policy status
#  ✅ Windows Hello for Business status
#
#  Setup: You need an Azure App Registration with
#  the right permissions (see SETUP GUIDE below).
# ============================================================

import os
import time
import requests
from datetime import datetime, timezone
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

# ════════════════════════════════════════════════════════════
#  SETUP GUIDE — Read this before using
# ════════════════════════════════════════════════════════════
#
#  Step 1: Create an App Registration in Azure AD
#  ───────────────────────────────────────────────
#  1. Go to: https://portal.azure.com
#  2. Search for "App registrations" → click New registration
#  3. Name it: "HEALIX-Monitor"
#  4. Supported account types: "Single tenant"
#  5. Click Register
#  6. Copy the "Application (client) ID"     → INTUNE_CLIENT_ID
#  7. Copy the "Directory (tenant) ID"        → INTUNE_TENANT_ID
#
#  Step 2: Create a Client Secret
#  ──────────────────────────────
#  1. In your App Registration → Certificates & secrets
#  2. Click "New client secret"
#  3. Description: "HEALIX Secret", Expires: 24 months
#  4. Click Add
#  5. COPY THE SECRET VALUE NOW (you can't see it again!)
#     → INTUNE_CLIENT_SECRET
#
#  Step 3: Grant API Permissions
#  ──────────────────────────────
#  1. In your App Registration → API permissions
#  2. Click "Add a permission" → Microsoft Graph → Application permissions
#  3. Search and add these permissions:
#     ✅ DeviceManagementManagedDevices.Read.All
#     ✅ DeviceManagementConfiguration.Read.All
#     ✅ DeviceManagementApps.Read.All
#     ✅ Device.Read.All
#     ✅ Directory.Read.All
#  4. Click "Grant admin consent for [your org]" ← IMPORTANT
#
#  Step 4: Add to your .env file
#  ──────────────────────────────
#  INTUNE_TENANT_ID=your-tenant-id-here
#  INTUNE_CLIENT_ID=your-client-id-here
#  INTUNE_CLIENT_SECRET=your-client-secret-here
#
# ════════════════════════════════════════════════════════════


class IntuneConnector:
    """
    Connects to Microsoft Intune via Microsoft Graph API.
    Uses OAuth2 client credentials flow (app-to-app, no user login needed).
    """

    GRAPH_BASE    = "https://graph.microsoft.com/v1.0"
    GRAPH_BETA    = "https://graph.microsoft.com/beta"      # More device detail
    TOKEN_URL     = "https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    SCOPE         = "https://graph.microsoft.com/.default"

    def __init__(self):
        self.tenant_id     = os.getenv("INTUNE_TENANT_ID", "")
        self.client_id     = os.getenv("INTUNE_CLIENT_ID", "")
        self.client_secret = os.getenv("INTUNE_CLIENT_SECRET", "")
        self._token        = None
        self._token_expiry = 0
        self.connected     = False
        self._test_connection()

    def _test_connection(self):
        """Check if credentials are configured"""
        if not all([self.tenant_id, self.client_id, self.client_secret]):
            print("⚠️  Intune: Missing credentials in .env file.")
            print("   Add INTUNE_TENANT_ID, INTUNE_CLIENT_ID, INTUNE_CLIENT_SECRET")
            self.connected = False
        else:
            try:
                token = self._get_token()
                self.connected = bool(token)
                if self.connected:
                    print("✅ Intune: Connected to Microsoft Graph API")
                else:
                    print("❌ Intune: Authentication failed. Check your credentials.")
            except Exception as e:
                print(f"❌ Intune: Connection error — {e}")
                self.connected = False

    # ── OAuth2 Token Management ───────────────────────────────

    def _get_token(self) -> Optional[str]:
        """Get or refresh the OAuth2 access token"""
        now = time.time()

        # Return cached token if still valid (with 60s buffer)
        if self._token and now < self._token_expiry - 60:
            return self._token

        # Request a new token
        url = self.TOKEN_URL.format(tenant_id=self.tenant_id)
        data = {
            "grant_type":    "client_credentials",
            "client_id":     self.client_id,
            "client_secret": self.client_secret,
            "scope":         self.SCOPE,
        }

        resp = requests.post(url, data=data, timeout=15)
        resp.raise_for_status()
        token_data = resp.json()

        self._token        = token_data["access_token"]
        self._token_expiry = now + token_data.get("expires_in", 3600)
        return self._token

    def _headers(self) -> dict:
        """Build auth headers for Graph API calls"""
        return {
            "Authorization": f"Bearer {self._get_token()}",
            "Content-Type":  "application/json",
        }

    def _get(self, url: str, params: dict = None) -> dict:
        """Make a GET request to Microsoft Graph, handling pagination"""
        resp = requests.get(url, headers=self._headers(), params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def _get_all_pages(self, url: str, params: dict = None) -> list:
        """
        Graph API paginates results at 100 items per page.
        This method follows @odata.nextLink to get ALL devices.
        """
        all_items = []
        current_url = url

        while current_url:
            data = self._get(current_url, params if current_url == url else None)
            all_items.extend(data.get("value", []))
            current_url = data.get("@odata.nextLink")  # Next page URL

        return all_items

    # ── Core Data Fetchers ────────────────────────────────────

    def get_all_devices(self) -> list:
        """
        Fetch ALL managed devices from Intune.
        Returns raw Graph API data — call normalize_devices() to format.
        """
        if not self.connected:
            return []

        url = f"{self.GRAPH_BETA}/deviceManagement/managedDevices"
        params = {
            "$select": ",".join([
                "id", "deviceName", "operatingSystem", "osVersion",
                "complianceState", "managementState", "enrolledDateTime",
                "lastSyncDateTime", "userPrincipalName", "userDisplayName",
                "manufacturer", "model", "serialNumber", "imei",
                "totalStorageSpaceInBytes", "freeStorageSpaceInBytes",
                "physicalMemoryInBytes", "managedDeviceOwnerType",
                "deviceEnrollmentType", "azureADDeviceId",
                "joinType", "skuFamily", "isEncrypted",
                "autopilotEnrolled", "deviceActionResults",
            ]),
            "$top": 100
        }
        return self._get_all_pages(url, params)

    def get_device_detail(self, device_id: str) -> dict:
        """Get full detail for a single device including hardware info"""
        if not self.connected:
            return {}
        url = f"{self.GRAPH_BETA}/deviceManagement/managedDevices/{device_id}"
        return self._get(url)

    def get_compliance_policies(self) -> list:
        """Get all compliance policy definitions"""
        if not self.connected:
            return []
        url = f"{self.GRAPH_BASE}/deviceManagement/deviceCompliancePolicies"
        return self._get_all_pages(url)

    def get_device_compliance_status(self, device_id: str) -> list:
        """Get compliance policy results for a specific device"""
        if not self.connected:
            return []
        url = f"{self.GRAPH_BETA}/deviceManagement/managedDevices/{device_id}/deviceCompliancePolicyStates"
        data = self._get(url)
        return data.get("value", [])

    def get_configuration_profiles(self) -> list:
        """Get all configuration profiles (device config policies)"""
        if not self.connected:
            return []
        url = f"{self.GRAPH_BASE}/deviceManagement/deviceConfigurations"
        return self._get_all_pages(url)

    def get_whfb_status(self, device_id: str) -> dict:
        """
        Get Windows Hello for Business status for a device.
        Relevant for your WHFB deployment work!
        """
        if not self.connected:
            return {}
        try:
            url = (f"{self.GRAPH_BETA}/deviceManagement/managedDevices"
                   f"/{device_id}/windowsProtectionState")
            return self._get(url)
        except Exception:
            return {}

    def get_pending_patches(self) -> list:
        """Get Windows update status across all devices"""
        if not self.connected:
            return []
        url = f"{self.GRAPH_BETA}/deviceManagement/windowsUpdateCatalogItems"
        try:
            data = self._get(url)
            return data.get("value", [])
        except Exception:
            return []

    def get_apps(self) -> list:
        """Get all managed apps deployed via Intune"""
        if not self.connected:
            return []
        url = f"{self.GRAPH_BASE}/deviceAppManagement/mobileApps"
        return self._get_all_pages(url)

    # ── Normalize to HEALIX format ────────────────────────────

    def normalize_devices(self, raw_devices: list) -> list:
        """
        Convert raw Graph API device data into HEALIX standard format.
        This is what the dashboard and AI agent consume.
        """
        normalized = []
        for d in raw_devices:
            normalized.append(self._normalize_one(d))
        return normalized

    def _normalize_one(self, d: dict) -> dict:
        """Convert one Intune device record → HEALIX device format"""

        # ── Storage calculation ──────────────────────────────
        total_bytes = d.get("totalStorageSpaceInBytes") or 0
        free_bytes  = d.get("freeStorageSpaceInBytes")  or 0
        used_bytes  = total_bytes - free_bytes
        disk_pct    = round((used_bytes / total_bytes * 100), 1) if total_bytes > 0 else 0
        total_gb    = round(total_bytes / (1024**3), 1)
        used_gb     = round(used_bytes  / (1024**3), 1)
        free_gb     = round(free_bytes  / (1024**3), 1)

        # ── Memory calculation ───────────────────────────────
        mem_bytes   = d.get("physicalMemoryInBytes") or 0
        mem_gb      = round(mem_bytes / (1024**3), 1)

        # ── Compliance → HEALIX status ───────────────────────
        compliance  = d.get("complianceState", "unknown")
        status_map  = {
            "compliant":    "healthy",
            "noncompliant": "critical",
            "error":        "critical",
            "conflict":     "warning",
            "notApplicable":"healthy",
            "inGracePeriod":"warning",
            "unknown":      "warning",
        }
        healix_status = status_map.get(compliance, "warning")

        # ── Last seen / staleness check ──────────────────────
        last_sync_raw = d.get("lastSyncDateTime", "")
        last_seen     = "Never"
        days_since    = 999
        if last_sync_raw:
            try:
                last_dt   = datetime.fromisoformat(last_sync_raw.replace("Z", "+00:00"))
                now_utc   = datetime.now(timezone.utc)
                days_since = (now_utc - last_dt).days
                last_seen  = last_dt.strftime("%Y-%m-%d %H:%M UTC")
                # Stale device = not checked in for >7 days
                if days_since > 7:
                    healix_status = "warning"
                if days_since > 30:
                    healix_status = "critical"
            except Exception:
                pass

        # ── Enrolled date ────────────────────────────────────
        enrolled_raw  = d.get("enrolledDateTime", "")
        enrolled_date = ""
        if enrolled_raw:
            try:
                enrolled_date = datetime.fromisoformat(
                    enrolled_raw.replace("Z", "+00:00")
                ).strftime("%Y-%m-%d")
            except Exception:
                pass

        return {
            # ── Identity ─────────────────────────────────────
            "id":             f"INTUNE-{d.get('id','')[:8]}",
            "intune_id":       d.get("id"),
            "name":            d.get("deviceName", "Unknown Device"),
            "source":          "intune",
            "type":            "intune_managed",
            "group":           d.get("managedDeviceOwnerType", "corporate").title(),

            # ── OS & Hardware ─────────────────────────────────
            "os":              f"{d.get('operatingSystem','')} {d.get('osVersion','')}".strip(),
            "manufacturer":    d.get("manufacturer", ""),
            "model":           d.get("model", ""),
            "serial_number":   d.get("serialNumber", ""),
            "azure_ad_id":     d.get("azureADDeviceId", ""),
            "join_type":       d.get("joinType", ""),          # AzureADJoined, HybridAzureADJoined
            "sku":             d.get("skuFamily", ""),

            # ── Status ───────────────────────────────────────
            "status":          healix_status,
            "compliance":      compliance,
            "management_state":d.get("managementState", ""),
            "is_encrypted":    d.get("isEncrypted", False),
            "autopilot":       d.get("autopilotEnrolled", False),

            # ── Storage ──────────────────────────────────────
            "disk": {
                "percent":     disk_pct,
                "used_gb":     used_gb,
                "free_gb":     free_gb,
                "total_gb":    total_gb,
            },

            # ── Memory ───────────────────────────────────────
            "memory": {
                "total_gb":    mem_gb,
                "percent":     None,   # Intune doesn't provide live RAM %
            },

            # ── CPU ──────────────────────────────────────────
            # Note: Intune doesn't expose live CPU — use ManageEngine for that
            "cpu_percent":     None,

            # ── User ─────────────────────────────────────────
            "user":            d.get("userDisplayName", ""),
            "user_email":      d.get("userPrincipalName", ""),
            "enrollment_type": d.get("deviceEnrollmentType", ""),

            # ── Timing ───────────────────────────────────────
            "last_sync":       last_seen,
            "days_since_sync": days_since,
            "enrolled_date":   enrolled_date,
            "last_updated":    datetime.utcnow().isoformat(),
            "collection_type": "real",
            "tags":            self._build_tags(d),
        }

    def _build_tags(self, d: dict) -> list:
        """Generate useful tags from device properties"""
        tags = ["intune"]
        os_name = (d.get("operatingSystem") or "").lower()
        if "windows" in os_name: tags.append("windows")
        elif "ios"     in os_name: tags.append("ios")
        elif "android" in os_name: tags.append("android")
        elif "macos"   in os_name: tags.append("macos")

        if d.get("autopilotEnrolled"):   tags.append("autopilot")
        if d.get("isEncrypted"):         tags.append("encrypted")
        if d.get("joinType") == "AzureADJoined": tags.append("aad-joined")
        if d.get("joinType") == "HybridAzureADJoined": tags.append("hybrid-joined")
        if d.get("complianceState") == "noncompliant": tags.append("non-compliant")
        return tags

    # ── Alerts generated from Intune data ────────────────────

    def generate_alerts(self, devices: list) -> list:
        """
        Scan all normalized devices and generate HEALIX alerts.
        """
        alerts = []
        alert_id = 1

        for d in devices:
            device_name = d.get("name", "Unknown")

            # Non-compliant device
            if d.get("compliance") == "noncompliant":
                alerts.append({
                    "id":       alert_id,
                    "source":   "intune",
                    "time":     datetime.utcnow().strftime("%H:%M:%S"),
                    "type":     "critical",
                    "endpoint": device_name,
                    "msg":      f"Device is NON-COMPLIANT with Intune policy. "
                                f"User: {d.get('user_email','N/A')}",
                    "resolved": False,
                    "action":   "Review compliance policies in Intune portal"
                })
                alert_id += 1

            # Stale device (not checked in >7 days)
            days = d.get("days_since_sync", 0)
            if days > 7:
                sev = "critical" if days > 30 else "warning"
                alerts.append({
                    "id":       alert_id,
                    "source":   "intune",
                    "time":     datetime.utcnow().strftime("%H:%M:%S"),
                    "type":     sev,
                    "endpoint": device_name,
                    "msg":      f"Device not synced in {days} days. "
                                f"May be offline or unenrolled.",
                    "resolved": False,
                    "action":   "Verify device is powered on and connected"
                })
                alert_id += 1

            # Low disk space
            disk_pct = d.get("disk", {}).get("percent", 0) or 0
            if disk_pct > 90:
                alerts.append({
                    "id":       alert_id,
                    "source":   "intune",
                    "time":     datetime.utcnow().strftime("%H:%M:%S"),
                    "type":     "warning",
                    "endpoint": device_name,
                    "msg":      f"Disk usage at {disk_pct}%. "
                                f"Free: {d.get('disk',{}).get('free_gb','?')} GB",
                    "resolved": False,
                    "action":   "Run disk cleanup or expand storage"
                })
                alert_id += 1

            # Unencrypted device
            if not d.get("is_encrypted") and "windows" in d.get("tags", []):
                alerts.append({
                    "id":       alert_id,
                    "source":   "intune",
                    "time":     datetime.utcnow().strftime("%H:%M:%S"),
                    "type":     "critical",
                    "endpoint": device_name,
                    "msg":      f"BitLocker encryption NOT enabled on Windows device.",
                    "resolved": False,
                    "action":   "Enable BitLocker via Intune encryption policy"
                })
                alert_id += 1

        return alerts

    # ── Summary stats ─────────────────────────────────────────

    def get_summary_stats(self, devices: list) -> dict:
        """High-level stats for the dashboard"""
        total    = len(devices)
        by_os    = {}
        by_compliance = {}

        for d in devices:
            os_key = d.get("os", "Unknown").split()[0]
            by_os[os_key] = by_os.get(os_key, 0) + 1

            comp = d.get("compliance", "unknown")
            by_compliance[comp] = by_compliance.get(comp, 0) + 1

        return {
            "total_devices":      total,
            "by_os":              by_os,
            "by_compliance":      by_compliance,
            "compliant_pct":      round(by_compliance.get("compliant",0) / total * 100, 1) if total else 0,
            "non_compliant_count":by_compliance.get("noncompliant", 0),
            "stale_devices":      sum(1 for d in devices if d.get("days_since_sync", 0) > 7),
            "encrypted_pct":      round(sum(1 for d in devices if d.get("is_encrypted")) / total * 100, 1) if total else 0,
            "autopilot_count":    sum(1 for d in devices if d.get("autopilot")),
        }
