# ============================================================
#  HEALIX AWS Client — integrations/aws_client.py
#  Agentless EC2 / CloudWatch / SSM / Logs polling via boto3.
#  boto3 import is guarded — server starts normally even if absent.
# ============================================================

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict

logger = logging.getLogger("healix.aws")

_BOTO3_AVAILABLE = False
try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
    _BOTO3_AVAILABLE = True
except ImportError:
    pass


class AWSClient:
    """Agentless AWS EC2/CloudWatch monitoring client."""

    def __init__(self, config):
        """
        Args:
            config: AWSConfig instance from config.py
        """
        self.config = config
        self._available = False
        self._session = None
        self._ec2 = None
        self._cloudwatch = None
        self._ssm = None
        self._logs = None
        self._initialize()

    def _initialize(self):
        if not _BOTO3_AVAILABLE:
            logger.info("AWSClient: boto3 not installed. Run `pip install boto3` to enable AWS support.")
            return

        if not self.config or not self.config.is_configured:
            logger.info("AWSClient: No AWS credentials configured. Running without AWS support.")
            return

        try:
            self._session = boto3.Session(
                aws_access_key_id=self.config.access_key_id,
                aws_secret_access_key=self.config.secret_access_key,
                region_name=self.config.region,
            )
            self._ec2 = self._session.client("ec2")
            self._cloudwatch = self._session.client("cloudwatch")
            self._ssm = self._session.client("ssm")
            self._logs = self._session.client("logs")

            # Connectivity test: describe regions (lightweight)
            self._ec2.describe_regions(Filters=[{"Name": "opt-in-status", "Values": ["opt-in-not-required"]}])
            self._available = True
            logger.info(f"AWSClient: Connected. Region={self.config.region}")
        except Exception as e:
            logger.error(f"AWSClient: Initialization failed: {e}")
            self._available = False

    @property
    def is_available(self) -> bool:
        return self._available

    # ── EC2 instance listing ────────────────────────────────────

    async def list_instances(self) -> List[Dict]:
        """List all EC2 instances in the configured region."""
        if not self._available:
            return self._demo_instances()

        loop = asyncio.get_event_loop()
        try:
            data = await loop.run_in_executor(
                None,
                lambda: self._ec2.describe_instances()
            )
        except Exception as e:
            logger.error(f"AWSClient.list_instances: {e}")
            return self._demo_instances()

        instances = []
        for reservation in data.get("Reservations", []):
            for inst in reservation.get("Instances", []):
                name = ""
                for tag in inst.get("Tags", []):
                    if tag.get("Key") == "Name":
                        name = tag.get("Value", "")
                        break

                instances.append({
                    "id": inst.get("InstanceId", ""),
                    "name": name or inst.get("InstanceId", ""),
                    "type": inst.get("InstanceType", ""),
                    "state": inst.get("State", {}).get("Name", "unknown"),
                    "status": _state_to_status(inst.get("State", {}).get("Name", "")),
                    "platform": inst.get("Platform", "linux"),
                    "private_ip": inst.get("PrivateIpAddress", ""),
                    "region": self.config.region,
                    "az": inst.get("Placement", {}).get("AvailabilityZone", ""),
                    "_demo": False,
                })

        return instances if instances else self._demo_instances()

    async def get_instance_status(self, instance_id: str) -> Dict:
        """Get instance status from EC2 status checks."""
        if not self._available:
            return {"instance_id": instance_id, "state": "demo", "status_checks": "demo"}

        loop = asyncio.get_event_loop()
        try:
            data = await loop.run_in_executor(
                None,
                lambda: self._ec2.describe_instance_status(
                    InstanceIds=[instance_id], IncludeAllInstances=True
                )
            )
            statuses = data.get("InstanceStatuses", [])
            if not statuses:
                return {"instance_id": instance_id, "state": "unknown"}
            s = statuses[0]
            return {
                "instance_id": instance_id,
                "state": s.get("InstanceState", {}).get("Name", "unknown"),
                "instance_status": s.get("InstanceStatus", {}).get("Status", "unknown"),
                "system_status": s.get("SystemStatus", {}).get("Status", "unknown"),
            }
        except Exception as e:
            return {"instance_id": instance_id, "error": str(e)}

    async def get_instance_metrics(self, instance_id: str, hours: int = 1) -> List[Dict]:
        """Get CloudWatch metrics for an EC2 instance."""
        if not self._available:
            return self._demo_metrics(instance_id, hours)

        loop = asyncio.get_event_loop()
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(hours=hours)

        metric_definitions = [
            ("CPUUtilization", "Percent"),
            ("NetworkIn", "Bytes"),
            ("NetworkOut", "Bytes"),
            ("DiskReadBytes", "Bytes"),
            ("DiskWriteBytes", "Bytes"),
        ]

        results = []
        for metric_name, unit in metric_definitions:
            try:
                data = await loop.run_in_executor(
                    None,
                    lambda mn=metric_name, u=unit: self._cloudwatch.get_metric_statistics(
                        Namespace="AWS/EC2",
                        MetricName=mn,
                        Dimensions=[{"Name": "InstanceId", "Value": instance_id}],
                        StartTime=start_time,
                        EndTime=end_time,
                        Period=300,
                        Statistics=["Average", "Maximum"],
                    )
                )
                points = data.get("Datapoints", [])
                avg_vals = [p["Average"] for p in points if "Average" in p]
                max_vals = [p["Maximum"] for p in points if "Maximum" in p]
                results.append({
                    "metric": metric_name,
                    "unit": unit,
                    "average": round(sum(avg_vals) / len(avg_vals), 4) if avg_vals else None,
                    "maximum": max(max_vals) if max_vals else None,
                    "data_points": len(points),
                })
            except Exception as e:
                results.append({"metric": metric_name, "unit": unit, "error": str(e)})

        return results

    async def get_instance_logs(self, instance_id: str, log_group: str,
                                hours: int = 1) -> List[Dict]:
        """Fetch CloudWatch log events for an instance."""
        if not self._available:
            return []

        loop = asyncio.get_event_loop()
        end_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        start_ms = end_ms - hours * 3600 * 1000
        try:
            data = await loop.run_in_executor(
                None,
                lambda: self._logs.filter_log_events(
                    logGroupName=log_group,
                    startTime=start_ms,
                    endTime=end_ms,
                    limit=100,
                )
            )
            return [
                {
                    "timestamp": datetime.fromtimestamp(
                        e["timestamp"] / 1000, tz=timezone.utc
                    ).isoformat(),
                    "message": e.get("message", ""),
                    "log_stream": e.get("logStreamName", ""),
                }
                for e in data.get("events", [])
            ]
        except Exception as e:
            return [{"error": str(e)}]

    async def get_ssm_instance_info(self, instance_id: str) -> Optional[Dict]:
        """Get SSM managed instance info (if SSM agent is installed)."""
        if not self._available:
            return None

        loop = asyncio.get_event_loop()
        try:
            data = await loop.run_in_executor(
                None,
                lambda: self._ssm.describe_instance_information(
                    Filters=[{"Key": "InstanceIds", "Values": [instance_id]}]
                )
            )
            items = data.get("InstanceInformationList", [])
            return items[0] if items else None
        except Exception:
            return None

    async def sync_instances_to_db(self, db) -> int:
        """Upsert all EC2 instances into the endpoints table. Returns count."""
        instances = await self.list_instances()
        count = 0
        for inst in instances:
            if inst.get("_demo"):
                continue
            ep_id = f"AWS-{inst['id']}"
            await db.upsert_endpoint(
                id=ep_id,
                name=inst.get("name") or inst["id"],
                os=inst.get("platform", "linux"),
                status=inst.get("status", "unknown"),
                source="aws_ec2",
                metadata={
                    "instance_id": inst["id"],
                    "instance_type": inst.get("type"),
                    "region": inst.get("region"),
                    "az": inst.get("az"),
                    "private_ip": inst.get("private_ip"),
                    "state": inst.get("state"),
                },
                last_seen_at=datetime.now(timezone.utc).isoformat(),
            )
            count += 1
        return count

    async def close(self):
        """No-op — boto3 clients have no persistent connections to close."""
        pass

    # ── Demo data ────────────────────────────────────────────────

    def _demo_instances(self) -> List[Dict]:
        return [
            {"id": "i-0abc123456789001", "name": "AWS-PROD-WEB-01",
             "type": "t3.large", "state": "running", "status": "healthy",
             "platform": "linux", "private_ip": "10.0.1.10",
             "region": "us-east-1", "az": "us-east-1a", "_demo": True},
            {"id": "i-0abc123456789002", "name": "AWS-PROD-DB-01",
             "type": "r5.xlarge", "state": "running", "status": "healthy",
             "platform": "linux", "private_ip": "10.0.2.20",
             "region": "us-east-1", "az": "us-east-1b", "_demo": True},
            {"id": "i-0abc123456789003", "name": "AWS-DEV-APP-01",
             "type": "t3.medium", "state": "stopped", "status": "warning",
             "platform": "linux", "private_ip": "10.0.3.30",
             "region": "us-east-1", "az": "us-east-1c", "_demo": True},
        ]

    def _demo_metrics(self, instance_id: str, hours: int) -> List[Dict]:
        return [
            {"metric": "CPUUtilization", "unit": "Percent", "average": 28.4, "maximum": 54.1, "data_points": hours * 12},
            {"metric": "NetworkIn", "unit": "Bytes", "average": 1048576, "maximum": 5242880, "data_points": hours * 12},
            {"metric": "NetworkOut", "unit": "Bytes", "average": 524288, "maximum": 2097152, "data_points": hours * 12},
            {"metric": "DiskReadBytes", "unit": "Bytes", "average": 204800, "maximum": 2097152, "data_points": hours * 12},
            {"metric": "DiskWriteBytes", "unit": "Bytes", "average": 102400, "maximum": 1048576, "data_points": hours * 12},
        ]


def _state_to_status(state: str) -> str:
    """Map EC2 instance state to HEALIX endpoint status."""
    mapping = {
        "running": "healthy",
        "pending": "healing",
        "stopping": "warning",
        "stopped": "warning",
        "shutting-down": "warning",
        "terminated": "critical",
    }
    return mapping.get(state.lower(), "unknown")
