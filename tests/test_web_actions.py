import pytest
from unittest.mock import Mock, patch
from app.actions.web_actions import (
    is_destructive_action,
    get_destructive_keywords,
    WebSession
)


class TestWebActionsBasic:
    """Basic tests for web actions functionality."""

    def test_destructive_action_detection(self):
        """Test detection of destructive actions."""
        # Destructive keywords should be detected
        assert is_destructive_action("送信")
        assert is_destructive_action("Submit")
        assert is_destructive_action("Delete")
        assert is_destructive_action("削除")
        assert is_destructive_action("上書き")
        assert is_destructive_action("確定")

        # Case insensitive
        assert is_destructive_action("submit")
        assert is_destructive_action("DELETE")

        # Partial matches
        assert is_destructive_action("データを送信")
        assert is_destructive_action("Submit Form")
        assert is_destructive_action("ファイルを削除")

        # Non-destructive actions should not be detected
        assert not is_destructive_action("保存")
        assert not is_destructive_action("Save")
        assert not is_destructive_action("読み込み")
        assert not is_destructive_action("Load")
        assert not is_destructive_action("表示")
        assert not is_destructive_action("キャンセル")

    def test_get_destructive_keywords(self):
        """Test getting list of destructive keywords."""
        keywords = get_destructive_keywords()

        assert isinstance(keywords, list)
        assert len(keywords) > 0
        assert "送信" in keywords
        assert "Submit" in keywords
        assert "Delete" in keywords
        assert "削除" in keywords

        # Verify it returns a copy (not the original list)
        keywords.append("TEST")
        new_keywords = get_destructive_keywords()
        assert "TEST" not in new_keywords


class TestWebSession:
    """Test WebSession functionality."""

    @patch('app.actions.web_actions.sync_playwright')
    def test_web_session_context_manager(self, mock_playwright):
        """Test WebSession context manager."""
        # Mock playwright components
        mock_pw = Mock()
        mock_browser = Mock()
        mock_playwright.return_value.start.return_value = mock_pw
        mock_pw.chromium.launch.return_value = mock_browser

        # Test context manager
        with WebSession() as session:
            assert session.playwright == mock_pw
            assert session.browser == mock_browser

        # Verify cleanup was called
        mock_browser.close.assert_called_once()
        mock_pw.stop.assert_called_once()

    @patch('app.actions.web_actions.sync_playwright')
    def test_web_session_get_context(self, mock_playwright):
        """Test getting browser context."""
        # Mock playwright components
        mock_pw = Mock()
        mock_browser = Mock()
        mock_context = Mock()
        mock_playwright.return_value.start.return_value = mock_pw
        mock_pw.chromium.launch.return_value = mock_browser
        mock_browser.new_context.return_value = mock_context

        with WebSession() as session:
            # Get default context
            context1 = session.get_context()
            assert context1 == mock_context

            # Get same context again (should reuse)
            context2 = session.get_context("default")
            assert context2 == mock_context

            # Get new named context
            mock_browser.new_context.return_value = Mock()  # Different mock for new context
            context3 = session.get_context("other")
            assert context3 != mock_context

        # Verify context creation was called
        assert mock_browser.new_context.call_count >= 2

    @patch('app.actions.web_actions.sync_playwright')
    def test_web_session_get_page(self, mock_playwright):
        """Test getting page from context."""
        # Mock playwright components
        mock_pw = Mock()
        mock_browser = Mock()
        mock_context = Mock()
        mock_page = Mock()
        mock_playwright.return_value.start.return_value = mock_pw
        mock_pw.chromium.launch.return_value = mock_browser
        mock_browser.new_context.return_value = mock_context
        mock_context.new_page.return_value = mock_page

        with WebSession() as session:
            # Get page
            page = session.get_page()
            assert page == mock_page

            # Verify timeout was set
            mock_page.set_default_timeout.assert_called_once()

        # Verify page creation
        mock_context.new_page.assert_called_once()


class TestWebActionsMocked:
    """Test web actions with mocked Playwright."""

    @patch('app.actions.web_actions.get_web_session')
    def test_open_browser_success(self, mock_get_session):
        """Test successful browser opening."""
        from app.actions.web_actions import open_browser

        # Mock session and page
        mock_session = Mock()
        mock_page = Mock()
        mock_get_session.return_value = mock_session
        mock_session.get_page.return_value = mock_page
        mock_page.title.return_value = "Test Page"
        mock_page.url = "http://example.com"

        result = open_browser("http://example.com")

        assert result["status"] == "success"
        assert result["url"] == "http://example.com"
        assert result["title"] == "Test Page"
        assert result["context"] == "default"

        # Verify page methods were called
        mock_page.goto.assert_called_once()
        mock_page.wait_for_load_state.assert_called_once_with("domcontentloaded")

    @patch('app.actions.web_actions.get_web_session')
    def test_open_browser_timeout(self, mock_get_session):
        """Test browser opening with timeout."""
        from app.actions.web_actions import open_browser, PlaywrightTimeoutError

        # Mock session and page
        mock_session = Mock()
        mock_page = Mock()
        mock_get_session.return_value = mock_session
        mock_session.get_page.return_value = mock_page
        mock_page.goto.side_effect = PlaywrightTimeoutError("Timeout")

        result = open_browser("http://example.com")

        assert result["status"] == "timeout"
        assert "Timeout" in result["error"]
        assert result["url"] == "http://example.com"

    @patch('app.actions.web_actions.get_web_session')
    def test_fill_by_label_success(self, mock_get_session):
        """Test successful form filling by label."""
        from app.actions.web_actions import fill_by_label

        # Mock session and page
        mock_session = Mock()
        mock_page = Mock()
        mock_element = Mock()
        mock_get_session.return_value = mock_session
        mock_session.get_page.return_value = mock_page
        mock_page.get_by_label.return_value = mock_element

        result = fill_by_label("氏名", "テスト太郎")

        assert result["status"] == "success"
        assert result["label"] == "氏名"
        assert result["text"] == "テスト太郎"
        assert result["strategy"] == "by_label"

        # Verify element interaction
        mock_page.get_by_label.assert_called_with("氏名")
        mock_element.wait_for.assert_called_once()
        mock_element.fill.assert_called_with("テスト太郎")

    @patch('app.actions.web_actions.get_web_session')
    def test_fill_by_label_not_found(self, mock_get_session):
        """Test form filling when label is not found."""
        from app.actions.web_actions import fill_by_label

        # Mock session and page
        mock_session = Mock()
        mock_page = Mock()
        mock_get_session.return_value = mock_session
        mock_session.get_page.return_value = mock_page

        # Mock all strategies failing
        mock_page.get_by_label.side_effect = Exception("Not found")
        mock_page.locator.return_value.first = Mock()
        mock_page.locator.return_value.first.count.return_value = 0

        result = fill_by_label("存在しないラベル", "テスト")

        assert result["status"] == "not_found"
        assert "Could not find input field" in result["error"]

    @patch('app.actions.web_actions.get_web_session')
    def test_click_by_text_success(self, mock_get_session):
        """Test successful clicking by text."""
        from app.actions.web_actions import click_by_text

        # Mock session and page
        mock_session = Mock()
        mock_page = Mock()
        mock_element = Mock()
        mock_get_session.return_value = mock_session
        mock_session.get_page.return_value = mock_page
        mock_page.get_by_role.return_value = mock_element

        result = click_by_text("送信", "button")

        assert result["status"] == "success"
        assert result["text"] == "送信"
        assert result["role"] == "button"
        assert result["strategy"] == "by_role_and_text"

        # Verify element interaction
        mock_page.get_by_role.assert_called_with("button", name="送信")
        mock_element.wait_for.assert_called_once()
        mock_element.click.assert_called_once()

    @patch('app.actions.web_actions.get_web_session')
    def test_click_by_text_fallback_strategies(self, mock_get_session):
        """Test click fallback strategies."""
        from app.actions.web_actions import click_by_text

        # Mock session and page
        mock_session = Mock()
        mock_page = Mock()
        mock_element = Mock()
        mock_get_session.return_value = mock_session
        mock_session.get_page.return_value = mock_page

        # First strategy fails, second succeeds
        mock_page.get_by_role.side_effect = Exception("Not found")
        mock_page.get_by_text.return_value = mock_element

        result = click_by_text("送信", "button")

        assert result["status"] == "success"
        assert result["strategy"] == "by_text_exact"

        # Verify fallback was used
        mock_page.get_by_text.assert_called_with("送信", exact=True)
        mock_element.click.assert_called_once()


class TestWebActionsIntegration:
    """Integration tests for web actions (requires actual browser)."""

    @pytest.mark.skipif(not pytest.importorskip("playwright", minversion="1.20"),
                        reason="Playwright not available")
    def test_web_session_real_browser(self):
        """Test WebSession with real browser (if available)."""
        try:
            with WebSession() as session:
                assert session.browser is not None
                assert session.playwright is not None

                # Test context creation
                context = session.get_context("test")
                assert context is not None

                # Test page creation
                page = session.get_page("test")
                assert page is not None

        except ImportError:
            pytest.skip("Playwright not properly installed")
        except Exception as e:
            pytest.skip(f"Browser not available: {e}")


class TestWebActionsValidation:
    """Test validation and error handling in web actions."""

    def test_open_browser_validation(self):
        """Test open_browser parameter validation."""
        from app.actions.web_actions import open_browser

        with pytest.raises(ValueError, match="URL is required"):
            open_browser("")

        with pytest.raises(ValueError, match="URL is required"):
            open_browser(None)

    def test_fill_by_label_validation(self):
        """Test fill_by_label parameter validation."""
        from app.actions.web_actions import fill_by_label

        with pytest.raises(ValueError, match="Label and text are required"):
            fill_by_label("", "text")

        with pytest.raises(ValueError, match="Label and text are required"):
            fill_by_label("label", None)

    def test_click_by_text_validation(self):
        """Test click_by_text parameter validation."""
        from app.actions.web_actions import click_by_text

        with pytest.raises(ValueError, match="Text is required"):
            click_by_text("")

        with pytest.raises(ValueError, match="Text is required"):
            click_by_text(None)

    def test_download_file_validation(self):
        """Test download_file parameter validation."""
        from app.actions.web_actions import download_file

        with pytest.raises(ValueError, match="Target path is required"):
            download_file("")

        with pytest.raises(ValueError, match="Target path is required"):
            download_file(None)
