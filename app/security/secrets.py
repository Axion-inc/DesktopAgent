"""
Secrets Management System for Desktop Agent.

Provides secure storage and retrieval of sensitive data using multiple backends:
- macOS Keychain (primary)
- File-based storage (fallback) 
- Environment variables (read-only)

Features:
- secrets:// reference resolution in DSL templates
- Automatic masking for logs
- Audit logging
- Multiple backend support with fallback
- Keychain integration for macOS
"""

import os
import re
import json
import subprocess
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from pathlib import Path
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64


class SecretReference:
    """Represents a secrets:// reference."""
    
    def __init__(self, key: str, service: Optional[str] = None):
        self.key = key
        self.service = service
    
    @classmethod
    def parse(cls, reference: str) -> 'SecretReference':
        """Parse a secrets:// reference string."""
        if not reference.startswith("secrets://"):
            raise ValueError("Invalid secret reference: must start with 'secrets://'")
        
        # Remove the protocol
        path = reference[10:]  # len("secrets://") = 10
        
        if not path:
            raise ValueError("Empty secret key")
        
        # Check for service/key format
        if "/" in path:
            service, key = path.split("/", 1)
            if not key:
                raise ValueError("Empty secret key")
            return cls(key, service)
        else:
            return cls(path)
    
    def __str__(self):
        if self.service:
            return f"secrets://{self.service}/{self.key}"
        return f"secrets://{self.key}"


class KeychainBackend:
    """macOS Keychain backend for secret storage."""
    
    def __init__(self):
        self.service_prefix = "com.axion.desktop-agent"
    
    def store(self, service: str, key: str, value: str) -> None:
        """Store a secret in the keychain."""
        full_service = f"{self.service_prefix}.{service}" if service else self.service_prefix
        
        cmd = [
            "security", "add-generic-password",
            "-s", full_service,
            "-a", key,
            "-w", value,
            "-U"  # Update if exists
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if result.returncode != 0:
                raise RuntimeError(f"Keychain store failed: {result.stderr}")
        except FileNotFoundError:
            raise RuntimeError("Keychain access failed: security command not found (not on macOS?)")
    
    def retrieve(self, service: str, key: str) -> str:
        """Retrieve a secret from the keychain."""
        full_service = f"{self.service_prefix}.{service}" if service else self.service_prefix
        
        cmd = [
            "security", "find-generic-password",
            "-s", full_service,
            "-a", key,
            "-w"  # Return password only
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if result.returncode != 0:
                if "could not be found" in result.stderr:
                    raise KeyError(f"Secret '{key}' not found in keychain")
                raise RuntimeError(f"Keychain access failed: {result.stderr}")
            
            return result.stdout.strip()
        except FileNotFoundError:
            raise RuntimeError("Keychain access failed: security command not found (not on macOS?)")
    
    def delete(self, service: str, key: str) -> None:
        """Delete a secret from the keychain."""
        full_service = f"{self.service_prefix}.{service}" if service else self.service_prefix
        
        cmd = [
            "security", "delete-generic-password",
            "-s", full_service,
            "-a", key
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if result.returncode != 0 and "could not be found" not in result.stderr:
                raise RuntimeError(f"Keychain delete failed: {result.stderr}")
        except FileNotFoundError:
            raise RuntimeError("Keychain access failed: security command not found (not on macOS?)")
    
    def exists(self, service: str, key: str) -> bool:
        """Check if a secret exists in the keychain."""
        try:
            self.retrieve(service, key)
            return True
        except KeyError:
            return False


class FileBackend:
    """File-based encrypted backend for secret storage."""
    
    def __init__(self, storage_path: Optional[str] = None):
        if storage_path:
            self.storage_path = Path(storage_path)
        else:
            self.storage_path = Path.home() / ".desktop-agent" / "secrets.db"
        
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self._key = self._get_encryption_key()
    
    def _init_db(self):
        """Initialize the secrets database."""
        with sqlite3.connect(str(self.storage_path)) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS secrets (
                    service TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value BLOB NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (service, key)
                )
            ''')
    
    def _get_encryption_key(self) -> bytes:
        """Get or create encryption key."""
        key_file = self.storage_path.parent / "key.bin"
        
        if key_file.exists():
            return key_file.read_bytes()
        else:
            # Generate new key
            key = Fernet.generate_key()
            key_file.write_bytes(key)
            # Secure file permissions (owner only)
            os.chmod(key_file, 0o600)
            return key
    
    def _encrypt_value(self, value: str) -> bytes:
        """Encrypt a secret value."""
        f = Fernet(self._key)
        return f.encrypt(value.encode('utf-8'))
    
    def _decrypt_value(self, encrypted_value: bytes) -> str:
        """Decrypt a secret value."""
        f = Fernet(self._key)
        return f.decrypt(encrypted_value).decode('utf-8')
    
    def store(self, service: str, key: str, value: str) -> None:
        """Store an encrypted secret in the file backend."""
        encrypted_value = self._encrypt_value(value)
        
        with sqlite3.connect(str(self.storage_path)) as conn:
            conn.execute('''
                INSERT OR REPLACE INTO secrets (service, key, value, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ''', (service or "", key, encrypted_value))
    
    def retrieve(self, service: str, key: str) -> str:
        """Retrieve and decrypt a secret from the file backend."""
        with sqlite3.connect(str(self.storage_path)) as conn:
            cursor = conn.execute(
                'SELECT value FROM secrets WHERE service = ? AND key = ?',
                (service or "", key)
            )
            row = cursor.fetchone()
            
            if not row:
                raise KeyError(f"Secret '{key}' not found")
            
            return self._decrypt_value(row[0])
    
    def delete(self, service: str, key: str) -> None:
        """Delete a secret from the file backend."""
        with sqlite3.connect(str(self.storage_path)) as conn:
            cursor = conn.execute(
                'DELETE FROM secrets WHERE service = ? AND key = ?',
                (service or "", key)
            )
            if cursor.rowcount == 0:
                raise KeyError(f"Secret '{key}' not found")
    
    def exists(self, service: str, key: str) -> bool:
        """Check if a secret exists in the file backend."""
        try:
            self.retrieve(service, key)
            return True
        except KeyError:
            return False


class EnvironmentBackend:
    """Environment variables backend (read-only)."""
    
    def __init__(self, prefix: str = "DESKTOP_AGENT_SECRET_"):
        self.prefix = prefix
    
    def retrieve(self, service: str, key: str) -> str:
        """Retrieve secret from environment variable."""
        env_key = f"{self.prefix}{key}"
        if env_key in os.environ:
            return os.environ[env_key]
        raise KeyError(f"Secret '{key}' not found in environment")
    
    def exists(self, service: str, key: str) -> bool:
        """Check if secret exists in environment."""
        env_key = f"{self.prefix}{key}"
        return env_key in os.environ
    
    def store(self, service: str, key: str, value: str) -> None:
        """Environment backend is read-only."""
        raise NotImplementedError("Environment backend is read-only")
    
    def delete(self, service: str, key: str) -> None:
        """Environment backend is read-only."""
        raise NotImplementedError("Environment backend is read-only")


class SecretsManager:
    """Main secrets management interface."""
    
    REFERENCE_PATTERN = re.compile(r'\{\{secrets://([^}]+)\}\}')
    
    def __init__(self, backends: Optional[List[str]] = None, storage_path: Optional[str] = None):
        self.backends = []
        self.metrics = {
            "lookups": 0,
            "stores": 0,
            "errors": 0,
            "key_access_count": {},
            "last_reset": datetime.now()
        }
        
        # Initialize audit database
        self._init_audit_db(storage_path)
        
        # Setup backends in order of preference
        backend_list = backends or ["keychain", "file", "environment"]
        
        for backend_name in backend_list:
            try:
                if backend_name == "keychain":
                    self.backends.append(KeychainBackend())
                elif backend_name == "file":
                    self.backends.append(FileBackend(storage_path))
                elif backend_name == "environment":
                    self.backends.append(EnvironmentBackend())
            except Exception as e:
                print(f"Warning: Failed to initialize {backend_name} backend: {e}")
        
        if not self.backends:
            # Fallback to file backend at minimum
            self.backends.append(FileBackend(storage_path))
    
    def _init_audit_db(self, storage_path: Optional[str] = None):
        """Initialize audit logging database."""
        if storage_path:
            audit_path = Path(storage_path).parent / "secrets_audit.db"
        else:
            audit_path = Path.home() / ".desktop-agent" / "secrets_audit.db"
        
        audit_path.parent.mkdir(parents=True, exist_ok=True)
        self._audit_db = str(audit_path)
        
        with sqlite3.connect(self._audit_db) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    action TEXT NOT NULL,
                    secret_key TEXT NOT NULL,
                    user_id TEXT,
                    success BOOLEAN NOT NULL,
                    error_message TEXT
                )
            ''')
    
    def _log_audit(self, action: str, secret_key: str, success: bool, error_message: str = None, user_id: str = None):
        """Log secret access for audit purposes."""
        try:
            # Try to get current user from middleware if available
            if not user_id:
                try:
                    from app.middleware.auth import get_current_user
                    user = get_current_user()
                    user_id = getattr(user, 'id', 'unknown') if user else 'system'
                except:
                    user_id = 'system'
            
            with sqlite3.connect(self._audit_db) as conn:
                conn.execute('''
                    INSERT INTO audit_log (action, secret_key, user_id, success, error_message)
                    VALUES (?, ?, ?, ?, ?)
                ''', (action, secret_key, user_id, success, error_message))
        except Exception:
            # Don't fail operations due to audit logging issues
            pass
    
    def _validate_key(self, key: str) -> None:
        """Validate secret key format."""
        if not key:
            raise ValueError("Empty secret key")
        
        if len(key) > 255:
            raise ValueError("Secret key too long (max 255 characters)")
        
        # Allow alphanumeric and underscores
        if not re.match(r'^[A-Z0-9_]+$', key):
            raise ValueError("Invalid secret key: use only uppercase letters, numbers, and underscores")
    
    def _validate_value(self, value: str) -> None:
        """Validate secret value."""
        if not value:
            raise ValueError("Empty secret value")
        
        if len(value) > 50000:  # 50KB limit
            raise ValueError("Secret value too long (max 50KB)")
        
        # Check if it's text (not binary)
        try:
            value.encode('utf-8')
        except UnicodeEncodeError:
            raise ValueError("Secret must be text (UTF-8 encodable)")
    
    def store(self, key: str, value: str, service: Optional[str] = None) -> None:
        """Store a secret using the first available backend."""
        self._validate_key(key)
        self._validate_value(value)
        
        success = False
        last_error = None
        
        # Try each backend until one succeeds
        for backend in self.backends:
            try:
                if hasattr(backend, 'store'):
                    backend.store(service, key, value)
                    success = True
                    break
            except NotImplementedError:
                continue  # Skip read-only backends
            except Exception as e:
                last_error = str(e)
                continue
        
        if success:
            self.metrics["stores"] += 1
            self._log_audit("secret_stored", key, True)
        else:
            self.metrics["errors"] += 1
            error_msg = last_error or "All backends failed"
            self._log_audit("secret_store_failed", key, False, error_msg)
            raise RuntimeError(f"Failed to store secret '{key}': {error_msg}")
    
    def get(self, key: str, service: Optional[str] = None) -> str:
        """Retrieve a secret from any available backend."""
        self._validate_key(key)
        
        # Track access
        self.metrics["lookups"] += 1
        self.metrics["key_access_count"][key] = self.metrics["key_access_count"].get(key, 0) + 1
        
        last_error = None
        
        # Try each backend until one succeeds
        for backend in self.backends:
            try:
                value = backend.retrieve(service, key)
                self._log_audit("secret_accessed", key, True)
                return value
            except KeyError:
                continue  # Try next backend
            except Exception as e:
                last_error = str(e)
                continue
        
        # Not found in any backend
        self.metrics["errors"] += 1
        error_msg = f"Secret '{key}' not found"
        self._log_audit("secret_access_failed", key, False, error_msg)
        raise KeyError(error_msg)
    
    def exists(self, key: str, service: Optional[str] = None) -> bool:
        """Check if a secret exists in any backend."""
        self._validate_key(key)
        
        for backend in self.backends:
            try:
                if backend.exists(service, key):
                    return True
            except Exception:
                continue
        
        return False
    
    def delete(self, key: str, service: Optional[str] = None) -> None:
        """Delete a secret from all backends."""
        self._validate_key(key)
        
        deleted = False
        
        for backend in self.backends:
            try:
                if hasattr(backend, 'delete') and backend.exists(service, key):
                    backend.delete(service, key)
                    deleted = True
            except NotImplementedError:
                continue  # Skip read-only backends
            except Exception:
                continue
        
        if deleted:
            self._log_audit("secret_deleted", key, True)
        else:
            self._log_audit("secret_delete_failed", key, False, "Not found in any backend")
            raise KeyError(f"Secret '{key}' not found")
    
    def resolve_template(self, template: str) -> str:
        """Resolve secrets:// references in a template string."""
        def replace_secret(match):
            reference_str = match.group(1)
            try:
                ref = SecretReference.parse(f"secrets://{reference_str}")
                return self.get(ref.key, ref.service)
            except Exception as e:
                raise ValueError(f"Failed to resolve secret reference '{reference_str}': {e}")
        
        return self.REFERENCE_PATTERN.sub(replace_secret, template)
    
    def resolve_for_logging(self, template: str) -> str:
        """Resolve secrets:// references with masking for safe logging."""
        def mask_secret(match):
            return "***"
        
        return self.REFERENCE_PATTERN.sub(mask_secret, template)
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get secrets usage metrics."""
        # Reset daily metrics if needed
        now = datetime.now()
        if (now - self.metrics["last_reset"]).days >= 1:
            self.metrics["lookups"] = 0
            self.metrics["stores"] = 0
            self.metrics["errors"] = 0
            self.metrics["last_reset"] = now
        
        return {
            "lookups_24h": self.metrics["lookups"],
            "stores_24h": self.metrics["stores"],
            "errors_24h": self.metrics["errors"],
            "popular_keys": list(self.metrics["key_access_count"].keys())[:10],
            "backends_active": len(self.backends),
            "backend_types": [type(b).__name__ for b in self.backends]
        }
    
    def get_audit_log(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent audit log entries."""
        with sqlite3.connect(self._audit_db) as conn:
            conn.row_factory = sqlite3.Row  # Enable dict-like access
            cursor = conn.execute('''
                SELECT * FROM audit_log 
                ORDER BY timestamp DESC 
                LIMIT ?
            ''', (limit,))
            
            return [dict(row) for row in cursor.fetchall()]


# Global secrets manager instance
_secrets_manager = None

def get_secrets_manager() -> SecretsManager:
    """Get the global secrets manager instance."""
    global _secrets_manager
    if _secrets_manager is None:
        _secrets_manager = SecretsManager()
    return _secrets_manager


def store_secret(key: str, value: str, service: Optional[str] = None) -> None:
    """Convenience function to store a secret."""
    get_secrets_manager().store(key, value, service)


def get_secret(key: str, service: Optional[str] = None) -> str:
    """Convenience function to get a secret."""
    return get_secrets_manager().get(key, service)


def secret_exists(key: str, service: Optional[str] = None) -> bool:
    """Convenience function to check if a secret exists."""
    return get_secrets_manager().exists(key, service)


def delete_secret(key: str, service: Optional[str] = None) -> None:
    """Convenience function to delete a secret."""
    get_secrets_manager().delete(key, service)