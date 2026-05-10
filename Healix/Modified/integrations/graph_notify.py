# ============================================================
#  HEALIX Graph Notify — integrations/graph_notify.py
#  Alert delivery via Microsoft Teams webhook and email.
# ============================================================

import json
import logging
from typing import Optional, Dict, List

import httpx
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from config import AlertDeliveryConfig

logger = logging.getLogger("healix.notify")

SEVERITY_COLORS = {
    "critical": "#FF0000",
    "high": "#FF6600",
    "warning": "#FFB800",
    "medium": "#FFB800",
    "info": "#0078D4",
    "low": "#00CC6A",
    "success": "#00CC6A",
}


class NotificationService:
    """Routes alerts to configured notification channels."""

    def __init__(self, config: AlertDeliveryConfig):
        self.config = config
        self._http = httpx.AsyncClient(timeout=15.0)

    async def send_teams_alert(self, alert: Dict) -> bool:
        """Send an Adaptive Card to a Teams channel via Incoming Webhook."""
        if not self.config.teams_configured:
            logger.debug("Teams webhook not configured. Skipping.")
            return False

        severity = alert.get("alert_type", alert.get("severity", "info"))
        color = SEVERITY_COLORS.get(severity, "#0078D4")

        card = {
            "type": "message",
            "attachments": [{
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": {
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "type": "AdaptiveCard",
                    "version": "1.4",
                    "body": [
                        {
                            "type": "Container",
                            "style": "emphasis",
                            "items": [{
                                "type": "TextBlock",
                                "text": f"HEALIX Alert: {severity.upper()}",
                                "weight": "bolder",
                                "size": "medium",
                                "color": "attention" if severity in ("critical", "high") else "warning",
                            }],
                        },
                        {
                            "type": "TextBlock",
                            "text": alert.get("title", "Security Alert"),
                            "weight": "bolder",
                            "size": "large",
                            "wrap": True,
                        },
                        {
                            "type": "FactSet",
                            "facts": [
                                {"title": "Endpoint", "value": alert.get("endpoint_name", "N/A")},
                                {"title": "Source", "value": alert.get("source", "HEALIX")},
                                {"title": "Severity", "value": severity.upper()},
                                {"title": "Time", "value": alert.get("timestamp", "")},
                            ],
                        },
                        {
                            "type": "TextBlock",
                            "text": alert.get("description", ""),
                            "wrap": True,
                            "isSubtle": True,
                        },
                    ],
                },
            }],
        }

        try:
            response = await self._http.post(self.config.teams_webhook_url, json=card)
            if response.status_code in (200, 202):
                logger.info(f"Teams alert sent: {alert.get('title', '')}")
                return True
            else:
                logger.error(f"Teams webhook failed ({response.status_code}): {response.text[:200]}")
                return False
        except Exception as e:
            logger.error(f"Teams notification error: {e}")
            return False

    async def send_email_alert(self, alert: Dict) -> bool:
        """Send alert notification via SMTP email."""
        if not self.config.email_configured:
            logger.debug("Email not configured. Skipping.")
            return False

        severity = alert.get("alert_type", alert.get("severity", "info")).upper()
        subject = f"[HEALIX {severity}] {alert.get('title', 'Security Alert')}"

        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; background: #1a1a2e; color: #e0e0e0; padding: 20px;">
            <div style="max-width: 600px; margin: auto; background: #16213e; border-radius: 8px; padding: 20px;
                        border-left: 4px solid {SEVERITY_COLORS.get(alert.get('alert_type', 'info'), '#0078D4')};">
                <h2 style="color: #00d2ff; margin-top: 0;">HEALIX Security Alert</h2>
                <table style="width: 100%; border-collapse: collapse;">
                    <tr><td style="padding: 8px; color: #888;">Severity</td>
                        <td style="padding: 8px; font-weight: bold;">{severity}</td></tr>
                    <tr><td style="padding: 8px; color: #888;">Title</td>
                        <td style="padding: 8px;">{alert.get('title', 'N/A')}</td></tr>
                    <tr><td style="padding: 8px; color: #888;">Endpoint</td>
                        <td style="padding: 8px;">{alert.get('endpoint_name', 'N/A')}</td></tr>
                    <tr><td style="padding: 8px; color: #888;">Source</td>
                        <td style="padding: 8px;">{alert.get('source', 'HEALIX')}</td></tr>
                    <tr><td style="padding: 8px; color: #888;">Time</td>
                        <td style="padding: 8px;">{alert.get('timestamp', '')}</td></tr>
                </table>
                <p style="padding: 8px; margin-top: 12px; background: #0d1b2a; border-radius: 4px;">
                    {alert.get('description', '')}
                </p>
                <p style="color: #555; font-size: 12px; margin-top: 20px;">
                    Sent by HEALIX Autonomous Security Platform
                </p>
            </div>
        </body>
        </html>
        """

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.config.smtp_user
        msg["To"] = ", ".join(self.config.alert_email_recipients)
        msg.attach(MIMEText(html_body, "html"))

        try:
            await aiosmtplib.send(
                msg,
                hostname=self.config.smtp_host,
                port=self.config.smtp_port,
                username=self.config.smtp_user,
                password=self.config.smtp_password,
                start_tls=True,
            )
            logger.info(f"Email alert sent: {subject}")
            return True
        except Exception as e:
            logger.error(f"Email notification error: {e}")
            return False

    async def notify(self, alert: Dict, channels: List[str]) -> Dict:
        """Route alert to specified notification channels."""
        results = {"dashboard": True}  # Dashboard always gets it

        if "teams" in channels:
            results["teams"] = await self.send_teams_alert(alert)
        if "email" in channels:
            results["email"] = await self.send_email_alert(alert)

        return results

    async def close(self):
        await self._http.aclose()
