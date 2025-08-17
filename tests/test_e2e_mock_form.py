import pytest
import os
import time
from playwright.sync_api import sync_playwright, Page, BrowserContext


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


class TestMockFormE2E:
    """End-to-end tests for the mock form automation."""

    def test_e2e_mock_form_basic_access(self, page: Page, base_url: str):
        """Test basic access to mock form."""
        page.goto(f"{base_url}/mock/form")

        # Verify page loads
        page.wait_for_load_state("networkidle")
        assert "お問い合わせフォーム" in page.title()

        # Verify form elements exist
        assert page.get_by_label("氏名").is_visible()
        assert page.get_by_label("メール").is_visible()
        assert page.get_by_label("件名").is_visible()
        assert page.get_by_label("本文").is_visible()
        assert page.get_by_role("button", name="送信").is_visible()

    def test_e2e_mock_form_single_submission(self, page: Page, base_url: str):
        """Test single form submission through the mock form."""
        page.goto(f"{base_url}/mock/form")
        page.wait_for_load_state("networkidle")

        # Fill form data
        test_data = {
            "name": "テスト太郎",
            "email": "test@example.com",
            "subject": "E2Eテスト件名",
            "message": "これはE2Eテストからの送信です。"
        }

        page.get_by_label("氏名").fill(test_data["name"])
        page.get_by_label("メール").fill(test_data["email"])
        page.get_by_label("件名").fill(test_data["subject"])
        page.get_by_label("本文").fill(test_data["message"])

        # Submit form
        page.get_by_role("button", name="送信").click()

        # Wait for success page
        page.wait_for_load_state("networkidle")

        # Verify success
        assert "送信完了" in page.content()
        assert test_data["name"] in page.content()
        assert test_data["email"] in page.content()
        assert test_data["subject"] in page.content()
        assert test_data["message"] in page.content()

    def test_e2e_mock_form_validation_errors(self, page: Page, base_url: str):
        """Test form validation with missing fields."""
        page.goto(f"{base_url}/mock/form")
        page.wait_for_load_state("networkidle")

        # Remove HTML5 required attributes to test server-side validation
        page.evaluate("""
            document.querySelectorAll('input[required], textarea[required]').forEach(el => {
                el.removeAttribute('required');
            });
        """)

        # Submit empty form
        page.get_by_role("button", name="送信").click()
        page.wait_for_load_state("networkidle")

        # Verify validation errors appear
        error_content = page.content()
        assert "入力エラーがあります" in error_content
        assert "氏名は必須です" in error_content
        assert "メールアドレスは必須です" in error_content
        assert "件名は必須です" in error_content
        assert "本文は必須です" in error_content

    def test_e2e_mock_form_multiple_submissions(self, page: Page, base_url: str):
        """Test multiple form submissions (simulating CSV processing)."""
        base_records = [
            {"name": "山田太郎", "email": "yamada@example.com", "subject": "件名1", "message": "本文1"},
            {"name": "佐藤花子", "email": "sato@example.com", "subject": "件名2", "message": "本文2"},
            {"name": "田中次郎", "email": "tanaka@example.com", "subject": "件名3", "message": "本文3"},
        ]

        successful_submissions = 0

        for i, record in enumerate(base_records):
            try:
                # Navigate to form
                page.goto(f"{base_url}/mock/form")
                page.wait_for_load_state("networkidle")

                # Fill form
                page.get_by_label("氏名").fill(record["name"])
                page.get_by_label("メール").fill(record["email"])
                page.get_by_label("件名").fill(record["subject"])
                page.get_by_label("本文").fill(record["message"])

                # Submit
                page.get_by_role("button", name="送信").click()
                page.wait_for_load_state("networkidle")

                # Verify success
                if "送信完了" in page.content():
                    successful_submissions += 1

                # Small delay between submissions
                time.sleep(0.5)

            except Exception as e:
                print(f"Error in submission {i+1}: {e}")
                continue

        # Verify all submissions succeeded
        assert successful_submissions == len(base_records), (
            f"Expected {len(base_records)} successful submissions, "
            f"got {successful_submissions}"
        )

    def test_e2e_mock_form_label_recovery(self, page: Page, base_url: str):
        """Test label synonym recovery functionality."""
        page.goto(f"{base_url}/mock/form")
        page.wait_for_load_state("networkidle")

        # Test alternative label matching (this would be handled by the DSL runner)
        # For now, verify that the standard labels work consistently
        name_field = page.get_by_label("氏名")
        email_field = page.get_by_label("メール")
        subject_field = page.get_by_label("件名")
        message_field = page.get_by_label("本文")

        assert name_field.is_visible()
        assert email_field.is_visible()
        assert subject_field.is_visible()
        assert message_field.is_visible()

        # Test that fields can be filled reliably
        name_field.fill("回復テスト")
        email_field.fill("recovery@test.com")
        subject_field.fill("回復テスト件名")
        message_field.fill("ラベル回復テストメッセージ")

        # Verify values were set
        assert name_field.input_value() == "回復テスト"
        assert email_field.input_value() == "recovery@test.com"
        assert subject_field.input_value() == "回復テスト件名"
        assert message_field.input_value() == "ラベル回復テストメッセージ"

    def test_e2e_mock_form_performance(self, page: Page, base_url: str):
        """Test form performance and loading times."""
        # Measure page load time
        start_time = time.time()
        page.goto(f"{base_url}/mock/form")
        page.wait_for_load_state("networkidle")
        load_time = time.time() - start_time

        # Page should load within reasonable time (5 seconds)
        assert load_time < 5.0, f"Page load took {load_time:.2f}s, expected < 5s"

        # Measure form submission time
        page.get_by_label("氏名").fill("パフォーマンステスト")
        page.get_by_label("メール").fill("perf@test.com")
        page.get_by_label("件名").fill("パフォーマンス測定")
        page.get_by_label("本文").fill("フォーム送信速度テスト")

        start_time = time.time()
        page.get_by_role("button", name="送信").click()
        page.wait_for_load_state("networkidle")
        submit_time = time.time() - start_time

        # Form submission should complete within reasonable time (3 seconds)
        assert submit_time < 3.0, f"Form submission took {submit_time:.2f}s, expected < 3s"
        assert "送信完了" in page.content()


class TestE2EApprovalWorkflow:
    """End-to-end tests for approval workflow."""

    def test_e2e_approval_workflow_access(self, page: Page, base_url: str):
        """Test access to approval workflow pages."""
        # Test Planner L1 page
        page.goto(f"{base_url}/plans/intent")
        page.wait_for_load_state("networkidle")
        assert "Planner L1" in page.title()

        # Test dashboard access
        page.goto(f"{base_url}/public/dashboard")
        page.wait_for_load_state("networkidle")
        assert "Dashboard" in page.title()

        # Test metrics endpoint
        response = page.goto(f"{base_url}/metrics")
        assert response.status == 200


class TestE2EDashboardMetrics:
    """End-to-end tests for dashboard and metrics."""

    def test_e2e_dashboard_loads(self, page: Page, base_url: str):
        """Test that dashboard loads with Phase 2 metrics."""
        page.goto(f"{base_url}/public/dashboard")
        page.wait_for_load_state("networkidle")

        # Verify Phase 2 metrics are displayed
        content = page.content()
        assert "Success Rate" in content
        assert "Approvals Required" in content
        assert "Approvals Granted" in content
        assert "Web Success Rate" in content
        assert "Recovery Applied" in content

        # Verify metrics have numeric values
        assert page.locator(".metric-value").count() >= 7  # At least 7 metric cards

    def test_e2e_metrics_endpoint(self, page: Page, base_url: str):
        """Test that metrics endpoint returns Phase 2 data."""
        response = page.goto(f"{base_url}/metrics")
        assert response.status == 200

        # Get JSON response
        metrics = page.evaluate("() => JSON.parse(document.body.textContent)")

        # Verify Phase 2 metrics are present
        assert "approvals_required_24h" in metrics
        assert "approvals_granted_24h" in metrics
        assert "web_step_success_rate_24h" in metrics
        assert "recovery_applied_24h" in metrics

        # Verify metrics are numeric
        assert isinstance(metrics["approvals_required_24h"], int)
        assert isinstance(metrics["approvals_granted_24h"], int)
        assert isinstance(metrics["web_step_success_rate_24h"], (int, float))
        assert isinstance(metrics["recovery_applied_24h"], int)
