from app.planner.api import plan_with_llm_stub
from app.planner.draft_flow import DraftPipeline


def test_draft_pipeline_enforces_signature_before_execution():
    req = {
        "instruction": "PDFを結合してメール下書き。送信はしない",
        "dom": {"schema": {}, "tab": {}, "scroll": {}, "screenshot": "<redacted>"},
        "history": [],
        "capabilities": ["webx", "pdf", "mail_draft"],
    }
    resp = plan_with_llm_stub(req)
    draft = resp["draft_template"]

    pipe = DraftPipeline()
    # Draft is not executable until signed
    assert pipe.is_executable(draft) is False

    signed = pipe.process_and_sign(draft)
    assert signed.get("signature_verified") is True
    assert pipe.is_executable(signed) is True

