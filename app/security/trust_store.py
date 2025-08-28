"""
Trust store utilities for managing trusted keys and trust-level execution policy.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Any, Optional

import yaml


class TrustStoreManager:
    """Load and query trusted keys and trust levels from a YAML file.

    Expected YAML structure:
    keys:
      - key_id: "da:2025:alice"
        pubkey: "<base64 or PEM>"
        trust_level: "system|commercial|development|community|unknown"
    """

    EXECUTION_BY_LEVEL = {
        "system": "auto",
        "commercial": "auto",
        "development": "confirm",
        "community": "confirm",
        "unknown": "block",
    }

    def __init__(self, trust_store_path: Optional[Path] = None):
        self.trust_store_path = trust_store_path
        self._data: Dict[str, Any] = None  # lazy

    def _load(self) -> Dict[str, Any]:
        if self._data is None:
            if self.trust_store_path and Path(self.trust_store_path).exists():
                with open(self.trust_store_path, 'r') as f:
                    self._data = yaml.safe_load(f) or {}
            else:
                self._data = {}
        return self._data

    def is_trusted_key(self, key_id: str) -> bool:
        data = self._load()
        for entry in data.get("keys", []):
            if entry.get("key_id") == key_id:
                return True
        return False

    def get_trust_level(self, key_id: str) -> str:
        data = self._load()
        for entry in data.get("keys", []):
            if entry.get("key_id") == key_id:
                return entry.get("trust_level", "unknown")
        return "unknown"

    def get_execution_policy(self, trust_level: str) -> str:
        return self.EXECUTION_BY_LEVEL.get(trust_level, "block")

