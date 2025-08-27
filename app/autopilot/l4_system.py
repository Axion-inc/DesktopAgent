"""
L4 Autopilot System - Phase 7
Limited full automation with policy compliance and deviation detection
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

from app.policy.engine import PolicyEngine, PolicyViolation
from .deviation_detector import DeviationDetector, Deviation
from .execution_monitor import ExecutionMonitor, ExecutionState


logger = logging.getLogger(__name__)


@dataclass
class AutopilotDecision:
    """Result of autopilot validation with execution decision"""
    allowed: bool
    autopilot_enabled: bool
    deviation_monitoring: bool
    policy_violations: List[PolicyViolation]
    execution_id: str
    warnings: List[str] = None
    
    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []


class SafeFailException(Exception):
    """Exception raised when safe-fail threshold is exceeded"""
    def __init__(self, message: str, deviations: List[Deviation]):
        super().__init__(message)
        self.deviations = deviations


class L4AutopilotSystem:
    """L4 Autopilot: Limited full automation with policy compliance"""
    
    def __init__(self, policy_config: Dict[str, Any]):
        """Initialize L4 autopilot system"""
        self.policy_engine = PolicyEngine.from_dict(policy_config)
        self.autopilot_config = policy_config
        
        # Initialize deviation detection
        deviation_config = {
            'max_deviations': policy_config.get('deviation_threshold', 3),
            'step_timeout_threshold': policy_config.get('step_timeout', 30.0),
            'unexpected_step_penalty': policy_config.get('unexpected_penalty', 2),
            'failed_step_penalty': policy_config.get('failed_penalty', 1),
            'risk_escalation_penalty': policy_config.get('risk_penalty', 5)
        }
        self.deviation_detector = DeviationDetector(deviation_config)
        
        # Active execution monitors
        self.active_monitors: Dict[str, ExecutionMonitor] = {}
        
        logger.info("L4 Autopilot system initialized with policy enforcement")
    
    def is_enabled(self) -> bool:
        """Check if autopilot is enabled"""
        return self.autopilot_config.get('autopilot', False)
    
    def validate_execution(
        self, 
        template_manifest: Dict[str, Any],
        current_time: Optional[datetime] = None
    ) -> AutopilotDecision:
        """
        Validate template execution against policy and create autopilot decision
        """
        execution_id = str(uuid.uuid4())
        
        try:
            # Policy validation through Policy Engine
            policy_decision = self.policy_engine.validate_execution(
                template_manifest, 
                current_time
            )
            
            # If policy allows execution
            autopilot_enabled = (
                self.is_enabled() and 
                policy_decision.allowed and 
                policy_decision.autopilot_enabled
            )
            
            decision = AutopilotDecision(
                allowed=policy_decision.allowed,
                autopilot_enabled=autopilot_enabled,
                deviation_monitoring=autopilot_enabled,
                policy_violations=[],
                execution_id=execution_id,
                warnings=policy_decision.warnings
            )
            
            logger.info(
                f"Execution validation passed: autopilot={autopilot_enabled}, "
                f"execution_id={execution_id}"
            )
            
            return decision
            
        except PolicyViolation as violation:
            # Policy violation - block execution
            decision = AutopilotDecision(
                allowed=False,
                autopilot_enabled=False,
                deviation_monitoring=False,
                policy_violations=[violation],
                execution_id=execution_id
            )
            
            logger.warning(
                f"Execution blocked by policy violation: {violation.type} - {violation.message}"
            )
            
            return decision
        
        except Exception as e:
            logger.error(f"Autopilot validation error: {e}")
            
            # Safe-fail: deny execution on unexpected errors
            decision = AutopilotDecision(
                allowed=False,
                autopilot_enabled=False,
                deviation_monitoring=False,
                policy_violations=[],
                execution_id=execution_id,
                warnings=[f"System error during validation: {str(e)}"]
            )
            
            return decision
    
    def start_execution_monitoring(
        self, 
        execution_id: str, 
        expected_steps: List[Dict[str, Any]]
    ) -> ExecutionMonitor:
        """Start monitoring execution with deviation detection"""
        monitor = ExecutionMonitor(execution_id, expected_steps)
        self.active_monitors[execution_id] = monitor
        
        logger.info(f"Started execution monitoring for {execution_id}")
        return monitor
    
    def get_execution_monitor(self, execution_id: str) -> Optional[ExecutionMonitor]:
        """Get execution monitor by ID"""
        return self.active_monitors.get(execution_id)
    
    def check_execution_safety(self, execution_id: str) -> bool:
        """Check if execution is within safety parameters"""
        monitor = self.active_monitors.get(execution_id)
        if not monitor:
            logger.warning(f"No monitor found for execution {execution_id}")
            return False
        
        # Check for deviations using deviation detector
        deviations = monitor.check_deviations()
        
        # Update deviation detector with any new deviations
        for deviation in deviations:
            self.deviation_detector._record_deviation(deviation)
        
        # Check safety threshold
        threshold_exceeded = self.deviation_detector.assess_safety_threshold()
        
        if threshold_exceeded:
            # Trigger safe-fail
            self._trigger_safe_fail(execution_id, self.deviation_detector.detected_deviations)
            return False
        
        return True
    
    def _trigger_safe_fail(self, execution_id: str, deviations: List[Deviation]):
        """Trigger safe-fail response to execution deviations"""
        monitor = self.active_monitors.get(execution_id)
        if monitor:
            monitor.execution_state = ExecutionState.BLOCKED
            monitor.end_time = datetime.now(timezone.utc)
        
        # Record metrics
        try:
            from app.metrics import get_metrics_collector
            metrics = get_metrics_collector()
            metrics.increment_counter('autopilot_safe_fail_24h')
        except Exception as e:
            logger.error(f"Failed to record safe-fail metrics: {e}")
        
        logger.critical(
            f"Safe-fail triggered for execution {execution_id}: "
            f"{len(deviations)} deviations detected"
        )
        
        raise SafeFailException(
            f"Execution {execution_id} blocked due to safety threshold exceeded",
            deviations
        )
    
    def finalize_execution(self, execution_id: str, success: bool):
        """Finalize execution monitoring and record metrics"""
        monitor = self.active_monitors.get(execution_id)
        if not monitor:
            logger.warning(f"No monitor found for execution {execution_id}")
            return
        
        monitor.record_completion(success)
        
        # Record autopilot metrics
        self._record_autopilot_metrics(execution_id, monitor, success)
        
        # Clean up completed monitor
        if execution_id in self.active_monitors:
            del self.active_monitors[execution_id]
        
        logger.info(f"Execution {execution_id} finalized with success={success}")
    
    def _record_autopilot_metrics(
        self, 
        execution_id: str, 
        monitor: ExecutionMonitor, 
        success: bool
    ):
        """Record autopilot execution metrics"""
        try:
            from app.metrics import get_metrics_collector
            metrics = get_metrics_collector()
            
            # Core autopilot metrics
            metrics.increment_counter('autopilot_executions_24h')
            
            if success:
                metrics.increment_counter('autopilot_success_24h')
            else:
                metrics.increment_counter('autopilot_failures_24h')
            
            # Deviation metrics
            deviation_count = len(self.deviation_detector.detected_deviations)
            if deviation_count > 0:
                metrics.increment_counter('autopilot_deviations_24h', deviation_count)
            
            # Performance metrics
            summary = monitor.get_execution_summary()
            if summary.get('total_duration_ms'):
                # Could record duration distribution metrics here
                pass
            
        except Exception as e:
            logger.error(f"Failed to record autopilot metrics: {e}")
    
    def get_autopilot_status(self) -> Dict[str, Any]:
        """Get current autopilot system status"""
        active_executions = len(self.active_monitors)
        deviation_summary = self.deviation_detector.get_deviation_summary()
        
        return {
            'enabled': self.is_enabled(),
            'active_executions': active_executions,
            'execution_ids': list(self.active_monitors.keys()),
            'deviation_summary': deviation_summary,
            'policy_config': {
                'allow_domains': self.autopilot_config.get('allow_domains', []),
                'allow_risks': self.autopilot_config.get('allow_risks', []),
                'window': self.autopilot_config.get('window', 'always'),
                'require_signed_templates': self.autopilot_config.get('require_signed_templates', True)
            }
        }