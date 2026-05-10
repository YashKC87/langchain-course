# ============================================================
#  HEALIX Azure Monitor Client — integrations/azure_monitor_client.py
#  Agentless Azure VM polling via ARM API and Azure Monitor Metrics.
#  Subclasses MicrosoftBaseClient so MSAL/token handling is shared.
# ============================================================

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict

from .base_client import MicrosoftBaseClient

logger = logging.getLogger("healix.azure_monitor")

# ARM management endpoint
ARM_BASE = "https://management.azure.com"
ARM_SCOPE = "https://management.azure.com/.default"


class AzureMonitorClient(MicrosoftBaseClient):
    """ARM + Azure Monitor Metrics client for agentless VM monitoring."""

    SCOPE = ARM_SCOPE

    def __init__(self, tenant_id: str, client_id: str, client_secret: str,
                 subscription_id: str = ""):
        super().__init__(tenant_id, client_id, client_secret)
        self.subscription_id = subscription_id

    # ── VM listing ──────────────────────────────────────────────

    async def list_vms(self) -> List[Dict]:
        """List all VMs in the subscription with power state."""
        if not self._available:
            return self._demo_vms()

        if not self.subscription_id:
            logger.warning("AzureMonitorClient: No subscription_id configured.")
            return self._demo_vms()

        url = (
            f"{ARM_BASE}/subscriptions/{self.subscription_id}"
            "/providers/Microsoft.Compute/virtualMachines"
        )
        params = {"api-version": "2023-09-01", "$expand": "instanceView"}
        data = await self._request("GET", url, scope=ARM_SCOPE, params=params)

        if not data or "value" not in data:
            return self._demo_vms()

        vms = []
        for vm in data["value"]:
            props = vm.get("properties", {})
            iv = props.get("instanceView", {})
            statuses = iv.get("statuses", [])
            power_state = "unknown"
            for s in statuses:
                code = s.get("code", "")
                if code.startswith("PowerState/"):
                    power_state = code.replace("PowerState/", "")
                    break

            rg = vm.get("id", "").split("/resourceGroups/")
            resource_group = rg[1].split("/")[0] if len(rg) > 1 else ""

            vms.append({
                "id": vm.get("id", ""),
                "name": vm.get("name", ""),
                "location": vm.get("location", ""),
                "resource_group": resource_group,
                "os_type": props.get("storageProfile", {}).get("osDisk", {}).get("osType", ""),
                "vm_size": props.get("hardwareProfile", {}).get("vmSize", ""),
                "power_state": power_state,
                "status": _power_to_status(power_state),
                "_demo": False,
            })

        return vms if vms else self._demo_vms()

    async def get_vm_status(self, resource_group: str, vm_name: str) -> Dict:
        """Get instance view (power state) for a single VM."""
        if not self._available:
            return {"vm_name": vm_name, "power_state": "demo", "status": "demo"}

        url = (
            f"{ARM_BASE}/subscriptions/{self.subscription_id}/resourceGroups/{resource_group}"
            f"/providers/Microsoft.Compute/virtualMachines/{vm_name}/instanceView"
        )
        data = await self._request("GET", url, scope=ARM_SCOPE,
                                   params={"api-version": "2023-09-01"})

        if not data:
            return {"vm_name": vm_name, "error": "Not found or inaccessible"}

        statuses = data.get("statuses", [])
        power_state = "unknown"
        for s in statuses:
            code = s.get("code", "")
            if code.startswith("PowerState/"):
                power_state = code.replace("PowerState/", "")
                break

        return {
            "vm_name": vm_name,
            "resource_group": resource_group,
            "power_state": power_state,
            "status": _power_to_status(power_state),
            "statuses": statuses,
        }

    async def get_vm_metrics(self, resource_group: str, vm_name: str,
                             hours: int = 1) -> List[Dict]:
        """Get Azure Monitor metrics for a VM."""
        if not self._available:
            return self._demo_metrics(vm_name, hours)

        resource_id = (
            f"/subscriptions/{self.subscription_id}/resourceGroups/{resource_group}"
            f"/providers/Microsoft.Compute/virtualMachines/{vm_name}"
        )
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(hours=hours)

        metric_names = (
            "Percentage CPU,Available Memory Bytes,"
            "Disk Read Bytes,Disk Write Bytes,"
            "Network In Total,Network Out Total"
        )
        url = f"{ARM_BASE}{resource_id}/providers/microsoft.insights/metrics"
        params = {
            "api-version": "2023-10-01",
            "metricnames": metric_names,
            "aggregation": "Average,Maximum",
            "interval": "PT5M",
            "timespan": f"{start_time.strftime('%Y-%m-%dT%H:%M:%SZ')}/{end_time.strftime('%Y-%m-%dT%H:%M:%SZ')}",
        }
        data = await self._request("GET", url, scope=ARM_SCOPE, params=params)

        if not data or "value" not in data:
            return self._demo_metrics(vm_name, hours)

        results = []
        for metric in data["value"]:
            m_name = metric.get("name", {}).get("value", "")
            unit = metric.get("unit", "")
            ts_data = metric.get("timeseries", [{}])[0].get("data", []) if metric.get("timeseries") else []
            values = [d.get("average") for d in ts_data if d.get("average") is not None]
            results.append({
                "metric": m_name,
                "unit": unit,
                "average": round(sum(values) / len(values), 2) if values else None,
                "maximum": max(values) if values else None,
                "data_points": len(values),
            })

        return results if results else self._demo_metrics(vm_name, hours)

    async def sync_vms_to_db(self, db) -> int:
        """Upsert all Azure VMs into the endpoints table. Returns count."""
        vms = await self.list_vms()
        count = 0
        for vm in vms:
            if vm.get("_demo"):
                continue  # don't sync demo data — real endpoints are already seeded
            ep_id = f"AZ-VM-{vm['name']}"
            await db.upsert_endpoint(
                id=ep_id,
                name=vm["name"],
                os=vm.get("os_type", ""),
                status=vm.get("status", "unknown"),
                source="azure_vm",
                metadata={
                    "location": vm.get("location"),
                    "vm_size": vm.get("vm_size"),
                    "resource_group": vm.get("resource_group"),
                    "power_state": vm.get("power_state"),
                },
                last_seen_at=datetime.now(timezone.utc).isoformat(),
            )
            count += 1
        return count

    # ── Demo data ────────────────────────────────────────────────

    def _demo_vms(self) -> List[Dict]:
        return [
            {"name": "AZ-PROD-VM-01", "location": "eastus", "resource_group": "rg-prod",
             "os_type": "Windows", "vm_size": "Standard_D4s_v3",
             "power_state": "running", "status": "healthy", "_demo": True},
            {"name": "AZ-LINUX-VM-02", "location": "westeurope", "resource_group": "rg-prod",
             "os_type": "Linux", "vm_size": "Standard_B2s",
             "power_state": "running", "status": "healthy", "_demo": True},
            {"name": "AZ-DEV-VM-03", "location": "eastus", "resource_group": "rg-dev",
             "os_type": "Linux", "vm_size": "Standard_B1ms",
             "power_state": "deallocated", "status": "warning", "_demo": True},
        ]

    def _demo_metrics(self, vm_name: str, hours: int) -> List[Dict]:
        return [
            {"metric": "Percentage CPU", "unit": "Percent", "average": 34.2, "maximum": 67.5, "data_points": hours * 12},
            {"metric": "Available Memory Bytes", "unit": "Bytes", "average": 2147483648, "maximum": 3221225472, "data_points": hours * 12},
            {"metric": "Disk Read Bytes", "unit": "Bytes", "average": 1048576, "maximum": 8388608, "data_points": hours * 12},
            {"metric": "Disk Write Bytes", "unit": "Bytes", "average": 524288, "maximum": 4194304, "data_points": hours * 12},
            {"metric": "Network In Total", "unit": "Bytes", "average": 2097152, "maximum": 10485760, "data_points": hours * 12},
            {"metric": "Network Out Total", "unit": "Bytes", "average": 1048576, "maximum": 5242880, "data_points": hours * 12},
        ]


def _power_to_status(power_state: str) -> str:
    """Map Azure VM power state to HEALIX endpoint status."""
    mapping = {
        "running": "healthy",
        "starting": "healing",
        "stopping": "warning",
        "stopped": "warning",
        "deallocating": "warning",
        "deallocated": "warning",
    }
    return mapping.get(power_state.lower(), "unknown")
