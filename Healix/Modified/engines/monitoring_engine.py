# ============================================================
#  HEALIX Monitoring Engine — engines/monitoring_engine.py
#  Real-time metric aggregation and anomaly detection.
# ============================================================

import logging
import statistics
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict

logger = logging.getLogger("healix.monitoring")


class MonitoringEngine:
    """Aggregates near real-time performance metrics and detects anomalies."""

    def __init__(self, db, intune_client=None, sentinel_client=None,
                 azure_monitor_client=None, aws_client=None, config=None):
        self.db = db
        self.intune = intune_client
        self.sentinel = sentinel_client
        self.azure_monitor = azure_monitor_client
        self.aws = aws_client
        self.config = config

    async def collect_metrics(self) -> Dict:
        """Pull latest metrics from all sources and update endpoints table."""
        updated = 0

        # Pull from Intune
        if self.intune and self.intune.is_available:
            count = await self.intune.sync_endpoints_to_db(self.db)
            updated += count

        # Pull performance data from Sentinel
        if self.sentinel and self.sentinel.is_available:
            try:
                perf_data = await self.sentinel.query_performance("PT5M")
                for entry in perf_data:
                    computer = entry.get("Computer", "")
                    if not computer:
                        continue
                    # Update endpoint metrics from perf counters
                    counter = entry.get("CounterName", "")
                    value = entry.get("AvgValue", 0)
                    endpoints = await self.db.get_endpoints()
                    for ep in endpoints:
                        if ep.get("name") == computer:
                            update = {}
                            if "Processor" in counter:
                                update["last_cpu"] = value
                            elif "Memory" in counter:
                                update["last_mem"] = value
                            elif "Free Space" in counter:
                                update["last_disk"] = 100 - value  # Convert free to used
                            if update:
                                await self.db.upsert_endpoint(
                                    id=ep["id"], name=ep["name"],
                                    os=ep.get("os", ""), status=ep.get("status", "unknown"),
                                    **update
                                )
                                updated += 1
            except Exception as e:
                logger.error(f"Failed to collect performance metrics: {e}")

        # If no real data, ensure demo endpoints exist
        if updated == 0:
            await self._ensure_demo_endpoints()

        # Azure VMs (agentless ARM + Azure Monitor)
        if self.azure_monitor and self.azure_monitor.is_available:
            try:
                count = await self.azure_monitor.sync_vms_to_db(self.db)
                updated += count
            except Exception as e:
                logger.error(f"Azure Monitor sync failed: {e}")

        # AWS EC2 (agentless CloudWatch)
        if self.aws and self.aws.is_available:
            try:
                count = await self.aws.sync_instances_to_db(self.db)
                updated += count
            except Exception as e:
                logger.error(f"AWS EC2 sync failed: {e}")

        return {"updated": updated, "timestamp": _now()}

    async def get_system_overview(self) -> Dict:
        """Return aggregate dashboard metrics."""
        endpoints = await self.db.get_endpoints()

        if not endpoints:
            return self._demo_overview()

        total = len(endpoints)
        healthy = sum(1 for e in endpoints if e.get("status") == "healthy")
        warning = sum(1 for e in endpoints if e.get("status") == "warning")
        critical = sum(1 for e in endpoints if e.get("status") in ("critical", "noncompliant"))
        healing = sum(1 for e in endpoints if e.get("status") == "healing")

        cpu_values = [e["last_cpu"] for e in endpoints if e.get("last_cpu") is not None]
        mem_values = [e["last_mem"] for e in endpoints if e.get("last_mem") is not None]

        alert_stats = await self.db.get_alert_stats()
        healing_stats = await self.db.get_healing_stats()

        return {
            "total_endpoints": total,
            "healthy": healthy,
            "warning": warning,
            "critical": critical,
            "healing": healing,
            "avg_cpu": round(statistics.mean(cpu_values), 1) if cpu_values else 0,
            "avg_mem": round(statistics.mean(mem_values), 1) if mem_values else 0,
            "active_alerts": alert_stats.get("active", 0),
            "critical_alerts": alert_stats.get("critical", 0),
            "healing_success_rate": healing_stats.get("success_rate", "N/A"),
            "last_updated": _now(),
        }

    async def get_endpoint_detail(self, endpoint_id: str) -> Optional[Dict]:
        """Return detailed metrics for one endpoint with recent history."""
        endpoint = await self.db.get_endpoint(endpoint_id)
        if not endpoint:
            return None

        # Get recent logs for this endpoint
        recent_logs = await self.db.query_logs(
            search=endpoint.get("name", ""), hours=24, limit=50
        )

        # Get recent alerts for this endpoint
        all_alerts = await self.db.get_alerts(limit=100)
        endpoint_alerts = [a for a in all_alerts
                          if a.get("endpoint_name") == endpoint.get("name")]

        return {
            **endpoint,
            "recent_logs": recent_logs[:20],
            "recent_alerts": endpoint_alerts[:10],
        }

    async def get_metric_history(self, endpoint_name: str, metric: str,
                                 hours: int = 24) -> List[Dict]:
        """Query logs for performance data points over time."""
        # Query from logs with performance category
        logs = await self.db.query_logs(
            search=endpoint_name, hours=hours, limit=500
        )

        # Extract metric values from logs
        history = []
        for log in logs:
            raw = log.get("raw_data")
            if raw:
                try:
                    data = raw if isinstance(raw, dict) else {}
                    value = data.get(metric) or data.get("AvgValue")
                    if value is not None:
                        history.append({
                            "timestamp": log.get("timestamp"),
                            "value": float(value),
                        })
                except (ValueError, TypeError):
                    pass

        # If no real history, generate demo data
        if not history:
            history = self._demo_metric_history(endpoint_name, metric, hours)

        return history

    async def detect_anomalies(self) -> List[Dict]:
        """Statistical anomaly detection on recent metrics."""
        endpoints = await self.db.get_endpoints()
        anomalies = []

        if not endpoints:
            return self._demo_anomalies()

        for ep in endpoints:
            cpu = ep.get("last_cpu")
            mem = ep.get("last_mem")
            disk = ep.get("last_disk")

            # Simple threshold-based anomaly detection
            if cpu is not None and cpu > 90:
                anomalies.append({
                    "endpoint": ep.get("name", ""),
                    "metric": "CPU",
                    "value": cpu,
                    "threshold": 90,
                    "severity": "critical" if cpu > 95 else "warning",
                    "message": f"CPU at {cpu}% exceeds threshold",
                    "detected_at": _now(),
                })
            if mem is not None and mem > 85:
                anomalies.append({
                    "endpoint": ep.get("name", ""),
                    "metric": "Memory",
                    "value": mem,
                    "threshold": 85,
                    "severity": "critical" if mem > 95 else "warning",
                    "message": f"Memory at {mem}% exceeds threshold",
                    "detected_at": _now(),
                })
            if disk is not None and disk > 85:
                anomalies.append({
                    "endpoint": ep.get("name", ""),
                    "metric": "Disk",
                    "value": disk,
                    "threshold": 85,
                    "severity": "critical" if disk > 95 else "warning",
                    "message": f"Disk at {disk}% exceeds threshold",
                    "detected_at": _now(),
                })

        return anomalies

    async def get_heartbeat_status(self) -> List[Dict]:
        """Get agent connectivity status."""
        if self.sentinel and self.sentinel.is_available:
            return await self.sentinel.query_heartbeat()

        # Demo heartbeat data
        return [
            {"Computer": "PROD-SRV-01", "Status": "Connected", "OSType": "Windows", "LastCall": _now()},
            {"Computer": "PROD-SRV-02", "Status": "Connected", "OSType": "Linux", "LastCall": _now()},
            {"Computer": "DEV-WS-015", "Status": "Connected", "OSType": "Windows", "LastCall": _now()},
            {"Computer": "DB-CLUSTER-01", "Status": "Connected", "OSType": "Linux", "LastCall": _now()},
            {"Computer": "EDGE-NODE-07", "Status": "Degraded", "OSType": "Linux", "LastCall": _now()},
            {"Computer": "BACKUP-SRV", "Status": "Connected", "OSType": "Windows", "LastCall": _now()},
        ]

    async def _ensure_demo_endpoints(self):
        """Seed database with demo endpoints if empty."""
        import random
        existing = await self.db.get_endpoints()
        if existing:
            return

        demo_endpoints = [
            ("EP-001", "PROD-SRV-01", "Windows Server 2022", "healthy", random.randint(20, 30), random.randint(55, 65), 44, "99.97%"),
            ("EP-002", "PROD-SRV-02", "Ubuntu 22.04 LTS", "warning", random.randint(80, 90), random.randint(75, 82), 72, "99.81%"),
            ("EP-003", "DEV-WS-015", "Windows 11 Pro", "healing", random.randint(40, 50), random.randint(50, 58), 38, "98.20%"),
            ("EP-004", "DB-CLUSTER-01", "RHEL 9", "healthy", random.randint(30, 38), random.randint(80, 85), 91, "99.99%"),
            ("EP-005", "EDGE-NODE-07", "Alpine Linux", "critical", random.randint(95, 100), random.randint(90, 97), 60, "95.40%"),
            ("EP-006", "BACKUP-SRV", "Windows Server 2019", "healthy", random.randint(10, 15), random.randint(38, 45), 55, "100%"),
        ]
        for ep_id, name, os, status, cpu, mem, disk, uptime in demo_endpoints:
            await self.db.upsert_endpoint(
                id=ep_id, name=name, os=os, status=status,
                source="demo", last_cpu=cpu, last_mem=mem,
                last_disk=disk, uptime=uptime, last_seen_at=_now(),
            )

    def _demo_overview(self) -> Dict:
        return {
            "total_endpoints": 6, "healthy": 3, "warning": 1, "critical": 1, "healing": 1,
            "avg_cpu": 48.5, "avg_mem": 67.2, "active_alerts": 2, "critical_alerts": 1,
            "healing_success_rate": "98.4%", "last_updated": _now(),
        }

    def _demo_metric_history(self, endpoint: str, metric: str, hours: int) -> List[Dict]:
        import random
        now = datetime.now(timezone.utc)
        history = []
        base = {"cpu": 45, "mem": 65, "disk": 55}.get(metric, 50)
        for i in range(hours * 4):  # 15-min intervals
            ts = now - timedelta(minutes=15 * (hours * 4 - i))
            value = base + random.uniform(-10, 15)
            history.append({"timestamp": ts.isoformat(), "value": round(max(0, min(100, value)), 1)})
        return history

    def _demo_anomalies(self) -> List[Dict]:
        return [
            {"endpoint": "EDGE-NODE-07", "metric": "CPU", "value": 97, "threshold": 90,
             "severity": "critical", "message": "CPU at 97% exceeds threshold", "detected_at": _now()},
            {"endpoint": "PROD-SRV-02", "metric": "Memory", "value": 88, "threshold": 85,
             "severity": "warning", "message": "Memory at 88% exceeds threshold", "detected_at": _now()},
            {"endpoint": "DB-CLUSTER-01", "metric": "Disk", "value": 91, "threshold": 85,
             "severity": "warning", "message": "Disk at 91% exceeds threshold", "detected_at": _now()},
        ]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
