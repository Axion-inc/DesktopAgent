import json
from app.orch.graph import Orchestrator
from app.models import init_db, get_run, get_run_steps


def test_run_detail_contains_phase8_steps():
    init_db()
    orch = Orchestrator()
    # first run interrupted and paused
    r1 = orch.run_recorded("t-x", "送信→提出で受付完了", simulate_interrupt=True)
    assert r1["status"] == "interrupted"
    run_id = r1["run_id"]
    steps = get_run_steps(run_id)
    names = [s["name"] for s in steps]
    assert "policy_guard" in names and "planner_draft" in names and "exec_batch" in names
    # resume should complete and add a verify
    r2 = orch.resume_recorded("t-x")
    assert r2["status"] == "completed"
    steps2 = get_run_steps(run_id)
    names2 = [s["name"] for s in steps2]
    assert names2.count("verify") >= 1

