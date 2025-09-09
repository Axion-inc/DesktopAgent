# Phase 8: LangGraph Runtime (Scaffold)

This phase introduces a node-style orchestrator façade that mirrors a LangGraph
execution without requiring the LangGraph dependency at runtime. It lets us
validate contracts, checkpoint/resume semantics, and recorded runs.

Key nodes:
- PolicyGate: marks planning run and returns `{allowed: true}`.
- Plan: returns deterministic patch + draft_template for testing.
- Navigate: simulates one-batch navigation and records metrics.
- Verify: aggregates verification and finalizes when passing.

Runtime:
- `LangGraphRuntime` provides `run`, `resume`, and recorded variants
  `run_recorded` / `resume_recorded` with DB-backed steps.

CLI:
- `./cli.py lg-run [--interrupt] [--recorded] [--instruction …]`
  - `--interrupt` simulates an interrupt before navigation to test checkpointing.
  - `--recorded` persists steps into the DB and returns `run_id`.

Tests:
- See `tests/phase8/` for node IO contracts and checkpoint/resume behavior.

