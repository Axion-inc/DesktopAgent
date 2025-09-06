from app.autopilot.runner import AutoRunner


def test_deviation_stops_on_assert_failure(monkeypatch):
    runner = AutoRunner()
    # Simulate a step result with failure from Verifier
    steps = [
        {"status": "success"},
        {"status": "FAIL", "message": "Element not found"},
    ]
    verdict = runner.check_deviation(steps, current_url="https://partner.example.com/form",
                                     expected_domain="partner.example.com")
    assert verdict.should_pause is True
    assert 'verifier' in verdict.reason


def test_deviation_on_domain_drift():
    runner = AutoRunner()
    steps = [{"status": "success"}]
    verdict = runner.check_deviation(steps, current_url="https://evil.example.com/",
                                     expected_domain="partner.example.com")
    assert verdict.should_pause is True
    assert 'domain' in verdict.reason


def test_deviation_on_download_failure():
    runner = AutoRunner()
    steps = [{"status": "success"}]
    verdict = runner.check_deviation(steps, current_url="https://partner.example.com/",
                                     expected_domain="partner.example.com",
                                     downloads_failed=1)
    assert verdict.should_pause is True
    assert 'download' in verdict.reason


def test_deviation_on_retry_exceeded():
    runner = AutoRunner()
    steps = [{"status": "success"}]
    verdict = runner.check_deviation(steps, current_url="https://partner.example.com/",
                                     expected_domain="partner.example.com",
                                     retry_exceeded=True)
    assert verdict.should_pause is True
    assert 'retry' in verdict.reason
