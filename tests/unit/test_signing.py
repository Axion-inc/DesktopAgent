"""
Unit tests for Ed25519 template signing and verification system
Red tests first (TDD) - should fail initially
"""

import pytest
import tempfile
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

from app.security.policy_engine import get_policy_engine, VerificationResult
from app.security.template_signing import TemplateSigningManager, SignatureVerificationError


class TestTemplateSigning:
    """Test Ed25519 signing and verification"""

    def test_generate_ed25519_keypair(self):
        """Should generate valid Ed25519 key pair"""
        # RED: This will fail - TemplateSigningManager doesn't exist yet
        signing_manager = TemplateSigningManager()

        with tempfile.TemporaryDirectory() as temp_dir:
            private_key_path = Path(temp_dir) / "test_private.pem"
            public_key_path = Path(temp_dir) / "test_public.pem"

            signing_manager.generate_keypair(
                key_id="da:2025:test",
                private_key_path=private_key_path,
                public_key_path=public_key_path
            )

            assert private_key_path.exists()
            assert public_key_path.exists()
            assert "BEGIN PRIVATE KEY" in private_key_path.read_text()
            assert "BEGIN PUBLIC KEY" in public_key_path.read_text()

    def test_sign_template_creates_signature_file(self):
        """Should create .sig.json file when signing template"""
        # RED: Will fail - signing functionality not implemented
        signing_manager = TemplateSigningManager()

        with tempfile.TemporaryDirectory() as temp_dir:
            template_path = Path(temp_dir) / "test_template.yaml"
            template_path.write_text("""
dsl_version: "1.1"
name: "Test Template"
steps:
  - log:
      message: "Hello World"
""")

            private_key_path = Path(temp_dir) / "private.pem"
            # Mock key generation for test
            with patch.object(signing_manager, 'generate_keypair'):
                signing_manager.generate_keypair("da:2025:test", private_key_path, None)

            signature_path = signing_manager.sign_template(
                template_path=template_path,
                private_key_path=private_key_path,
                key_id="da:2025:test"
            )

            assert signature_path.exists()
            assert signature_path.name == "test_template.sig.json"

            # Verify signature file structure
            signature_data = json.loads(signature_path.read_text())
            assert signature_data["algo"] == "ed25519"
            assert signature_data["key_id"] == "da:2025:test"
            assert "sha256" in signature_data
            assert "signature" in signature_data
            assert "created_at" in signature_data

    def test_verify_valid_signature(self):
        """Should successfully verify valid template signature"""
        # RED: Will fail - verification not implemented
        signing_manager = TemplateSigningManager()

        with tempfile.TemporaryDirectory() as temp_dir:
            template_path = Path(temp_dir) / "test.yaml"
            template_path.write_text("dsl_version: '1.1'\nname: Test\nsteps: []")

            # Mock successful verification
            result = signing_manager.verify_template_signature(template_path)

            assert result.is_valid is True
            assert result.key_id == "da:2025:test"
            assert result.trust_level == "development"

    def test_verify_tampered_template_fails(self):
        """Should fail verification if template content was modified"""
        # RED: Will fail - verification logic not implemented
        signing_manager = TemplateSigningManager()

        with tempfile.TemporaryDirectory() as temp_dir:
            template_path = Path(temp_dir) / "test.yaml"
            signature_path = Path(temp_dir) / "test.sig.json"

            # Create template and signature
            template_path.write_text("original content")
            signature_path.write_text(json.dumps({
                "algo": "ed25519",
                "key_id": "da:2025:test",
                "sha256": "original_hash",
                "signature": "valid_signature"
            }))

            # Modify template content
            template_path.write_text("tampered content")

            with pytest.raises(SignatureVerificationError):
                signing_manager.verify_template_signature(template_path)

    def test_unsigned_template_blocked_by_policy(self):
        """Should block unsigned templates when policy requires signatures"""
        # RED: Will fail - policy enforcement not implemented
        policy_engine = get_policy_engine()

        # Set policy to require signatures
        policy_engine.update_policy({
            "require_signed_templates": True,
            "allow_unsigned": False
        })

        with tempfile.TemporaryDirectory() as temp_dir:
            template_path = Path(temp_dir) / "unsigned.yaml"
            template_path.write_text("dsl_version: '1.1'\nname: Test")

            result = policy_engine.check_template_execution_policy(template_path)

            assert result.allowed is False
            assert "signature required" in result.reason.lower()

    def test_migration_grace_period(self):
        """Should allow unsigned templates during grace period"""
        # RED: Will fail - grace period logic not implemented
        policy_engine = get_policy_engine()

        # Set policy with future grace period end
        policy_engine.update_policy({
            "require_signed_templates": True,
            "allow_unsigned_until": "2025-12-31"
        })

        with tempfile.TemporaryDirectory() as temp_dir:
            template_path = Path(temp_dir) / "unsigned.yaml"
            template_path.write_text("dsl_version: '1.1'\nname: Test")

            result = policy_engine.check_template_execution_policy(template_path)

            assert result.allowed is True
            assert "grace period" in result.reason.lower()


class TestTrustStore:
    """Test trust store management"""

    def test_load_trust_store_from_yaml(self):
        """Should load trusted keys from YAML configuration"""
        # RED: Will fail - trust store loading not implemented
        from app.security.trust_store import TrustStoreManager

        with tempfile.TemporaryDirectory() as temp_dir:
            trust_store_path = Path(temp_dir) / "trust_store.yaml"
            trust_store_path.write_text("""
keys:
  - key_id: "da:2025:alice"
    pubkey: "MCowBQYDK2VwAyEAGg9i69JSL5XLkoXaSmSMbxB7"
    trust_level: "system"
  - key_id: "da:2025:bob"
    pubkey: "MCowBQYDK2VwAyEAHh8j78KTM6YMmlpYbTnPncC8"
    trust_level: "development"
""")

            trust_manager = TrustStoreManager(trust_store_path)

            assert trust_manager.is_trusted_key("da:2025:alice")
            assert trust_manager.get_trust_level("da:2025:alice") == "system"
            assert trust_manager.get_trust_level("da:2025:bob") == "development"
            assert not trust_manager.is_trusted_key("da:2025:unknown")

    def test_trust_level_hierarchy(self):
        """Should enforce trust level hierarchy for execution decisions"""
        # RED: Will fail - trust hierarchy not implemented
        from app.security.trust_store import TrustStoreManager

        trust_manager = TrustStoreManager()

        # System level should auto-execute
        assert trust_manager.get_execution_policy("system") == "auto"

        # Development level should require confirmation
        assert trust_manager.get_execution_policy("development") == "confirm"

        # Unknown should be blocked
        assert trust_manager.get_execution_policy("unknown") == "block"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
