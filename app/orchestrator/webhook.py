"""
Webhook Handler for Desktop Agent.

Provides webhook endpoint capabilities to trigger plan execution via HTTP requests.
Integrates with the queue system for execution management.

Features:
- Webhook endpoint registration and management
- HMAC signature verification for security
- Request payload validation
- Integration with QueueManager
- Configurable webhook triggers
- Request logging and metrics
"""

# import os
import hmac
import hashlib
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from fastapi import HTTPException, Request, Header
import ipaddress

@dataclass
class WebhookConfig:
    """Configuration for a webhook endpoint."""

    id: str
    name: str
    endpoint: str  # URL path (e.g., "/webhooks/deploy")
    template: str  # Plan template to execute
    secret: Optional[str] = None  # HMAC secret for signature verification
    allowed_ips: List[str] = None  # IP whitelist
    queue: str = "default"
    priority: int = 5
    enabled: bool = True
    variables: Dict[str, Any] = None  # Static variables for template
    extract_variables: List[str] = None  # Keys to extract from payload
    signature_header: str = "X-Signature-256"  # Header containing HMAC signature
    signature_prefix: str = "sha256="  # Prefix for signature value
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def __post_init__(self):
        if self.allowed_ips is None:
            self.allowed_ips = []
        if self.variables is None:
            self.variables = {}
        if self.extract_variables is None:
            self.extract_variables = []

    def validate_signature(self, payload: bytes, signature: str) -> bool:
        """Validate HMAC signature of the payload."""
        if not self.secret:
            return True  # No signature verification if no secret configured

        if not signature:
            return False

        # Remove prefix if present
        if self.signature_prefix and signature.startswith(self.signature_prefix):
            signature = signature[len(self.signature_prefix):]

        # Calculate expected signature
        expected = hmac.new(
            self.secret.encode('utf-8'),
            payload,
            hashlib.sha256
        ).hexdigest()

        # Constant-time comparison to prevent timing attacks
        return hmac.compare_digest(expected, signature)

    def is_ip_allowed(self, ip_address: str) -> bool:
        """Check if an IP address is allowed to access this webhook."""
        if not self.allowed_ips:
            return True  # No IP restrictions if list is empty

        try:
            client_ip = ipaddress.ip_address(ip_address)
            for allowed in self.allowed_ips:
                try:
                    # Try as network (e.g., "192.168.1.0/24")
                    if '/' in allowed:
                        network = ipaddress.ip_network(allowed, strict=False)
                        if client_ip in network:
                            return True
                    else:
                        # Try as single IP
                        allowed_ip = ipaddress.ip_address(allowed)
                        if client_ip == allowed_ip:
                            return True
                except ValueError:
                    continue
            return False
        except ValueError:
            # Invalid IP address
            return False

    def extract_payload_variables(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Extract variables from webhook payload."""
        extracted = {}

        for key in self.extract_variables:
            # Support nested key access with dot notation
            value = payload
            for part in key.split('.'):
                if isinstance(value, dict) and part in value:
                    value = value[part]
                else:
                    value = None
                    break

            if value is not None:
                extracted[key.replace('.', '_')] = value

        return extracted

    def validate(self) -> List[str]:
        """Validate webhook configuration."""
        errors = []

        if not self.id or not self.id.strip():
            errors.append("Webhook ID is required")

        if not self.name or not self.name.strip():
            errors.append("Webhook name is required")

        if not self.endpoint or not self.endpoint.strip():
            errors.append("Endpoint path is required")
        elif not self.endpoint.startswith('/'):
            errors.append("Endpoint path must start with '/'")

        if not self.template or not self.template.strip():
            errors.append("Template path is required")

        if not isinstance(self.priority, int) or self.priority < 1 or self.priority > 9:
            errors.append("Priority must be an integer from 1 to 9")

        if not self.queue or not self.queue.strip():
            errors.append("Queue name is required")

        # Validate IP addresses
        for ip in self.allowed_ips:
            try:
                if '/' in ip:
                    ipaddress.ip_network(ip, strict=False)
                else:
                    ipaddress.ip_address(ip)
            except ValueError:
                errors.append(f"Invalid IP address or network: {ip}")

        return errors

class WebhookService:
    """Main webhook service that manages webhook endpoints."""

    def __init__(self, storage_path: Optional[str] = None):
        self.storage_path = storage_path or str(Path.home() / ".desktop-agent" / "webhooks.db")

        # Initialize database
        Path(self.storage_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

        # Metrics
        self.metrics = {
            "requests_received": 0,
            "requests_successful": 0,
            "requests_failed": 0,
            "signature_failures": 0,
            "ip_blocks": 0,
            "last_request": None
        }

    def _init_db(self):
        """Initialize the webhook database."""
        with sqlite3.connect(self.storage_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS webhooks (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    endpoint TEXT NOT NULL UNIQUE,
                    template TEXT NOT NULL,
                    secret TEXT,
                    allowed_ips TEXT DEFAULT '[]',
                    queue TEXT DEFAULT 'default',
                    priority INTEGER DEFAULT 5,
                    enabled BOOLEAN DEFAULT 1,
                    variables TEXT DEFAULT '{}',
                    extract_variables TEXT DEFAULT '[]',
                    signature_header TEXT DEFAULT 'X-Signature-256',
                    signature_prefix TEXT DEFAULT 'sha256=',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            conn.execute('''
                CREATE TABLE IF NOT EXISTS webhook_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    webhook_id TEXT NOT NULL,
                    client_ip TEXT,
                    user_agent TEXT,
                    payload_size INTEGER,
                    run_id INTEGER,
                    received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    processed_at TIMESTAMP,
                    success BOOLEAN,
                    error_message TEXT,
                    signature_valid BOOLEAN,
                    FOREIGN KEY (webhook_id) REFERENCES webhooks (id)
                )
            ''')

    def add_webhook(self, config: WebhookConfig) -> None:
        """Add a new webhook configuration."""
        # Validate configuration
        errors = config.validate()
        if errors:
            raise ValueError(f"Invalid webhook config: {'; '.join(errors)}")

        with sqlite3.connect(self.storage_path) as conn:
            conn.execute('''
                INSERT OR REPLACE INTO webhooks
                (id, name, endpoint, template, secret, allowed_ips, queue, priority,
                 enabled, variables, extract_variables, signature_header, signature_prefix, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (
                config.id, config.name, config.endpoint, config.template, config.secret,
                json.dumps(config.allowed_ips), config.queue, config.priority,
                config.enabled, json.dumps(config.variables),
                json.dumps(config.extract_variables), config.signature_header,
                config.signature_prefix
            ))

    def remove_webhook(self, webhook_id: str) -> bool:
        """Remove a webhook by ID."""
        with sqlite3.connect(self.storage_path) as conn:
            cursor = conn.execute('DELETE FROM webhooks WHERE id = ?', (webhook_id,))
            return cursor.rowcount > 0

    def get_webhook(self, webhook_id: str) -> Optional[WebhookConfig]:
        """Get a webhook by ID."""
        with sqlite3.connect(self.storage_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute('SELECT * FROM webhooks WHERE id = ?', (webhook_id,))
            row = cursor.fetchone()

            if not row:
                return None

            return self._row_to_config(row)

    def get_webhook_by_endpoint(self, endpoint: str) -> Optional[WebhookConfig]:
        """Get a webhook by endpoint path."""
        with sqlite3.connect(self.storage_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute('SELECT * FROM webhooks WHERE endpoint = ? AND enabled = 1', (endpoint,))
            row = cursor.fetchone()

            if not row:
                return None

            return self._row_to_config(row)

    def list_webhooks(self, enabled_only: bool = False) -> List[WebhookConfig]:
        """List all webhooks."""
        with sqlite3.connect(self.storage_path) as conn:
            conn.row_factory = sqlite3.Row

            query = 'SELECT * FROM webhooks'
            if enabled_only:
                query += ' WHERE enabled = 1'
            query += ' ORDER BY endpoint'

            cursor = conn.execute(query)
            return [self._row_to_config(row) for row in cursor.fetchall()]

    def _row_to_config(self, row) -> WebhookConfig:
        """Convert database row to WebhookConfig object."""
        return WebhookConfig(
            id=row['id'],
            name=row['name'],
            endpoint=row['endpoint'],
            template=row['template'],
            secret=row['secret'],
            allowed_ips=json.loads(row['allowed_ips']) if row['allowed_ips'] else [],
            queue=row['queue'],
            priority=row['priority'],
            enabled=bool(row['enabled']),
            variables=json.loads(row['variables']) if row['variables'] else {},
            extract_variables=json.loads(row['extract_variables']) if row['extract_variables'] else [],
            signature_header=row['signature_header'],
            signature_prefix=row['signature_prefix'],
            created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None,
            updated_at=datetime.fromisoformat(row['updated_at']) if row['updated_at'] else None
        )

    async def handle_webhook_request(self, request: Request, endpoint: str) -> Dict[str, Any]:
        """Handle an incoming webhook request."""
        self.metrics["requests_received"] += 1
        self.metrics["last_request"] = datetime.now()

        # Get client IP
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "")

        # Find webhook configuration
        config = self.get_webhook_by_endpoint(endpoint)
        if not config:
            self.metrics["requests_failed"] += 1
            raise HTTPException(status_code=404, detail="Webhook endpoint not found")

        # Check IP whitelist
        if not config.is_ip_allowed(client_ip):
            self.metrics["requests_failed"] += 1
            self.metrics["ip_blocks"] += 1
            self._log_request(config.id, client_ip, user_agent, 0, None, False, "IP address not allowed", False)
            raise HTTPException(status_code=403, detail="IP address not allowed")

        # Read payload
        try:
            payload_bytes = await request.body()
            payload_size = len(payload_bytes)

            # Parse JSON payload
            if payload_bytes:
                payload_data = json.loads(payload_bytes.decode('utf-8'))
            else:
                payload_data = {}
        except Exception as e:
            self.metrics["requests_failed"] += 1
            self._log_request(config.id, client_ip, user_agent, 0, None, False, "Invalid payload", False)
            raise HTTPException(status_code=400, detail="Invalid JSON payload")

        # Verify signature if configured
        signature_valid = True
        if config.secret:
            signature = request.headers.get(config.signature_header, "")
            signature_valid = config.validate_signature(payload_bytes, signature)

            if not signature_valid:
                self.metrics["requests_failed"] += 1
                self.metrics["signature_failures"] += 1
                self._log_request(config.id, client_ip, user_agent, payload_size, None, False, "Invalid signature", False)
                raise HTTPException(status_code=401, detail="Invalid signature")

        # Process the webhook
        try:
            result = await self._process_webhook(config, payload_data, client_ip, user_agent, payload_size)
            self.metrics["requests_successful"] += 1
            return result
        except Exception as e:
            self.metrics["requests_failed"] += 1
            self._log_request(config.id, client_ip, user_agent, payload_size, None, False, str(e), signature_valid)
            raise HTTPException(status_code=500, detail="Webhook processing failed")

    async def _process_webhook(self, config: WebhookConfig, payload: Dict[str, Any],
                              client_ip: str, user_agent: str, payload_size: int) -> Dict[str, Any]:
        """Process a validated webhook request."""
        try:
            from app.orchestrator.queue import get_queue_manager
            queue_manager = get_queue_manager()

            # Combine static variables with extracted payload variables
            variables = dict(config.variables)
            variables.update(config.extract_payload_variables(payload))

            # Add webhook metadata
            variables.update({
                "webhook_id": config.id,
                "webhook_endpoint": config.endpoint,
                "webhook_client_ip": client_ip,
                "webhook_user_agent": user_agent,
                "webhook_received_at": datetime.now().isoformat(),
                "webhook_payload": payload
            })

            # Create run request for the queue
            run_request = {
                "template": config.template,
                "variables": variables,
                "queue": config.queue,
                "priority": config.priority,
                "source": f"webhook:{config.id}",
                "concurrency_tag": f"webhook_{config.id}"
            }

            # Add to queue
            run_id = queue_manager.enqueue_run(run_request)

            # Log successful request
            self._log_request(config.id, client_ip, user_agent, payload_size, run_id, True, None, True)

            return {
                "success": True,
                "run_id": run_id,
                "message": f"Webhook processed successfully, queued as run {run_id}",
                "webhook": {
                    "id": config.id,
                    "name": config.name,
                    "endpoint": config.endpoint
                }
            }

        except Exception as e:
            self._log_request(config.id, client_ip, user_agent, payload_size, None, False, "Processing failed", True)
            raise

    def _log_request(self, webhook_id: str, client_ip: str, user_agent: str, payload_size: int,
                     run_id: Optional[int], success: bool, error_message: Optional[str], signature_valid: bool):
        """Log a webhook request."""
        with sqlite3.connect(self.storage_path) as conn:
            conn.execute('''
                INSERT INTO webhook_requests
                (webhook_id, client_ip, user_agent, payload_size, run_id,
                 processed_at, success, error_message, signature_valid)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?, ?, ?)
            ''', (webhook_id, client_ip, user_agent, payload_size, run_id, success, error_message, signature_valid))

    def get_metrics(self) -> Dict[str, Any]:
        """Get webhook metrics."""
        return {
            **self.metrics,
            "webhooks_count": len(self.list_webhooks()),
            "enabled_webhooks": len(self.list_webhooks(enabled_only=True)),
            "endpoints": [w.endpoint for w in self.list_webhooks(enabled_only=True)]
        }

    def get_request_history(self, webhook_id: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Get webhook request history."""
        with sqlite3.connect(self.storage_path) as conn:
            conn.row_factory = sqlite3.Row

            query = '''
                SELECT r.*, w.name as webhook_name, w.endpoint
                FROM webhook_requests r
                JOIN webhooks w ON r.webhook_id = w.id
            '''
            params = []

            if webhook_id:
                query += ' WHERE r.webhook_id = ?'
                params.append(webhook_id)

            query += ' ORDER BY r.received_at DESC LIMIT ?'
            params.append(limit)

            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

# Global webhook service
_webhook_service = None

def get_webhook_service() -> WebhookService:
    """Get the global webhook service instance."""
    global _webhook_service
    if _webhook_service is None:
        _webhook_service = WebhookService()
    return _webhook_service

def setup_webhook_routes(app):
    """Setup webhook routes in the FastAPI app."""
    webhook_service = get_webhook_service()

    @app.post("/webhooks/{endpoint:path}")
    async def webhook_handler(endpoint: str, request: Request):
        """Generic webhook handler for all configured endpoints."""
        return await webhook_service.handle_webhook_request(request, f"/{endpoint}")

    @app.get("/webhooks")
    async def list_webhooks():
        """List all configured webhooks."""
        return {"webhooks": [
            {
                "id": w.id,
                "name": w.name,
                "endpoint": w.endpoint,
                "template": w.template,
                "enabled": w.enabled,
                "queue": w.queue,
                "priority": w.priority
            }
            for w in webhook_service.list_webhooks()
        ]}

    @app.get("/webhooks/metrics")
    async def webhook_metrics():
        """Get webhook metrics."""
        return webhook_service.get_metrics()

    @app.get("/webhooks/history")
    async def webhook_history(webhook_id: Optional[str] = None, limit: int = 100):
        """Get webhook request history."""
        return {
            "history": webhook_service.get_request_history(webhook_id, limit)
        }
