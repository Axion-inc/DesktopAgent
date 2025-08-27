# Planner L2 Documentation

## Overview

Planner L2 provides differential patch proposal system that analyzes execution failures and proposes incremental changes to improve template stability. It works seamlessly with L4 Autopilot to enable adaptive automation through intelligent patch generation and adoption policies.

## Architecture

```
Planner L2 System
├── Schema Analysis      - Screen schema and UI element analysis
├── Patch Generation     - Differential patch creation algorithms
├── Text Replacements    - UI vocabulary variation handling
├── Fallback Search      - Synonym-based element location strategies
├── Wait Tuning         - Timeout adjustment based on failure patterns
├── Adoption Policies   - Risk-based auto-adoption decision making
└── DSL Application     - Template patching and version control
```

## Core Concepts

### Differential Patches

Small, incremental changes to templates that address specific execution failures:

```python
@dataclass
class DifferentialPatch:
    patch_type: str         # "replace_text", "fallback_search", "wait_tuning"
    confidence: float       # Confidence score 0.0-1.0
    risk_level: str        # "low", "medium", "high"
    
    # Patch content (one populated based on patch_type)
    replacements: List[TextReplacement]
    fallback_search: Optional[FallbackSearch]
    wait_tuning: Optional[WaitTuning]
    
    generated_at: datetime
    metadata: Dict[str, Any]
```

### Patch Types

1. **Text Replacements**: Handle UI vocabulary variations
2. **Fallback Search**: Provide synonym-based search strategies  
3. **Wait Tuning**: Adjust timeouts based on failure patterns
4. **Add Step**: Insert new steps for better reliability

## Usage Examples

### Initialize Planner L2

```python
from app.planner.l2 import PlannerL2

# Initialize with configuration
planner_config = {
    "adopt_policy": {
        "low_risk_auto": True,
        "min_confidence": 0.85,
        "max_auto_changes": 3
    }
}

planner = PlannerL2(planner_config)
```

### Analyze Execution Failures

```python
# Screen schema from failed execution
screen_schema = {
    "elements": [
        {"text": "確定", "role": "button", "selector": "#confirm-btn"},
        {"text": "キャンセル", "role": "button", "selector": "#cancel-btn"},
        {"text": "送信", "role": "link", "selector": "#submit-link"}
    ]
}

# Failure information
failure_info = {
    "failed_step": "click_by_text",
    "failed_params": {"text": "送信", "role": "button"},
    "error": "Button with text '送信' not found"
}

# Analyze for patch opportunities
patch = planner.analyze_for_text_patches(screen_schema, failure_info)

if patch:
    print(f"Generated patch: {patch.patch_type}")
    print(f"Confidence: {patch.confidence:.2f}")
    print(f"Replacements: {[r.with_text for r in patch.replacements]}")
```

### Generate Fallback Search Patch

```python
# When element not found, generate fallback strategies
failure_info = {
    "failed_step": "click_by_text",
    "failed_params": {"text": "提出", "role": "button"},
    "error": "Element not found"
}

fallback_patch = planner.generate_fallback_search(failure_info)

print(f"Goal: {fallback_patch.fallback_search.goal}")
print(f"Synonyms: {fallback_patch.fallback_search.synonyms}")
# Output: Goal: 提出ボタン
# Synonyms: ['確定', '送信', '送出', '実行']
```

### Wait Timing Adjustment

```python
# Adjust timeouts based on failure patterns
failure_info = {
    "failed_step": "wait_for_element",
    "failed_params": {"selector": "#loading", "timeout_ms": 5000},
    "error": "Timeout waiting for element",
    "duration_ms": 5000
}

wait_patch = planner.generate_wait_tuning(failure_info)

print(f"Original timeout: {failure_info['failed_params']['timeout_ms']}ms")
print(f"New timeout: {wait_patch.wait_tuning.timeout_ms}ms")
# Output: Original timeout: 5000ms, New timeout: 10000ms
```

## Patch Adoption Policies

### Auto-Adoption Rules

Patches are automatically adopted based on policy configuration:

```python
def evaluate_adoption_policy(self, patch, context):
    """Evaluate whether patch should be auto-adopted"""
    
    autopilot_enabled = context.get("autopilot_enabled", False)
    policy_window = context.get("policy_window", False)
    min_confidence = context.get("min_confidence", 0.85)
    
    # Block high-risk patches
    if patch.risk_level == "high":
        return AdoptionDecision(
            auto_adopt=False,
            blocked=True,
            reason="High-risk operation blocked by policy"
        )
    
    # Auto-adopt low-risk patches in L4 window
    if (patch.risk_level == "low" and 
        autopilot_enabled and 
        policy_window and 
        patch.confidence >= min_confidence):
        
        return AdoptionDecision(
            auto_adopt=True,
            requires_confirmation=False,
            reason="Low risk, high confidence, L4 window"
        )
    
    # Default: require confirmation
    return AdoptionDecision(
        auto_adopt=False,
        requires_confirmation=True,
        reason="Default policy - requires confirmation"
    )
```

### Context-Aware Adoption

```python
# L4 autopilot context
l4_context = {
    "autopilot_enabled": True,
    "policy_window": True,
    "min_confidence": 0.85,
    "execution_id": "exec_20240827_001"
}

adoption_decision = planner.evaluate_adoption_policy(patch, l4_context)

if adoption_decision.auto_adopt:
    print("✅ Auto-adopting patch")
    modified_template = planner.apply_patches(original_template, [patch])
    
elif adoption_decision.requires_confirmation:
    print("⚠️ Patch requires manual approval")
    # Send notification for approval
    await notification_manager.send_patch_proposal_notification(
        patch_data=patch.to_dict(),
        template_name=template_name,
        requires_approval=True
    )
```

## Patch Application

### Apply to DSL Template

```python
# Original template DSL
original_dsl = {
    "steps": [
        {"click_by_text": {"text": "送信", "role": "button"}},
        {"wait_for_element": {"selector": "#result", "timeout_ms": 5000}}
    ]
}

# Apply multiple patches
patches = [
    text_replacement_patch,    # 送信 → 確定
    wait_tuning_patch         # 5000ms → 10000ms
]

modified_dsl = planner.apply_patches(original_dsl, patches)

# Result
assert modified_dsl["steps"][0]["click_by_text"]["text"] == "確定"
assert modified_dsl["steps"][1]["wait_for_element"]["timeout_ms"] == 10000

# Track applied patches
print(f"Applied patches: {len(modified_dsl['_applied_patches'])}")
print(f"Modified at: {modified_dsl['_modified_at']}")
```

### Version Control Integration

```python
# Create versioned patch application
def apply_patches_with_versioning(template_path, patches):
    # Load original template
    with open(template_path) as f:
        original = yaml.safe_load(f)
    
    # Apply patches
    modified = planner.apply_patches(original, patches)
    
    # Generate version info
    version_info = {
        "original_version": original.get("version", "1.0"),
        "patch_count": len(patches),
        "patches_applied": [
            {
                "type": p.patch_type,
                "confidence": p.confidence,
                "timestamp": p.generated_at.isoformat()
            }
            for p in patches
        ]
    }
    
    # Create new version
    new_version = increment_version(original.get("version", "1.0"))
    modified["version"] = new_version
    modified["patch_history"] = version_info
    
    # Save patched template
    patched_path = template_path.replace(".yaml", f"_v{new_version}.yaml")
    with open(patched_path, "w") as f:
        yaml.dump(modified, f)
    
    return patched_path, version_info
```

## Schema Analysis

### UI Vocabulary Extraction

```python
from app.planner.schema_ops import SchemaAnalyzer

analyzer = SchemaAnalyzer()

# Extract UI vocabulary from screen schema
schema = {
    "elements": [
        {"text": "Submit", "role": "button"},
        {"text": "確定", "role": "button"}, 
        {"text": "送信", "role": "link"},
        {"text": "Cancel", "role": "button"}
    ]
}

vocabulary = analyzer.extract_ui_vocabulary(schema)

print(vocabulary)
# Output: {
#   "buttons": ["Submit", "確定", "Cancel"],
#   "links": ["送信"],
#   "forms": [],
#   "labels": []
# }
```

### Semantic Matching

```python
# Find semantically similar elements
elements = [
    {"text": "Submit", "role": "button"},
    {"text": "確定", "role": "button"},
    {"text": "送信", "role": "button"},
    {"text": "Cancel", "role": "button"}
]

similar = analyzer.find_semantic_matches("提出", elements, threshold=0.7)

print(f"Found {len(similar)} similar elements:")
for elem in similar:
    print(f"- {elem['text']} (similarity: {elem.get('similarity', 0):.2f})")

# Output: 
# Found 3 similar elements:
# - Submit (similarity: 0.85)
# - 確定 (similarity: 0.72)  
# - 送信 (similarity: 0.78)
```

### Spatial Analysis

```python
# Find nearby elements for context
target_element = {"text": "Submit", "role": "button", "x": 205, "y": 195}

nearby = analyzer.find_nearby_elements(schema, target_element, radius=50)

print(f"Found {len(nearby)} nearby elements:")
for elem in nearby:
    distance = calculate_distance(target_element, elem)
    print(f"- {elem['text']} (distance: {distance:.1f}px)")
```

## Advanced Features

### Multi-Language Support

```python
# Handle Japanese/English UI variations
japanese_synonyms = {
    "送信": ["Submit", "Send", "確定", "実行"],
    "確定": ["OK", "Confirm", "送信", "決定"],
    "キャンセル": ["Cancel", "取消", "中止"]
}

def generate_multilingual_patch(target_text, available_elements):
    """Generate patches for multilingual UI variations"""
    
    # Find direct translations
    direct_synonyms = japanese_synonyms.get(target_text, [])
    
    # Find available translations on screen
    available_texts = [elem["text"] for elem in available_elements]
    matching_synonyms = [s for s in direct_synonyms if s in available_texts]
    
    if matching_synonyms:
        return DifferentialPatch(
            patch_type="replace_text",
            replacements=[
                TextReplacement(
                    find=target_text,
                    with_text=synonym,
                    role="button",
                    confidence=0.9
                )
                for synonym in matching_synonyms
            ],
            confidence=0.9,
            risk_level="low"
        )
    
    return None
```

### Context-Aware Patching

```python
# Generate patches based on execution context
def generate_contextual_patches(failure_info, execution_context):
    """Generate patches based on broader execution context"""
    
    patches = []
    
    # Time-based adaptations
    if execution_context.get("time_of_day") == "peak_hours":
        # Increase timeouts during peak traffic
        timeout_patch = DifferentialPatch(
            patch_type="wait_tuning",
            wait_tuning=WaitTuning(
                step=failure_info["failed_step"],
                timeout_ms=failure_info["failed_params"]["timeout_ms"] * 2
            ),
            confidence=0.8,
            risk_level="low"
        )
        patches.append(timeout_patch)
    
    # Device-specific adaptations  
    if execution_context.get("device_type") == "mobile":
        # Use mobile-specific selectors
        mobile_patch = generate_mobile_selector_patch(failure_info)
        if mobile_patch:
            patches.append(mobile_patch)
    
    return patches
```

### Learning from Patch History

```python
def learn_from_patch_history(template_name):
    """Learn from historical patch success rates"""
    
    # Query patch history
    patch_history = get_patch_history(template_name)
    
    # Analyze success patterns
    successful_patterns = {}
    for patch in patch_history:
        if patch["success_rate"] > 0.8:
            pattern = (patch["type"], patch["target_text"])
            successful_patterns[pattern] = patch["success_rate"]
    
    # Generate learned recommendations
    recommendations = []
    for pattern, success_rate in successful_patterns.items():
        recommendations.append({
            "pattern": pattern,
            "success_rate": success_rate,
            "recommendation": f"Consider {pattern[0]} patches for {pattern[1]}"
        })
    
    return recommendations
```

## Integration with L4 Autopilot

### Real-Time Patch Application

```python
# During L4 execution, apply patches automatically
def handle_l4_deviation_with_patching(deviation, execution_context):
    """Handle L4 deviation with automatic patching"""
    
    # Generate patch for deviation
    patch = planner.analyze_failure_for_patch(
        failure_info=deviation,
        execution_context=execution_context
    )
    
    if not patch:
        return {"action": "escalate_to_hitl", "reason": "No patch available"}
    
    # Evaluate adoption policy
    adoption = planner.evaluate_adoption_policy(patch, execution_context)
    
    if adoption.auto_adopt:
        # Apply patch and continue execution
        modified_template = planner.apply_patches(
            execution_context["current_template"], 
            [patch]
        )
        
        # Update execution engine with patched template
        execution_engine.update_template(modified_template)
        
        # Log auto-adaptation
        logger.info(f"Auto-applied patch: {patch.patch_type} (confidence: {patch.confidence:.2f})")
        
        return {
            "action": "continue_with_patch",
            "patch_applied": patch.to_dict(),
            "modified_template": modified_template
        }
    else:
        # Create patch proposal for manual review
        github_manager.create_patch_proposal_pr(
            patch_data=patch.to_dict(),
            template_name=execution_context["template_name"],
            branch_name=f"patch/{execution_context['execution_id']}"
        )
        
        return {
            "action": "escalate_to_hitl",
            "patch_proposed": patch.to_dict(),
            "requires_manual_review": True
        }
```

### Patch Effectiveness Tracking

```python
def track_patch_effectiveness():
    """Track how effective patches are in practice"""
    
    metrics = {}
    
    # Get recent patch applications
    recent_patches = get_recent_patch_applications(days=7)
    
    for patch in recent_patches:
        # Check if subsequent executions succeeded
        success_rate = calculate_patch_success_rate(
            template_name=patch["template_name"],
            patch_type=patch["patch_type"],
            applied_after=patch["applied_at"]
        )
        
        # Group by patch type
        patch_type = patch["patch_type"]
        if patch_type not in metrics:
            metrics[patch_type] = {
                "count": 0,
                "success_rates": [],
                "avg_confidence": []
            }
        
        metrics[patch_type]["count"] += 1
        metrics[patch_type]["success_rates"].append(success_rate)
        metrics[patch_type]["avg_confidence"].append(patch["confidence"])
    
    # Calculate aggregated metrics
    for patch_type, data in metrics.items():
        data["avg_success_rate"] = sum(data["success_rates"]) / len(data["success_rates"])
        data["avg_confidence"] = sum(data["avg_confidence"]) / len(data["avg_confidence"])
        data["effectiveness_score"] = data["avg_success_rate"] * data["avg_confidence"]
    
    return metrics
```

## Configuration

### Planner L2 Configuration

```yaml
# configs/planner_l2.yaml
planner_l2:
  # Patch generation settings
  confidence_threshold: 0.7
  max_patches_per_failure: 3
  semantic_similarity_threshold: 0.75
  
  # Adoption policy
  adopt_policy:
    low_risk_auto: true
    min_confidence: 0.85
    max_auto_changes: 3
    require_confirmation_outside_l4: true
    block_high_risk: true
  
  # Text replacement settings
  synonyms:
    enable_builtin: true
    custom_mappings:
      "提出": ["送信", "確定", "Submit"]
      "削除": ["Delete", "Remove", "消去"]
  
  # Wait tuning settings
  timeout_multipliers:
    slow_connection: 2.0
    peak_hours: 1.5
    mobile_device: 1.8
  
  # Integration settings
  github_integration:
    create_patch_prs: true
    auto_merge_low_risk: false
    pr_template: "templates/patch_pr_template.md"
```

### Risk Assessment Rules

```python
# Risk level determination
def assess_patch_risk(patch):
    """Assess risk level of a patch"""
    
    high_risk_indicators = [
        "deletes existing steps",
        "modifies security-related fields", 
        "changes domain or URL",
        "adds file system operations"
    ]
    
    medium_risk_indicators = [
        "modifies timeout values significantly",
        "changes element selectors",
        "adds new steps"
    ]
    
    # Analyze patch content
    risk_score = 0
    
    if patch.patch_type == "add_step":
        risk_score += 2  # Adding steps is riskier
    
    if patch.patch_type == "wait_tuning":
        if patch.wait_tuning.timeout_ms > 30000:  # > 30 seconds
            risk_score += 1
    
    if patch.confidence < 0.7:
        risk_score += 1  # Lower confidence = higher risk
    
    # Determine risk level
    if risk_score >= 3:
        return "high"
    elif risk_score >= 1:
        return "medium"
    else:
        return "low"
```

## Monitoring and Metrics

### Planner L2 Metrics

- `patches_proposed_24h`: Number of patches proposed
- `patches_applied_24h`: Number of patches applied
- `patches_auto_adopted_24h`: Number of auto-adopted patches
- `patch_success_rate`: Success rate of applied patches
- `avg_patch_confidence`: Average confidence of generated patches

### Dashboard Integration

```python
def get_planner_l2_metrics():
    """Get Planner L2 metrics for dashboard"""
    
    return {
        "patches_today": get_counter('patches_proposed_24h'),
        "auto_adoption_rate": calculate_auto_adoption_rate(),
        "patch_effectiveness": get_patch_effectiveness_metrics(),
        "top_patch_types": get_top_patch_types(),
        "templates_improved": get_templates_with_patches(),
        "success_rate_by_type": {
            "replace_text": 0.92,
            "wait_tuning": 0.85,
            "fallback_search": 0.78
        }
    }
```

## API Reference

### PlannerL2 Class

```python
class PlannerL2:
    def __init__(self, config: Dict[str, Any] = None)
    def analyze_for_text_patches(self, screen_schema: Dict, failure_info: Dict) -> Optional[DifferentialPatch]
    def generate_fallback_search(self, failure_info: Dict) -> Optional[DifferentialPatch]
    def generate_wait_tuning(self, failure_info: Dict) -> Optional[DifferentialPatch]
    def evaluate_adoption_policy(self, patch: DifferentialPatch, context: Dict) -> AdoptionDecision
    def apply_patches(self, original_dsl: Dict, patches: List[DifferentialPatch]) -> Dict
```

### Patch Classes

```python
@dataclass
class TextReplacement:
    find: str
    with_text: str
    role: str
    confidence: float = 0.0

@dataclass
class FallbackSearch:
    goal: str
    synonyms: List[str]
    role: str
    attempts: int = 1
    confidence: float = 0.0

@dataclass
class AdoptionDecision:
    auto_adopt: bool
    requires_confirmation: bool
    blocked: bool = False
    reason: str = ""
```

---

*Planner L2 enables intelligent template adaptation through differential patching, making automation more resilient to UI changes while maintaining safety through risk-based adoption policies.*