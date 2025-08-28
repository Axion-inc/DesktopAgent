"""
Slack Notification Channel - Phase 7
Sends Slack messages for deviations and alerts
"""

import logging
import os
from typing import Dict, Any, List
import aiohttp

from .notification_manager import NotificationChannel, NotificationPayload, Priority

logger = logging.getLogger(__name__)


class SlackNotificationChannel(NotificationChannel):
    """Slack notification channel for Phase 7 alerts"""

    def __init__(
        self,
        webhook_url: str = None,
        bot_token: str = None,
        channel: str = None,
        username: str = "Desktop Agent"
    ):
        """Initialize Slack notification channel"""
        self.webhook_url = webhook_url or os.getenv("SLACK_WEBHOOK_URL", "")
        self.bot_token = bot_token or os.getenv("SLACK_BOT_TOKEN", "")
        self.channel = channel or os.getenv("SLACK_CHANNEL", "#alerts")
        self.username = username

        # Prefer webhook over bot token for simplicity
        self.use_webhook = bool(self.webhook_url)

        logger.info(f"Slack notification channel initialized ({'webhook' if self.use_webhook else 'bot token'})")

    def is_enabled(self) -> bool:
        """Check if Slack notifications are properly configured"""
        return bool(self.webhook_url or (self.bot_token and self.channel))

    async def send_notification(self, payload: NotificationPayload) -> bool:
        """Send Slack notification"""

        if not self.is_enabled():
            logger.warning("Slack notifications not properly configured")
            return False

        try:
            if self.use_webhook:
                return await self._send_webhook_message(payload)
            else:
                return await self._send_bot_message(payload)

        except Exception as e:
            logger.error(f"Failed to send Slack notification: {e}")
            return False

    async def _send_webhook_message(self, payload: NotificationPayload) -> bool:
        """Send message via Slack webhook"""

        message = self._format_slack_message(payload)

        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.webhook_url,
                headers={"Content-Type": "application/json"},
                json=message
            ) as response:
                if response.status == 200:
                    logger.info(f"Slack webhook notification sent: {payload.title}")
                    return True
                else:
                    logger.error(f"Slack webhook failed with status {response.status}")
                    return False

    async def _send_bot_message(self, payload: NotificationPayload) -> bool:
        """Send message via Slack bot token"""

        message = self._format_slack_message(payload, include_channel=True)

        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://slack.com/api/chat.postMessage",
                headers={
                    "Authorization": f"Bearer {self.bot_token}",
                    "Content-Type": "application/json"
                },
                json=message
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    if result.get("ok"):
                        logger.info(f"Slack bot notification sent: {payload.title}")
                        return True
                    else:
                        logger.error(f"Slack bot API error: {result.get('error', 'Unknown')}")
                        return False
                else:
                    logger.error(f"Slack bot API failed with status {response.status}")
                    return False

    def _format_slack_message(self, payload: NotificationPayload, include_channel: bool = False) -> Dict[str, Any]:
        """Format Slack message with rich formatting"""

        # Priority colors and emojis
        priority_config = {
            Priority.LOW: {"color": "#28a745", "emoji": "🟢"},
            Priority.MEDIUM: {"color": "#ffc107", "emoji": "🟡"},
            Priority.HIGH: {"color": "#fd7e14", "emoji": "🟠"},
            Priority.CRITICAL: {"color": "#dc3545", "emoji": "🔴"}
        }

        config = priority_config.get(payload.priority, {"color": "#6c757d", "emoji": "⚪"})

        # Notification type emojis
        type_emojis = {
            "l4_deviation": "🤖",
            "policy_violation": "🔒",
            "safe_fail_trigger": "🚨",
            "patch_proposal": "🔧",
            "system_alert": "⚠️"
        }

        type_emoji = type_emojis.get(payload.notification_type.value, "📢")

        # Build main message
        message = {
            "username": self.username,
            "icon_emoji": ":robot_face:",
            "text": f"{config['emoji']} {type_emoji} *{payload.title}*",
            "attachments": [
                {
                    "color": config["color"],
                    "fields": [
                        {
                            "title": "Message",
                            "value": payload.message,
                            "short": False
                        },
                        {
                            "title": "Priority",
                            "value": payload.priority.value.upper(),
                            "short": True
                        },
                        {
                            "title": "Type",
                            "value": payload.notification_type.value.replace('_', ' ').title(),
                            "short": True
                        }
                    ],
                    "footer": "Desktop Agent Phase 7",
                    "ts": int(payload.timestamp.timestamp())
                }
            ]
        }

        if include_channel:
            message["channel"] = self.channel

        # Add details fields
        attachment = message["attachments"][0]

        # Add key details as fields
        important_details = self._extract_important_details(payload)
        for key, value in important_details.items():
            attachment["fields"].append({
                "title": key.replace('_', ' ').title(),
                "value": str(value)[:500],  # Limit field length
                "short": len(str(value)) < 50
            })

        # Add action buttons for certain notification types
        if payload.notification_type in ["l4_deviation", "policy_violation"]:
            attachment["actions"] = self._create_action_buttons(payload)

        return message

    def _extract_important_details(self, payload: NotificationPayload) -> Dict[str, str]:
        """Extract important details for Slack display"""

        important = {}

        if payload.notification_type.value == "l4_deviation":
            important.update({
                "Execution ID": payload.details.get("execution_id", "")[:8],
                "Template": payload.details.get("template_name", ""),
                "Deviation Reason": payload.details.get("deviation_reason", "")
            })

        elif payload.notification_type.value == "policy_violation":
            important.update({
                "Violation Type": payload.details.get("violation_type", ""),
                "Template": payload.details.get("template_name", "")
            })

        elif payload.notification_type.value == "safe_fail_trigger":
            important.update({
                "Execution ID": payload.details.get("execution_id", "")[:8],
                "Threshold": str(payload.details.get("threshold_exceeded", 0)),
                "Deviations": str(len(payload.details.get("deviation_details", [])))
            })

        elif payload.notification_type.value == "patch_proposal":
            patch_data = payload.details.get("patch_data", {})
            important.update({
                "Template": payload.details.get("template_name", ""),
                "Patch Type": patch_data.get("patch_type", ""),
                "Confidence": f"{patch_data.get('confidence', 0):.2f}",
                "Approval Required": "Yes" if payload.details.get("requires_approval") else "No"
            })

        return important

    def _create_action_buttons(self, payload: NotificationPayload) -> List[Dict[str, Any]]:
        """Create action buttons for Slack message"""

        actions = []

        if payload.notification_type.value == "l4_deviation":
            execution_id = payload.details.get("execution_id", "")
            actions.extend([
                {
                    "type": "button",
                    "text": "View Logs",
                    "url": f"https://dashboard.example.com/executions/{execution_id}",
                    "style": "primary"
                },
                {
                    "type": "button",
                    "text": "Create GitHub Issue",
                    "url": f"https://github.com/your-org/repo/issues/new?title=L4%20Deviation%20-%20{execution_id[:8]}",
                    "style": "default"
                }
            ])

        elif payload.notification_type.value == "policy_violation":
            template_name = payload.details.get("template_name", "")
            actions.extend([
                {
                    "type": "button",
                    "text": "Review Policy",
                    "url": "https://dashboard.example.com/policy",
                    "style": "primary"
                },
                {
                    "type": "button",
                    "text": "Update Template",
                    "url": f"https://dashboard.example.com/templates/{template_name}",
                    "style": "default"
                }
            ])

        return actions
