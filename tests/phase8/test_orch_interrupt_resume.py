from app.orch.checkpoint import MemoryCheckpointer
from app.orch.graph import Orchestrator


def test_interrupt_and_resume_from_checkpoint():
    ck = MemoryCheckpointer()
    orch = Orchestrator(ck)

    thread_id = "t-001"
    instruction = "フォーム送信して受付完了まで。送信は承認待ち"

    # First run halts due to page change interrupt (simulated)
    res1 = orch.run(thread_id, instruction, simulate_interrupt=True)
    assert res1["status"] == "interrupted"
    assert ck.get(thread_id) is not None

    # Resume from checkpoint completes with verify pending (not final until verifier passes)
    res2 = orch.resume(thread_id)
    assert res2["status"] in ("planned", "verifier_pending", "completed")

