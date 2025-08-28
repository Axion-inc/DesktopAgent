# Planner L2 — Differential Patch Proposals

Planner L2 analyzes screen schemas and recent failures to propose small, safe patches that improve stability.

## Patch Schema
```
patch:
  replace_text:
    - { find: "送信", with: "提出", role: "button", confidence: 0.91 }
  fallback_search:
    - { goal: "提出ボタン", synonyms: ["確定","送出"], role: "button", attempts: 1, confidence: 0.88 }
  wait_tuning:
    - { step: "wait_for_element", timeout_ms: 12000 }
adopt_policy:
  low_risk_auto: true
  min_confidence: 0.85
```

Rules:
- Never add destructive operations (sends/deletes/overwrites) automatically.
- Patches are applied to DSL only; execution stays deterministic.
- In L4 window and above `min_confidence`, auto-adopt is allowed per policy.

