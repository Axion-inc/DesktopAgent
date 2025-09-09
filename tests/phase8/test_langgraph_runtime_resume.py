from __future__ import annotations

from app.orch.langgraph_graph import LangGraphRuntime
from app.orch.checkpoint import MemoryCheckpointer


def test_runtime_interrupt_and_resume_checkpoint_restored():
    rt = LangGraphRuntime(checkpointer=MemoryCheckpointer())
    tid = "lg-run-001"

    r1 = rt.run(tid, "フォーム送信して受付完了まで。", simulate_interrupt=True)
    assert isinstance(r1, dict)
    assert r1.get("status") == "interrupted"
    # checkpoint should exist
    assert rt.ck.get(tid) is not None

    r2 = rt.resume(tid)
    assert isinstance(r2, dict)
    assert r2.get("status") in ("planned", "verifier_pending", "completed")
    # upon completion, checkpoint is cleared (for our verifier it should complete)
    assert rt.ck.get(tid) is None

