import pytest

pytest.importorskip("langgraph")

from app.orch.langgraph_impl import LangGraphOrchestrator


def test_langgraph_orchestrator_interrupt_and_resume():
    orch = LangGraphOrchestrator()

    r1 = orch.run("lg-001", "フォーム送信して受付完了まで。", simulate_interrupt=True)
    assert isinstance(r1, dict)
    assert r1.get("status") == "interrupted"

    r2 = orch.resume("lg-001")
    assert isinstance(r2, dict)
    assert r2.get("status") in ("planned", "verifier_pending", "completed")

