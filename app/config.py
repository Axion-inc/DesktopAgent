"""
Configuration management for Desktop Agent
Provides configuration loading and access functions
"""

import yaml
from pathlib import Path
from typing import Dict, Any, Optional

_config_cache: Optional[Dict[str, Any]] = None


def get_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """Get application configuration, loading from file if needed"""
    global _config_cache

    if _config_cache is None:
        _config_cache = load_config(config_path)

    return _config_cache


def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """Load configuration from YAML file"""
    if config_path is None:
        # Default config paths to try
        possible_paths = [
            "configs/web_engine.yaml",
            "config.yaml",
            "config/app.yaml"
        ]

        for path in possible_paths:
            if Path(path).exists():
                config_path = path
                break

    if config_path and Path(config_path).exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            print(f"Warning: Failed to load config from {config_path}: {e}")

    # Return default configuration
    return {
        'web_engine': {
            'engine': 'playwright',
            'extension': {
                'id': 'test_extension_id',
                'handshake_token': 'test_token',
                'timeout_ms': 15000,
                'enable_debugger_upload': False
            },
            'playwright': {
                'headless': True,
                'timeout_ms': 30000
            }
        },
        'logging': {
            'level': 'INFO'
        }
    }


def reload_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """Reload configuration from file"""
    global _config_cache
    _config_cache = load_config(config_path)
    return _config_cache


def update_config(updates: Dict[str, Any]) -> None:
    """Update configuration values in memory"""
    global _config_cache

    if _config_cache is None:
        _config_cache = get_config()

    def deep_update(base: Dict[str, Any], updates: Dict[str, Any]) -> None:
        """Recursively update nested dictionaries"""
        for key, value in updates.items():
            if isinstance(value, dict) and key in base and isinstance(base[key], dict):
                deep_update(base[key], value)
            else:
                base[key] = value

    deep_update(_config_cache, updates)
