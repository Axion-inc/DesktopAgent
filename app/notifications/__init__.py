"""
Notification System - Phase 7
Handles deviation detection alerts and notifications
"""

from .notification_manager import NotificationManager, NotificationChannel, NotificationType
from .email_notifications import EmailNotificationChannel
from .slack_notifications import SlackNotificationChannel
from .webhook_notifications import WebhookNotificationChannel

__all__ = [
    'NotificationManager',
    'NotificationChannel',
    'NotificationType',
    'EmailNotificationChannel',
    'SlackNotificationChannel',
    'WebhookNotificationChannel'
]
