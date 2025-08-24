"""
Role-Based Access Control (RBAC) for Phase 4.

Provides role management, permission checking, and access control middleware.
"""

import time
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass
from enum import Enum
import logging

from ..models import get_conn
from ..utils import get_logger

logger = get_logger()


class Role(Enum):
    """System roles in hierarchical order (higher values = more permissions)."""
    VIEWER = 1
    RUNNER = 2
    EDITOR = 3
    ADMIN = 4


@dataclass
class Permission:
    """Represents a system permission."""
    name: str
    description: str
    required_role: Role


@dataclass
class User:
    """Represents a system user."""
    id: str
    username: str
    role: Role
    created_at: datetime
    last_login: Optional[datetime] = None
    enabled: bool = True
    
    def can(self, permission: str) -> bool:
        """Check if user has a specific permission."""
        rbac = get_rbac_manager()
        return rbac.check_permission(self.role, permission)


class RBACManager:
    """Manages roles, permissions, and users."""
    
    def __init__(self):
        self._permissions = self._define_permissions()
        self._audit_entries = []
        self._init_database()
    
    def _define_permissions(self) -> Dict[str, Permission]:
        """Define system permissions and their required roles."""
        permissions = {
            # Read permissions (Viewer+)
            "read_runs": Permission("read_runs", "View run history and details", Role.VIEWER),
            "read_metrics": Permission("read_metrics", "View system metrics", Role.VIEWER),
            "read_dashboard": Permission("read_dashboard", "Access dashboard", Role.VIEWER),
            
            # Create permissions (Runner+)
            "create_runs": Permission("create_runs", "Create new runs", Role.RUNNER),
            "execute_templates": Permission("execute_templates", "Execute plan templates", Role.RUNNER),
            
            # Write permissions (Editor+)
            "write_runs": Permission("write_runs", "Modify runs", Role.EDITOR),
            "stop_runs": Permission("stop_runs", "Stop running runs", Role.EDITOR),
            "approve_runs": Permission("approve_runs", "Approve dangerous operations", Role.EDITOR),
            "manage_templates": Permission("manage_templates", "Create/modify templates", Role.EDITOR),
            "manage_schedules": Permission("manage_schedules", "Manage cron schedules", Role.EDITOR),
            "respond_hitl": Permission("respond_hitl", "Respond to HITL confirmations", Role.EDITOR),
            
            # Delete permissions (Editor+)
            "delete_runs": Permission("delete_runs", "Delete run history", Role.EDITOR),
            
            # System permissions (Admin only)
            "manage_users": Permission("manage_users", "Manage user accounts", Role.ADMIN),
            "manage_rbac": Permission("manage_rbac", "Manage roles and permissions", Role.ADMIN),
            "manage_secrets": Permission("manage_secrets", "Manage secret storage", Role.ADMIN),
            "manage_system": Permission("manage_system", "System configuration", Role.ADMIN),
            "view_audit_log": Permission("view_audit_log", "View audit log", Role.ADMIN),
            
            # Queue management (Admin only)
            "manage_queues": Permission("manage_queues", "Manage run queues", Role.ADMIN),
            "pause_queues": Permission("pause_queues", "Pause/resume queues", Role.ADMIN),
        }
        return permissions
    
    def _init_database(self):
        """Initialize RBAC database tables."""
        conn = get_conn()
        cur = conn.cursor()
        
        # Users table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS rbac_users (
                id TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP,
                enabled BOOLEAN DEFAULT TRUE
            )
        """)
        
        # Sessions table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS rbac_sessions (
                token TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                role INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL,
                FOREIGN KEY (user_id) REFERENCES rbac_users (id)
            )
        """)
        
        # Audit log table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS rbac_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                action TEXT NOT NULL,
                resource TEXT,
                success BOOLEAN NOT NULL,
                ip_address TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                details TEXT
            )
        """)
        
        # Permission denials table (for metrics)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS rbac_denials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                permission TEXT NOT NULL,
                resource TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ip_address TEXT
            )
        """)
        
        conn.commit()
        conn.close()
        
        # Create default admin user if none exists
        self._create_default_admin()
    
    def _create_default_admin(self):
        """Create default admin user if no users exist."""
        conn = get_conn()
        cur = conn.cursor()
        
        cur.execute("SELECT COUNT(*) as count FROM rbac_users")
        user_count = cur.fetchone()["count"]
        
        if user_count == 0:
            # Create default admin
            admin_id = self.create_user("admin", "admin123", Role.ADMIN)
            logger.info("Created default admin user (username: admin, password: admin123)")
            
            # Create other default users for testing
            self.create_user("editor", "editor123", Role.EDITOR)
            self.create_user("runner", "runner123", Role.RUNNER)
            self.create_user("viewer", "viewer123", Role.VIEWER)
            logger.info("Created default test users")
        
        conn.close()
    
    def create_user(self, username: str, password: str, role: Role = Role.VIEWER) -> str:
        """Create a new user."""
        conn = get_conn()
        cur = conn.cursor()
        
        # Generate user ID
        user_id = f"user_{int(time.time() * 1000)}"
        
        # Hash password
        password_hash = self._hash_password(password)
        
        try:
            cur.execute("""
                INSERT INTO rbac_users (id, username, password_hash, role)
                VALUES (?, ?, ?, ?)
            """, (user_id, username, password_hash, role.value))
            
            conn.commit()
            
            # Audit log
            self._log_audit_event("create_user", user_id, True, f"Created user {username} with role {role.name}")
            
            logger.info(f"Created user {username} ({user_id}) with role {role.name}")
            return user_id
            
        except Exception as e:
            logger.error(f"Failed to create user {username}: {e}")
            raise
        finally:
            conn.close()
    
    def authenticate(self, username: str, password: str) -> Optional[User]:
        """Authenticate user and return User object."""
        conn = get_conn()
        cur = conn.cursor()
        
        # Get user
        cur.execute("""
            SELECT id, username, password_hash, role, created_at, last_login, enabled
            FROM rbac_users
            WHERE username = ? AND enabled = TRUE
        """, (username,))
        
        row = cur.fetchone()
        if not row:
            self._log_audit_event("login_failed", None, False, f"User {username} not found")
            conn.close()
            return None
        
        # Verify password
        if not self._verify_password(password, row["password_hash"]):
            self._log_audit_event("login_failed", row["id"], False, f"Invalid password for {username}")
            conn.close()
            return None
        
        # Update last login
        cur.execute("""
            UPDATE rbac_users SET last_login = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (row["id"],))
        conn.commit()
        
        # Create user object
        user = User(
            id=row["id"],
            username=row["username"],
            role=Role(row["role"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            last_login=datetime.now(),
            enabled=row["enabled"]
        )
        
        self._log_audit_event("login_success", user.id, True, f"User {username} logged in")
        
        conn.close()
        return user
    
    def create_session(self, user: User, duration_hours: int = 24) -> str:
        """Create a session token for a user."""
        conn = get_conn()
        cur = conn.cursor()
        
        # Generate session token
        token_data = f"{user.id}:{time.time()}:{user.username}"
        token = hashlib.sha256(token_data.encode()).hexdigest()
        
        expires_at = datetime.now() + timedelta(hours=duration_hours)
        
        cur.execute("""
            INSERT INTO rbac_sessions (token, user_id, role, expires_at)
            VALUES (?, ?, ?, ?)
        """, (token, user.id, user.role.value, expires_at))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Created session for user {user.username}")
        return token
    
    def get_session_user(self, token: str) -> Optional[User]:
        """Get user from session token."""
        conn = get_conn()
        cur = conn.cursor()
        
        # Get session and user info
        cur.execute("""
            SELECT s.user_id, s.role, s.expires_at, u.username, u.created_at, u.enabled
            FROM rbac_sessions s
            JOIN rbac_users u ON s.user_id = u.id
            WHERE s.token = ? AND s.expires_at > CURRENT_TIMESTAMP AND u.enabled = TRUE
        """, (token,))
        
        row = cur.fetchone()
        if not row:
            conn.close()
            return None
        
        user = User(
            id=row["user_id"],
            username=row["username"],
            role=Role(row["role"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            enabled=row["enabled"]
        )
        
        conn.close()
        return user
    
    def check_permission(self, user_role: Role, permission_name: str) -> bool:
        """Check if a role has a specific permission."""
        permission = self._permissions.get(permission_name)
        if not permission:
            logger.warning(f"Unknown permission: {permission_name}")
            return False
        
        # Role hierarchy: higher or equal role can access
        return user_role.value >= permission.required_role.value
    
    def require_permission(self, user: Optional[User], permission_name: str, resource: str = "") -> None:
        """Require a permission, raise PermissionError if denied."""
        if not user:
            self._log_denial(None, permission_name, resource)
            raise PermissionError("Authentication required")
        
        if not self.check_permission(user.role, permission_name):
            self._log_denial(user.id, permission_name, resource)
            raise PermissionError(f"Permission '{permission_name}' required (current role: {user.role.name})")
    
    def get_role(self, role_name: str) -> Role:
        """Get role by name."""
        try:
            return Role[role_name.upper()]
        except KeyError:
            raise ValueError(f"Unknown role: {role_name}")
    
    def assign_role(self, user_id: str, role: Role) -> None:
        """Assign role to user."""
        conn = get_conn()
        cur = conn.cursor()
        
        cur.execute("""
            UPDATE rbac_users SET role = ?
            WHERE id = ?
        """, (role.value, user_id))
        
        if cur.rowcount == 0:
            raise ValueError(f"User {user_id} not found")
        
        conn.commit()
        conn.close()
        
        self._log_audit_event("assign_role", user_id, True, f"Assigned role {role.name}")
        logger.info(f"Assigned role {role.name} to user {user_id}")
    
    def _hash_password(self, password: str) -> str:
        """Hash password with salt."""
        salt = "desktop_agent_salt"  # In production, use proper random salt per user
        return hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000).hex()
    
    def _verify_password(self, password: str, password_hash: str) -> bool:
        """Verify password against hash."""
        return self._hash_password(password) == password_hash
    
    def _log_audit_event(self, action: str, user_id: Optional[str], success: bool, details: str):
        """Log audit event."""
        conn = get_conn()
        cur = conn.cursor()
        
        cur.execute("""
            INSERT INTO rbac_audit (user_id, action, success, details)
            VALUES (?, ?, ?, ?)
        """, (user_id, action, success, details))
        
        conn.commit()
        conn.close()
    
    def _log_denial(self, user_id: Optional[str], permission: str, resource: str):
        """Log permission denial for metrics."""
        conn = get_conn()
        cur = conn.cursor()
        
        cur.execute("""
            INSERT INTO rbac_denials (user_id, permission, resource)
            VALUES (?, ?, ?)
        """, (user_id, permission, resource))
        
        conn.commit()
        conn.close()
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get RBAC metrics."""
        conn = get_conn()
        cur = conn.cursor()
        
        # Get denials count (24h)
        cur.execute("""
            SELECT COUNT(*) as count
            FROM rbac_denials
            WHERE timestamp >= datetime('now', '-1 day')
        """)
        
        denials_count = cur.fetchone()["count"] or 0
        
        # Get most denied permissions
        cur.execute("""
            SELECT permission, COUNT(*) as count
            FROM rbac_denials
            WHERE timestamp >= datetime('now', '-1 day')
            GROUP BY permission
            ORDER BY count DESC
            LIMIT 5
        """)
        
        denied_permissions = []
        for row in cur.fetchall():
            denied_permissions.append({
                "permission": row["permission"],
                "count": row["count"]
            })
        
        metrics = {
            "rbac_denied_24h": denials_count,
            "top_denied_permissions": denied_permissions
        }
        
        conn.close()
        return metrics
    
    def get_audit_log(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent audit log entries."""
        conn = get_conn()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT a.action, a.success, a.details, a.timestamp, u.username
            FROM rbac_audit a
            LEFT JOIN rbac_users u ON a.user_id = u.id
            ORDER BY a.timestamp DESC
            LIMIT ?
        """, (limit,))
        
        audit_entries = []
        for row in cur.fetchall():
            audit_entries.append({
                "action": row["action"],
                "success": row["success"],
                "details": row["details"],
                "timestamp": row["timestamp"],
                "username": row["username"] or "system"
            })
        
        conn.close()
        return audit_entries


# Global RBAC manager instance
_rbac_manager: Optional[RBACManager] = None


def get_rbac_manager() -> RBACManager:
    """Get the global RBAC manager instance."""
    global _rbac_manager
    if _rbac_manager is None:
        _rbac_manager = RBACManager()
    return _rbac_manager


def init_rbac() -> RBACManager:
    """Initialize the global RBAC manager."""
    global _rbac_manager
    _rbac_manager = RBACManager()
    return _rbac_manager