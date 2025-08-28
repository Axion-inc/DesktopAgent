"""
Unit tests for Policy Engine v1 - Phase 7
TDD Red Phase: Should fail initially - Policy Engine not implemented yet
"""

import pytest
import tempfile
import os
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock

# These imports will initially fail - this is the RED phase of TDD
from app.policy.engine import PolicyEngine, PolicyViolation, PolicyDecision
from app.policy.time_window import TimeWindowParser


class TestPolicyEngine:
    """Test core policy engine functionality"""

    def test_policy_engine_initialization(self):
        """Should initialize policy engine with config file"""
        # RED: PolicyEngine class doesn't exist yet
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("""
autopilot: false
allow_domains: ["partner.example.com"]
allow_risks: ["sends"]
window: "SUN 00:00-06:00 Asia/Tokyo"
require_signed_templates: true
require_capabilities: ["webx"]
            """)
            f.flush()

            engine = PolicyEngine(config_path=f.name)

            assert engine.config['autopilot'] is False
            assert "partner.example.com" in engine.config['allow_domains']
            assert "sends" in engine.config['allow_risks']

            os.unlink(f.name)

    def test_policy_blocks_domain_violation(self):
        """Should block execution when domain not in allow_domains"""
        # RED: Will fail - policy validation not implemented
        config = {
            'autopilot': True,
            'allow_domains': ['trusted.example.com'],
            'allow_risks': ['sends'],
            'window': 'MON-FRI 09:00-17:00 Asia/Tokyo',
            'require_signed_templates': True,
            'require_capabilities': ['webx']
        }

        engine = PolicyEngine.from_dict(config)

        # Test template with unauthorized domain
        template_manifest = {
            'required_capabilities': ['webx'],
            'risk_flags': ['sends'],
            'webx_urls': ['https://malicious.com/form'],
            'signature_verified': True
        }

        with pytest.raises(PolicyViolation) as exc:
            engine.validate_execution(template_manifest)

        assert "domain_violation" in str(exc.value).lower()
        assert "malicious.com" in str(exc.value)

    def test_policy_blocks_time_window_violation(self):
        """Should block execution outside allowed time window"""
        # RED: Time window parsing not implemented
        config = {
            'autopilot': True,
            'allow_domains': ['trusted.example.com'],
            'window': 'MON-FRI 09:00-17:00 Asia/Tokyo'  # Business hours only
        }

        engine = PolicyEngine.from_dict(config)

        template_manifest = {
            'required_capabilities': ['webx'],
            'risk_flags': [],
            'webx_urls': ['https://trusted.example.com/form'],
            'signature_verified': True
        }

        # Use Saturday (weekend) as current time - should be blocked
        weekend_time = datetime(2025, 8, 30, 14, 0, 0, tzinfo=timezone.utc)  # Saturday

        with pytest.raises(PolicyViolation) as exc:
            engine.validate_execution(template_manifest, current_time=weekend_time)

        assert "time_window_violation" in str(exc.value).lower()

    def test_policy_blocks_risk_violation(self):
        """Should block execution when risk flags not in allow_risks"""
        # RED: Risk validation not implemented
        config = {
            'autopilot': True,
            'allow_domains': ['trusted.example.com'],
            'allow_risks': ['sends'],  # Only sends allowed
            'window': 'SUN-SAT 00:00-23:59 Asia/Tokyo'  # Always allowed
        }

        engine = PolicyEngine.from_dict(config)

        # Template with forbidden risk (deletes)
        template_manifest = {
            'required_capabilities': ['webx', 'fs'],
            'risk_flags': ['sends', 'deletes'],  # deletes not allowed
            'webx_urls': ['https://trusted.example.com/form'],
            'signature_verified': True
        }

        with pytest.raises(PolicyViolation) as exc:
            engine.validate_execution(template_manifest)

        assert "risk_violation" in str(exc.value).lower()
        assert "deletes" in str(exc.value)

    def test_policy_blocks_unsigned_template(self):
        """Should block execution when signature verification fails"""
        # RED: Signature validation not implemented
        config = {
            'require_signed_templates': True,
            'autopilot': True,
            'allow_domains': ['trusted.example.com']
        }

        engine = PolicyEngine.from_dict(config)

        # Template without signature
        template_manifest = {
            'required_capabilities': ['webx'],
            'risk_flags': [],
            'webx_urls': ['https://trusted.example.com/form'],
            'signature_verified': False  # NOT signed
        }

        with pytest.raises(PolicyViolation) as exc:
            engine.validate_execution(template_manifest)

        assert "signature required" in str(exc.value).lower()

    def test_policy_blocks_capability_mismatch(self):
        """Should block when required capabilities not satisfied"""
        # RED: Capability validation not implemented
        config = {
            'require_capabilities': ['webx', 'fs', 'mail_draft'],  # Strict requirements
            'autopilot': True,
            'allow_domains': ['trusted.example.com']
        }

        engine = PolicyEngine.from_dict(config)

        # Template with insufficient capabilities
        template_manifest = {
            'required_capabilities': ['webx'],  # Missing fs, mail_draft
            'risk_flags': [],
            'webx_urls': ['https://trusted.example.com/form'],
            'signature_verified': True
        }

        with pytest.raises(PolicyViolation) as exc:
            engine.validate_execution(template_manifest)

        assert "capability_mismatch" in str(exc.value).lower()

    def test_policy_allows_compliant_execution(self):
        """Should allow execution when all policy conditions met"""
        # RED: Complete validation flow not implemented
        config = {
            'autopilot': True,
            'allow_domains': ['trusted.example.com'],
            'allow_risks': ['sends'],
            'window': 'SUN-SAT 00:00-23:59 Asia/Tokyo',  # Always allowed
            'require_signed_templates': True,
            'require_capabilities': ['webx']
        }

        engine = PolicyEngine.from_dict(config)

        # Fully compliant template
        template_manifest = {
            'required_capabilities': ['webx'],
            'risk_flags': ['sends'],
            'webx_urls': ['https://trusted.example.com/form'],
            'signature_verified': True
        }

        # Should not raise exception
        decision = engine.validate_execution(template_manifest)

        assert decision.allowed is True
        assert decision.autopilot_enabled is True
        assert len(decision.violations) == 0


class TestTimeWindowParser:
    """Test time window parsing and validation"""

    def test_parse_business_hours_window(self):
        """Should parse business hours time window correctly"""
        # RED: TimeWindowParser doesn't exist yet
        parser = TimeWindowParser()

        window = parser.parse("MON-FRI 09:00-17:00 Asia/Tokyo")

        assert window.days == ['MON', 'TUE', 'WED', 'THU', 'FRI']
        assert window.start_time == "09:00"
        assert window.end_time == "17:00"
        assert window.timezone == "Asia/Tokyo"

    def test_parse_weekend_window(self):
        """Should parse weekend-only time window"""
        # RED: Weekend parsing not implemented
        parser = TimeWindowParser()

        window = parser.parse("SAT-SUN 00:00-06:00 Asia/Tokyo")

        assert window.days == ['SAT', 'SUN']
        assert window.start_time == "00:00"
        assert window.end_time == "06:00"

    def test_time_window_validation_business_hours(self):
        """Should validate current time against business hours window"""
        # RED: Time validation logic not implemented
        parser = TimeWindowParser()
        window = parser.parse("MON-FRI 09:00-17:00 Asia/Tokyo")

        # Tuesday 2:00 PM Tokyo time - should be allowed
        allowed_time = datetime(2025, 8, 26, 14, 0, 0)  # Tuesday
        assert window.is_allowed(allowed_time) is True

        # Saturday 2:00 PM Tokyo time - should be blocked
        blocked_time = datetime(2025, 8, 30, 14, 0, 0)  # Saturday
        assert window.is_allowed(blocked_time) is False

    def test_time_window_validation_overnight(self):
        """Should handle overnight time windows correctly"""
        # RED: Overnight window logic not implemented
        parser = TimeWindowParser()
        window = parser.parse("SUN 23:00-06:00 Asia/Tokyo")  # Overnight window

        # Sunday 11:30 PM - should be allowed (start of window)
        late_sunday = datetime(2025, 8, 31, 23, 30, 0)  # Sunday
        assert window.is_allowed(late_sunday) is True

        # Monday 3:00 AM - should be allowed (end of window)
        early_monday = datetime(2025, 9, 1, 3, 0, 0)  # Monday
        assert window.is_allowed(early_monday) is True

        # Monday 10:00 AM - should be blocked (outside window)
        monday_morning = datetime(2025, 9, 1, 10, 0, 0)  # Monday
        assert window.is_allowed(monday_morning) is False


class TestPolicyDecision:
    """Test policy decision data structure"""

    def test_policy_decision_allowed(self):
        """Should create policy decision for allowed execution"""
        # RED: PolicyDecision class doesn't exist
        decision = PolicyDecision(
            allowed=True,
            autopilot_enabled=True,
            violations=[],
            warnings=["Low confidence template"]
        )

        assert decision.allowed is True
        assert decision.autopilot_enabled is True
        assert len(decision.violations) == 0
        assert len(decision.warnings) == 1

    def test_policy_decision_blocked(self):
        """Should create policy decision for blocked execution"""
        # RED: PolicyViolation class doesn't exist
        violation = PolicyViolation(
            type="domain_violation",
            message="Domain 'malicious.com' not in allow_domains",
            suggested_action="Add domain to policy or use approved domain"
        )

        decision = PolicyDecision(
            allowed=False,
            autopilot_enabled=False,
            violations=[violation],
            warnings=[]
        )

        assert decision.allowed is False
        assert decision.autopilot_enabled is False
        assert len(decision.violations) == 1
        assert decision.violations[0].type == "domain_violation"


class TestPolicyMetrics:
    """Test policy enforcement metrics collection"""

    def test_policy_blocks_24h_increment(self):
        """Should increment policy_blocks_24h when execution blocked"""
        # RED: Metrics integration not implemented
        from app.metrics import get_metrics_collector

        config = {
            'autopilot': True,
            'allow_domains': ['trusted.example.com']
        }

        engine = PolicyEngine.from_dict(config)
        metrics = get_metrics_collector()

        # Block due to domain violation
        template_manifest = {
            'webx_urls': ['https://malicious.com/form']
        }

        initial_blocks = metrics.get_counter('policy_blocks_24h')

        with pytest.raises(PolicyViolation):
            engine.validate_execution(template_manifest)

        # Metrics should increment
        final_blocks = metrics.get_counter('policy_blocks_24h')
        assert final_blocks == initial_blocks + 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
