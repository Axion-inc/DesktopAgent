# L4 Autopilot Documentation

## Overview

L4 Limited Full Automation provides policy-gated autopilot execution with deviation detection and safe-fail mechanisms. It enables fully automated execution within defined policy boundaries while maintaining human oversight through deviation monitoring.

## Architecture

```
L4 Autopilot System
├── Policy Integration    - Policy Engine v1 validation
├── Execution Monitoring  - Real-time step tracking
├── Deviation Detection   - Behavioral anomaly detection  
├── Safe-Fail Triggers    - Automatic stop mechanisms
├── HITL Handoff         - Smooth transition to human control
└── Audit Logging        - Complete execution traceability
```

## Key Features

### 1. Policy-Gated Activation

L4 Autopilot only activates when explicitly enabled by policy:

```yaml
# configs/policy.yaml
autopilot: true  # Must be true to enable L4
window: "MON-FRI 09:00-17:00 Asia/Tokyo"
allow_domains: ["partner.example.com"]
```

### 2. Deviation Detection

Real-time monitoring of execution behavior:

- **Unexpected Elements**: UI elements not matching expected schema
- **Timing Anomalies**: Steps taking significantly longer than usual
- **Error Patterns**: Repeated failures or unexpected error messages
- **Navigation Deviations**: Unexpected page transitions or redirects

### 3. Safe-Fail Mechanisms

Automatic intervention when thresholds are exceeded:

- **Deviation Threshold**: Default 3 deviations trigger safe-fail
- **Step Timeout**: Individual step timeout enforcement
- **Execution Time Limits**: Maximum total execution duration
- **Error Rate Limits**: Maximum allowed failure rate

## Usage Examples

### Initialize L4 Autopilot

```python
from app.autopilot.l4_system import L4AutopilotSystem
from app.policy.engine import PolicyEngine

# Initialize with policy engine
policy_engine = PolicyEngine.from_config("configs/policy.yaml")
l4_autopilot = L4AutopilotSystem(policy_engine)

# Check if autopilot can be enabled
template_manifest = {
    "name": "data-export-template",
    "target_domain": "partner.example.com",
    "estimated_duration": 120,
    "risk_flags": ["sends"]
}

decision = l4_autopilot.validate_execution(template_manifest)
print(f"Autopilot enabled: {decision.autopilot_enabled}")
print(f"Reason: {decision.reason}")
```

### Start Monitored Execution

```python
# Start execution with monitoring
execution_id = "exec_20240827_001"
expected_steps = [
    {"action": "open_browser", "timeout": 10},
    {"action": "fill_form", "timeout": 5},
    {"action": "click_submit", "timeout": 3},
    {"action": "wait_for_completion", "timeout": 30}
]

monitor = l4_autopilot.start_execution_monitoring(
    execution_id=execution_id,
    expected_steps=expected_steps,
    template_manifest=template_manifest
)

print(f"L4 monitoring active for {execution_id}")
```

### Handle Deviations

```python
# Monitor execution progress
while monitor.is_active():
    status = monitor.get_status()
    
    if status.has_deviations():
        print(f"Deviations detected: {status.deviation_count}")
        
        for deviation in status.deviations:
            print(f"- {deviation.type}: {deviation.reason}")
    
    if status.should_trigger_safe_fail():
        print("🚨 Safe-fail triggered - handing off to human")
        
        # Automatic handoff to HITL
        handoff_result = monitor.trigger_safe_fail_handoff()
        
        # Send notifications
        await notification_manager.send_safe_fail_trigger(
            execution_id=execution_id,
            threshold_exceeded=status.deviation_count,
            deviation_details=status.deviations
        )
        
        break
    
    await asyncio.sleep(1)  # Check every second
```

## Deviation Types

### 1. Element Not Found Deviations

When expected UI elements are missing:

```python
deviation = {
    "type": "element_not_found",
    "step": 3,
    "expected": "button[text='Submit']",
    "found": "button[text='送信']",  # Japanese variant
    "severity": "medium",
    "suggested_patch": {
        "type": "text_replacement",
        "find": "Submit",
        "replace": "送信"
    }
}
```

### 2. Timing Deviations

When steps take longer than expected:

```python
deviation = {
    "type": "timing_anomaly", 
    "step": 4,
    "expected_duration": 5.0,
    "actual_duration": 15.2,
    "severity": "low",
    "suggested_patch": {
        "type": "timeout_adjustment",
        "new_timeout": 20
    }
}
```

### 3. Navigation Deviations

When page navigation differs from expected:

```python
deviation = {
    "type": "navigation_deviation",
    "step": 2,
    "expected_url": "https://partner.example.com/form",
    "actual_url": "https://partner.example.com/login",
    "severity": "high",
    "requires_hitl": True
}
```

## Safe-Fail Configuration

### Threshold Settings

```yaml
# configs/policy.yaml
deviation_threshold: 3        # Max deviations before safe-fail
step_timeout: 30.0           # Default step timeout (seconds)
execution_timeout: 300.0     # Maximum execution time (seconds)

# Deviation penalty weights
unexpected_penalty: 2        # Weight for unexpected elements
failed_penalty: 1           # Weight for failed steps  
risk_penalty: 5             # Weight for high-risk deviations
```

### Safe-Fail Scoring

```python
def calculate_safe_fail_score(deviations):
    """Calculate weighted safe-fail score"""
    score = 0
    
    for deviation in deviations:
        if deviation['type'] == 'element_not_found':
            score += 2  # unexpected_penalty
        elif deviation['type'] == 'step_failed':
            score += 1  # failed_penalty
        elif deviation['severity'] == 'high':
            score += 5  # risk_penalty
        else:
            score += 1  # default penalty
    
    return score
```

## Execution Monitoring

### Step-by-Step Tracking

```python
class ExecutionMonitor:
    def record_step_start(self, step_name: str, expected_duration: float):
        """Record when a step begins execution"""
        
    def record_step_completion(self, step_name: str, actual_duration: float, success: bool):
        """Record step completion with timing and success status"""
        
    def detect_deviation(self, step_context: Dict) -> Optional[Deviation]:
        """Analyze step context for deviations"""
        
    def should_trigger_safe_fail(self) -> bool:
        """Check if safe-fail threshold is exceeded"""
```

### Real-Time Status

```python
# Get current execution status
status = monitor.get_execution_status()

print(f"Status: {status.state}")  # "active", "monitoring", "deviated", "safe_fail"
print(f"Step: {status.current_step} / {status.total_steps}")
print(f"Deviations: {status.deviation_count} / {status.deviation_threshold}")
print(f"Duration: {status.elapsed_time:.1f}s")

# Check if intervention is needed
if status.requires_intervention():
    print("⚠️ Human intervention required")
```

## HITL Handoff Process

### Automatic Handoff

When safe-fail is triggered, L4 automatically hands control to human:

```python
def trigger_safe_fail_handoff(self):
    """Handle safe-fail trigger and HITL handoff"""
    
    # 1. Stop current execution
    self.execution_engine.pause_execution()
    
    # 2. Capture current state
    current_state = self.capture_execution_state()
    
    # 3. Generate handoff report
    handoff_report = self.generate_handoff_report()
    
    # 4. Send notifications
    self.notification_manager.send_l4_deviation_alert(
        execution_id=self.execution_id,
        template_name=self.template_name,
        deviation_reason="Safe-fail threshold exceeded",
        execution_context=current_state
    )
    
    # 5. Create GitHub issue for tracking
    self.github_manager.create_l4_execution_issue(
        execution_id=self.execution_id,
        template_name=self.template_name,
        deviation_reason="Multiple deviations detected",
        execution_context=handoff_report
    )
    
    # 6. Transition to manual mode
    return {
        "handoff_complete": True,
        "execution_state": current_state,
        "report": handoff_report,
        "github_issue": issue_url
    }
```

### Handoff Report

```python
handoff_report = {
    "execution_id": "exec_20240827_001",
    "template_name": "data-export-template",
    "safe_fail_triggered": True,
    "deviation_count": 3,
    "threshold_exceeded": True,
    
    "execution_summary": {
        "steps_completed": 5,
        "steps_total": 8,
        "duration_seconds": 127.3,
        "success_rate": 0.6
    },
    
    "deviations": [
        {
            "step": 3,
            "type": "element_not_found", 
            "severity": "medium",
            "description": "Submit button text mismatch"
        },
        {
            "step": 4,
            "type": "timing_anomaly",
            "severity": "low", 
            "description": "Form submission took 15.2s (expected 5s)"
        },
        {
            "step": 5,
            "type": "navigation_deviation",
            "severity": "high",
            "description": "Unexpected redirect to login page"
        }
    ],
    
    "current_state": {
        "url": "https://partner.example.com/login",
        "browser_context": "saved_as_session_123",
        "form_data": "partially_filled",
        "next_recommended_action": "manual_login_verification"
    },
    
    "recommendations": [
        "Verify login credentials",
        "Check for site maintenance",
        "Consider updating template for new UI",
        "Review domain access permissions"
    ]
}
```

## Integration with Planner L2

L4 Autopilot works with Planner L2 to propose fixes for deviations:

```python
# When deviation is detected
deviation_info = {
    "failed_step": "click_by_text",
    "failed_params": {"text": "Submit", "role": "button"},
    "screen_schema": current_screen_schema
}

# Generate patch proposal
patch = planner_l2.analyze_for_text_patches(
    screen_schema=deviation_info["screen_schema"],
    failure_info=deviation_info
)

if patch and patch.confidence >= 0.85:
    # In L4 window with high confidence - auto-apply
    adoption_decision = planner_l2.evaluate_adoption_policy(
        patch, 
        {"autopilot_enabled": True, "policy_window": True}
    )
    
    if adoption_decision.auto_adopt:
        modified_template = planner_l2.apply_patches(
            original_template, 
            [patch]
        )
        
        # Continue execution with patched template
        execution_engine.update_template(modified_template)
        
        # Record successful auto-adaptation
        monitor.record_auto_adaptation(patch)
```

## Metrics and Monitoring

### L4 Autopilot Metrics

- `l4_autoruns_24h`: Number of L4 autopilot executions
- `deviation_stops_24h`: Number of safe-fail triggers
- `l4_success_rate`: Success rate of L4 executions
- `avg_deviations_per_run`: Average deviation count per execution
- `hitl_handoffs_24h`: Number of HITL handoffs

### Performance Dashboard

```python
def get_l4_dashboard_data():
    return {
        "status": "active" if is_l4_enabled() else "disabled",
        "policy_window": in_policy_window(),
        "executions_today": get_counter('l4_autoruns_24h'),
        "success_rate": calculate_l4_success_rate(),
        "avg_duration": get_avg_execution_duration(),
        "deviations": {
            "total": get_counter('deviation_stops_24h'),
            "by_type": get_deviation_breakdown(),
            "top_templates": get_top_deviating_templates()
        },
        "handoffs": {
            "total": get_counter('hitl_handoffs_24h'),
            "avg_resolution_time": get_avg_handoff_resolution_time()
        }
    }
```

## Security Considerations

### Execution Isolation

L4 autopilot runs in isolated environments:

```python
# Isolated execution context
l4_context = {
    "network_isolation": True,
    "file_system_sandbox": "/tmp/l4_sandbox",
    "resource_limits": {
        "max_memory": "1GB",
        "max_cpu": "2 cores",
        "max_execution_time": 300
    },
    "audit_logging": True
}
```

### Data Protection

Sensitive data handling in L4 mode:

```python
def sanitize_execution_data(execution_data):
    """Remove sensitive information from execution logs"""
    sensitive_patterns = [
        r'password.*?[:=].*',
        r'token.*?[:=].*', 
        r'api[_-]?key.*?[:=].*',
        r'secret.*?[:=].*'
    ]
    
    # Redact sensitive data
    for pattern in sensitive_patterns:
        execution_data = re.sub(pattern, '[REDACTED]', execution_data, flags=re.IGNORECASE)
    
    return execution_data
```

## Troubleshooting

### Common Issues

1. **L4 Not Activating**
   - Check `autopilot: true` in policy configuration
   - Verify execution is within allowed time window
   - Confirm template passes policy validation
   - Check domain whitelist includes target domain

2. **Frequent Safe-Fail Triggers**
   - Review deviation threshold settings
   - Analyze deviation patterns in logs
   - Consider updating templates for UI changes
   - Check network connectivity and site performance

3. **HITL Handoff Issues**
   - Verify notification channels are configured
   - Check GitHub integration settings
   - Review handoff report generation
   - Test manual execution resumption

### Debug Mode

Enable detailed L4 logging:

```yaml
# configs/policy.yaml  
debug:
  l4_autopilot: true
  deviation_detection: true
  safe_fail_triggers: true
```

```python
# In code
l4_autopilot.set_debug_mode(True)
monitor = l4_autopilot.start_execution_monitoring(execution_id, steps)

# Access debug information
debug_log = monitor.get_debug_log()
deviation_analysis = monitor.get_deviation_analysis()
```

## Best Practices

### 1. Gradual L4 Adoption

Start with low-risk templates and gradually expand:

```python
# Phase 1: Manual execution with monitoring
l4_config = {
    "autopilot": False,
    "monitoring_only": True,
    "collect_deviation_data": True
}

# Phase 2: Limited autopilot in safe windows
l4_config = {
    "autopilot": True,
    "window": "SUN 00:00-06:00 Asia/Tokyo",  # Low-impact time
    "deviation_threshold": 1  # Conservative threshold
}

# Phase 3: Expanded autopilot hours
l4_config = {
    "autopilot": True,
    "window": "MON-FRI 09:00-17:00 Asia/Tokyo",
    "deviation_threshold": 3  # Standard threshold
}
```

### 2. Template Optimization

Optimize templates for L4 compatibility:

```python
# Add explicit waits for better reliability
template_steps = [
    {"action": "open_browser", "url": "https://partner.example.com"},
    {"action": "wait_for_element", "selector": "#login-form", "timeout": 10},
    {"action": "fill_by_label", "label": "Username", "value": "${username}"},
    {"action": "wait_for_element", "selector": "button[type=submit]", "timeout": 5},
    {"action": "click_by_text", "text": "Login", "role": "button"}
]

# Add fallback strategies
template_metadata = {
    "l4_compatible": True,
    "fallback_selectors": {
        "submit_button": ["button[type=submit]", ".submit-btn", "#login-submit"]
    },
    "expected_duration": 30,
    "max_deviations": 2
}
```

### 3. Monitoring and Alerting

Set up comprehensive monitoring:

```python
# Monitor L4 health
def monitor_l4_health():
    metrics = get_l4_metrics()
    
    # Alert on high deviation rates
    if metrics['deviation_rate'] > 0.3:
        send_alert("High L4 deviation rate", metrics)
    
    # Alert on frequent safe-fail triggers
    if metrics['safe_fail_rate'] > 0.1:
        send_alert("Frequent L4 safe-fail triggers", metrics)
    
    # Alert on long HITL handoff times
    if metrics['avg_handoff_resolution'] > 3600:  # 1 hour
        send_alert("Slow HITL handoff resolution", metrics)
```

## API Reference

### L4AutopilotSystem Class

```python
class L4AutopilotSystem:
    def __init__(self, policy_engine: PolicyEngine)
    def validate_execution(self, manifest: Dict) -> AutopilotDecision
    def start_execution_monitoring(self, execution_id: str, steps: List[Dict]) -> ExecutionMonitor
    def get_l4_status(self) -> Dict[str, Any]
    def get_l4_metrics(self) -> Dict[str, Any]
    def trigger_emergency_stop(self, execution_id: str, reason: str)
```

### ExecutionMonitor Class

```python
class ExecutionMonitor:
    def is_active(self) -> bool
    def get_status(self) -> ExecutionStatus
    def record_deviation(self, deviation: Deviation)
    def should_trigger_safe_fail(self) -> bool
    def trigger_safe_fail_handoff(self) -> HandoffResult
    def get_execution_report(self) -> ExecutionReport
```

---

*L4 Autopilot provides safe, policy-controlled automation while maintaining the flexibility to handle unexpected situations through intelligent deviation detection and smooth HITL handoff mechanisms.*