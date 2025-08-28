"""
Web Engine Config Validator
Ensures engine-specific settings are valid and normalized.
"""

from typing import Dict, Any


class WebEngineValidator:
    """Validate and normalize web engine configuration."""

    def validate_and_normalize_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        cfg = dict(config)  # shallow copy
        engine = cfg.get("engine", "playwright")
        ext = cfg.setdefault("extension", {})
        if engine == "extension":
            # Always enforce host permission validation in extension mode
            ext["host_permissions_validation"] = True
        return cfg

