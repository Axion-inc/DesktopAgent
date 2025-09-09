from __future__ import annotations

from app.orch.langgraph_graph import NodePolicyGate, NodePlan, NodeNavigate, NodeVerify
from app.web.dom_snapshot import capture_dom_snapshot


def test_nodes_io_contracts():
    policy = NodePolicyGate()
    planner = NodePlan()
    nav = NodeNavigate()
    verify = NodeVerify()

    pol = policy.invoke("フォーム送信して受付完了まで。")
    assert isinstance(pol, dict)
    assert pol.get("allowed") is True

    dom = capture_dom_snapshot()
    plan = planner.invoke(dom=dom, instruction="フォーム送信して受付完了まで。")
    assert isinstance(plan, dict)
    # Basic planner contract
    assert "patch" in plan and isinstance(plan["patch"], dict)
    assert "draft_template" in plan and isinstance(plan["draft_template"], dict)
    assert "done" in plan

    nav_res = nav.invoke(plan)
    assert isinstance(nav_res, dict)
    assert nav_res.get("status") == "success"
    assert isinstance(nav_res.get("steps"), int)

    ver = verify.invoke(plan)
    assert isinstance(ver, dict)
    assert set(["finalized", "passed"]).issubset(ver.keys())

