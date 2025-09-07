"""
Template Manifest System
Manages required_capabilities and risk_flags declarations for templates
"""

import json
import yaml
import hashlib
import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

from ..utils.logging import get_logger

logger = get_logger(__name__)


class ManifestValidationError(Exception):
    """Raised when manifest validation fails"""
    pass


@dataclass
class ValidationResult:
    is_valid: bool
    error_message: Optional[str] = None
    warnings: List[str] = None

    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []


class CapabilityAnalyzer:
    """Analyzes template content to detect capabilities and risk flags"""

    CAPABILITY_MAPPING = {
        # WebX capabilities
        'open_browser': 'webx',
        'click_by_text': 'webx',
        'click_by_position': 'webx',
        'fill_by_label': 'webx',
        'fill_by_selector': 'webx',
        'scroll': 'webx',
        'wait_for_element': 'webx',
        'take_screenshot': 'webx',

        # File system capabilities
        'attach_file': 'fs',
        'save_file': 'fs',
        'read_file': 'fs',
        'copy_file': 'fs',
        'move_file': 'fs',
        'delete_file': 'fs',

        # PDF capabilities
        'read_pdf': 'pdf',
        'extract_pdf_text': 'pdf',
        'merge_pdf': 'pdf',
        'split_pdf': 'pdf',

        # Mail capabilities
        'compose_mail': 'mail_draft',
        'send_mail': 'mail_draft',
        'read_mail': 'mail_draft',

        # System capabilities
        'run_command': 'system',
        'get_env': 'system'
    }

    RISK_FLAG_PATTERNS = {
        'sends': [
            r'compose_mail',  # Any compose_mail is potentially sending
            r'send_mail',
            r'http_post.*data',  # HTTP POST with data
            r'upload_file'
        ],
        'deletes': [
            r'delete_file',
            r'remove_file',
            r'rm\s+',
            r'unlink'
        ],
        'overwrites': [
            r'overwrite_file',
            r'write_file.*mode.*w',  # Write mode overwrites
            r'save_file.*overwrite.*true'
        ]
    }

    def detect_capabilities(self, template_content: str) -> List[str]:
        """Detect required capabilities from template actions"""
        capabilities = set()

        try:
            # Parse YAML to extract actions
            template_data = yaml.safe_load(template_content)
            steps = template_data.get('steps', [])

            for step in steps:
                if isinstance(step, dict):
                    for action in step.keys():
                        if action in self.CAPABILITY_MAPPING:
                            capabilities.add(self.CAPABILITY_MAPPING[action])

            return list(capabilities)

        except Exception as e:
            logger.warning(f"Failed to parse template for capability detection: {e}")

            # Fallback to text-based detection
            return self._detect_capabilities_from_text(template_content)

    def _detect_capabilities_from_text(self, content: str) -> List[str]:
        """Fallback text-based capability detection"""
        capabilities = set()
        content_lower = content.lower()

        for action, capability in self.CAPABILITY_MAPPING.items():
            if action in content_lower:
                capabilities.add(capability)

        return list(capabilities)

    def detect_risk_flags(self, template_content: str) -> List[str]:
        """Detect risk flags from template actions"""
        risk_flags = set()
        content_lower = template_content.lower()

        for risk_type, patterns in self.RISK_FLAG_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, content_lower):
                    risk_flags.add(risk_type)
                    break  # Found one pattern for this risk type

        return list(risk_flags)

    def extract_webx_urls(self, template_content: str) -> List[str]:
        """Extract URLs from WebX actions for permission validation"""
        urls = []

        try:
            template_data = yaml.safe_load(template_content)
            steps = template_data.get('steps', [])

            for step in steps:
                if isinstance(step, dict):
                    # Check open_browser actions
                    if 'open_browser' in step and isinstance(step['open_browser'], dict):
                        url = step['open_browser'].get('url')
                        if url:
                            urls.append(url)

            return urls

        except Exception as e:
            logger.warning(f"Failed to extract URLs from template: {e}")
            return []


class ManifestManager:
    """Manages template manifest creation, validation, and operations"""

    MANIFEST_SCHEMA = {
        "required_fields": ["id", "name", "version", "dsl_version", "required_capabilities", "risk_flags"],
        "optional_fields": ["author", "description", "created_at", "webx_urls", "signature_verified"]
    }

    def __init__(self):
        self.capability_analyzer = CapabilityAnalyzer()

    def generate_manifest(self, template_path: Path) -> Path:
        """Generate manifest.json file from template YAML"""
        try:
            template_content = template_path.read_text(encoding='utf-8')
            template_data = yaml.safe_load(template_content)

            # Extract basic template info
            name = template_data.get('name', template_path.stem)
            version = template_data.get('version', '1.0.0')
            dsl_version = template_data.get('dsl_version', '1.1')
            description = template_data.get('description', '')

            # Analyze capabilities and risks
            capabilities = self.capability_analyzer.detect_capabilities(template_content)
            risk_flags = self.capability_analyzer.detect_risk_flags(template_content)
            webx_urls = self.capability_analyzer.extract_webx_urls(template_content)

            # Generate manifest
            manifest = {
                "id": f"{template_path.stem}@v{version}",
                "name": name,
                "version": version,
                "dsl_version": dsl_version,
                "description": description,
                "required_capabilities": capabilities,
                "risk_flags": risk_flags,
                "webx_urls": webx_urls,
                "created_at": datetime.now().isoformat(),
                "template_hash": self._calculate_template_hash(template_content)
            }

            # Write manifest file
            manifest_path = template_path.parent / f"{template_path.stem}.manifest.json"
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding='utf-8')

            logger.info(f"Generated manifest: {manifest_path}")
            return manifest_path

        except Exception as e:
            logger.error(f"Failed to generate manifest for {template_path}: {e}")
            raise ManifestValidationError(f"Manifest generation failed: {e}")

    def generate_manifest_from_template(self, template_path: Path) -> Tuple[bool, str, str]:
        """Compatibility helper used by CLI: generate manifest and return (ok, msg, path)."""
        try:
            path = self.generate_manifest(template_path)
            return True, "Generated manifest", str(path)
        except Exception as e:
            return False, str(e), ""

    def validate_manifest(self, manifest_data: Dict[str, Any]) -> ValidationResult:
        """Validate manifest against schema"""
        errors = []
        warnings = []

        # Check required fields
        for field in self.MANIFEST_SCHEMA["required_fields"]:
            if field not in manifest_data:
                errors.append(f"Missing required field: {field}")

        # Validate field types and values
        if "required_capabilities" in manifest_data:
            if not isinstance(manifest_data["required_capabilities"], list):
                errors.append("required_capabilities must be a list")

        if "risk_flags" in manifest_data:
            if not isinstance(manifest_data["risk_flags"], list):
                errors.append("risk_flags must be a list")

            # Validate known risk flags
            known_risks = ["sends", "deletes", "overwrites"]
            for risk in manifest_data["risk_flags"]:
                if risk not in known_risks:
                    warnings.append(f"Unknown risk flag: {risk}")

        # Validate version format
        if "version" in manifest_data:
            version = manifest_data["version"]
            if not re.match(r'^\d+\.\d+\.\d+$', version):
                errors.append("version must follow semantic versioning (x.y.z)")

        is_valid = len(errors) == 0
        error_message = "; ".join(errors) if errors else None

        return ValidationResult(
            is_valid=is_valid,
            error_message=error_message,
            warnings=warnings,
        )

    def check_capability_compliance(
        self,
        manifest: Dict[str, Any],
        template_content: str,
    ) -> Tuple[bool, List[str], List[str]]:
        """Check that declared capabilities/risk_flags match the template content.

        Returns:
            (compliant, violations, warnings)
        """
        violations: List[str] = []
        warnings: List[str] = []

        try:
            actual_caps = set(self.capability_analyzer.detect_capabilities(template_content))
        except Exception:
            actual_caps = set()
        declared_caps = set(manifest.get("required_capabilities", []))

        missing_caps = actual_caps - declared_caps
        extra_caps = declared_caps - actual_caps
        for c in sorted(missing_caps):
            violations.append(f"{c} capability required but not declared in manifest")
        for c in sorted(extra_caps):
            warnings.append(f"{c} capability declared but not used in template")

        try:
            actual_risks = set(self.capability_analyzer.detect_risk_flags(template_content))
        except Exception:
            actual_risks = set()
        declared_risks = set(manifest.get("risk_flags", []))

        missing_risks = actual_risks - declared_risks
        for r in sorted(missing_risks):
            violations.append(f"Risk flag '{r}' detected but not declared in manifest")

        compliant = len(violations) == 0
        return compliant, violations, warnings

    def validate_template_manifest_match(
        self, template_content: str, manifest_data: Dict[str, Any]
    ) -> ValidationResult:
        """Validate that template actions match declared manifest capabilities"""
        errors = []
        warnings = []

        # Detect actual capabilities from template
        actual_capabilities = set(self.capability_analyzer.detect_capabilities(template_content))
        declared_capabilities = set(manifest_data.get("required_capabilities", []))

        # Check for missing capability declarations
        missing_capabilities = actual_capabilities - declared_capabilities
        if missing_capabilities:
            for capability in missing_capabilities:
                errors.append(f"{capability} capability required but not declared in manifest")

        # Check for over-declared capabilities
        extra_capabilities = declared_capabilities - actual_capabilities
        if extra_capabilities:
            for capability in extra_capabilities:
                warnings.append(f"{capability} capability declared but not used in template")

        # Validate risk flags match
        actual_risks = set(self.capability_analyzer.detect_risk_flags(template_content))
        declared_risks = set(manifest_data.get("risk_flags", []))

        missing_risks = actual_risks - declared_risks
        if missing_risks:
            for risk in missing_risks:
                errors.append(f"Risk flag '{risk}' detected but not declared in manifest")

        is_valid = len(errors) == 0
        error_message = "; ".join(errors) if errors else None

        if not is_valid:
            raise ManifestValidationError(error_message)

        return ValidationResult(is_valid=is_valid, error_message=error_message, warnings=warnings)

    def load_manifest(self, manifest_path: Path) -> Dict[str, Any]:
        """Load and validate manifest from file"""
        try:
            manifest_data = json.loads(manifest_path.read_text(encoding='utf-8'))

            validation_result = self.validate_manifest(manifest_data)
            if not validation_result.is_valid:
                raise ManifestValidationError(validation_result.error_message)

            return manifest_data

        except json.JSONDecodeError as e:
            raise ManifestValidationError(f"Invalid JSON in manifest file: {e}")
        except Exception as e:
            raise ManifestValidationError(f"Failed to load manifest: {e}")

    def _calculate_template_hash(self, template_content: str) -> str:
        """Calculate SHA256 hash of template content"""
        return hashlib.sha256(template_content.encode('utf-8')).hexdigest()


# Singleton accessor for ManifestManager (used by CLI)
_manifest_manager_instance: Optional[ManifestManager] = None


def get_manifest_manager() -> ManifestManager:
    """Return a process-wide singleton ManifestManager instance"""
    global _manifest_manager_instance
    if _manifest_manager_instance is None:
        _manifest_manager_instance = ManifestManager()
    return _manifest_manager_instance


# CLI commands for manifest management
def generate_manifest_cli(template_path: str) -> None:
    """CLI command to generate manifest for a template"""
    manager = ManifestManager()
    path = Path(template_path)

    if not path.exists():
        print(f"Error: Template file not found: {template_path}")
        return

    try:
        manifest_path = manager.generate_manifest(path)
        print(f"Generated manifest: {manifest_path}")
    except ManifestValidationError as e:
        print(f"Error: {e}")


def validate_manifest_cli(manifest_path: str) -> None:
    """CLI command to validate a manifest file"""
    manager = ManifestManager()
    path = Path(manifest_path)

    if not path.exists():
        print(f"Error: Manifest file not found: {manifest_path}")
        return

    try:
        manifest_data = manager.load_manifest(path)
        result = manager.validate_manifest(manifest_data)

        if result.is_valid:
            print("✅ Manifest is valid")
            if result.warnings:
                print("Warnings:")
                for warning in result.warnings:
                    print(f"  ⚠️ {warning}")
        else:
            print("❌ Manifest validation failed:")
            print(f"  {result.error_message}")

    except ManifestValidationError as e:
        print(f"Error: {e}")


def list_capabilities_cli() -> None:
    """CLI command to list known capabilities"""
    analyzer = CapabilityAnalyzer()

    print("Known Capabilities:")
    capabilities = set(analyzer.CAPABILITY_MAPPING.values())
    for capability in sorted(capabilities):
        actions = [action for action, cap in analyzer.CAPABILITY_MAPPING.items() if cap == capability]
        print(f"  {capability}: {', '.join(actions)}")

    print("\\nRisk Flags:")
    for risk_flag, patterns in analyzer.RISK_FLAG_PATTERNS.items():
        print(f"  {risk_flag}: {len(patterns)} detection patterns")


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python -m app.security.template_manifest generate <template.yaml>")
        print("  python -m app.security.template_manifest validate <manifest.json>")
        print("  python -m app.security.template_manifest capabilities")
        sys.exit(1)

    command = sys.argv[1]

    if command == "generate" and len(sys.argv) == 3:
        generate_manifest_cli(sys.argv[2])
    elif command == "validate" and len(sys.argv) == 3:
        validate_manifest_cli(sys.argv[2])
    elif command == "capabilities":
        list_capabilities_cli()
    else:
        print("Invalid command or arguments")
        sys.exit(1)
