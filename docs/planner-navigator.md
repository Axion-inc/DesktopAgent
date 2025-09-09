# Phase 8: Planner/Navigator Orchestrator

This document describes the Phase 8 loop: Plan → Navigate → Verify with interrupt/resume and checkpointing.

## Goals

- Intermittent planning: generate small batches, execute, observe, re-plan.
- Safety: policy-gated, signed templates only; planner drafts are proposals (non-executable) until signed.
- Robustness: page change interrupts halt batches; resume from the same state.

## Nodes (minimal scaffolding)

- PolicyGate: Evaluate allowance (hooks into PolicyEngine).
- Plan: `app/planner/api.plan_with_llm_stub` returns patch and draft (LLM proposal only).
- Navigate: `app/navigator/runner.NavigatorRunner.exec` sends `webx.exec_batch` JSON-RPC to extension/CDP.
- Verify: `app/verify/core.aggregate_verification` decides completion; planner `done=true` is only a candidate.
- Deviation/HITL: interrupts (e.g., domain drift, major DOM diff) cause loop break; operator may approve fixes.

## Interrupt & Resume

- Checkpoint: `app/orch/checkpoint.MemoryCheckpointer` stores state per `thread_id`.
- Orchestrator: `app/orch/graph.Orchestrator` simulates a LangGraph-like executor. `run()` sets a checkpoint before Navigate; `resume()` restarts from the saved phase.

### Optional: LangGraph Integration

- A facade `app/orch/langgraph_impl.LangGraphOrchestrator` is provided. If the `langgraph` package is installed, this can be wired to actual nodes/checkpointer.
- Two-stage adoption is recommended:
  1) Local-only trial: `pip install langgraph==<stable>` and run `pytest -k langgraph_orchestrator`.
  2) CI rollout: pin the version in `requirements.txt` and enable related tests in CI.

### Current State (Scaffolding)

- `app/orch/langgraph_graph.LangGraphRuntime` forwards to the existing Orchestrator while the node graph is stabilized.
- This allows us to merge APIs and tests early; later we can flip the internals to real graph nodes without changing callers.

## Metrics

- planning_runs_24h, navigator_avg_batch, page_change_interrupts_24h,
- planner_draft_count_24h, draft_signoff_rate_7d, verifier_pass_rate_24h.

## Safety Principles

- LLM drafts are never executed. Only after passing `DraftPipeline` (lint → dry-run×3 → sign) they become executable.
- Dangerous actions are never auto-added by patches (`apply_patch` blocks them).
