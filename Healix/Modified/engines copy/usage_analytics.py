# ============================================================
#  HEALIX Usage Analytics — engines/usage_analytics.py
#  Tracks Security Copilot usage, adoption, and efficiency.
# ============================================================

import logging
from datetime import datetime, timezone
from typing import Optional, Dict

logger = logging.getLogger("healix.usage")


class UsageAnalytics:
    """Tracks platform usage metrics for adoption dashboards."""

    def __init__(self, db):
        self.db = db

    async def record_event(self, metric_type: str, service: str, action: str,
                           user: str = "", tokens: int = 0,
                           response_ms: float = 0, success: bool = True,
                           metadata: Optional[Dict] = None):
        """Record a usage event."""
        await self.db.insert_usage_metric(
            timestamp=_now(),
            metric_type=metric_type,
            service=service,
            action=action,
            user_identifier=user,
            token_count=tokens,
            response_time_ms=response_ms,
            success=success,
            metadata=metadata,
        )

    async def get_usage_summary(self, period: str = "7d") -> Dict:
        """Aggregate usage overview for a period."""
        hours = self._period_to_hours(period)
        summary = await self.db.get_usage_summary(hours=hours)

        return {
            "period": period,
            "total_queries": summary.get("total_queries", 0),
            "total_tokens": summary.get("total_tokens", 0),
            "by_service": summary.get("by_service", []),
            "estimated_cost": self._estimate_cost(summary.get("total_tokens", 0)),
            "timestamp": _now(),
        }

    async def get_adoption_metrics(self) -> Dict:
        """Active services, query frequency trends, top actions."""
        summary_7d = await self.db.get_usage_summary(hours=168)
        summary_30d = await self.db.get_usage_summary(hours=720)

        services = summary_7d.get("by_service", [])
        active_services = len([s for s in services if s.get("count", 0) > 0])

        return {
            "active_services_7d": active_services,
            "queries_7d": summary_7d.get("total_queries", 0),
            "queries_30d": summary_30d.get("total_queries", 0),
            "trend": self._compute_trend(
                summary_7d.get("total_queries", 0),
                summary_30d.get("total_queries", 0)
            ),
            "by_service": services,
            "timestamp": _now(),
        }

    async def get_workload_distribution(self) -> Dict:
        """Queries per service and action type."""
        summary = await self.db.get_usage_summary(hours=168)
        services = summary.get("by_service", [])

        distribution = {}
        for svc in services:
            distribution[svc.get("service", "unknown")] = {
                "count": svc.get("count", 0),
                "avg_response_ms": round(svc.get("avg_response", 0) or 0, 1),
                "total_tokens": svc.get("total_tokens", 0) or 0,
            }

        return {
            "distribution": distribution,
            "total": summary.get("total_queries", 0),
            "period": "7d",
            "timestamp": _now(),
        }

    async def get_token_usage(self, period: str = "30d") -> Dict:
        """Token consumption over time with cost estimation."""
        hours = self._period_to_hours(period)
        summary = await self.db.get_usage_summary(hours=hours)
        total_tokens = summary.get("total_tokens", 0)

        return {
            "period": period,
            "total_tokens": total_tokens,
            "estimated_cost_usd": self._estimate_cost(total_tokens),
            "by_service": summary.get("by_service", []),
            "timestamp": _now(),
        }

    async def get_efficiency_metrics(self) -> Dict:
        """MTTR, auto-resolve rate, and SLA compliance."""
        healing_stats = await self.db.get_healing_stats()
        alert_stats = await self.db.get_alert_stats()

        total_healed = healing_stats.get("total", 0)
        completed = healing_stats.get("completed", 0)
        failed = healing_stats.get("failed", 0)

        return {
            "total_actions": total_healed,
            "auto_resolve_rate": healing_stats.get("success_rate", "N/A"),
            "completed": completed,
            "failed": failed,
            "active_alerts": alert_stats.get("active", 0),
            "total_alerts": alert_stats.get("total", 0),
            "timestamp": _now(),
        }

    @staticmethod
    def _period_to_hours(period: str) -> int:
        if period.endswith("d"):
            return int(period[:-1]) * 24
        if period.endswith("h"):
            return int(period[:-1])
        return 168  # default 7 days

    @staticmethod
    def _estimate_cost(tokens: int) -> float:
        """Estimate OpenAI API cost based on token count.
        GPT-4o-mini: ~$0.15/1M input, ~$0.60/1M output tokens.
        Rough average: ~$0.30/1M tokens.
        """
        return round(tokens * 0.0000003, 4)

    @staticmethod
    def _compute_trend(recent: int, total: int) -> str:
        if total == 0:
            return "stable"
        weekly_avg = total / 4.3  # ~4.3 weeks in 30 days
        if recent > weekly_avg * 1.2:
            return "increasing"
        elif recent < weekly_avg * 0.8:
            return "decreasing"
        return "stable"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
