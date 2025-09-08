from __future__ import annotations

from typing import Any, Dict, Optional

from ..metrics import get_metrics_collector
from ..policy.engine import PolicyEngine, PolicyViolation
from ..config import get_config
from ..web.dom_snapshot import capture_dom_snapshot
from ..planner.api import plan_with_llm_stub
from ..verify.core import aggregate_verification
from .checkpoint import MemoryCheckpointer


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
