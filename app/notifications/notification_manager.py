"""
Notification Manager - Phase 7
Manages deviation detection alerts and multi-channel notifications
"""

import logging
from typing import Dict, List, Any, Optional, Protocol
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import asyncio
from abc import abstractmethod

logger = logging.getLogger(__name__)


class NotificationType(Enum):
    """Types of notifications"""
    L4_DEVIATION = "l4_deviation"
    POLICY_VIOLATION = "policy_violation"
    SAFE_FAIL_TRIGGER = "safe_fail_trigger"
    PATCH_PROPOSAL = "patch_proposal"
    SYSTEM_ALERT = "system_alert"


class Priority(Enum):
    """Notification priority levels"""
    LOW = "low"
    MEDIUM = "medium" 
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class NotificationPayload:
    """Notification payload data"""
    notification_type: NotificationType
    title: str
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    priority: Priority = Priority.MEDIUM
    source: str = "desktop_agent"
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    tags: List[str] = field(default_factory=list)


class NotificationChannel(Protocol):
    """Protocol for notification channels"""
    
    @abstractmethod
    async def send_notification(self, payload: NotificationPayload) -> bool:
        """Send notification via this channel"""
        pass
    
    @abstractmethod
    def is_enabled(self) -> bool:
        """Check if channel is enabled"""
        pass


class NotificationManager:
    """
    Centralized notification manager for Phase 7 alerts
    Supports multiple channels and smart routing
    """
    
    def __init__(self):
        """Initialize notification manager"""
        self.channels: Dict[str, NotificationChannel] = {}
        self.notification_rules: Dict[NotificationType, List[str]] = {}
        self.rate_limits: Dict[str, datetime] = {}
        self.notification_history: List[NotificationPayload] = []
        
        # Default routing rules
        self._setup_default_routing()
        
        logger.info("Notification manager initialized")
    
    def _setup_default_routing(self):
        """Setup default notification routing rules"""
        self.notification_rules = {
            NotificationType.L4_DEVIATION: ["email", "slack", "github"],
            NotificationType.POLICY_VIOLATION: ["email", "slack", "github"],
            NotificationType.SAFE_FAIL_TRIGGER: ["email", "slack", "webhook"],
            NotificationType.PATCH_PROPOSAL: ["slack", "github"],
            NotificationType.SYSTEM_ALERT: ["email", "webhook"]
        }
    
    def register_channel(self, name: str, channel: NotificationChannel):
        """Register a notification channel"""
        self.channels[name] = channel
        logger.info(f"Registered notification channel: {name}")
    
    def configure_routing(self, notification_type: NotificationType, channels: List[str]):
        """Configure routing for notification type"""
        self.notification_rules[notification_type] = channels
        logger.info(f"Configured routing for {notification_type.value}: {channels}")
    
    async def send_l4_deviation_alert(
        self,
        execution_id: str,
        template_name: str,
        deviation_reason: str,
        execution_context: Dict[str, Any]
    ):
        """Send L4 autopilot deviation alert"""
        
        payload = NotificationPayload(
            notification_type=NotificationType.L4_DEVIATION,
            title=f"L4 Autopilot Deviation - {template_name}",
            message=f"Execution {execution_id[:8]} deviated: {deviation_reason}",
            details={
                "execution_id": execution_id,
                "template_name": template_name,
                "deviation_reason": deviation_reason,
                "execution_context": execution_context
            },
            priority=Priority.HIGH,
            tags=["l4", "autopilot", "deviation"]
        )
        
        await self._send_notification(payload)
    
    async def send_policy_violation_alert(
        self,
        violation_type: str,
        template_name: str,
        policy_details: Dict[str, Any]
    ):
        """Send policy violation alert"""
        
        payload = NotificationPayload(
            notification_type=NotificationType.POLICY_VIOLATION,
            title=f"Policy Violation - {violation_type}",
            message=f"Template {template_name} violated policy: {violation_type}",
            details={
                "violation_type": violation_type,
                "template_name": template_name,
                "policy_details": policy_details
            },
            priority=Priority.HIGH,
            tags=["policy", "violation", "security"]
        )
        
        await self._send_notification(payload)
    
    async def send_safe_fail_trigger(
        self,
        execution_id: str,
        threshold_exceeded: int,
        deviation_details: List[Dict[str, Any]]
    ):
        """Send safe-fail trigger notification"""
        
        payload = NotificationPayload(
            notification_type=NotificationType.SAFE_FAIL_TRIGGER,
            title=f"Safe-Fail Triggered - Execution {execution_id[:8]}",
            message=f"Autopilot stopped after {threshold_exceeded} deviations",
            details={
                "execution_id": execution_id,
                "threshold_exceeded": threshold_exceeded,
                "deviation_details": deviation_details
            },
            priority=Priority.CRITICAL,
            tags=["safe-fail", "autopilot", "critical"]
        )
        
        await self._send_notification(payload)
    
    async def send_patch_proposal_notification(
        self,
        patch_data: Dict[str, Any],
        template_name: str,
        requires_approval: bool
    ):
        """Send patch proposal notification"""
        
        priority = Priority.MEDIUM if requires_approval else Priority.LOW
        
        payload = NotificationPayload(
            notification_type=NotificationType.PATCH_PROPOSAL,
            title=f"Patch Proposal - {template_name}",
            message=f"L2 Planner proposed {patch_data.get('patch_type', 'unknown')} patch",
            details={
                "patch_data": patch_data,
                "template_name": template_name,
                "requires_approval": requires_approval
            },
            priority=priority,
            tags=["planner-l2", "patch", "proposal"]
        )
        
        await self._send_notification(payload)
    
    async def send_system_alert(
        self,
        alert_type: str,
        message: str,
        details: Dict[str, Any],
        priority: Priority = Priority.MEDIUM
    ):
        """Send generic system alert"""
        
        payload = NotificationPayload(
            notification_type=NotificationType.SYSTEM_ALERT,
            title=f"System Alert - {alert_type}",
            message=message,
            details=details,
            priority=priority,
            tags=["system", "alert"]
        )
        
        await self._send_notification(payload)
    
    async def _send_notification(self, payload: NotificationPayload):
        """Send notification to configured channels"""
        
        # Check rate limiting
        rate_limit_key = f"{payload.notification_type.value}:{payload.details.get('execution_id', 'global')}"
        if self._is_rate_limited(rate_limit_key):
            logger.warning(f"Rate limited notification: {payload.title}")
            return
        
        # Get channels for this notification type
        channel_names = self.notification_rules.get(payload.notification_type, [])
        
        if not channel_names:
            logger.warning(f"No channels configured for {payload.notification_type.value}")
            return
        
        # Send to each channel
        sent_count = 0
        failed_channels = []
        
        for channel_name in channel_names:
            channel = self.channels.get(channel_name)
            if not channel:
                logger.warning(f"Channel not found: {channel_name}")
                continue
            
            if not channel.is_enabled():
                logger.debug(f"Channel disabled: {channel_name}")
                continue
            
            try:
                success = await channel.send_notification(payload)
                if success:
                    sent_count += 1
                    logger.info(f"Sent notification to {channel_name}: {payload.title}")
                else:
                    failed_channels.append(channel_name)
                    logger.error(f"Failed to send notification to {channel_name}")
                    
            except Exception as e:
                failed_channels.append(channel_name)
                logger.error(f"Exception sending notification to {channel_name}: {e}")
        
        # Store in history
        self.notification_history.append(payload)
        if len(self.notification_history) > 1000:  # Limit history size
            self.notification_history = self.notification_history[-500:]
        
        # Update rate limiting
        self._update_rate_limit(rate_limit_key)
        
        logger.info(f"Notification sent to {sent_count} channels, {len(failed_channels)} failed")
    
    def _is_rate_limited(self, key: str, window_minutes: int = 5) -> bool:
        """Check if notification is rate limited"""
        if key not in self.rate_limits:
            return False
        
        last_sent = self.rate_limits[key]
        window_delta = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
        
        return last_sent > window_delta
    
    def _update_rate_limit(self, key: str):
        """Update rate limit timestamp"""
        self.rate_limits[key] = datetime.now(timezone.utc)
    
    def get_notification_history(self, limit: int = 50) -> List[NotificationPayload]:
        """Get recent notification history"""
        return self.notification_history[-limit:]
    
    def get_channel_status(self) -> Dict[str, bool]:
        """Get status of all registered channels"""
        return {
            name: channel.is_enabled()
            for name, channel in self.channels.items()
        }
    
    def get_notification_stats(self) -> Dict[str, Any]:
        """Get notification statistics"""
        from collections import Counter
        from datetime import timedelta
        
        # Stats for last 24 hours
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        recent_notifications = [
            n for n in self.notification_history
            if n.timestamp > cutoff
        ]
        
        type_counts = Counter(n.notification_type.value for n in recent_notifications)
        priority_counts = Counter(n.priority.value for n in recent_notifications)
        
        return {
            "total_24h": len(recent_notifications),
            "by_type": dict(type_counts),
            "by_priority": dict(priority_counts),
            "channels_active": sum(1 for c in self.channels.values() if c.is_enabled()),
            "channels_total": len(self.channels)
        }


# Singleton instance
_notification_manager_instance = None


def get_notification_manager() -> NotificationManager:
    """Get singleton notification manager instance"""
    global _notification_manager_instance
    if _notification_manager_instance is None:
        _notification_manager_instance = NotificationManager()
    return _notification_manager_instance