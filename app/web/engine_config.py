"""
Web Engine Configuration Management
Handles web engine configuration for WebX and Playwright engines
"""

import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from ..utils.logging import get_logger

logger = get_logger(__name__)


class WebEngineConfigLoader:
    """Loads and manages web engine configuration"""
    
    DEFAULT_CONFIG = {
        "engine": "extension",
        "extension": {
            "manifest_path": "extension/manifest.json",
            "host_permissions_validation": True,
            "block_on_mismatch": True
        },
        "playwright": {
            "headless": False,
            "timeout": 30000,
            "viewport": {"width": 1280, "height": 720}
        }
    }
    
    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or Path("configs/web_engine.yaml")
        self._config_cache = None
    
    def load_config(self, config_path: Optional[Path] = None) -> Dict[str, Any]:
        """Load web engine configuration from YAML file"""
        config_path = config_path or self.config_path
        
        if not config_path.exists():
            logger.info(f"Web engine config not found, using defaults: {config_path}")
            return self.DEFAULT_CONFIG.copy()
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f) or {}
            
            # Merge with defaults
            merged_config = self._merge_config(self.DEFAULT_CONFIG, config)
            
            logger.info(f"Loaded web engine config: {config_path}")
            return merged_config
            
        except Exception as e:
            logger.error(f"Failed to load web engine config: {e}")
            return self.DEFAULT_CONFIG.copy()
    
    def _merge_config(self, default: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Merge configuration dictionaries"""
        merged = default.copy()
        
        for key, value in override.items():
            if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
                merged[key] = self._merge_config(merged[key], value)
            else:
                merged[key] = value
        
        return merged
    
    def get_cached_config(self) -> Dict[str, Any]:
        """Get cached configuration (loads if not cached)"""
        if self._config_cache is None:
            self._config_cache = self.load_config()
        return self._config_cache
    
    def refresh_config(self):
        """Refresh configuration cache"""
        self._config_cache = None


class WebEngineValidator:
    """Validates and normalizes web engine configuration"""
    
    VALID_ENGINES = ["extension", "playwright"]
    
    def validate_and_normalize_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and normalize web engine configuration"""
        validated_config = config.copy()
        
        # Validate engine type
        engine = validated_config.get("engine", "extension")
        if engine not in self.VALID_ENGINES:
            logger.warning(f"Invalid engine type: {engine}, defaulting to extension")
            validated_config["engine"] = "extension"
        
        # Engine-specific validation
        if engine == "extension":
            validated_config = self._validate_extension_config(validated_config)
        elif engine == "playwright":
            validated_config = self._validate_playwright_config(validated_config)
        
        return validated_config
    
    def _validate_extension_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate extension engine configuration"""
        extension_config = config.get("extension", {})
        
        # Force enable host permissions validation for extension engine
        if not extension_config.get("host_permissions_validation", True):
            logger.info("Force enabling host_permissions_validation for extension engine")
            extension_config["host_permissions_validation"] = True
        
        # Ensure manifest path is specified
        if not extension_config.get("manifest_path"):
            extension_config["manifest_path"] = "extension/manifest.json"
            logger.info("Using default extension manifest path")
        
        # Default to blocking on mismatch for security
        if "block_on_mismatch" not in extension_config:
            extension_config["block_on_mismatch"] = True
        
        config["extension"] = extension_config
        return config
    
    def _validate_playwright_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate playwright engine configuration"""
        playwright_config = config.get("playwright", {})
        
        # Validate timeout
        timeout = playwright_config.get("timeout", 30000)
        if not isinstance(timeout, int) or timeout < 1000:
            logger.warning(f"Invalid timeout {timeout}, using default 30000")
            playwright_config["timeout"] = 30000
        
        # Validate viewport
        viewport = playwright_config.get("viewport", {})
        if not isinstance(viewport, dict):
            viewport = {"width": 1280, "height": 720}
        
        if "width" not in viewport or not isinstance(viewport["width"], int):
            viewport["width"] = 1280
        if "height" not in viewport or not isinstance(viewport["height"], int):
            viewport["height"] = 720
        
        playwright_config["viewport"] = viewport
        config["playwright"] = playwright_config
        return config


# Global instances
_config_loader: Optional[WebEngineConfigLoader] = None
_config_validator: Optional[WebEngineValidator] = None


def get_web_engine_config_loader() -> WebEngineConfigLoader:
    """Get global web engine config loader"""
    global _config_loader
    if _config_loader is None:
        _config_loader = WebEngineConfigLoader()
    return _config_loader


def get_web_engine_validator() -> WebEngineValidator:
    """Get global web engine validator"""
    global _config_validator
    if _config_validator is None:
        _config_validator = WebEngineValidator()
    return _config_validator