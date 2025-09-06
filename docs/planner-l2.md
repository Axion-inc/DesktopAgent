# Planner L2 (Differential Patch)

Inputs: screen schema + failure context (e.g., assert_text goal)

Proposals:
- replace_text: UI vocabulary substitution (e.g., 送信→提出/確定)
- fallback_search: near-synonym exploration (1 attempt)
- wait_tuning: safe wait/verify adjustments

Adoption Policy:
- auto-adopt when `low_risk_auto=true` AND `confidence >= min_confidence` AND patch is low-risk
- otherwise require HITL approval

Execution remains DSL-only; no new dangerous steps are added automatically.

