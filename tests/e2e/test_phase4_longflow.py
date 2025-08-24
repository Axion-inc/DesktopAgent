"""
Phase 4 End-to-End Acceptance Tests

These are the "red" tests for TDD - they define the acceptance criteria
and will initially fail until the Phase 4 features are implemented.

Test Coverage:
- Orchestration: Queue/Retry/HITL
- RBAC: Role-based access control
- Secrets: Keychain/Keyring integration
- Scheduler/Triggers: cron, folder watch, webhook
- Failure Clustering: Error analysis and dashboard
- Metrics: New Phase 4 indicators
- Backward Compatibility: Phase 2/3 E2E still pass
"""

import pytest
import os
import time
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
from playwright.sync_api import sync_playwright, Page, BrowserContext

# These imports will initially fail - that's expected for TDD red phase
try:
    from app.orchestrator.queue import QueueManager
    from app.orchestrator.scheduler import CronScheduler  
    from app.orchestrator.watcher import FolderWatcher
    from app.orchestrator.webhook import WebhookHandler
    from app.security.rbac import RBACManager, Role
    from app.security.secrets import SecretsManager
    from app.clustering.failure_analyzer import FailureClusterAnalyzer
except ImportError:
    # Expected during red phase - modules don't exist yet
    pass


@pytest.fixture(scope="session")
def base_url():
    """Base URL for the test server."""
    return os.environ.get("BASE_URL", "http://localhost:8000")


@pytest.fixture(scope="session") 
def browser_context():
    """Shared browser context for all tests."""
    headless = os.environ.get("PLAYWRIGHT_HEADLESS", "true").lower() == "true"
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(
            viewport={'width': 1280, 'height': 720}
        )
        yield context
        context.close()
        browser.close()


@pytest.fixture
def page(browser_context: BrowserContext):
    """Fresh page for each test."""
    page = browser_context.new_page()
    yield page
    page.close()


class TestPhase4Orchestration:
    """Test orchestration features: Queue/Retry/HITL."""
    
    @pytest.mark.xfail(reason="TDD red phase - Queue not implemented yet")
    def test_queue_concurrency_control(self):
        """Test queue manages concurrency by tag."""
        # This will fail initially - QueueManager doesn't exist
        queue = QueueManager()
        
        # Submit 5 runs with same concurrency_tag
        run_ids = []
        for i in range(5):
            run_id = queue.enqueue({
                "template": "test_template.yaml",
                "execution": {
                    "concurrency_tag": "web-form",
                    "priority": 5
                }
            })
            run_ids.append(run_id)
        
        # Only 2 should run simultaneously (configured limit)
        running = queue.get_running_by_tag("web-form")
        assert len(running) <= 2
        
        queued = queue.get_queued_by_tag("web-form")
        assert len(queued) >= 3
    
    @pytest.mark.xfail(reason="TDD red phase - HITL not implemented yet")
    def test_human_confirm_pause_resume(self, page: Page, base_url: str):
        """Test human_confirm pauses run, UI resume continues."""
        # Create test plan with human_confirm
        test_plan = {
            "dsl_version": "1.1",
            "steps": [
                {"log": {"message": "Starting test"}},
                {"human_confirm": {
                    "message": "Continue with dangerous operation?",
                    "timeout_ms": 600000
                }},
                {"log": {"message": "After confirmation"}}
            ]
        }
        
        # Submit run - should pause at human_confirm
        response = page.request.post(f"{base_url}/api/runs", 
                                   data=json.dumps(test_plan))
        run_data = response.json()
        run_id = run_data["run_id"]
        
        # Wait for pause
        time.sleep(2)
        
        # Check run is PAUSED
        page.goto(f"{base_url}/runs/{run_id}")
        assert "PAUSED" in page.content()
        assert "Continue with dangerous operation?" in page.content()
        
        # Click resume button
        page.get_by_role("button", name="Resume").click()
        
        # Should complete
        page.wait_for_load_state("networkidle")
        assert "COMPLETED" in page.content()
        assert "After confirmation" in page.content()
    
    @pytest.mark.xfail(reason="TDD red phase - Auto-retry not implemented yet") 
    def test_idempotent_step_auto_retry(self):
        """Test idempotent steps automatically retry on failure."""
        # This will fail - auto-retry logic doesn't exist
        from app.dsl.runner import Runner
        
        runner = Runner()
        
        # Mock a failing idempotent step
        with patch('app.actions.verification_actions.wait_for_element') as mock_wait:
            mock_wait.side_effect = [Exception("Timeout"), {"found": True}]
            
            result = runner.execute_step({
                "wait_for_element": {
                    "text": "Submit",
                    "timeout_ms": 5000
                }
            })
            
            # Should succeed on retry
            assert result["status"] == "RETRY"  # Succeeded after retry
            assert mock_wait.call_count == 2


class TestPhase4RBAC:
    """Test role-based access control."""
    
    @pytest.mark.xfail(reason="TDD red phase - RBAC not implemented yet")
    def test_viewer_cannot_stop_run(self, page: Page, base_url: str):
        """Test Viewer role cannot perform dangerous operations."""
        # This will fail - RBAC middleware doesn't exist
        
        # Login as viewer
        page.goto(f"{base_url}/auth/login")
        page.fill("#username", "test_viewer")
        page.fill("#password", "password") 
        page.click("button[type=submit]")
        
        # Try to stop a run - should get 403
        page.goto(f"{base_url}/runs/1")
        page.click("button.stop-run")
        
        assert "403" in page.content() or "Forbidden" in page.content()
    
    @pytest.mark.xfail(reason="TDD red phase - RBAC not implemented yet")
    def test_editor_can_approve_runs(self, page: Page, base_url: str):
        """Test Editor role can approve dangerous operations."""
        # Login as editor 
        page.goto(f"{base_url}/auth/login")
        page.fill("#username", "test_editor")  
        page.fill("#password", "password")
        page.click("button[type=submit]")
        
        # Should be able to approve
        page.goto(f"{base_url}/runs/pending-approval")
        approve_button = page.get_by_role("button", name="Approve")
        assert approve_button.is_enabled()
        
        approve_button.click()
        assert "Approved" in page.content()
    
    @pytest.mark.xfail(reason="TDD red phase - RBAC not implemented yet")
    def test_rbac_metrics_tracking(self, page: Page, base_url: str):
        """Test RBAC denials are tracked in metrics."""
        # Generate some RBAC denials
        for i in range(3):
            response = page.request.post(f"{base_url}/api/runs/1/stop",
                                       headers={"Authorization": "Bearer viewer_token"})
            assert response.status == 403
        
        # Check metrics
        metrics_response = page.goto(f"{base_url}/metrics")
        metrics = page.evaluate("() => JSON.parse(document.body.textContent)")
        
        assert "rbac_denied_24h" in metrics
        assert metrics["rbac_denied_24h"] >= 3


class TestPhase4Secrets:
    """Test secrets management integration."""
    
    @pytest.mark.xfail(reason="TDD red phase - Secrets not implemented yet")
    def test_secrets_reference_in_template(self):
        """Test secrets://key reference in templates."""
        # This will fail - SecretsManager doesn't exist
        secrets = SecretsManager()
        
        # Store a test secret
        secrets.store("SMTP_PASSWORD", "secret123")
        
        # Template with secrets reference
        template_content = """
        dsl_version: "1.1"
        steps:
          - log:
              message: "Using password: {{secrets://SMTP_PASSWORD}}"
        """
        
        # Should resolve secret without logging value
        resolved = secrets.resolve_template(template_content)
        assert "secret123" in resolved
        
        # But logs should mask the value
        log_output = secrets.get_resolved_for_logging(template_content)
        assert "***" in log_output
        assert "secret123" not in log_output
    
    @pytest.mark.xfail(reason="TDD red phase - Secrets not implemented yet") 
    def test_secrets_not_leaked_in_error_logs(self, page: Page, base_url: str):
        """Test secrets are not leaked even when steps fail."""
        # Create run with secrets reference that will fail
        test_plan = {
            "dsl_version": "1.1", 
            "steps": [
                {"compose_mail_draft": {
                    "to": ["test@example.com"],
                    "subject": "Test",
                    "body": "Password: {{secrets://SMTP_PASSWORD}}",
                    "smtp_password": "{{secrets://SMTP_PASSWORD}}"
                }}
            ]
        }
        
        # This should fail but not leak the secret
        response = page.request.post(f"{base_url}/api/runs",
                                   data=json.dumps(test_plan))
        run_data = response.json()
        run_id = run_data["run_id"]
        
        # Check run details - secret should be masked
        page.goto(f"{base_url}/runs/{run_id}")
        content = page.content()
        
        # Should see masked value, not actual secret
        assert "***" in content
        assert "secret123" not in content


class TestPhase4Triggers:
    """Test scheduler and trigger functionality."""
    
    @pytest.mark.xfail(reason="TDD red phase - Scheduler not implemented yet")
    def test_cron_scheduled_run(self):
        """Test cron scheduler triggers runs at correct times."""
        # This will fail - CronScheduler doesn't exist
        scheduler = CronScheduler()
        
        # Schedule run for every minute
        schedule_id = scheduler.add_schedule({
            "cron": "* * * * *",  # Every minute
            "template": "weekly_report.yaml",
            "queue": "scheduled",
            "priority": 3
        })
        
        # Fast-forward time and check if run was triggered
        with patch('time.time', return_value=time.time() + 60):
            triggered_runs = scheduler.get_triggered_runs()
            assert len(triggered_runs) >= 1
            assert triggered_runs[0]["template"] == "weekly_report.yaml"
    
    @pytest.mark.xfail(reason="TDD red phase - FolderWatcher not implemented yet")
    def test_folder_watch_trigger(self):
        """Test folder monitoring triggers on new files."""
        # This will fail - FolderWatcher doesn't exist
        watcher = FolderWatcher()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Setup folder watch
            watcher.watch_folder(
                path=temp_dir,
                template="process_pdf.yaml",
                file_pattern="*.pdf"
            )
            
            # Create a new PDF file
            pdf_path = Path(temp_dir) / "test.pdf"
            pdf_path.write_text("fake pdf content")
            
            # Should trigger a run
            time.sleep(1)
            triggered = watcher.get_triggered_runs()
            assert len(triggered) >= 1
            assert "test.pdf" in triggered[0]["variables"]["input_file"]
    
    @pytest.mark.xfail(reason="TDD red phase - Webhook not implemented yet")
    def test_webhook_trigger_with_signature(self, page: Page, base_url: str):
        """Test webhook triggers with HMAC signature verification."""
        # This will fail - webhook handler doesn't exist
        import hmac
        import hashlib
        
        secret = "webhook_secret_key"
        payload = json.dumps({"template": "webhook_test.yaml"})
        signature = hmac.new(
            secret.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()
        
        # Valid signature should trigger run
        response = page.request.post(
            f"{base_url}/hooks/run?template=webhook_test",
            data=payload,
            headers={"X-Hub-Signature-256": f"sha256={signature}"}
        )
        assert response.status == 200
        
        # Invalid signature should return 401
        response = page.request.post(
            f"{base_url}/hooks/run?template=webhook_test", 
            data=payload,
            headers={"X-Hub-Signature-256": "sha256=invalid"}
        )
        assert response.status == 401


class TestPhase4FailureClustering:
    """Test failure clustering and analysis."""
    
    @pytest.mark.xfail(reason="TDD red phase - FailureClusterAnalyzer not implemented yet")
    def test_failure_clustering_dashboard(self, page: Page, base_url: str):
        """Test failure clustering appears in dashboard with trends."""
        # This will fail - clustering not implemented
        
        # Generate different types of failures
        failure_types = [
            "PDF parse error: Invalid header",
            "Web element not found: Submit button", 
            "Permission denied: Screen recording not authorized"
        ]
        
        # Simulate failures (would be done via actual failed runs)
        analyzer = FailureClusterAnalyzer()
        for i, error in enumerate(failure_types):
            for j in range(i + 2):  # Different frequencies
                analyzer.record_failure(error, f"run_{i}_{j}")
        
        # Check dashboard shows clustered failures
        page.goto(f"{base_url}/public/dashboard")
        content = page.content()
        
        assert "Top Failure Clusters" in content
        assert "PDF_PARSE_ERROR" in content
        assert "WEB_ELEMENT_NOT_FOUND" in content
        assert "PERMISSION_BLOCKED" in content
        
        # Should show trend data (sparklines or counts)
        assert "trend" in content.lower() or "count" in content.lower()
    
    @pytest.mark.xfail(reason="TDD red phase - Clustering metrics not implemented yet")
    def test_failure_cluster_metrics(self, page: Page, base_url: str):
        """Test failure clusters appear in metrics endpoint."""
        metrics_response = page.goto(f"{base_url}/metrics")
        metrics = page.evaluate("() => JSON.parse(document.body.textContent)")
        
        assert "top_failure_clusters_24h" in metrics
        assert isinstance(metrics["top_failure_clusters_24h"], list)
        
        if len(metrics["top_failure_clusters_24h"]) > 0:
            cluster = metrics["top_failure_clusters_24h"][0]
            assert "cluster" in cluster
            assert "count" in cluster
            assert "trend_3d" in cluster


class TestPhase4Metrics:
    """Test new Phase 4 metrics integration."""
    
    @pytest.mark.xfail(reason="TDD red phase - Phase 4 metrics not implemented yet")
    def test_new_metrics_in_endpoint(self, page: Page, base_url: str):
        """Test all new Phase 4 metrics appear in /metrics."""
        metrics_response = page.goto(f"{base_url}/metrics")
        metrics = page.evaluate("() => JSON.parse(document.body.textContent)")
        
        # All new Phase 4 metrics should be present
        expected_metrics = [
            "queue_depth_peak_24h",
            "runs_per_hour_24h", 
            "retry_rate_24h",
            "hitl_interventions_24h",
            "scheduled_runs_24h",
            "folder_triggers_24h",
            "webhook_triggers_24h",
            "secrets_lookups_24h",
            "rbac_denied_24h",
            "top_failure_clusters_24h"
        ]
        
        for metric in expected_metrics:
            assert metric in metrics, f"Missing Phase 4 metric: {metric}"
    
    @pytest.mark.xfail(reason="TDD red phase - Dashboard not updated yet")
    def test_dashboard_phase4_metrics(self, page: Page, base_url: str):
        """Test Phase 4 metrics appear in dashboard."""
        page.goto(f"{base_url}/public/dashboard")
        content = page.content()
        
        # Should have Phase 4 metrics section
        assert "Phase 4 Metrics" in content
        
        # Key metrics should be displayed
        assert "Queue Peak Depth" in content
        assert "Retry Rate" in content  
        assert "HITL Interventions" in content
        assert "Scheduled Runs" in content
        
        # Should have more metric cards than before
        metric_elements = page.locator(".metric-value").count()
        assert metric_elements >= 15  # Should have at least 15 metrics now


class TestPhase4BackwardCompatibility:
    """Test Phase 4 doesn't break existing functionality."""
    
    def test_phase2_e2e_still_passes(self, page: Page, base_url: str):
        """Test existing Phase 2 E2E tests still pass."""
        # This should pass immediately - backward compatibility
        page.goto(f"{base_url}/mock/form")
        page.wait_for_load_state("networkidle")
        
        # Fill form (Phase 2 functionality)
        page.get_by_label("氏名").fill("後方互換テスト")
        page.get_by_label("メール").fill("compat@test.com")
        page.get_by_label("件名").fill("Phase 4 後方互換")
        page.get_by_label("本文").fill("Phase 2の機能が引き続き動作することを確認")
        
        page.get_by_role("button", name="送信").click()
        page.wait_for_load_state("networkidle")
        
        # Should still work
        assert "送信完了" in page.content()
    
    def test_existing_templates_still_work(self):
        """Test existing YAML templates work without modification."""
        # Should pass - no breaking changes to DSL
        from app.dsl.validator import validate_plan
        
        # Existing Phase 2/3 template should validate
        existing_plan = {
            "dsl_version": "1.1",
            "steps": [
                {"open_browser": {"url": "https://example.com"}},
                {"fill_by_label": {"label": "Name", "text": "Test"}},
                {"assert_text": {"contains": "Success"}}
            ]
        }
        
        # Should not raise validation errors
        result = validate_plan(existing_plan)
        assert result["valid"] is True


class TestPhase4Integration:
    """Integration tests combining multiple Phase 4 features."""
    
    @pytest.mark.xfail(reason="TDD red phase - Full integration not implemented yet")
    def test_full_phase4_workflow(self, page: Page, base_url: str):
        """Test complete Phase 4 workflow: Schedule → Queue → HITL → Complete."""
        # This is the ultimate integration test
        
        # 1. Schedule a run with execution policy
        schedule_config = {
            "cron": "0 9 * * 1",  # Every Monday 9 AM
            "template": "weekly_report.yaml",
            "execution": {
                "queue": "reports",
                "priority": 7,
                "concurrency_tag": "pdf-processing",
                "retry": {
                    "attempts": 2,
                    "backoff_ms": 10000,
                    "only_idempotent": True
                }
            }
        }
        
        # 2. Trigger the schedule
        response = page.request.post(f"{base_url}/api/schedules",
                                   data=json.dumps(schedule_config))
        assert response.status == 201
        
        # 3. Should be queued with correct priority
        page.goto(f"{base_url}/admin/queue")
        assert "reports" in page.content()
        assert "priority: 7" in page.content()
        
        # 4. When run starts, should pause at human_confirm
        time.sleep(5)  # Let it start
        runs_response = page.request.get(f"{base_url}/api/runs?status=PAUSED")
        paused_runs = runs_response.json()
        assert len(paused_runs) >= 1
        
        # 5. Resume via UI (requires Editor role)
        run_id = paused_runs[0]["id"]
        page.goto(f"{base_url}/runs/{run_id}")
        page.get_by_role("button", name="Resume").click()
        
        # 6. Should complete successfully
        page.wait_for_load_state("networkidle")
        assert "COMPLETED" in page.content()
        
        # 7. Metrics should reflect the activity
        metrics_response = page.goto(f"{base_url}/metrics")
        metrics = page.evaluate("() => JSON.parse(document.body.textContent)")
        
        assert metrics["scheduled_runs_24h"] >= 1
        assert metrics["hitl_interventions_24h"] >= 1
        assert metrics["queue_depth_peak_24h"] >= 1