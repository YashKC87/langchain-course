# ============================================================
#  HEALIX Intune Client — integrations/intune_client.py
#  Microsoft Intune device management integration.
#  Device inventory, compliance, and remote actions.
# ============================================================

import logging
from typing import Optional, List, Dict
from datetime import datetime, timezone, timedelta

from integrations.base_client import MicrosoftBaseClient

logger = logging.getLogger("healix.intune")


class IntuneClient(MicrosoftBaseClient):
    """Microsoft Intune API client via Microsoft Graph."""

    async def list_managed_devices(self, top: int = 100) -> List[Dict]:
        """List all Intune-managed devices."""
        if not self.is_available:
            return self._demo_devices()

        params = {
            "$top": top,
            "$select": "id,deviceName,operatingSystem,osVersion,complianceState,"
                       "managedDeviceOwnerType,enrolledDateTime,lastSyncDateTime,"
                       "model,manufacturer,serialNumber,userPrincipalName,"
                       "deviceRegistrationState,managementAgent,isEncrypted",
        }
        result = await self._get("/deviceManagement/managedDevices", params=params)
        if result and "value" in result:
            return result["value"]
        return self._demo_devices()

    async def get_device(self, device_id: str) -> Optional[Dict]:
        """Get detailed info about a specific managed device."""
        if not self.is_available:
            return self._demo_device_detail(device_id)

        result = await self._get(f"/deviceManagement/managedDevices/{device_id}")
        return result or self._demo_device_detail(device_id)

    async def get_compliance_policies(self) -> List[Dict]:
        """List device compliance policies."""
        if not self.is_available:
            return self._demo_compliance_policies()

        result = await self._get("/deviceManagement/deviceCompliancePolicies")
        if result and "value" in result:
            return result["value"]
        return self._demo_compliance_policies()

    async def get_device_compliance_state(self, device_id: str) -> Optional[Dict]:
        """Get compliance state for a specific device."""
        if not self.is_available:
            return {"complianceState": "compliant", "deviceId": device_id, "_demo": True}

        result = await self._get(
            f"/deviceManagement/managedDevices/{device_id}",
            params={"$select": "id,deviceName,complianceState,complianceGracePeriodExpirationDateTime"}
        )
        return result

    async def get_detected_apps(self, top: int = 50) -> List[Dict]:
        """List detected applications across managed devices."""
        if not self.is_available:
            return self._demo_detected_apps()

        result = await self._get("/deviceManagement/detectedApps",
                                 params={"$top": top, "$orderby": "deviceCount desc"})
        if result and "value" in result:
            return result["value"]
        return self._demo_detected_apps()

    async def trigger_device_action(self, device_id: str, action: str) -> Optional[Dict]:
        """Execute a remote action on a managed device.
        Actions: rebootNow, remoteLock, syncDevice, windowsDefenderScan,
                 retire, wipe, resetPasscode
        """
        if not self.is_available:
            return {
                "status": "demo_mode",
                "device_id": device_id,
                "action": action,
                "message": f"Action '{action}' simulated in demo mode",
            }

        result = await self._post(f"/deviceManagement/managedDevices/{device_id}/{action}")
        return result or {"status": "triggered", "device_id": device_id, "action": action}

    async def get_device_configurations(self) -> List[Dict]:
        """List device configuration profiles."""
        if not self.is_available:
            return self._demo_configurations()

        result = await self._get("/deviceManagement/deviceConfigurations")
        if result and "value" in result:
            return result["value"]
        return self._demo_configurations()

    async def sync_endpoints_to_db(self, db) -> int:
        """Pull Intune devices and upsert into the local endpoints table."""
        devices = await self.list_managed_devices()
        count = 0
        for d in devices:
            if d.get("_demo"):
                continue
            await db.upsert_endpoint(
                id=f"INTUNE-{d['id'][:8]}",
                name=d.get("deviceName", "Unknown"),
                os=f"{d.get('operatingSystem', '')} {d.get('osVersion', '')}".strip(),
                status="healthy" if d.get("complianceState") == "compliant" else "warning",
                source="intune",
                intune_device_id=d["id"],
                last_seen_at=d.get("lastSyncDateTime"),
                metadata={
                    "model": d.get("model"),
                    "manufacturer": d.get("manufacturer"),
                    "serialNumber": d.get("serialNumber"),
                    "userPrincipalName": d.get("userPrincipalName"),
                    "isEncrypted": d.get("isEncrypted"),
                },
            )
            count += 1
        logger.info(f"Synced {count} devices from Intune")
        return count

    # ── Demo data ───────────────────────────────────────────────

    def _demo_devices(self) -> List[Dict]:
        now = datetime.now(timezone.utc)
        return [
            {
                "id": "d1a2b3c4-0001", "deviceName": "PROD-SRV-01",
                "operatingSystem": "Windows", "osVersion": "10.0.20348.2159",
                "complianceState": "compliant", "managedDeviceOwnerType": "company",
                "enrolledDateTime": (now - timedelta(days=180)).isoformat(),
                "lastSyncDateTime": (now - timedelta(minutes=15)).isoformat(),
                "model": "Virtual Machine", "manufacturer": "Microsoft Corporation",
                "serialNumber": "VM-001-PROD", "userPrincipalName": "admin@contoso.com",
                "isEncrypted": True, "_demo": True,
            },
            {
                "id": "d1a2b3c4-0002", "deviceName": "PROD-SRV-02",
                "operatingSystem": "Linux", "osVersion": "Ubuntu 22.04 LTS",
                "complianceState": "noncompliant", "managedDeviceOwnerType": "company",
                "enrolledDateTime": (now - timedelta(days=120)).isoformat(),
                "lastSyncDateTime": (now - timedelta(hours=2)).isoformat(),
                "model": "Standard_D4s_v3", "manufacturer": "Microsoft Corporation",
                "serialNumber": "VM-002-PROD", "userPrincipalName": "devops@contoso.com",
                "isEncrypted": False, "_demo": True,
            },
            {
                "id": "d1a2b3c4-0003", "deviceName": "DEV-WS-015",
                "operatingSystem": "Windows", "osVersion": "10.0.22631.2861",
                "complianceState": "compliant", "managedDeviceOwnerType": "company",
                "enrolledDateTime": (now - timedelta(days=90)).isoformat(),
                "lastSyncDateTime": (now - timedelta(minutes=45)).isoformat(),
                "model": "Surface Laptop 5", "manufacturer": "Microsoft Corporation",
                "serialNumber": "SL5-015-DEV", "userPrincipalName": "developer@contoso.com",
                "isEncrypted": True, "_demo": True,
            },
            {
                "id": "d1a2b3c4-0004", "deviceName": "EDGE-NODE-07",
                "operatingSystem": "Linux", "osVersion": "Alpine 3.18",
                "complianceState": "noncompliant", "managedDeviceOwnerType": "company",
                "enrolledDateTime": (now - timedelta(days=60)).isoformat(),
                "lastSyncDateTime": (now - timedelta(hours=6)).isoformat(),
                "model": "IoT Edge Device", "manufacturer": "Custom",
                "serialNumber": "EDGE-007", "userPrincipalName": "iot@contoso.com",
                "isEncrypted": False, "_demo": True,
            },
        ]

    def _demo_device_detail(self, device_id: str) -> Dict:
        devices = self._demo_devices()
        for d in devices:
            if d["id"] == device_id:
                return d
        return devices[0] if devices else {}

    def _demo_compliance_policies(self) -> List[Dict]:
        return [
            {
                "id": "pol-001", "displayName": "Windows Compliance Policy",
                "description": "Requires encryption, firewall, antivirus",
                "platform": "windows10AndLater",
                "scheduledActionsForRule": [{"ruleName": "PasswordRequired"}],
                "_demo": True,
            },
            {
                "id": "pol-002", "displayName": "Linux Baseline Compliance",
                "description": "Requires minimum OS version, SSH key auth",
                "platform": "linux",
                "scheduledActionsForRule": [{"ruleName": "OSVersionRequired"}],
                "_demo": True,
            },
        ]

    def _demo_detected_apps(self) -> List[Dict]:
        return [
            {"displayName": "Microsoft Edge", "version": "120.0.2210.91", "deviceCount": 45, "_demo": True},
            {"displayName": "Visual Studio Code", "version": "1.85.1", "deviceCount": 32, "_demo": True},
            {"displayName": "OpenSSL", "version": "3.0.7", "deviceCount": 18, "_demo": True},
            {"displayName": "Node.js", "version": "20.5.1", "deviceCount": 12, "_demo": True},
        ]

    def _demo_configurations(self) -> List[Dict]:
        return [
            {
                "id": "cfg-001", "displayName": "Windows Security Baseline",
                "description": "Enforces BitLocker, Windows Firewall, Defender ATP",
                "platform": "windows10AndLater", "_demo": True,
            },
            {
                "id": "cfg-002", "displayName": "Endpoint Protection",
                "description": "Real-time protection, cloud-delivered protection",
                "platform": "windows10AndLater", "_demo": True,
            },
        ]
