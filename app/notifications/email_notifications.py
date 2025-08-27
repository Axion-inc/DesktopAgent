"""
Email Notification Channel - Phase 7
Sends notification emails for deviations and alerts
"""

import logging
import smtplib
import os
from typing import Optional
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formatdate

from .notification_manager import NotificationChannel, NotificationPayload

logger = logging.getLogger(__name__)


class EmailNotificationChannel(NotificationChannel):
    """Email notification channel for Phase 7 alerts"""
    
    def __init__(
        self,
        smtp_host: str = None,
        smtp_port: int = 587,
        username: str = None,
        password: str = None,
        from_email: str = None,
        to_emails: list = None,
        use_tls: bool = True
    ):
        """Initialize email notification channel"""
        self.smtp_host = smtp_host or os.getenv("SMTP_HOST", "")
        self.smtp_port = smtp_port
        self.username = username or os.getenv("SMTP_USERNAME", "")
        self.password = password or os.getenv("SMTP_PASSWORD", "")
        self.from_email = from_email or os.getenv("SMTP_FROM_EMAIL", "")
        self.to_emails = to_emails or os.getenv("NOTIFICATION_EMAILS", "").split(",")
        self.use_tls = use_tls
        
        # Clean up email list
        self.to_emails = [email.strip() for email in self.to_emails if email.strip()]
        
        logger.info(f"Email notification channel initialized with {len(self.to_emails)} recipients")
    
    def is_enabled(self) -> bool:
        """Check if email notifications are properly configured"""
        return bool(
            self.smtp_host and
            self.username and 
            self.password and
            self.from_email and
            self.to_emails
        )
    
    async def send_notification(self, payload: NotificationPayload) -> bool:
        """Send email notification"""
        
        if not self.is_enabled():
            logger.warning("Email notifications not properly configured")
            return False
        
        try:
            # Create message
            msg = MIMEMultipart()
            msg['From'] = self.from_email
            msg['To'] = ", ".join(self.to_emails)
            msg['Subject'] = f"[Desktop Agent] {payload.title}"
            msg['Date'] = formatdate(localtime=True)
            
            # Create email body
            body = self._format_email_body(payload)
            msg.attach(MIMEText(body, 'html'))
            
            # Send email
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                if self.use_tls:
                    server.starttls()
                
                server.login(self.username, self.password)
                
                for to_email in self.to_emails:
                    server.send_message(msg, to_addrs=[to_email])
            
            logger.info(f"Email notification sent: {payload.title}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email notification: {e}")
            return False
    
    def _format_email_body(self, payload: NotificationPayload) -> str:
        """Format email body with HTML styling"""
        
        priority_colors = {
            "low": "#28a745",
            "medium": "#ffc107", 
            "high": "#fd7e14",
            "critical": "#dc3545"
        }
        
        priority_color = priority_colors.get(payload.priority.value, "#6c757d")
        
        html = f"""
<html>
<head>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 0; padding: 20px; background: #f8f9fa; }}
        .container {{ max-width: 600px; margin: 0 auto; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .header {{ background: {priority_color}; color: white; padding: 20px; text-align: center; }}
        .content {{ padding: 20px; }}
        .details {{ background: #f8f9fa; padding: 15px; border-radius: 4px; margin: 15px 0; }}
        .footer {{ background: #343a40; color: white; padding: 15px; text-align: center; font-size: 12px; }}
        .priority {{ display: inline-block; padding: 4px 8px; border-radius: 4px; font-size: 12px; font-weight: bold; background: {priority_color}; color: white; }}
        .timestamp {{ color: #6c757d; font-size: 14px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚨 Desktop Agent Alert</h1>
            <div class="priority">{payload.priority.value.upper()}</div>
        </div>
        
        <div class="content">
            <h2>{payload.title}</h2>
            <p>{payload.message}</p>
            
            <div class="timestamp">
                <strong>Time:</strong> {payload.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}
            </div>
            
            <div class="details">
                <h3>Details:</h3>
"""
        
        # Add details
        for key, value in payload.details.items():
            if isinstance(value, dict):
                html += f"<strong>{key.replace('_', ' ').title()}:</strong><br>"
                for sub_key, sub_value in value.items():
                    html += f"&nbsp;&nbsp;• {sub_key}: {sub_value}<br>"
            elif isinstance(value, list):
                html += f"<strong>{key.replace('_', ' ').title()}:</strong><br>"
                for item in value:
                    html += f"&nbsp;&nbsp;• {item}<br>"
            else:
                html += f"<strong>{key.replace('_', ' ').title()}:</strong> {value}<br>"
        
        html += """
            </div>
            
            <div style="margin-top: 20px;">
                <strong>Notification Type:</strong> {payload.notification_type.value.replace('_', ' ').title()}<br>
                <strong>Source:</strong> {payload.source}<br>
                <strong>Tags:</strong> {', '.join(payload.tags)}
            </div>
        </div>
        
        <div class="footer">
            This is an automated notification from Desktop Agent Phase 7<br>
            L4 Autopilot + Policy Engine v1 + Planner L2
        </div>
    </div>
</body>
</html>
""".format(payload=payload)
        
        return html