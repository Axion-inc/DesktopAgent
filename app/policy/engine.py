"""
Policy Engine v1 - Phase 7
Execution-time policy enforcement with domain/time/risk/signature/capability validation
"""

import yaml
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

from .time_window import TimeWindowParser, TimeWindow


logger = logging.getLogger(__name__)


@dataclass
class PolicyViolation(Exception):
    """Represents a policy violation with details and suggested actions"""
    type: str
    message: str
    suggested_action: str
    
    def __str__(self):
        return f"{self.type}: {self.message}"


@dataclass  
class PolicyDecision:
    """Result of policy validation with enforcement decision"""
    allowed: bool
    autopilot_enabled: bool
    violations: List[PolicyViolation]
    warnings: List[str]


class PolicyEngine:
    """
    Policy Engine v1 for Phase 7
    Enforces execution policies with safe-fail blocking
    """
    
    def __init__(self, config_path: str):
        """Initialize policy engine with configuration file"""
        self.config_path = Path(config_path)
        self.config = self._load_config()
        self.time_parser = TimeWindowParser()
        self.time_window = self._parse_time_window()
        
        logger.info(f"Policy Engine initialized from {config_path}")
        logger.info(f"Autopilot: {self.config.get('autopilot', False)}")
        logger.info(f"Allow domains: {self.config.get('allow_domains', [])}")
    
    @classmethod
    def from_dict(cls, config: Dict[str, Any]) -> 'PolicyEngine':
        """Create policy engine from configuration dictionary (for testing)"""
        instance = cls.__new__(cls)
        instance.config = config
        instance.time_parser = TimeWindowParser()
        instance.time_window = instance._parse_time_window()
        return instance
    
    def _load_config(self) -> Dict[str, Any]:
        """Load policy configuration from YAML file"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            # Validate required fields
            if not isinstance(config, dict):
                raise ValueError("Policy config must be a dictionary")
            
            return config
            
        except FileNotFoundError:
            logger.error(f"Policy config not found: {self.config_path}")
            # Return safe default (restrictive policy)
            return {
                'autopilot': False,
                'allow_domains': [],
                'allow_risks': [],
                'window': 'never',
                'require_signed_templates': True,
                'require_capabilities': []
            }
        except Exception as e:
            logger.error(f"Failed to load policy config: {e}")
            raise
    
    def _parse_time_window(self) -> Optional[TimeWindow]:
        """Parse time window from configuration"""
        window_str = self.config.get('window')
        if not window_str or window_str == 'never':
            return None
        
        try:
            return self.time_parser.parse(window_str)
        except Exception as e:
            logger.error(f"Failed to parse time window '{window_str}': {e}")
            return None
    
    def validate_execution(
        self, 
        template_manifest: Dict[str, Any],
        current_time: Optional[datetime] = None
    ) -> PolicyDecision:
        """
        Validate template execution against policy
        Raises PolicyViolation for blocking violations
        Returns PolicyDecision for allowed executions with warnings
        """
        violations = []
        warnings = []
        
        # 1. Domain validation
        domain_violations = self._validate_domains(template_manifest)
        violations.extend(domain_violations)
        
        # 2. Time window validation  
        if current_time is None:
            current_time = datetime.now(timezone.utc)
        
        time_violations = self._validate_time_window(current_time)
        violations.extend(time_violations)
        
        # 3. Risk validation
        risk_violations = self._validate_risks(template_manifest)
        violations.extend(risk_violations)
        
        # 4. Signature validation
        signature_violations = self._validate_signature(template_manifest)
        violations.extend(signature_violations)
        
        # 5. Capability validation
        capability_violations = self._validate_capabilities(template_manifest)
        violations.extend(capability_violations)
        
        # If any blocking violations, raise exception (safe-fail)
        if violations:
            # Log policy block for metrics
            self._record_policy_block(violations)
            
            # Raise first violation as exception
            raise PolicyViolation(
                type=violations[0].type,
                message=violations[0].message,
                suggested_action=violations[0].suggested_action
            )
        
        # All checks passed - create decision
        autopilot_enabled = self.config.get('autopilot', False) and len(violations) == 0
        
        decision = PolicyDecision(
            allowed=True,
            autopilot_enabled=autopilot_enabled,
            violations=[],
            warnings=warnings
        )
        
        logger.info(f"Policy validation passed. Autopilot: {autopilot_enabled}")
        return decision
    
    def _validate_domains(self, template_manifest: Dict[str, Any]) -> List[PolicyViolation]:
        """Validate template URLs against allowed domains"""
        violations = []
        allow_domains = self.config.get('allow_domains', [])
        
        if not allow_domains:
            # No domain restrictions
            return violations
        
        webx_urls = template_manifest.get('webx_urls', [])
        
        for url in webx_urls:
            # Extract domain from URL
            from urllib.parse import urlparse
            parsed = urlparse(url)
            domain = parsed.netloc
            
            # Check if domain is allowed
            domain_allowed = False
            for allowed in allow_domains:
                if domain == allowed or domain.endswith(f'.{allowed}'):
                    domain_allowed = True
                    break
            
            if not domain_allowed:
                violations.append(PolicyViolation(
                    type="domain_violation",
                    message=f"Domain '{domain}' not in allow_domains: {allow_domains}",
                    suggested_action=f"Add '{domain}' to policy allow_domains or use approved domain"
                ))
        
        return violations
    
    def _validate_time_window(self, current_time: datetime) -> List[PolicyViolation]:
        """Validate current time against allowed time window"""
        violations = []
        
        if self.time_window is None:
            # No time restrictions or 'never' policy
            if self.config.get('window') == 'never':
                violations.append(PolicyViolation(
                    type="time_window_violation", 
                    message="Policy window set to 'never' - execution blocked",
                    suggested_action="Update policy window to allow execution times"
                ))
            return violations
        
        if not self.time_window.is_allowed(current_time):
            violations.append(PolicyViolation(
                type="time_window_violation",
                message=f"Current time {current_time} outside allowed window: {self.config['window']}",
                suggested_action="Execute during allowed time window or update policy"
            ))
        
        return violations
    
    def _validate_risks(self, template_manifest: Dict[str, Any]) -> List[PolicyViolation]:
        """Validate template risk flags against allowed risks"""
        violations = []
        allow_risks = self.config.get('allow_risks', [])
        risk_flags = template_manifest.get('risk_flags', [])
        
        for risk in risk_flags:
            if risk not in allow_risks:
                violations.append(PolicyViolation(
                    type="risk_violation",
                    message=f"Risk '{risk}' not in allow_risks: {allow_risks}",
                    suggested_action=f"Add '{risk}' to policy allow_risks or modify template to remove risk"
                ))
        
        return violations
    
    def _validate_signature(self, template_manifest: Dict[str, Any]) -> List[PolicyViolation]:
        """Validate template signature verification"""
        violations = []
        
        require_signed = self.config.get('require_signed_templates', True)
        signature_verified = template_manifest.get('signature_verified', False)
        
        if require_signed and not signature_verified:
            violations.append(PolicyViolation(
                type="signature_violation",
                message="Template signature required but not verified",
                suggested_action="Sign template with Ed25519 key or disable signature requirement"
            ))
        
        return violations
    
    def _validate_capabilities(self, template_manifest: Dict[str, Any]) -> List[PolicyViolation]:
        """Validate template capabilities against policy requirements"""
        violations = []
        
        required_capabilities = self.config.get('require_capabilities', [])
        template_capabilities = template_manifest.get('required_capabilities', [])
        
        for required in required_capabilities:
            if required not in template_capabilities:
                violations.append(PolicyViolation(
                    type="capability_mismatch",
                    message=f"Required capability '{required}' missing from template capabilities: {template_capabilities}",
                    suggested_action=f"Add '{required}' capability to template or remove from policy requirements"
                ))
        
        return violations
    
    def _record_policy_block(self, violations: List[PolicyViolation]):
        """Record policy block in metrics for monitoring"""
        try:
            # Import metrics collector and increment counter
            from app.metrics import get_metrics_collector
            
            metrics = get_metrics_collector()
            if metrics:
                metrics.increment_counter('policy_blocks_24h')
                
                # Record violation types for analysis
                for violation in violations:
                    metrics.increment_counter(f'policy_block_{violation.type}_24h')
                    
            logger.warning(f"Policy block recorded: {[v.type for v in violations]}")
            
        except Exception as e:
            logger.error(f"Failed to record policy block metrics: {e}")


def get_policy_engine(config_path: str = "configs/policy.yaml") -> PolicyEngine:
    """Get policy engine instance (singleton pattern)"""
    if not hasattr(get_policy_engine, '_instance'):
        get_policy_engine._instance = PolicyEngine(config_path)
    return get_policy_engine._instance