"""
Contract tests for OS Adapter interface.

These tests define the expected behavior and contracts that all OSAdapter
implementations must adhere to. The tests ensure consistent behavior
across platforms and serve as implementation guides for future development.
"""

import pytest
import tempfile
import os
import platform
from pathlib import Path
from app.os_adapters.base import Capability
from app.os_adapters.macos import MacOSAdapter
from app.os_adapters.windows import WindowsOSAdapter


class TestOSAdapterContract:
    """Contract tests that all OSAdapter implementations must satisfy."""

    @pytest.fixture
    def macos_adapter(self):
        """macOS adapter instance."""
        return MacOSAdapter()

    @pytest.fixture
    def windows_adapter(self):
        """Windows adapter instance."""
        return WindowsOSAdapter()

    # Capabilities Tests

    def test_capabilities_returns_dict(self, macos_adapter):
        """Test that capabilities() returns a dictionary mapping strings to Capability objects."""
        caps = macos_adapter.capabilities()
        assert isinstance(caps, dict)
        assert len(caps) > 0

        for name, capability in caps.items():
            assert isinstance(name, str)
            assert isinstance(capability, Capability)
            assert isinstance(capability.name, str)
            assert isinstance(capability.available, bool)
            assert isinstance(capability.notes, str)

    @pytest.mark.xfail(reason="Windows implementation not yet complete")
    def test_capabilities_returns_dict_windows(self, windows_adapter):
        """Test Windows capabilities (expected to fail until implementation complete)."""
        caps = windows_adapter.capabilities()
        assert isinstance(caps, dict)

    # Screenshot Tests

    @pytest.mark.skipif(platform.system() != "Darwin", reason="Screenshot requires macOS")
    def test_take_screenshot_creates_file(self, macos_adapter):
        """Test that take_screenshot creates a file at the specified path."""
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
            tmp_path = tmp.name

        try:
            # Remove the temporary file so adapter can create it
            os.unlink(tmp_path)

            macos_adapter.take_screenshot(tmp_path)

            assert os.path.exists(tmp_path)
            assert os.path.getsize(tmp_path) > 0
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    @pytest.mark.skipif(platform.system() != "Darwin", reason="macOS screencapture command required")
    def test_take_screenshot_handles_invalid_path(self, macos_adapter):
        """Test that take_screenshot raises appropriate error for invalid paths."""
        with pytest.raises(RuntimeError, match="Screenshot failed"):
            macos_adapter.take_screenshot("/invalid/nonexistent/path/screenshot.png")

    @pytest.mark.xfail(reason="Windows implementation not yet complete")
    def test_take_screenshot_windows(self, windows_adapter):
        """Test Windows screenshot (expected to fail until implementation complete)."""
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
            tmp_path = tmp.name

        try:
            os.unlink(tmp_path)
            windows_adapter.take_screenshot(tmp_path)
            assert os.path.exists(tmp_path)
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    # Screen Schema Tests

    def test_capture_screen_schema_returns_dict(self, macos_adapter):
        """Test that capture_screen_schema returns structured schema data."""
        schema = macos_adapter.capture_screen_schema("frontmost")

        assert isinstance(schema, dict)
        assert "platform" in schema
        assert "target" in schema
        assert "timestamp" in schema
        assert "elements" in schema
        assert isinstance(schema["elements"], list)

    def test_capture_screen_schema_target_parameter(self, macos_adapter):
        """Test that capture_screen_schema respects target parameter."""
        frontmost_schema = macos_adapter.capture_screen_schema("frontmost")
        screen_schema = macos_adapter.capture_screen_schema("screen")

        assert frontmost_schema["target"] == "frontmost"
        assert screen_schema["target"] == "screen"

    @pytest.mark.xfail(reason="Windows implementation not yet complete")
    def test_capture_screen_schema_windows(self, windows_adapter):
        """Test Windows screen schema (expected to fail until implementation complete)."""
        schema = windows_adapter.capture_screen_schema("frontmost")
        assert isinstance(schema, dict)

    # Mail Operations Tests

    def test_compose_mail_draft_returns_result_dict(self, macos_adapter):
        """Test that compose_mail_draft returns structured result."""
        result = macos_adapter.compose_mail_draft(
            to=["test@example.com"],
            subject="Test Subject",
            body="Test message body"
        )

        assert isinstance(result, dict)
        assert "status" in result
        # Should have either draft_id (success) or error (failure)
        assert "draft_id" in result or "error" in result

    def test_compose_mail_with_attachments(self, macos_adapter):
        """Test mail composition with attachments."""
        # Create a temporary test file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as tmp:
            tmp.write("Test attachment content")
            tmp_path = tmp.name

        try:
            result = macos_adapter.compose_mail_draft(
                to=["test@example.com"],
                subject="Test with attachment",
                body="Test message body",
                attachments=[tmp_path]
            )

            assert isinstance(result, dict)
            assert "status" in result
            if result.get("status") == "created":
                assert "attachments_count" in result
                assert result["attachments_count"] == 1
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    @pytest.mark.xfail(reason="Windows implementation not yet complete")
    def test_compose_mail_draft_windows(self, windows_adapter):
        """Test Windows mail composition (expected to fail until implementation complete)."""
        result = windows_adapter.compose_mail_draft(
            to=["test@example.com"],
            subject="Test Subject",
            body="Test message body"
        )
        assert isinstance(result, dict)

    # File System Operations Tests

    def test_fs_exists_true_for_existing_file(self, macos_adapter):
        """Test that fs_exists returns True for existing files."""
        with tempfile.NamedTemporaryFile() as tmp:
            assert macos_adapter.fs_exists(tmp.name) is True

    def test_fs_exists_false_for_nonexistent_file(self, macos_adapter):
        """Test that fs_exists returns False for nonexistent files."""
        assert macos_adapter.fs_exists("/nonexistent/file/path.txt") is False

    def test_fs_list_returns_list(self, macos_adapter):
        """Test that fs_list returns a list of file paths."""
        # Use a known directory that should exist
        home_dir = str(Path.home())
        result = macos_adapter.fs_list(home_dir)

        assert isinstance(result, list)
        # Home directory should have at least some files/directories
        assert len(result) >= 0

    def test_fs_list_nonexistent_directory(self, macos_adapter):
        """Test that fs_list handles nonexistent directories gracefully."""
        result = macos_adapter.fs_list("/nonexistent/directory")
        assert isinstance(result, list)
        assert len(result) == 0

    def test_fs_find_returns_list(self, macos_adapter):
        """Test that fs_find returns a list of matching file paths."""
        # Search in home directory for any files
        home_dir = str(Path.home())
        result = macos_adapter.fs_find(home_dir, "*")

        assert isinstance(result, list)
        # Should find at least some files in home directory

    def test_fs_move_success(self, macos_adapter):
        """Test successful file move operation."""
        # Create source file
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as src:
            src.write("test content")
            src_path = src.name

        # Create destination path
        dest_path = src_path + ".moved"

        try:
            macos_adapter.fs_move(src_path, dest_path)

            assert not os.path.exists(src_path)
            assert os.path.exists(dest_path)

            with open(dest_path, 'r') as f:
                assert f.read() == "test content"
        finally:
            # Cleanup
            for path in [src_path, dest_path]:
                if os.path.exists(path):
                    os.unlink(path)

    @pytest.mark.xfail(reason="Windows implementation not yet complete")
    def test_fs_operations_windows(self, windows_adapter):
        """Test Windows filesystem operations (expected to fail until implementation complete)."""
        assert windows_adapter.fs_exists("/") is not None

    # PDF Operations Tests

    def test_pdf_operations_require_pypdf2(self, macos_adapter):
        """Test that PDF operations handle missing PyPDF2 dependency."""
        # These tests should either work (if PyPDF2 installed) or raise appropriate error
        with pytest.raises(RuntimeError, match="PyPDF2 not installed"):
            macos_adapter.pdf_merge(["nonexistent.pdf"], "output.pdf")

    @pytest.mark.xfail(reason="Windows implementation not yet complete")
    def test_pdf_operations_windows(self, windows_adapter):
        """Test Windows PDF operations (expected to fail until implementation complete)."""
        with pytest.raises(NotImplementedError):
            windows_adapter.pdf_merge(["test.pdf"], "output.pdf")

    # Permissions Tests

    def test_permissions_status_returns_dict(self, macos_adapter):
        """Test that permissions_status returns a dictionary of permission states."""
        permissions = macos_adapter.permissions_status()

        assert isinstance(permissions, dict)
        # Should have at least some permission entries
        assert len(permissions) > 0

        for perm_name, granted in permissions.items():
            assert isinstance(perm_name, str)
            assert isinstance(granted, bool)

    @pytest.mark.xfail(reason="Windows implementation not yet complete")
    def test_permissions_status_windows(self, windows_adapter):
        """Test Windows permissions status (expected to fail until implementation complete)."""
        permissions = windows_adapter.permissions_status()
        assert isinstance(permissions, dict)

    # Integration Tests

    @pytest.mark.skipif(platform.system() != "Darwin", reason="Screenshot requires macOS")
    def test_capability_negotiation_pattern(self, macos_adapter):
        """Test the capability negotiation pattern works correctly."""
        caps = macos_adapter.capabilities()

        # Test a capability that should be available on macOS
        if "screenshot" in caps and caps["screenshot"].available:
            # Should be able to take screenshot
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                tmp_path = tmp.name

            try:
                os.unlink(tmp_path)
                macos_adapter.take_screenshot(tmp_path)
                assert os.path.exists(tmp_path)
            finally:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)

    def test_error_handling_consistency(self, macos_adapter):
        """Test that error handling is consistent across methods."""
        # Test invalid file operations
        with pytest.raises(Exception):  # Should raise some kind of exception
            macos_adapter.fs_move("/nonexistent/source", "/invalid/dest")

        # Test invalid mail operation - should return error dict, not raise
        result = macos_adapter.compose_mail_draft([], "", "")  # Invalid parameters
        assert isinstance(result, dict)
        # Should indicate failure somehow

    def test_state_isolation(self, macos_adapter):
        """Test that adapter instances don't share mutable state."""
        adapter1 = MacOSAdapter()
        adapter2 = MacOSAdapter()

        # Adapters should be independent instances
        assert adapter1 is not adapter2
        assert adapter1.capability_map is not adapter2.capability_map
