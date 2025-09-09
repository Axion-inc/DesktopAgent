from unittest.mock import patch

from app.navigator.runner import NavigatorRunner, BatchErrorType


def test_exec_batch_contract_error_maps_to_batched_halt():
    runner = NavigatorRunner(batch_limit=2)
    actions = [
        {"id": "a1", "type": "goto", "url": "https://example.com"},
        {"id": "a2", "type": "click_by_text", "text": "提出"},
    ]
    guards = {"allowHosts": ["example.com"], "risk": [], "maxRetriesPerStep": 0}

    # Patch the symbol imported in runner module
    with patch("app.navigator.runner.exec_batch", return_value={"status": "error", "engine": "cdp", "error": "halted"}):
        result = runner.exec(actions, guards, evidence={})
        assert result["status"] == "halted"
        assert result["error_type"] == BatchErrorType.BATCH_HALTED
