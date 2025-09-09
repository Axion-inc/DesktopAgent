from __future__ import annotations

from typing import Any, Dict, Optional
import json

from ..metrics import get_metrics_collector
from ..policy.engine import PolicyEngine, PolicyViolation
from ..config import get_config
from ..web.dom_snapshot import capture_dom_snapshot
from ..planner.api import plan_with_llm_stub
from ..verify.core import aggregate_verification
from .checkpoint import MemoryCheckpointer
from ..models import (
    init_db,
    insert_plan,
    insert_run,
    update_run,
    set_run_started_now,
    set_run_finished_now,
    insert_run_step,
    finalize_run_step,
)


class Orchestrator:
    """Minimal orchestrator loop with interrupt/resume semantics.

    This is a lightweight, dependency-free approximation of a LangGraph
    executor with nodes: PolicyGate -> Plan -> Navigate -> Verify.
    """

    def __init__(self, checkpointer: Optional[MemoryCheckpointer] = None):
        self.ck = checkpointer or MemoryCheckpointer()
        self.metrics = get_metrics_collector()
        self.policy = PolicyEngine.from_dict(get_config().get('policy', {}))

    def _policy_gate(self, instruction: str) -> None:
        # Allow by default; integrate with PolicyEngine's validate_execution API for future
        self.metrics.mark_planning_run()

    def _plan(self, dom: Dict[str, Any], instruction: str) -> Dict[str, Any]:
        req = {"instruction": instruction, "dom": dom, "history": [], "capabilities": ["webx"]}
        return plan_with_llm_stub(req)

    def run(self, thread_id: str, instruction: str, simulate_interrupt: bool = False) -> Dict[str, Any]:
        # Policy gate
        self._policy_gate(instruction)

        # Capture DOM snapshot once per cycle
        dom = capture_dom_snapshot()

        # Plan
        plan = self._plan(dom, instruction)

        # Save checkpoint before navigation to support resume
        self.ck.save(thread_id, {
            'phase': 'after_plan',
            'instruction': instruction,
            'plan': plan,
            'dom': dom,
        })

        if simulate_interrupt:
            self.metrics.mark_page_change_interrupt()
            return {"status": "interrupted", "reason": "page_change"}

        # Navigate (simulated as success, limited batch size)
        # Simulated single-batch execute; record batch size for average metric
        self.metrics.mark_navigator_batch(1)

        # Verify - treat planner done as candidate; require verifier to pass
        verify = aggregate_verification([{"name": "wait_for_text", "status": "success"}], planner_done=plan.get('done', False))

        # Clear checkpoint on completion
        if verify.get('finalized'):
            self.ck.clear(thread_id)
            return {"status": "completed"}
        else:
            return {"status": "verifier_pending"}

    def resume(self, thread_id: str) -> Dict[str, Any]:
        st = self.ck.get(thread_id)
        if not st:
            return {"status": "noop"}

        # Resume from after_plan -> attempt verify again
        plan = st.get('plan') or {}
        verify = aggregate_verification([{"name": "wait_for_text", "status": "success"}], planner_done=plan.get('done', False))
        if verify.get('finalized'):
            self.ck.clear(thread_id)
            return {"status": "completed"}
        return {"status": "planned"}

    # Recorded variants for UI/metrics: persist a run and steps to DB
    def run_recorded(self, thread_id: str, instruction: str, simulate_interrupt: bool = False) -> Dict[str, Any]:
        init_db()
        plan_id = insert_plan("Phase8 Orchestrated Run", yaml="name: phase8\n")
        run_id = insert_run(plan_id, status="running")
        set_run_started_now(run_id)

        # policy gate step
        pol_step = insert_run_step(run_id, 1, "policy_guard", input_json=json.dumps({"instruction": instruction}), status="running")
        self._policy_gate(instruction)
        finalize_run_step(pol_step, status="success", output_json=json.dumps({"allowed": True}))

        # snapshot
        dom = capture_dom_snapshot()

        # plan step (draft)
        plan_step = insert_run_step(run_id, 2, "planner_draft", input_json=json.dumps({"dom": "captured"}), status="running")
        plan = self._plan(dom, instruction)
        finalize_run_step(plan_step, status="success", output_json=json.dumps({"patch": plan.get("patch"), "draft": True}))
        # Persist a patch artifact for UI (optional)
        try:
            import os
            os.makedirs("artifacts/patches", exist_ok=True)
            artifact = {
                "step_index": 2,
                "adopt": False,
                "proposal": plan.get("patch", {}),
                "evidence": {
                    "screenshot": (dom or {}).get("screenshot"),
                    "schema": (dom or {}).get("schema"),
                },
            }
            with open(f"artifacts/patches/run_{run_id}_step_2_patch.json", "w", encoding="utf-8") as f:
                json.dump(artifact, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

        # checkpoint
        self.ck.save(thread_id, {"phase": "after_plan", "instruction": instruction, "plan": plan, "dom": dom, "run_id": run_id, "plan_id": plan_id})

        # navigate (exec_batch)
        nav_step = insert_run_step(run_id, 3, "exec_batch", input_json=json.dumps({"batch": 1}), status="running")
        if simulate_interrupt:
            self.metrics.mark_page_change_interrupt()
            finalize_run_step(nav_step, status="failed", error_message="page_change_interrupt")
            update_run(run_id, status="paused")
            return {"status": "interrupted", "run_id": run_id}
        else:
            self.metrics.mark_navigator_batch(1)
            finalize_run_step(nav_step, status="success", output_json=json.dumps({"steps": 1}))

        # verify
        ver_step = insert_run_step(run_id, 4, "verify", input_json=json.dumps({"checks": 1}), status="running")
        verify = aggregate_verification([{"name": "wait_for_text", "status": "success"}], planner_done=plan.get("done", False))
        finalize_run_step(ver_step, status="success" if verify.get("passed") else "failed", output_json=json.dumps(verify))

        set_run_finished_now(run_id)
        update_run(run_id, status="success")
        self.ck.clear(thread_id)
        return {"status": "completed", "run_id": run_id}

    def resume_recorded(self, thread_id: str) -> Dict[str, Any]:
        st = self.ck.get(thread_id)
        if not st:
            return {"status": "noop"}
        run_id = st.get("run_id")
        if not run_id:
            return {"status": "noop"}

        # resume with verify step
        ver_step = insert_run_step(run_id, 5, "verify", input_json=json.dumps({"checks": 1}), status="running")
        plan = st.get("plan") or {}
        verify = aggregate_verification([{"name": "wait_for_text", "status": "success"}], planner_done=plan.get("done", False))
        finalize_run_step(ver_step, status="success" if verify.get("passed") else "failed", output_json=json.dumps(verify))
        set_run_finished_now(run_id)
        update_run(run_id, status="success" if verify.get("passed") else "failed")
        self.ck.clear(thread_id)
        return {"status": "completed", "run_id": run_id}
