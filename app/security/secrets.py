"""
Secrets management for Desktop Agent
Provides secure storage and retrieval of sensitive configuration
"""

import os
from typing import Optional, Dict, Any
from pathlib import Path
import json


class SecretsManager:
    """Manages secrets and sensitive configuration"""
    
    def __init__(self, secrets_path: Optional[str] = None):
        self.secrets_path = secrets_path or os.path.expanduser("~/.config/desktop-agent/secrets.json")
        self._secrets_cache: Optional[Dict[str, str]] = None
    
    def get_secret(self, key: str) -> Optional[str]:
        """Get a secret value by key"""
        secrets = self._load_secrets()
        return secrets.get(key)
    
    def set_secret(self, key: str, value: str) -> None:
        """Set a secret value"""
        secrets = self._load_secrets()
        secrets[key] = value
        self._save_secrets(secrets)
        self._secrets_cache = secrets
    
    def _load_secrets(self) -> Dict[str, str]:
        """Load secrets from file"""
        if self._secrets_cache is not None:
            return self._secrets_cache
        
        secrets_file = Path(self.secrets_path)
        if secrets_file.exists():
            try:
                with open(secrets_file, 'r') as f:
                    self._secrets_cache = json.load(f)
                    return self._secrets_cache
            except Exception:
                pass
        
        # Return empty dict if no secrets file
        self._secrets_cache = {}
        return self._secrets_cache
    
    def _save_secrets(self, secrets: Dict[str, str]) -> None:
        """Save secrets to file"""
        secrets_file = Path(self.secrets_path)
        secrets_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(secrets_file, 'w') as f:
            json.dump(secrets, f, indent=2)
        
        # Set restrictive permissions
        secrets_file.chmod(0o600)
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get metrics about secrets management"""
        secrets = self._load_secrets()
        return {
            'secrets_count': len(secrets),
            'secrets_file_exists': Path(self.secrets_path).exists(),
            'last_modified': Path(self.secrets_path).stat().st_mtime if Path(self.secrets_path).exists() else None
        }


# Global secrets manager instance
_secrets_manager: Optional[SecretsManager] = None


def get_secrets_manager() -> SecretsManager:
    """Get global secrets manager instance"""
    global _secrets_manager
    if _secrets_manager is None:
        _secrets_manager = SecretsManager()
    return _secrets_manager