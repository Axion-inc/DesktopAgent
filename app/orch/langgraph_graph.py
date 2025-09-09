from __future__ import annotations

"""
LangGraph node scaffolding (safe fallback).

If `langgraph` is available at runtime, this module provides a thin runtime
wrapper that mimics a node-based execution. For now, nodes delegate to the
existing Orchestrator logic to keep behavior identical while we land the
interfaces and tests. This allows us to switch to real LangGraph nodes later
without breaking callers.
"""

from typing import Any, Dict, Optional
import json

try:
    import langgraph  # type: ignore  # noqa: F401
    _HAS_LANGGRAPH = True
except Exception:
    _HAS_LANGGRAPH = False

from .graph import Orchestrator as _FallbackOrchestrator
from .checkpoint import MemoryCheckpointer
from ..metrics import get_metrics_collector
from ..policy.engine import PolicyEngine
from ..config import get_config
from ..web.dom_snapshot import capture_dom_snapshot
from ..planner.api import plan_with_llm_stub
from ..verify.core import aggregate_verification
from .. import models


class NodePolicyGate:
    """PolicyGate node: records metrics and validates via PolicyEngine.

    Returns a small dict for contract stability.
    """

    def __init__(self) -> None:
        self.metrics = get_metrics_collector()
        self.policy = PolicyEngine.from_dict(get_config().get("policy", {}))

    def invoke(self, instruction: str) -> Dict[str, Any]:
        # For parity with current behavior, allow and count a planning run
        self.metrics.mark_planning_run()
        # In future, call self.policy.validate_execution(instruction)
        return {"allowed": True}


class NodePlan:
    """Plan node: produces a deterministic planning suggestion."""

    def invoke(self, dom: Dict[str, Any], instruction: str) -> Dict[str, Any]:
        req = {"instruction": instruction, "dom": dom, "history": [], "capabilities": ["webx"]}
        return plan_with_llm_stub(req)


class NodeNavigate:
    """Navigate node: simulates a single-batch execution and records metrics."""

    def __init__(self) -> None:
        self.metrics = get_metrics_collector()

    def invoke(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        # Parity with Orchestrator: one batch, success
        self.metrics.mark_navigator_batch(1)
        return {"steps": 1, "status": "success"}


class NodeVerify:
    """Verify node: aggregates verification and returns pass/finalized flags."""

    def invoke(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        steps = [{"name": "wait_for_text", "status": "success"}]
        return aggregate_verification(steps, planner_done=bool(plan.get("done", False)))


class LangGraphRuntime:
    """Node-style orchestrator façade using in-process memory checkpoints.

    If `langgraph` is present we still execute these nodes linearly for
    behavioral parity while the real graph wiring lands later.
    """

    def __init__(self, checkpointer: Optional[MemoryCheckpointer] = None) -> None:
        # Keep a fallback orchestrator handy for future divergence, but prefer nodes
        self._fb = _FallbackOrchestrator(MemoryCheckpointer())
        self.ck = checkpointer or MemoryCheckpointer()
        # Nodes
        self._policy = NodePolicyGate()
        self._planner = NodePlan()
        self._nav = NodeNavigate()
        self._verifier = NodeVerify()

    def run(self, thread_id: str, instruction: str, simulate_interrupt: bool = False) -> Dict[str, Any]:
        # Policy gate
        pol = self._policy.invoke(instruction)
        if not pol.get("allowed", False):
            return {"status": "blocked"}

        # Snapshot
        dom = capture_dom_snapshot()

        # Plan
        plan = self._planner.invoke(dom=dom, instruction=instruction)

        # Save checkpoint before navigation
        self.ck.save(thread_id, {
            "phase": "after_plan",
            "instruction": instruction,
            "plan": plan,
            "dom": dom,
        })

        # Optional interrupt
        if simulate_interrupt:
            # Keep metrics parity with Orchestrator
            try:
                get_metrics_collector().mark_page_change_interrupt()
            except Exception:
                pass
            return {"status": "interrupted", "reason": "page_change"}

        # Navigate (simulated)
        _ = self._nav.invoke(plan)

        # Verify
        ver = self._verifier.invoke(plan)
        if ver.get("finalized"):
            self.ck.clear(thread_id)
            return {"status": "completed"}
        return {"status": "verifier_pending"}

    def resume(self, thread_id: str) -> Dict[str, Any]:
        st = self.ck.get(thread_id)
        if not st:
            return {"status": "noop"}
        plan = st.get("plan") or {}
        ver = self._verifier.invoke(plan)
        if ver.get("finalized"):
            self.ck.clear(thread_id)
            return {"status": "completed"}
        return {"status": "planned"}

    # Recorded variants for UI/metrics parity
    def run_recorded(self, thread_id: str, instruction: str, simulate_interrupt: bool = False) -> Dict[str, Any]:
        models.init_db()
        plan_id = models.insert_plan("Phase8 LG Orchestrated Run", yaml="name: phase8-lg\n")
        run_id = models.insert_run(plan_id, status="running")
        models.set_run_started_now(run_id)

        # policy gate
        pol_step = models.insert_run_step(run_id, 1, "policy_guard", input_json=json.dumps({"instruction": instruction}), status="running")
        pol = self._policy.invoke(instruction)
        models.finalize_run_step(pol_step, status="success" if pol.get("allowed") else "failed", output_json=json.dumps(pol))
        if not pol.get("allowed"):
            models.update_run(run_id, status="blocked")
            models.set_run_finished_now(run_id)
            return {"status": "blocked", "run_id": run_id}

        # snapshot
        dom = capture_dom_snapshot()

        # plan step
        plan_step = models.insert_run_step(run_id, 2, "planner_draft", input_json=json.dumps({"dom": "captured"}), status="running")
        plan = self._planner.invoke(dom=dom, instruction=instruction)
        models.finalize_run_step(plan_step, status="success", output_json=json.dumps({"patch": plan.get("patch"), "draft": True}))

        # checkpoint
        self.ck.save(thread_id, {"phase": "after_plan", "instruction": instruction, "plan": plan, "dom": dom, "run_id": run_id, "plan_id": plan_id})

        # navigate
        nav_step = models.insert_run_step(run_id, 3, "exec_batch", input_json=json.dumps({"batch": 1}), status="running")
        if simulate_interrupt:
            try:
                get_metrics_collector().mark_page_change_interrupt()
            except Exception:
                pass
            models.finalize_run_step(nav_step, status="failed", error_message="page_change_interrupt")
            models.update_run(run_id, status="paused")
            return {"status": "interrupted", "run_id": run_id}
        else:
            self._nav.invoke(plan)
            models.finalize_run_step(nav_step, status="success", output_json=json.dumps({"steps": 1}))

        # verify
        ver_step = models.insert_run_step(run_id, 4, "verify", input_json=json.dumps({"checks": 1}), status="running")
        ver = self._verifier.invoke(plan)
        models.finalize_run_step(ver_step, status="success" if ver.get("passed") else "failed", output_json=json.dumps(ver))

        models.set_run_finished_now(run_id)
        models.update_run(run_id, status="success" if ver.get("passed") else "failed")
        self.ck.clear(thread_id)
        return {"status": "completed", "run_id": run_id}

    def resume_recorded(self, thread_id: str) -> Dict[str, Any]:
        st = self.ck.get(thread_id)
        if not st:
            return {"status": "noop"}
        run_id = st.get("run_id")
        if not run_id:
            return {"status": "noop"}
        plan = st.get("plan") or {}
        ver_step = models.insert_run_step(run_id, 5, "verify", input_json=json.dumps({"checks": 1}), status="running")
        ver = self._verifier.invoke(plan)
        models.finalize_run_step(ver_step, status="success" if ver.get("passed") else "failed", output_json=json.dumps(ver))
        models.set_run_finished_now(run_id)
        models.update_run(run_id, status="success" if ver.get("passed") else "failed")
        self.ck.clear(thread_id)
        return {"status": "completed", "run_id": run_id}
