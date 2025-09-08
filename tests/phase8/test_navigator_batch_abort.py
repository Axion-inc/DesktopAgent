from app.navigator.runner import NavigatorRunner, BatchErrorType


def test_navigator_aborts_on_domain_drift():
    runner = NavigatorRunner(batch_limit=3)

    actions = [
        {"id": "a1", "type": "goto", "url": "https://trusted.example.com/form"},
        {"id": "a2", "type": "click_by_text", "text": "提出"},
        {"id": "a3", "type": "wait_for_text", "contains": "受付完了", "timeoutMs": 5000},
    ]
    guards = {"allowHosts": ["trusted.example.com"], "risk": ["sends"], "maxRetriesPerStep": 1}
    evidence = {"screenshotEach": True, "domSchemaEach": True}

    # Simulate a drift via runner option
    result = runner.exec(actions, guards, evidence, simulate_domain="malicious.example.com")

    assert result["status"] == "halted"
    assert result["error_type"] == BatchErrorType.DOMAIN_MISMATCH

