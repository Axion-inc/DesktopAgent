from app.planner import set_planner_enabled

from app.planner import __all__ as _  # ensure package loads

from app.planner import __all__

from app.planner import l1 as _l1  # type: ignore

from app.planner.schema import PLANNER_REQUEST_SCHEMA, PLANNER_RESPONSE_SCHEMA
from app.planner.api import plan_with_llm_stub
from app.planner.apply_patch import apply_patch


def test_llm_planner_outputs_patch_and_draft():
    req = {
        "instruction": "フォーム送信して受付完了まで。送信は承認待ち",
        "dom": {"schema": {}, "tab": {}, "scroll": {}, "screenshot": "<redacted>"},
        "history": [{"step": "fill", "ok": True}],
        "capabilities": ["webx", "pdf", "mail_draft"],
    }
    resp = plan_with_llm_stub(req)
    assert "patch" in resp and "draft_template" in resp
    # confidence should be reasonably high for explicit instruction
    patch = resp["patch"]
    assert patch.get("replace_text")
    assert resp.get("done") is False


def test_apply_patch_blocks_dangerous_actions():
    base_plan = {"dsl_version": "1.1", "steps": [{"click_by_text": {"text": "提出"}}]}
    patch = {
        "add_steps": [
            {"delete_files": {"path": "/"}},  # dangerous, should be blocked
        ]
    }
    ok, updated, msg = apply_patch(base_plan, patch)
    assert ok is False
    assert "danger" in msg.lower()

