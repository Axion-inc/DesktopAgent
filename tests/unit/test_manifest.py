"""
Unit tests for Template Manifest System
Red tests first (TDD) - should fail initially
"""

import pytest
import tempfile
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

from app.security.template_manifest import ManifestManager, ManifestValidationError
from app.review.capability_analyzer import CapabilityAnalyzer


class TestTemplateManifest:
    """Test template manifest creation and validation"""

    def test_generate_manifest_from_template(self):
        """Should generate manifest.json from template YAML"""
        # RED: Will fail - ManifestManager doesn't exist
        manifest_manager = ManifestManager()

        with tempfile.TemporaryDirectory() as temp_dir:
            template_path = Path(temp_dir) / "test_template.yaml"
            template_path.write_text("""
dsl_version: "1.1"
name: "Monthly Report Generator"
description: "Generates monthly reports from web data"
steps:
  - open_browser:
      url: "https://dashboard.example.com"
  - click_by_text: "Download CSV"
  - attach_file:
      file_path: "data.csv"
  - compose_mail:
      to: "manager@company.com"
      subject: "Monthly Report"
""")

            manifest_path = manifest_manager.generate_manifest(template_path)

            assert manifest_path.exists()
            assert manifest_path.name == "test_template.manifest.json"

            manifest_data = json.loads(manifest_path.read_text())

            # Verify manifest structure
            assert manifest_data["name"] == "Monthly Report Generator"
            assert manifest_data["dsl_version"] == "1.1"
            assert "webx" in manifest_data["required_capabilities"]
            assert "fs" in manifest_data["required_capabilities"]
            assert "mail_draft" in manifest_data["required_capabilities"]
            assert "sends" in manifest_data["risk_flags"]

    def test_validate_manifest_schema(self):
        """Should validate manifest against required schema"""
        # RED: Will fail - validation not implemented
        manifest_manager = ManifestManager()

        valid_manifest = {
            "id": "test@v1.0.0",
            "name": "Test Template",
            "version": "1.0.0",
            "dsl_version": "1.1",
            "required_capabilities": ["webx", "fs"],
            "risk_flags": ["sends"],
            "author": "da:2025:alice"
        }

        # Should pass validation
        result = manifest_manager.validate_manifest(valid_manifest)
        assert result.is_valid is True

        # Should fail with missing required fields
        invalid_manifest = {"name": "Test"}
        result = manifest_manager.validate_manifest(invalid_manifest)
        assert result.is_valid is False
        assert "missing required field" in result.error_message.lower()

    def test_detect_capabilities_from_actions(self):
        """Should automatically detect required capabilities from DSL actions"""
        # RED: Will fail - CapabilityAnalyzer doesn't exist
        analyzer = CapabilityAnalyzer()

        template_content = """
dsl_version: "1.1"
name: "Multi-capability Template"
steps:
  - open_browser:
      url: "https://example.com"
  - fill_by_label:
      label: "Username"
      text: "user"
  - attach_file:
      file_path: "document.pdf"
  - read_pdf:
      file_path: "report.pdf"
  - compose_mail:
      to: "recipient@example.com"
"""

        capabilities = analyzer.detect_capabilities(template_content)

        assert "webx" in capabilities  # open_browser, fill_by_label
        assert "fs" in capabilities    # attach_file
        assert "pdf" in capabilities   # read_pdf
        assert "mail_draft" in capabilities  # compose_mail

    def test_detect_risk_flags_from_actions(self):
        """Should detect risk flags from potentially dangerous actions"""
        # RED: Will fail - risk detection not implemented
        analyzer = CapabilityAnalyzer()

        high_risk_template = """
steps:
  - compose_mail:
      to: "external@domain.com"
      subject: "Data Export"
  - delete_file:
      file_path: "important.txt"
  - overwrite_file:
      file_path: "config.json"
      content: "new content"
"""

        risk_flags = analyzer.detect_risk_flags(high_risk_template)

        assert "sends" in risk_flags     # compose_mail to external
        assert "deletes" in risk_flags   # delete_file
        assert "overwrites" in risk_flags # overwrite_file

    def test_capability_requirement_validation(self):
        """Should validate that template actions match declared capabilities"""
        # RED: Will fail - validation logic not implemented
        manifest_manager = ManifestManager()

        template_with_webx_actions = """
steps:
  - open_browser:
      url: "https://example.com"
  - click_by_text: "Submit"
"""

        manifest_without_webx = {
            "required_capabilities": ["fs"],  # Missing webx!
            "risk_flags": []
        }

        # Should fail validation - template uses webx but doesn't declare it
        with pytest.raises(ManifestValidationError) as exc:
            manifest_manager.validate_template_manifest_match(
                template_with_webx_actions,
                manifest_without_webx
            )

        assert "webx capability required" in str(exc.value).lower()


class TestReviewScreenIntegration:
    """Test manifest integration with review screen"""

    def test_review_displays_capabilities_and_risks(self):
        """Review screen should highlight required capabilities and risk flags"""
        # RED: Will fail - review screen integration not implemented
        from app.review.manifest_display import ReviewManifestDisplay

        manifest = {
            "required_capabilities": ["webx", "fs", "mail_draft"],
            "risk_flags": ["sends", "overwrites"],
            "author": "da:2025:alice"
        }

        display = ReviewManifestDisplay()
        html_output = display.render_capability_warnings(manifest)

        # Should highlight high-risk flags in red
        assert 'risk-critical' in html_output
        assert "sends" in html_output
        assert "overwrites" in html_output

        # Should show required capabilities
        assert "webx" in html_output
        assert "mail_draft" in html_output

    def test_approval_gate_for_high_risk_templates(self):
        """Templates with sends/deletes/overwrites should require explicit approval"""
        # RED: Will fail - approval gate not implemented
        from app.review.approval_gate import ApprovalGateManager

        high_risk_manifest = {
            "risk_flags": ["sends", "deletes", "overwrites"]
        }

        low_risk_manifest = {
            "risk_flags": []
        }

        gate_manager = ApprovalGateManager()

        # High risk should require approval
        assert gate_manager.requires_approval(high_risk_manifest) is True

        # Low risk should auto-approve
        assert gate_manager.requires_approval(low_risk_manifest) is False

    def test_manifest_display_in_run_detail(self):
        """Run detail page should show manifest info for executed templates"""
        # RED: Will fail - run detail integration not implemented
        from app.web.run_detail_renderer import RunDetailRenderer

        run_data = {
            "template_path": "plans/templates/test.yaml",
            "manifest": {
                "required_capabilities": ["webx"],
                "risk_flags": ["sends"],
                "signature_verified": True
            }
        }

        renderer = RunDetailRenderer()
        html = renderer.render_manifest_section(run_data)

        assert "Signature Verified" in html
        assert "webx" in html
        assert "sends" in html


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
