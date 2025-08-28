"""
Deviation Detector - Phase 7
Algorithm for detecting execution deviations and triggering safe-fail responses
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from dataclasses import dataclass


logger = logging.getLogger(__name__)


@dataclass
class Deviation:
    """Represents a detected execution deviation"""
    type: str
    severity: str  # "low", "medium", "high", "critical"
    step_name: Optional[str] = None
    step_index: Optional[int] = None
    duration: Optional[float] = None
    escalated_risks: Optional[List[str]] = None
    details: Optional[str] = None
    detected_at: Optional[datetime] = None

    def __post_init__(self):
        if self.detected_at is None:
            self.detected_at = datetime.now(timezone.utc)


class DeviationDetector:
    """Detect execution deviations and assess safety thresholds"""

    def __init__(self, config: Dict[str, Any]):
        """Initialize deviation detector with configuration"""
        self.max_deviations = config.get('max_deviations', 3)
        self.step_timeout_threshold = config.get('step_timeout_threshold', 30.0)
        self.unexpected_step_penalty = config.get('unexpected_step_penalty', 2)
        self.failed_step_penalty = config.get('failed_step_penalty', 1)
        self.risk_escalation_penalty = config.get('risk_escalation_penalty', 5)

        self.deviation_count = 0
        self.detected_deviations: List[Deviation] = []

        logger.info(f"Deviation detector initialized with max_deviations={self.max_deviations}")

    def analyze_sequence_deviation(
        self,
        expected_sequence: List[str],
        actual_sequence: List[str]
    ) -> List[Deviation]:
        """Analyze sequence deviation with insertion-aware alignment.

        Reports an unexpected_step when an insertion occurs and avoids
        cascading sequence_deviation reports due to simple shifts.
        """
        deviations: List[Deviation] = []
        e_idx = 0
        a_idx = 0
        while a_idx < len(actual_sequence) and e_idx < len(expected_sequence):
            a_step = actual_sequence[a_idx]
            e_step = expected_sequence[e_idx]

            if a_step == e_step:
                a_idx += 1
                e_idx += 1
                continue

            # If actual step isn't part of expected at all, treat as insertion
            if a_step not in expected_sequence:
                deviation = Deviation(
                    type="unexpected_step",
                    severity="high",
                    step_name=a_step,
                    step_index=a_idx,
                    details=f"Step '{a_step}' not found in expected sequence"
                )
                deviations.append(deviation)
                self._record_deviation(deviation)
                a_idx += 1
                # Do not advance e_idx; re-align on next actual step
                continue

            # Otherwise, it's a reordering deviation
            deviation = Deviation(
                type="sequence_deviation",
                severity="medium",
                step_name=a_step,
                step_index=a_idx,
                details=f"Expected '{e_step}' but got '{a_step}'"
            )
            deviations.append(deviation)
            self._record_deviation(deviation)
            a_idx += 1
            e_idx += 1

        # Any trailing actual steps beyond expected are unexpected insertions
        while a_idx < len(actual_sequence):
            a_step = actual_sequence[a_idx]
            if a_step not in expected_sequence:
                deviation = Deviation(
                    type="unexpected_step",
                    severity="high",
                    step_name=a_step,
                    step_index=a_idx,
                    details=f"Step '{a_step}' not found in expected sequence"
                )
                deviations.append(deviation)
                self._record_deviation(deviation)
            a_idx += 1

        return deviations

    def check_step_timeout(self, step_name: str, execution_duration: float) -> Optional[Deviation]:
        """Check if step execution exceeded timeout threshold"""
        if execution_duration > self.step_timeout_threshold:
            deviation = Deviation(
                type="step_timeout",
                severity="medium",
                step_name=step_name,
                duration=execution_duration,
                details=f"Step '{step_name}' took {execution_duration:.1f}s (threshold: {self.step_timeout_threshold}s)"
            )
            self._record_deviation(deviation)
            return deviation

        return None

    def check_risk_escalation(
        self,
        expected_risks: List[str],
        actual_risks: List[str]
    ) -> Optional[Deviation]:
        """Check for risk level escalation during execution"""
        escalated_risks = [risk for risk in actual_risks if risk not in expected_risks]

        if escalated_risks:
            # Determine severity based on escalated risk types
            severity = "critical"
            for risk in escalated_risks:
                if risk in ["deletes", "overwrites", "system_modify"]:
                    severity = "critical"
                    break
                elif risk in ["sends", "uploads"]:
                    severity = "high"
                elif risk in ["reads", "downloads"]:
                    severity = "medium"

            deviation = Deviation(
                type="risk_escalation",
                severity=severity,
                escalated_risks=escalated_risks,
                details=f"Risk escalation detected: {escalated_risks}"
            )
            self._record_deviation(deviation)
            return deviation

        return None

    def check_domain_deviation(
        self,
        expected_domains: List[str],
        actual_domain: str
    ) -> Optional[Deviation]:
        """Check for unauthorized domain access"""
        if actual_domain not in expected_domains:
            deviation = Deviation(
                type="domain_deviation",
                severity="high",
                details=f"Unauthorized domain access: {actual_domain} not in {expected_domains}"
            )
            self._record_deviation(deviation)
            return deviation

        return None

    def assess_safety_threshold(self) -> bool:
        """Assess if safety threshold has been exceeded"""
        total_penalty = 0

        for deviation in self.detected_deviations:
            if deviation.type == "unexpected_step":
                total_penalty += self.unexpected_step_penalty
            elif deviation.type == "step_timeout":
                total_penalty += self.failed_step_penalty
            elif deviation.type == "risk_escalation":
                total_penalty += self.risk_escalation_penalty
            else:
                total_penalty += 1  # Default penalty

        threshold_exceeded = total_penalty >= self.max_deviations

        if threshold_exceeded:
            logger.critical(f"Safety threshold exceeded: penalty={total_penalty}, max={self.max_deviations}")

        return threshold_exceeded

    def get_deviation_summary(self) -> Dict[str, Any]:
        """Get summary of all detected deviations"""
        severity_counts = {}
        type_counts = {}

        for deviation in self.detected_deviations:
            severity_counts[deviation.severity] = severity_counts.get(deviation.severity, 0) + 1
            type_counts[deviation.type] = type_counts.get(deviation.type, 0) + 1

        return {
            'total_deviations': len(self.detected_deviations),
            'deviation_count': self.deviation_count,
            'safety_threshold_exceeded': self.assess_safety_threshold(),
            'severity_breakdown': severity_counts,
            'type_breakdown': type_counts,
            'recent_deviations': [
                {
                    'type': dev.type,
                    'severity': dev.severity,
                    'step_name': dev.step_name,
                    'details': dev.details,
                    'detected_at': dev.detected_at
                }
                for dev in self.detected_deviations[-5:]  # Last 5 deviations
            ]
        }

    def _record_deviation(self, deviation: Deviation):
        """Record a detected deviation"""
        self.detected_deviations.append(deviation)
        self.deviation_count += 1

        logger.warning(
            f"Deviation detected: {deviation.type} "
            f"(severity: {deviation.severity}, step: {deviation.step_name})"
        )
