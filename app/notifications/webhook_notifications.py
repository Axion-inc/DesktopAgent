"""
Webhook Notification Channel - Phase 7
Sends HTTP webhook notifications for deviations and alerts
"""

import logging
import json
import os
from typing import Optional, Dict, Any, List
import aiohttp

from .notification_manager import NotificationChannel, NotificationPayload

logger = logging.getLogger(__name__)


class WebhookNotificationChannel(NotificationChannel):
    """Generic webhook notification channel for Phase 7 alerts"""
    
    def __init__(
        self,
        webhook_urls: List[str] = None,
        headers: Dict[str, str] = None,
        timeout_seconds: int = 10,
        retry_attempts: int = 3
    ):
        """Initialize webhook notification channel"""
        self.webhook_urls = webhook_urls or self._parse_webhook_urls()
        self.headers = headers or {"Content-Type": "application/json"}
        self.timeout_seconds = timeout_seconds
        self.retry_attempts = retry_attempts
        
        # Add any additional headers from environment
        auth_header = os.getenv("WEBHOOK_AUTH_HEADER", "")
        if auth_header:
            self.headers["Authorization"] = auth_header
        
        logger.info(f"Webhook notification channel initialized with {len(self.webhook_urls)} endpoints")
    
    def _parse_webhook_urls(self) -> List[str]:
        """Parse webhook URLs from environment variables"""
        webhook_env = os.getenv("WEBHOOK_URLS", "")
        if webhook_env:
            return [url.strip() for url in webhook_env.split(",") if url.strip()]
        
        # Check for individual webhook URL
        single_url = os.getenv("WEBHOOK_URL", "")
        return [single_url] if single_url else []
    
    def is_enabled(self) -> bool:
        """Check if webhook notifications are properly configured"""
        return bool(self.webhook_urls)
    
    async def send_notification(self, payload: NotificationPayload) -> bool:
        """Send webhook notification to all configured endpoints"""
        
        if not self.is_enabled():
            logger.warning("Webhook notifications not properly configured")
            return False
        
        webhook_payload = self._format_webhook_payload(payload)
        
        success_count = 0
        
        for url in self.webhook_urls:
            success = await self._send_to_webhook(url, webhook_payload)
            if success:
                success_count += 1
        
        # Consider successful if at least one webhook succeeded
        overall_success = success_count > 0
        
        if overall_success:
            logger.info(f"Webhook notification sent to {success_count}/{len(self.webhook_urls)} endpoints")
        else:
            logger.error("Failed to send webhook notification to any endpoint")
        
        return overall_success
    
    async def _send_to_webhook(self, url: str, payload: Dict[str, Any]) -> bool:
        """Send payload to specific webhook URL with retries"""
        
        for attempt in range(self.retry_attempts):
            try:
                timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)
                
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.post(
                        url,
                        headers=self.headers,
                        json=payload
                    ) as response:
                        if 200 <= response.status < 300:
                            logger.info(f"Webhook notification sent successfully to {url}")
                            return True
                        else:
                            logger.warning(f"Webhook {url} returned status {response.status}")
                            
            except aiohttp.ClientError as e:
                logger.warning(f"Webhook attempt {attempt + 1} failed for {url}: {e}")
            except Exception as e:
                logger.error(f"Unexpected error sending to webhook {url}: {e}")
            
            # Don't retry on last attempt
            if attempt < self.retry_attempts - 1:
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
        
        logger.error(f"Failed to send webhook notification to {url} after {self.retry_attempts} attempts")
        return False
    
    def _format_webhook_payload(self, payload: NotificationPayload) -> Dict[str, Any]:
        """Format notification payload for webhook delivery"""
        
        return {
            "event": "notification",
            "version": "1.0",
            "source": "desktop_agent_phase7",
            "timestamp": payload.timestamp.isoformat(),
            "notification": {
                "id": f"{payload.notification_type.value}_{int(payload.timestamp.timestamp())}",
                "type": payload.notification_type.value,
                "priority": payload.priority.value,
                "title": payload.title,
                "message": payload.message,
                "details": payload.details,
                "tags": payload.tags,
                "source": payload.source
            },
            "context": {
                "phase": "7",
                "features": ["l4_autopilot", "policy_engine_v1", "planner_l2", "webx_enhancements"],
                "agent_version": "phase7"
            }
        }


class DiscordWebhookChannel(WebhookNotificationChannel):
    """Discord-specific webhook notification channel"""
    
    def __init__(self, discord_webhook_url: str = None, **kwargs):
        """Initialize Discord webhook channel"""
        discord_url = discord_webhook_url or os.getenv("DISCORD_WEBHOOK_URL", "")
        webhook_urls = [discord_url] if discord_url else []
        
        super().__init__(webhook_urls=webhook_urls, **kwargs)
        logger.info("Discord webhook channel initialized")
    
    def _format_webhook_payload(self, payload: NotificationPayload) -> Dict[str, Any]:
        """Format payload for Discord webhook"""
        
        # Priority colors and emojis
        priority_colors = {
            "low": 0x28a745,       # Green
            "medium": 0xffc107,    # Yellow
            "high": 0xfd7e14,      # Orange
            "critical": 0xdc3545   # Red
        }
        
        color = priority_colors.get(payload.priority.value, 0x6c757d)
        
        # Create embed
        embed = {
            "title": payload.title,
            "description": payload.message,
            "color": color,
            "timestamp": payload.timestamp.isoformat(),
            "footer": {
                "text": "Desktop Agent Phase 7"
            },
            "fields": [
                {
                    "name": "Priority",
                    "value": payload.priority.value.upper(),
                    "inline": True
                },
                {
                    "name": "Type",
                    "value": payload.notification_type.value.replace('_', ' ').title(),
                    "inline": True
                }
            ]
        }
        
        # Add important details as fields
        important_details = self._extract_important_details_for_discord(payload)
        for key, value in important_details.items():
            embed["fields"].append({
                "name": key,
                "value": str(value)[:1024],  # Discord field value limit
                "inline": len(str(value)) < 50
            })
        
        return {
            "username": "Desktop Agent",
            "embeds": [embed]
        }
    
    def _extract_important_details_for_discord(self, payload: NotificationPayload) -> Dict[str, str]:
        """Extract key details for Discord display"""
        
        details = {}
        
        # Common details based on notification type
        if payload.notification_type.value == "l4_deviation":
            details["Execution"] = payload.details.get("execution_id", "")[:8]
            details["Template"] = payload.details.get("template_name", "")
            details["Reason"] = payload.details.get("deviation_reason", "")
        
        elif payload.notification_type.value == "policy_violation":
            details["Violation"] = payload.details.get("violation_type", "")
            details["Template"] = payload.details.get("template_name", "")
        
        return details


class TeamsWebhookChannel(WebhookNotificationChannel):
    """Microsoft Teams-specific webhook notification channel"""
    
    def __init__(self, teams_webhook_url: str = None, **kwargs):
        """Initialize Teams webhook channel"""
        teams_url = teams_webhook_url or os.getenv("TEAMS_WEBHOOK_URL", "")
        webhook_urls = [teams_url] if teams_url else []
        
        super().__init__(webhook_urls=webhook_urls, **kwargs)
        logger.info("Teams webhook channel initialized")
    
    def _format_webhook_payload(self, payload: NotificationPayload) -> Dict[str, Any]:
        """Format payload for Microsoft Teams webhook"""
        
        # Priority theme colors
        theme_colors = {
            "low": "good",
            "medium": "warning",
            "high": "attention",
            "critical": "attention"
        }
        
        theme_color = theme_colors.get(payload.priority.value, "default")
        
        # Build activity card
        card = {
            "@type": "MessageCard",
            "@context": "https://schema.org/extensions",
            "summary": payload.title,
            "themeColor": theme_color,
            "sections": [
                {
                    "activityTitle": payload.title,
                    "activitySubtitle": f"Priority: {payload.priority.value.upper()}",
                    "text": payload.message,
                    "facts": [
                        {
                            "name": "Type",
                            "value": payload.notification_type.value.replace('_', ' ').title()
                        },
                        {
                            "name": "Time",
                            "value": payload.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')
                        }
                    ]
                }
            ]
        }
        
        # Add details as facts
        important_details = self._extract_important_details_for_teams(payload)
        for key, value in important_details.items():
            card["sections"][0]["facts"].append({
                "name": key,
                "value": str(value)
            })
        
        return card
    
    def _extract_important_details_for_teams(self, payload: NotificationPayload) -> Dict[str, str]:
        """Extract key details for Teams display"""
        
        details = {}
        
        if payload.notification_type.value == "l4_deviation":
            details["Execution ID"] = payload.details.get("execution_id", "")[:8]
            details["Template Name"] = payload.details.get("template_name", "")
            details["Deviation Reason"] = payload.details.get("deviation_reason", "")
        
        elif payload.notification_type.value == "policy_violation":
            details["Violation Type"] = payload.details.get("violation_type", "")
            details["Template Name"] = payload.details.get("template_name", "")
        
        elif payload.notification_type.value == "patch_proposal":
            patch_data = payload.details.get("patch_data", {})
            details["Template"] = payload.details.get("template_name", "")
            details["Patch Type"] = patch_data.get("patch_type", "")
            details["Confidence"] = f"{patch_data.get('confidence', 0):.2f}"
        
        return details