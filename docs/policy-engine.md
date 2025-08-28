# Policy Engine v1

This document describes the Phase 7 Policy Engine (v1): execution-time guardrails for Desktop Agent templates.

## Goals
- Pre-execution guard across: allowed domains, time windows (TZ-aware), high-risk flags (sends/deletes/overwrites), signature verification, and required capabilities.
- Safety-first: policy violations block execution and produce a human-readable reason and an audit log entry.

## Configuration
Location: `configs/policy.yaml`

Example:
```
autopilot: false
allow_domains: ["partner.example.com"]
allow_risks: ["sends"]
window: "SUN 00:00-06:00 Asia/Tokyo"
require_signed_templates: true
require_capabilities: ["webx"]
```

## Runtime Evaluation
At execution, the engine cross-checks the manifest and runtime context:
- Domain: All target URLs must match `allow_domains`.
- Window: Current time must be within `window` (timezone supported via pytz).
- Risk: Risk flags must be a subset of `allow_risks`.
- Signature: Template must be signed and valid (grace period is configurable).
- Capabilities: `required_capabilities` must be covered by `require_capabilities`.

Violations cause a block with a reason string suitable for UI and audit capture.

## API Sketch
- `PolicyEngine.verify_template_signature(path)`
- `PolicyEngine.evaluate_execution_policy(path, verification_result)`
- `PolicyEngine.update_policy(dict)` (tests)/ `load_configurations()` (runtime)
- `verify_template_before_execution(path)` convenience function

## Auditing
On block, systems should emit an audit record with the decision, reasons, and key context.

