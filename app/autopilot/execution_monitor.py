"""
Execution Monitor - Phase 7
Real-time execution tracking and state management for L4 Autopilot
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum


logger = logging.getLogger(__name__)


class ExecutionState(Enum):
    """Execution state enumeration"""
    INITIALIZED = "initialized"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


@dataclass
class StepExecution:
    """Individual step execution tracking"""
    step_name: str
    step_index: int
    params: Dict[str, Any]
    status: str
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_ms: Optional[float] = None
    error_message: Optional[str] = None


class ExecutionMonitor:
    """Monitor execution progress and detect deviations in real-time"""
    
    def __init__(self, execution_id: str, expected_steps: List[Dict[str, Any]]):
        """Initialize execution monitor"""
        self.execution_id = execution_id
        self.expected_steps = expected_steps
        self.current_step_index = 0
        self.execution_state = ExecutionState.INITIALIZED
        self.step_executions: List[StepExecution] = []
        self.start_time = datetime.now(timezone.utc)
        self.end_time: Optional[datetime] = None
        
        logger.info(f"Execution monitor initialized for {execution_id} with {len(expected_steps)} steps")
    
    def record_step_start(self, step_name: str, params: Dict[str, Any]):
        """Record step execution start"""
        step_execution = StepExecution(
            step_name=step_name,
            step_index=self.current_step_index,
            params=params,
            status="running",
            start_time=datetime.now(timezone.utc)
        )
        
        self.step_executions.append(step_execution)
        self.execution_state = ExecutionState.EXECUTING
        
        logger.debug(f"Step {step_name} started at index {self.current_step_index}")
    
    def record_step_success(self, step_name: str):
        """Record step execution success"""
        current_step = self._get_current_step_execution()
        if current_step and current_step.step_name == step_name:
            current_step.status = "success"
            current_step.end_time = datetime.now(timezone.utc)
            
            if current_step.start_time:
                duration = (current_step.end_time - current_step.start_time).total_seconds() * 1000
                current_step.duration_ms = duration
            
            self.current_step_index += 1
            
            # Check if execution completed
            if self.current_step_index >= len(self.expected_steps):
                self.execution_state = ExecutionState.COMPLETED
                self.end_time = datetime.now(timezone.utc)
            
            logger.debug(f"Step {step_name} completed successfully")
    
    def record_step_failure(self, step_name: str, error_message: str):
        """Record step execution failure"""
        current_step = self._get_current_step_execution()
        if current_step and current_step.step_name == step_name:
            current_step.status = "failed"
            current_step.end_time = datetime.now(timezone.utc)
            current_step.error_message = error_message
            
            if current_step.start_time:
                duration = (current_step.end_time - current_step.start_time).total_seconds() * 1000
                current_step.duration_ms = duration
            
            self.execution_state = ExecutionState.FAILED
            self.end_time = datetime.now(timezone.utc)
            
            logger.warning(f"Step {step_name} failed: {error_message}")
    
    def record_completion(self, success: bool):
        """Record execution completion"""
        if success:
            self.execution_state = ExecutionState.COMPLETED
        else:
            self.execution_state = ExecutionState.FAILED
        
        self.end_time = datetime.now(timezone.utc)
        logger.info(f"Execution {self.execution_id} completed with success={success}")
    
    def get_execution_state(self) -> ExecutionState:
        """Get current execution state"""
        return self.execution_state
    
    def get_current_step_index(self) -> int:
        """Get current step index"""
        return self.current_step_index
    
    def get_completion_percentage(self) -> float:
        """Calculate execution progress percentage"""
        if len(self.expected_steps) == 0:
            return 100.0
        
        completed_steps = sum(1 for step in self.step_executions if step.status == "success")
        return (completed_steps / len(self.expected_steps)) * 100.0
    
    def get_current_step_execution(self) -> Optional[Dict[str, Any]]:
        """Get current step execution details"""
        current_step = self._get_current_step_execution()
        if current_step:
            return {
                'step_name': current_step.step_name,
                'step_index': current_step.step_index,
                'params': current_step.params,
                'status': current_step.status,
                'start_time': current_step.start_time,
                'end_time': current_step.end_time,
                'duration_ms': current_step.duration_ms,
                'error_message': current_step.error_message
            }
        return None
    
    def check_deviations(self) -> List[Any]:
        """Check for execution deviations"""
        from .deviation_detector import DeviationDetector
        
        # Create temporary deviation detector for analysis
        detector = DeviationDetector({'max_deviations': 10})
        
        # Analyze sequence deviation
        expected_sequence = [step.get('name', 'unknown') for step in self.expected_steps]
        actual_sequence = [step.step_name for step in self.step_executions]
        
        deviations = detector.analyze_sequence_deviation(expected_sequence, actual_sequence)
        
        # Check for step timeouts
        for step_execution in self.step_executions:
            if step_execution.duration_ms and step_execution.duration_ms > 30000:  # 30s threshold
                timeout_deviation = detector.check_step_timeout(
                    step_execution.step_name, 
                    step_execution.duration_ms / 1000.0
                )
                if timeout_deviation:
                    deviations.append(timeout_deviation)
        
        return deviations
    
    def check_safety_threshold(self):
        """Check if safety threshold exceeded"""
        deviations = self.check_deviations()
        if len(deviations) >= 3:  # Simple threshold check
            from .l4_system import SafeFailException
            raise SafeFailException("Safety threshold exceeded", deviations)
    
    def _get_current_step_execution(self) -> Optional[StepExecution]:
        """Get the most recent step execution"""
        if self.step_executions:
            return self.step_executions[-1]
        return None
    
    def get_execution_summary(self) -> Dict[str, Any]:
        """Get comprehensive execution summary"""
        total_duration = None
        if self.start_time and self.end_time:
            total_duration = (self.end_time - self.start_time).total_seconds() * 1000
        
        return {
            'execution_id': self.execution_id,
            'state': self.execution_state.value,
            'progress_percentage': self.get_completion_percentage(),
            'current_step_index': self.current_step_index,
            'total_steps': len(self.expected_steps),
            'start_time': self.start_time,
            'end_time': self.end_time,
            'total_duration_ms': total_duration,
            'steps_completed': len([s for s in self.step_executions if s.status == "success"]),
            'steps_failed': len([s for s in self.step_executions if s.status == "failed"]),
            'step_executions': [
                {
                    'step_name': step.step_name,
                    'status': step.status,
                    'duration_ms': step.duration_ms,
                    'error_message': step.error_message
                }
                for step in self.step_executions
            ]
        }