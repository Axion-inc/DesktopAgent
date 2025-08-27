"""
Unit tests for WebX Host Permissions Integrity Checking
Red tests first (TDD) - should fail initially  
"""

import pytest
import tempfile
import json
import yaml
from pathlib import Path
from unittest.mock import patch, MagicMock

from app.web.webx_integrity import WebXIntegrityChecker, PermissionMismatchError, WebXCompatibilityValidator


class TestWebXIntegrityChecker:
    """Test WebX extension host permissions validation"""
    
    def test_load_extension_host_permissions(self):
        """Should load host_permissions from web extension configuration"""
        # RED: Will fail - WebXIntegrityChecker doesn't exist
        checker = WebXIntegrityChecker()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Mock extension manifest
            extension_manifest = {
                "manifest_version": 3,
                "host_permissions": [
                    "https://dashboard.example.com/*",
                    "https://api.company.com/*",
                    "https://*.trusted-domain.com/*"
                ]
            }
            
            manifest_path = Path(temp_dir) / "manifest.json"
            manifest_path.write_text(json.dumps(extension_manifest))
            
            permissions = checker.load_extension_permissions(manifest_path)
            
            assert "https://dashboard.example.com/*" in permissions
            assert "https://api.company.com/*" in permissions
            assert "https://*.trusted-domain.com/*" in permissions
    
    def test_validate_template_url_against_permissions(self):
        """Should validate template URLs against extension host_permissions"""
        # RED: Will fail - URL validation logic not implemented
        checker = WebXIntegrityChecker()
        
        # Mock extension permissions
        checker.host_permissions = [
            "https://dashboard.example.com/*",
            "https://*.trusted-domain.com/*"
        ]
        
        # These should pass
        assert checker.validate_url("https://dashboard.example.com/login") is True
        assert checker.validate_url("https://sub.trusted-domain.com/api") is True
        
        # These should fail
        assert checker.validate_url("https://malicious.com/steal-data") is False
        assert checker.validate_url("https://unauthorized.example.com/") is False
    
    def test_check_template_webx_compatibility(self):
        """Should check if template webx actions are compatible with extension permissions"""
        # RED: Will fail - compatibility checking not implemented
        checker = WebXIntegrityChecker()
        checker.host_permissions = ["https://dashboard.example.com/*"]
        
        compatible_template = """
dsl_version: "1.1"
name: "Compatible Template"
steps:
  - open_browser:
      url: "https://dashboard.example.com/reports"
  - click_by_text: "Generate Report"
"""
        
        incompatible_template = """
dsl_version: "1.1" 
name: "Incompatible Template"
steps:
  - open_browser:
      url: "https://unauthorized-domain.com/data"
  - fill_by_label:
      label: "API Key"
      text: "secret"
"""
        
        # Compatible template should pass
        result = checker.check_template_compatibility(compatible_template)
        assert result.is_compatible is True
        
        # Incompatible template should fail
        result = checker.check_template_compatibility(incompatible_template)
        assert result.is_compatible is False
        assert "unauthorized-domain.com" in result.violations[0]
    
    def test_webx_integrity_with_manifest_validation(self):
        """Should integrate webx validation with template manifest checking"""
        # RED: Will fail - integrated validation not implemented
        validator = WebXCompatibilityValidator()
        
        template_manifest = {
            "required_capabilities": ["webx", "fs"],
            "risk_flags": ["sends"],
            "webx_urls": [
                "https://dashboard.example.com/*",
                "https://unauthorized.com/api"  # This should trigger warning
            ]
        }
        
        extension_permissions = [
            "https://dashboard.example.com/*"
            # Missing unauthorized.com - should cause validation failure
        ]
        
        result = validator.validate_manifest_webx_compatibility(
            template_manifest, 
            extension_permissions
        )
        
        assert result.has_violations is True
        assert "unauthorized.com" in str(result.violations)
    
    def test_execution_block_on_sends_with_permission_mismatch(self):
        """Should block execution if template has 'sends' risk flag and permission mismatch"""
        # RED: Will fail - execution blocking not implemented
        checker = WebXIntegrityChecker()
        
        high_risk_template_manifest = {
            "risk_flags": ["sends"],  # High risk - sends data
            "required_capabilities": ["webx", "mail_draft"]
        }
        
        # Extension doesn't have permission for the domain template wants to access
        extension_permissions = ["https://safe-domain.com/*"]
        template_urls = ["https://external-data-collector.com/api"]
        
        with pytest.raises(PermissionMismatchError) as exc:
            checker.validate_execution_safety(
                template_manifest=high_risk_template_manifest,
                template_urls=template_urls,
                extension_permissions=extension_permissions
            )
        
        assert "execution blocked" in str(exc.value).lower()
        assert "sends" in str(exc.value)
    
    def test_warning_only_for_low_risk_permission_mismatch(self):
        """Should only warn (not block) for low-risk templates with permission mismatches"""
        # RED: Will fail - risk-based blocking logic not implemented
        checker = WebXIntegrityChecker()
        
        low_risk_template_manifest = {
            "risk_flags": [],  # No high-risk flags
            "required_capabilities": ["webx"]
        }
        
        extension_permissions = ["https://allowed.com/*"]
        template_urls = ["https://other-domain.com/read-only"]
        
        # Should return warning but allow execution
        result = checker.validate_execution_safety(
            template_manifest=low_risk_template_manifest,
            template_urls=template_urls,
            extension_permissions=extension_permissions
        )
        
        assert result.execution_allowed is True
        assert result.has_warnings is True
        assert "permission mismatch" in result.warnings[0].lower()


class TestWebXEngineConfig:
    """Test WebX engine configuration integration"""
    
    def test_load_web_engine_config(self):
        """Should load web engine configuration from configs/web_engine.yaml"""
        # RED: Will fail - config loading not implemented
        from app.web.engine_config import WebEngineConfigLoader
        
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "web_engine.yaml"
            config_path.write_text("""
engine: "extension"
extension:
  manifest_path: "/path/to/extension/manifest.json"
  host_permissions_validation: true
  block_on_mismatch: true
  
playwright:
  headless: false
  timeout: 30000
""")
            
            loader = WebEngineConfigLoader()
            config = loader.load_config(config_path)
            
            assert config["engine"] == "extension"
            assert config["extension"]["host_permissions_validation"] is True
            assert config["extension"]["block_on_mismatch"] is True
    
    def test_engine_extension_requires_permission_validation(self):
        """Should enforce permission validation when engine=extension"""
        # RED: Will fail - engine-specific validation not implemented
        from app.web.engine_validator import WebEngineValidator
        
        extension_config = {
            "engine": "extension",
            "extension": {
                "host_permissions_validation": False  # Should force to True
            }
        }
        
        validator = WebEngineValidator()
        validated_config = validator.validate_and_normalize_config(extension_config)
        
        # Should automatically enable host_permissions_validation for extension engine
        assert validated_config["extension"]["host_permissions_validation"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])