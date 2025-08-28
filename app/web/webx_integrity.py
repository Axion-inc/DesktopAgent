"""
WebX Integrity Checker
Validates WebX extension host permissions against template requirements
"""

import json
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from urllib.parse import urlparse

from ..utils.logging import get_logger
from ..security.template_manifest import CapabilityAnalyzer

logger = get_logger(__name__)


class PermissionMismatchError(Exception):
    """Raised when template URLs don't match extension permissions"""
    pass


@dataclass
class CompatibilityResult:
    is_compatible: bool
    violations: List[str] = None
    warnings: List[str] = None

    def __post_init__(self):
        if self.violations is None:
            self.violations = []
        if self.warnings is None:
            self.warnings = []

    @property
    def has_violations(self) -> bool:
        return len(self.violations) > 0

    @property
    def has_warnings(self) -> bool:
        return len(self.warnings) > 0


@dataclass
class ExecutionSafetyResult:
    execution_allowed: bool
    warnings: List[str] = None
    blocking_violations: List[str] = None

    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []
        if self.blocking_violations is None:
            self.blocking_violations = []

    @property
    def has_warnings(self) -> bool:
        return len(self.warnings) > 0


class WebXIntegrityChecker:
    """Validates WebX extension permissions against template requirements"""

    def __init__(self, extension_manifest_path: Optional[Path] = None):
        self.extension_manifest_path = extension_manifest_path
        self.host_permissions: List[str] = []
        self.capability_analyzer = CapabilityAnalyzer()

        if extension_manifest_path and extension_manifest_path.exists():
            self.load_extension_permissions(extension_manifest_path)

    def load_extension_permissions(self, manifest_path: Path) -> List[str]:
        """Load host permissions from WebX extension manifest"""
        try:
            manifest_data = json.loads(manifest_path.read_text(encoding='utf-8'))

            # Extract host_permissions (Manifest V3) or permissions (Manifest V2)
            permissions = manifest_data.get('host_permissions', [])
            if not permissions:
                permissions = [
                    perm for perm in manifest_data.get('permissions', [])
                    if isinstance(perm, str) and ('://' in perm or perm.startswith('*'))
                ]

            self.host_permissions = permissions
            logger.info(f"Loaded {len(permissions)} host permissions from extension manifest")

            return permissions

        except Exception as e:
            logger.error(f"Failed to load extension manifest: {e}")
            raise

    def validate_url(self, url: str) -> bool:
        """Validate if URL is allowed by extension host permissions"""
        if not self.host_permissions:
            logger.warning("No host permissions loaded - allowing all URLs")
            return True

        parsed_url = urlparse(url)
        url_to_check = f"{parsed_url.scheme}://{parsed_url.netloc}/*"

        for permission in self.host_permissions:
            if self._match_permission_pattern(url_to_check, permission):
                return True

        return False

    def _match_permission_pattern(self, url: str, permission: str) -> bool:
        """Check if URL matches a permission pattern"""
        # Handle wildcard patterns
        if permission == "*":
            return True

        if permission == "<all_urls>":
            return True

        # Convert permission pattern to regex
        if "*" in permission:
            # Replace wildcards with appropriate regex
            pattern = permission.replace("*", ".*")
            pattern = pattern.replace(".*://", r"https?://")  # Handle protocol wildcards

            try:
                return bool(re.match(pattern, url))
            except re.error:
                logger.warning(f"Invalid permission pattern: {permission}")
                return False

        # Exact match
        return url == permission or url.startswith(permission)

    def check_template_compatibility(self, template_content: str) -> CompatibilityResult:
        """Check if template WebX actions are compatible with extension permissions"""
        violations = []
        warnings = []

        # Extract URLs from template
        template_urls = self.capability_analyzer.extract_webx_urls(template_content)

        if not template_urls:
            # No WebX URLs to validate
            return CompatibilityResult(is_compatible=True)

        # Check each URL against permissions
        for url in template_urls:
            if not self.validate_url(url):
                parsed = urlparse(url)
                domain = f"{parsed.scheme}://{parsed.netloc}"
                violations.append(f"Unauthorized domain access: {domain}")

        is_compatible = len(violations) == 0

        if violations:
            logger.warning(f"Template compatibility violations found: {violations}")

        return CompatibilityResult(
            is_compatible=is_compatible,
            violations=violations,
            warnings=warnings
        )

    def validate_execution_safety(
        self,
        template_manifest: Dict[str, Any],
        template_urls: List[str],
        extension_permissions: List[str]
    ) -> ExecutionSafetyResult:
        """Validate execution safety based on risk flags and permission mismatches"""
        warnings = []
        blocking_violations = []

        # Update permissions for this check
        original_permissions = self.host_permissions
        self.host_permissions = extension_permissions

        try:
            # Check for permission mismatches
            permission_violations = []
            for url in template_urls:
                if not self.validate_url(url):
                    parsed = urlparse(url)
                    domain = f"{parsed.scheme}://{parsed.netloc}"
                    permission_violations.append(domain)

            # Check risk flags
            risk_flags = template_manifest.get("risk_flags", [])
            high_risk_flags = ["sends", "deletes", "overwrites"]

            has_high_risk = any(flag in risk_flags for flag in high_risk_flags)

            # Decision logic
            if permission_violations:
                if has_high_risk:
                    # High risk + permission mismatch = block execution
                    blocking_violations.extend([
                        f"Execution blocked: High-risk template accessing unauthorized domain {domain}"
                        for domain in permission_violations
                    ])
                else:
                    # Low risk + permission mismatch = warning only
                    warnings.extend([
                        f"Permission mismatch warning: Template accesses {domain} but extension lacks permission"
                        for domain in permission_violations
                    ])

            execution_allowed = len(blocking_violations) == 0

            if blocking_violations:
                logger.error(f"Template execution blocked due to security violations: {blocking_violations}")
                raise PermissionMismatchError("Execution blocked due to security violations")

            return ExecutionSafetyResult(
                execution_allowed=execution_allowed,
                warnings=warnings,
                blocking_violations=blocking_violations
            )

        finally:
            # Restore original permissions
            self.host_permissions = original_permissions


class WebXCompatibilityValidator:
    """Validates WebX compatibility for template manifests"""

    def __init__(self, integrity_checker: Optional[WebXIntegrityChecker] = None):
        self.integrity_checker = integrity_checker or WebXIntegrityChecker()

    def validate_manifest_webx_compatibility(
        self,
        template_manifest: Dict[str, Any],
        extension_permissions: List[str]
    ) -> CompatibilityResult:
        """Validate template manifest WebX compatibility"""
        violations = []
        warnings = []

        # Check if template requires webx capability
        required_capabilities = template_manifest.get("required_capabilities", [])
        if "webx" not in required_capabilities:
            # No WebX requirements
            return CompatibilityResult(is_compatible=True)

        # Check webx_urls against extension permissions
        webx_urls = template_manifest.get("webx_urls", [])

        if not webx_urls:
            warnings.append("Template requires webx capability but no URLs specified")
            return CompatibilityResult(is_compatible=True, warnings=warnings)

        # Update checker permissions
        original_permissions = self.integrity_checker.host_permissions
        self.integrity_checker.host_permissions = extension_permissions

        try:
            for url in webx_urls:
                if not self.integrity_checker.validate_url(url):
                    parsed = urlparse(url)
                    domain = f"{parsed.scheme}://{parsed.netloc}"
                    violations.append(f"Extension lacks permission for domain: {domain}")

            is_compatible = len(violations) == 0

            return CompatibilityResult(
                is_compatible=is_compatible,
                violations=violations,
                warnings=warnings
            )

        finally:
            # Restore original permissions
            self.integrity_checker.host_permissions = original_permissions


# Global instances
_webx_integrity_checker: Optional[WebXIntegrityChecker] = None
_webx_compatibility_validator: Optional[WebXCompatibilityValidator] = None


def get_webx_integrity_checker() -> WebXIntegrityChecker:
    """Get global WebX integrity checker instance"""
    global _webx_integrity_checker
    if _webx_integrity_checker is None:
        _webx_integrity_checker = WebXIntegrityChecker()
    return _webx_integrity_checker


def get_webx_compatibility_validator() -> WebXCompatibilityValidator:
    """Get global WebX compatibility validator instance"""
    global _webx_compatibility_validator
    if _webx_compatibility_validator is None:
        _webx_compatibility_validator = WebXCompatibilityValidator()
    return _webx_compatibility_validator
