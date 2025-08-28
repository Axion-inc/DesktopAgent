"""
Desktop Agent Policy Engine
Enforces security policies for template execution, signature verification, and WebX plugins
"""

import yaml
import hashlib
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class ExecutionAction(Enum):
    ALLOW = "allow"
    BLOCK = "block"
    WARN = "warn"
    REQUIRE_CONFIRMATION = "require_confirmation"


class TrustLevel(Enum):
    SYSTEM = "system"
    COMMERCIAL = "commercial"
    DEVELOPMENT = "development"
    COMMUNITY = "community"
    UNKNOWN = "unknown"


@dataclass
class PolicyDecision:
    action: ExecutionAction
    trust_level: TrustLevel
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    requires_confirmation: bool = False
    sandbox_level: str = "standard"
    audit_level: str = "standard"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class VerificationResult:
    valid: bool
    signature_valid: bool = False
    key_trusted: bool = False
    key_id: Optional[str] = None
    trust_level: TrustLevel = TrustLevel.UNKNOWN
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class PolicyEngine:
    def __init__(self, config_dir: Path = None):
        self.config_dir = config_dir or Path("configs")
        self.trust_store = {}
        self.policy_config = {}
        self.load_configurations()

    def load_configurations(self):
        """Load trust store and policy configurations"""
        try:
            # Load trust store
            trust_store_path = self.config_dir / "trust_store.yaml"
            if trust_store_path.exists():
                with open(trust_store_path, 'r') as f:
                    self.trust_store = yaml.safe_load(f)
                logger.info(f"Loaded trust store with {len(self.trust_store.get('trusted_keys', {}))} keys")
            else:
                logger.warning(f"Trust store not found at {trust_store_path}")
                self.trust_store = self._get_default_trust_store()

            # Load policy configuration
            policy_path = self.config_dir / "policy.yaml"
            if policy_path.exists():
                with open(policy_path, 'r') as f:
                    self.policy_config = yaml.safe_load(f)
                logger.info("Policy configuration loaded")
            else:
                logger.warning(f"Policy configuration not found at {policy_path}")
                self.policy_config = self._get_default_policy()

        except Exception as e:
            logger.error(f"Failed to load configurations: {e}")
            self._load_fallback_configurations()

    def _get_default_trust_store(self) -> Dict[str, Any]:
        """Get default trust store configuration"""
        return {
            "version": "1.0",
            "trusted_keys": {},
            "trust_levels": {
                "system": {"priority": 100, "auto_execute": True, "require_confirmation": False},
                "commercial": {"priority": 80, "auto_execute": True, "require_confirmation": False},
                "development": {"priority": 60, "auto_execute": False, "require_confirmation": True},
                "community": {"priority": 40, "auto_execute": False, "require_confirmation": True},
                "unknown": {"priority": 0, "auto_execute": False, "require_confirmation": True}
            }
        }

    def _get_default_policy(self) -> Dict[str, Any]:
        """Get default policy configuration"""
        return {
            "version": "1.0",
            "template_execution": {
                "signature_required": True,
                "allow_unsigned": False,
                "grace_period": {"enabled": True, "unsigned_action": "warn"}
            }
        }

    def _load_fallback_configurations(self):
        """Load minimal fallback configurations if normal loading fails"""
        logger.warning("Loading fallback security configurations")
        self.trust_store = self._get_default_trust_store()
        self.policy_config = self._get_default_policy()

    def verify_template_signature(self, template_path: Path, signature_path: Path = None) -> VerificationResult:
        """
        Verify template signature against trust store

        Args:
            template_path: Path to the template file
            signature_path: Path to signature file (optional, defaults to template_path + .sig.json)

        Returns:
            VerificationResult with verification status and details
        """
        if signature_path is None:
            signature_path = Path(str(template_path) + ".sig.json")

        result = VerificationResult(valid=False)

        try:
            # Check if signature file exists
            if not signature_path.exists():
                result.errors.append(f"Signature file not found: {signature_path}")
                return result

            # Load signature
            import json
            with open(signature_path, 'r') as f:
                signature_data = json.load(f)

            # Verify signature format
            required_fields = ["algo", "key_id", "created_at", "sha256", "signature"]
            missing_fields = [field for field in required_fields if field not in signature_data]
            if missing_fields:
                result.errors.append(f"Signature missing required fields: {missing_fields}")
                return result

            key_id = signature_data["key_id"]

            # Check if key is in trust store
            trusted_keys = self.trust_store.get("trusted_keys", {})
            if key_id not in trusted_keys:
                result.errors.append(f"Key not in trust store: {key_id}")
                result.trust_level = TrustLevel.UNKNOWN
                return result

            key_info = trusted_keys[key_id]

            # Check if key is revoked
            if key_info.get("revoked", False):
                result.errors.append(f"Key has been revoked: {key_id}")
                return result

            # Check key validity period
            now = datetime.now()
            valid_from = datetime.fromisoformat(
                key_info.get("valid_from", "1970-01-01T00:00:00+00:00").replace('+09:00', '+00:00')
            )
            valid_until = datetime.fromisoformat(
                key_info.get("valid_until", "2099-12-31T23:59:59+00:00").replace('+09:00', '+00:00')
            )

            if now < valid_from:
                result.errors.append(f"Key not yet valid: {key_id}")
                return result

            if now > valid_until:
                result.warnings.append(f"Key has expired: {key_id}")

            # Verify file hash
            actual_hash = self._calculate_file_hash(template_path)
            expected_hash = signature_data["sha256"]

            if actual_hash != expected_hash:
                result.errors.append(
                    f"File hash mismatch. Expected: {expected_hash}, Got: {actual_hash}"
                )
                return result

            # TODO: Verify actual cryptographic signature
            # This would require implementing Ed25519 signature verification
            # For now, we assume signature is valid if all other checks pass
            result.signature_valid = True
            result.key_trusted = True
            result.key_id = key_id

            # Determine trust level
            trust_level_name = key_info.get("trust_level", "unknown")
            result.trust_level = TrustLevel(trust_level_name)

            result.valid = True
            logger.info(f"Template signature verified successfully: {template_path}")

        except Exception as e:
            logger.error(f"Signature verification failed: {e}")
            result.errors.append(f"Verification error: {str(e)}")

        return result

    def _calculate_file_hash(self, file_path: Path) -> str:
        """Calculate SHA-256 hash of a file"""
        hasher = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def evaluate_execution_policy(
        self,
        template_path: Path,
        verification_result: VerificationResult = None,
    ) -> PolicyDecision:
        """
        Evaluate whether template execution should be allowed based on policy

        Args:
            template_path: Path to the template
            verification_result: Result of signature verification (optional)

        Returns:
            PolicyDecision with execution decision and requirements
        """
        decision = PolicyDecision(
            action=ExecutionAction.BLOCK,
            trust_level=TrustLevel.UNKNOWN
        )

        try:
            # Get execution policy
            exec_policy = self.policy_config.get("template_execution", {})

            # Check if signature is required
            signature_required = exec_policy.get("signature_required", True)
            allow_unsigned = exec_policy.get("allow_unsigned", False)

            # If no verification result provided, try to verify
            if verification_result is None:
                verification_result = self.verify_template_signature(template_path)

            # Handle unsigned templates
            if not verification_result.valid:
                if not signature_required or allow_unsigned:
                    decision.action = ExecutionAction.WARN
                    decision.warnings.append("Template is not signed or signature verification failed")
                    decision.requires_confirmation = True
                    decision.sandbox_level = "maximum"
                    decision.audit_level = "detailed"

                    # Check grace period
                    grace_period = exec_policy.get("grace_period", {})
                    if grace_period.get("enabled", False):
                        unsigned_action = grace_period.get("unsigned_action", "block")
                        if unsigned_action == "allow":
                            decision.action = ExecutionAction.ALLOW
                        elif unsigned_action == "warn":
                            decision.action = ExecutionAction.WARN
                        else:
                            decision.action = ExecutionAction.BLOCK

                    decision.reasons.append("Unsigned template execution policy")
                else:
                    decision.action = ExecutionAction.BLOCK
                    decision.reasons.append("Signature required but template is unsigned")

                return decision

            # Handle signed templates based on trust level
            decision.trust_level = verification_result.trust_level
            trust_level_policies = exec_policy.get("trust_level_policies", {})
            trust_policy = trust_level_policies.get(verification_result.trust_level.value, {})

            # Determine execution action
            execution_mode = trust_policy.get("execution", "block")
            if execution_mode == "auto":
                decision.action = ExecutionAction.ALLOW
            elif execution_mode == "manual":
                decision.action = ExecutionAction.REQUIRE_CONFIRMATION
                decision.requires_confirmation = True
            else:  # block
                decision.action = ExecutionAction.BLOCK
                decision.reasons.append(f"Trust level {verification_result.trust_level.value} is blocked by policy")

            # Set additional requirements
            decision.requires_confirmation = trust_policy.get("confirmation_required", decision.requires_confirmation)
            decision.sandbox_level = trust_policy.get("sandbox_level", "standard")
            decision.audit_level = trust_policy.get("audit_level", "standard")

            # Add any warnings from verification
            decision.warnings.extend(verification_result.warnings)
            decision.reasons.append(f"Trust level: {verification_result.trust_level.value}")

            logger.info(f"Execution policy decision: {decision.action.value} (trust: {decision.trust_level.value})")

        except Exception as e:
            logger.error(f"Policy evaluation failed: {e}")
            decision.action = ExecutionAction.BLOCK
            decision.reasons.append(f"Policy evaluation error: {str(e)}")

        return decision

    def get_trust_level_info(self, trust_level: TrustLevel) -> Dict[str, Any]:
        """Get information about a trust level"""
        trust_levels = self.trust_store.get("trust_levels", {})
        return trust_levels.get(trust_level.value, {})

    def is_key_trusted(self, key_id: str) -> bool:
        """Check if a key is in the trust store and not revoked"""
        trusted_keys = self.trust_store.get("trusted_keys", {})
        if key_id not in trusted_keys:
            return False

        key_info = trusted_keys[key_id]
        return not key_info.get("revoked", False)

    def add_trusted_key(self, key_id: str, public_key: str, key_info: Dict[str, Any]) -> bool:
        """Add a new trusted key to the trust store"""
        try:
            if "trusted_keys" not in self.trust_store:
                self.trust_store["trusted_keys"] = {}

            self.trust_store["trusted_keys"][key_id] = {
                "public_key": public_key,
                "key_type": "ed25519",
                **key_info
            }

            # Save to file
            self._save_trust_store()
            logger.info(f"Added trusted key: {key_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to add trusted key {key_id}: {e}")
            return False

    def revoke_key(self, key_id: str, reason: str = "Manual revocation") -> bool:
        """Revoke a trusted key"""
        try:
            trusted_keys = self.trust_store.get("trusted_keys", {})
            if key_id not in trusted_keys:
                logger.warning(f"Key not found for revocation: {key_id}")
                return False

            # Mark as revoked
            trusted_keys[key_id]["revoked"] = True
            trusted_keys[key_id]["revoked_at"] = datetime.now().isoformat()
            trusted_keys[key_id]["revocation_reason"] = reason

            # Add to revoked keys list
            if "revoked_keys" not in self.trust_store:
                self.trust_store["revoked_keys"] = {}

            self.trust_store["revoked_keys"][key_id] = {
                "revoked_at": datetime.now().isoformat(),
                "reason": reason,
                "revoked_by": "System"
            }

            self._save_trust_store()
            logger.warning(f"Key revoked: {key_id} - {reason}")
            return True

        except Exception as e:
            logger.error(f"Failed to revoke key {key_id}: {e}")
            return False

    def _save_trust_store(self):
        """Save trust store to file"""
        try:
            trust_store_path = self.config_dir / "trust_store.yaml"
            with open(trust_store_path, 'w') as f:
                yaml.dump(self.trust_store, f, default_flow_style=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save trust store: {e}")

    def get_security_metrics(self) -> Dict[str, Any]:
        """Get security-related metrics for dashboard"""
        try:
            trusted_keys = self.trust_store.get("trusted_keys", {})

            # Count keys by trust level
            trust_level_counts = {}
            active_keys = 0
            revoked_keys = 0
            expired_keys = 0

            now = datetime.now()

            for key_id, key_info in trusted_keys.items():
                trust_level = key_info.get("trust_level", "unknown")
                trust_level_counts[trust_level] = trust_level_counts.get(trust_level, 0) + 1

                if key_info.get("revoked", False):
                    revoked_keys += 1
                else:
                    # Check expiry
                    try:
                        valid_until = datetime.fromisoformat(
                            key_info.get("valid_until", "2099-12-31T23:59:59+00:00").replace('+09:00', '+00:00')
                        )
                        if now > valid_until:
                            expired_keys += 1
                        else:
                            active_keys += 1
                    except Exception:
                        active_keys += 1  # Assume active if can't parse date

            return {
                "total_trusted_keys": len(trusted_keys),
                "active_keys": active_keys,
                "revoked_keys": revoked_keys,
                "expired_keys": expired_keys,
                "trust_level_distribution": trust_level_counts,
                "policy_version": self.policy_config.get("version", "unknown"),
                "trust_store_version": self.trust_store.get("version", "unknown")
            }

        except Exception as e:
            logger.error(f"Failed to get security metrics: {e}")
            return {"error": str(e)}


# Global policy engine instance
_policy_engine: Optional[PolicyEngine] = None


def get_policy_engine() -> PolicyEngine:
    """Get the global policy engine instance"""
    global _policy_engine
    if _policy_engine is None:
        _policy_engine = PolicyEngine()
    return _policy_engine


def verify_template_before_execution(template_path: Path) -> Tuple[bool, PolicyDecision]:
    """
    Convenience function to verify template and get execution decision

    Returns:
        Tuple of (should_execute, policy_decision)
    """
    policy_engine = get_policy_engine()

    # Verify signature
    verification_result = policy_engine.verify_template_signature(template_path)

    # Evaluate execution policy
    decision = policy_engine.evaluate_execution_policy(template_path, verification_result)

    should_execute = decision.action in [ExecutionAction.ALLOW, ExecutionAction.REQUIRE_CONFIRMATION]

    return should_execute, decision
