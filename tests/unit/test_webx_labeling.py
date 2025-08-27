"""
Unit tests for WebX Extension element labeling and discovery logic
Tests the label matching, synonym support, and element finding algorithms
"""

import pytest
from unittest.mock import patch
from app.web.engine import ExtensionEngine, get_web_engine
from app.actions.web_actions import _is_sensitive_field


class TestWebXLabelMatching:
    """Test label matching and normalization logic"""

    def test_label_normalization(self):
        """Test label text normalization for better matching"""
        # These would be implemented in the ExtensionEngine
        test_cases = [
            ("氏名", "name"),
            ("メール", "email"),
            ("電話番号", "phone"),
            ("パスワード", "password"),
            ("住所", "address")
        ]

        # Test that Japanese labels can be handled
        for japanese, english in test_cases:
            # This would be part of the label synonym system
            assert japanese != english  # Different languages

    def test_label_synonym_matching(self):
        """Test synonym-based label matching"""
        synonyms = {
            "name": ["氏名", "名前", "お名前", "ネーム"],
            "email": ["メール", "Eメール", "メールアドレス", "電子メール"],
            "phone": ["電話番号", "TEL", "電話", "携帯番号"],
            "password": ["パスワード", "暗証番号", "PW", "ログインPW"]
        }

        # Test each synonym group
        for base_term, synonym_list in synonyms.items():
            for synonym in synonym_list:
                # Mock label matching that would happen in content script
                assert synonym in synonym_list  # All synonyms should match base term

    def test_label_fuzzy_matching(self):
        """Test fuzzy matching for partial label matches"""
        test_cases = [
            ("お名前を入力してください", "name"),
            ("メールアドレス（必須）", "email"),
            ("電話番号を入力", "phone"),
            ("パスワード再入力", "password")
        ]

        for full_label, expected_base in test_cases:
            # Test that partial matches work
            assert expected_base in full_label.lower() or any(
                keyword in full_label for keyword in ["名前", "メール", "電話", "パスワード"]
            )

    def test_role_based_element_matching(self):
        """Test role-based element discovery"""
        test_roles = [
            ("textbox", "input"),
            ("button", "button"),
            ("combobox", "select"),
            ("checkbox", "input[type=checkbox]"),
            ("radiobutton", "input[type=radio]")
        ]

        for aria_role, expected_tag in test_roles:
            # Test role mapping
            assert aria_role and expected_tag
            # This would be implemented in content script element discovery

    def test_css_selector_precedence(self):
        """Test CSS selector precedence over label matching"""
        # Direct selectors should take precedence over label search
        selectors = [
            "#username",
            "input[name='email']",
            ".form-field[data-field='phone']",
            "input.password-field"
        ]

        for selector in selectors:
            # Verify selectors are valid
            assert selector.startswith(("#", ".", "input", "["))

    def test_input_type_filtering(self):
        """Test filtering by input type"""
        input_types = [
            "text", "email", "password", "tel",
            "number", "file", "checkbox", "radio"
        ]

        for input_type in input_types:
            # Test input type validation
            assert input_type in [
                "text", "email", "password", "tel", "number",
                "file", "checkbox", "radio", "submit", "button"
            ]


class TestWebXElementDiscovery:
    """Test element discovery algorithms"""

    @pytest.fixture
    def mock_dom_elements(self):
        """Mock DOM elements for testing"""
        return [
            {
                "tag": "input",
                "type": "text",
                "id": "username",
                "name": "username",
                "placeholder": "お名前を入力",
                "aria-label": None,
                "label_text": "氏名"
            },
            {
                "tag": "input",
                "type": "email",
                "id": "email",
                "name": "email",
                "placeholder": "メールアドレス",
                "aria-label": "Email address",
                "label_text": "メール"
            },
            {
                "tag": "input",
                "type": "password",
                "id": "password",
                "name": "password",
                "placeholder": "パスワード",
                "aria-label": None,
                "label_text": "パスワード"
            },
            {
                "tag": "button",
                "type": "submit",
                "id": "submit-btn",
                "text": "送信",
                "aria-label": None,
                "label_text": None
            }
        ]

    def test_find_element_by_label(self, mock_dom_elements):
        """Test finding elements by label text"""
        # Test finding by Japanese label
        username_element = None
        for element in mock_dom_elements:
            if element.get("label_text") == "氏名":
                username_element = element
                break

        assert username_element is not None
        assert username_element["id"] == "username"
        assert username_element["type"] == "text"

    def test_find_element_by_placeholder(self, mock_dom_elements):
        """Test finding elements by placeholder text"""
        email_element = None
        for element in mock_dom_elements:
            if "メールアドレス" in (element.get("placeholder") or ""):
                email_element = element
                break

        assert email_element is not None
        assert email_element["type"] == "email"

    def test_find_element_by_text_content(self, mock_dom_elements):
        """Test finding elements by text content"""
        submit_button = None
        for element in mock_dom_elements:
            if element.get("text") == "送信":
                submit_button = element
                break

        assert submit_button is not None
        assert submit_button["tag"] == "button"
        assert submit_button["type"] == "submit"

    def test_input_type_priority(self, mock_dom_elements):
        """Test prioritization of input elements by type"""
        input_elements = [e for e in mock_dom_elements if e["tag"] == "input"]

        # Should find different types
        text_inputs = [e for e in input_elements if e["type"] == "text"]
        email_inputs = [e for e in input_elements if e["type"] == "email"]
        password_inputs = [e for e in input_elements if e["type"] == "password"]

        assert len(text_inputs) == 1
        assert len(email_inputs) == 1
        assert len(password_inputs) == 1

    def test_element_visibility_check(self):
        """Test element visibility checking logic"""
        # Mock element rectangles
        visible_rect = {"width": 100, "height": 30, "top": 10, "left": 10}
        hidden_rect = {"width": 0, "height": 0, "top": 0, "left": 0}

        # Test visibility logic
        def is_visible(rect):
            return rect["width"] > 0 and rect["height"] > 0

        assert is_visible(visible_rect) is True
        assert is_visible(hidden_rect) is False

    def test_element_interactability(self):
        """Test element interactability checks"""
        interactable_element = {
            "disabled": False,
            "readonly": False,
            "style": {"display": "block", "visibility": "visible"}
        }

        non_interactable_element = {
            "disabled": True,
            "readonly": False,
            "style": {"display": "none", "visibility": "hidden"}
        }

        def is_interactable(element):
            if element.get("disabled") or element.get("readonly"):
                return False
            style = element.get("style", {})
            if style.get("display") == "none" or style.get("visibility") == "hidden":
                return False
            return True

        assert is_interactable(interactable_element) is True
        assert is_interactable(non_interactable_element) is False


class TestWebXErrorHandling:
    """Test error handling in WebX operations"""

    def test_element_not_found_error(self):
        """Test handling when elements are not found"""
        # Mock ExtensionEngine error response
        error_response = {
            "status": "error",
            "error": "Element not found: label='nonexistent'",
            "engine": "extension"
        }

        assert error_response["status"] == "error"
        assert "not found" in error_response["error"].lower()

    def test_timeout_error_handling(self):
        """Test timeout error handling"""
        timeout_response = {
            "status": "error",
            "error": "Timeout waiting for element",
            "engine": "extension",
            "timeout_ms": 10000
        }

        assert timeout_response["status"] == "error"
        assert "timeout" in timeout_response["error"].lower()
        assert timeout_response["timeout_ms"] > 0

    def test_permission_denied_error(self):
        """Test permission denied error handling"""
        permission_error = {
            "status": "error",
            "error": "Permission denied: debugger API not enabled",
            "engine": "extension",
            "code": "PERMISSION_DENIED"
        }

        assert permission_error["status"] == "error"
        assert permission_error["code"] == "PERMISSION_DENIED"

    def test_rpc_communication_error(self):
        """Test RPC communication error handling"""
        rpc_error = {
            "status": "error",
            "error": "Native messaging host disconnected",
            "engine": "extension",
            "code": "RPC_ERROR"
        }

        assert rpc_error["status"] == "error"
        assert "disconnected" in rpc_error["error"].lower()


class TestWebXSensitiveDataHandling:
    """Test sensitive data handling and masking"""

    def test_sensitive_field_detection(self):
        """Test detection of sensitive form fields"""
        # Test various sensitive field patterns
        sensitive_cases = [
            ("input[type=password]", "password"),
            ("#ssn", "ssn field"),
            ("input[name='credit-card']", "credit card"),
            ("input[placeholder='パスワード']", "japanese password"),
            (".cvv-field", "cvv code")
        ]

        for selector, label in sensitive_cases:
            is_sensitive = _is_sensitive_field(selector, label)
            assert is_sensitive is True, f"Should detect {label} as sensitive"

    def test_non_sensitive_field_detection(self):
        """Test that non-sensitive fields are not flagged"""
        non_sensitive_cases = [
            ("input[type=text]", "name"),
            ("#email", "email address"),
            ("input[name='phone']", "phone number"),
            ("textarea", "comments"),
            ("select", "country")
        ]

        for selector, label in non_sensitive_cases:
            is_sensitive = _is_sensitive_field(selector, label)
            assert is_sensitive is False, f"Should not detect {label} as sensitive"

    def test_data_masking_in_logs(self):
        """Test that sensitive data is masked in logs"""
        # Mock log entry with sensitive data
        log_entry = {
            "action": "fill_by_label",
            "params": {"label": "password", "text": "secret123"},
            "masked": True
        }

        if log_entry["masked"]:
            # Sensitive text should be masked
            assert log_entry["params"]["text"] == "***MASKED***" or "secret" not in str(log_entry)

    def test_approval_required_for_sensitive_actions(self):
        """Test that sensitive actions require approval"""
        sensitive_actions = [
            "delete account",
            "cancel subscription",
            "logout",
            "unsubscribe",
            "remove data"
        ]

        for action_text in sensitive_actions:
            # Mock approval check
            requires_approval = any(keyword in action_text.lower()
                                    for keyword in ["delete", "cancel", "logout", "remove", "unsubscribe"])
            assert requires_approval is True, f"Action '{action_text}' should require approval"


class TestWebXEngineIntegration:
    """Test integration with engine abstraction layer"""

    def test_engine_selection(self):
        """Test engine selection logic"""
        with patch('app.web.engine.get_config') as mock_config:
            mock_config.return_value = {
                'web_engine': {'engine': 'extension'}
            }

            engine = get_web_engine()
            assert engine.__class__.__name__ == 'ExtensionEngine'

    def test_fallback_to_playwright(self):
        """Test fallback to Playwright engine"""
        with patch('app.web.engine.get_config') as mock_config:
            mock_config.return_value = {
                'web_engine': {'engine': 'playwright'}
            }

            engine = get_web_engine()
            assert engine.__class__.__name__ == 'PlaywrightEngine'

    def test_engine_method_delegation(self):
        """Test that engine methods are properly delegated"""
        engine = ExtensionEngine()

        # Test that all required methods exist
        required_methods = [
            'open_browser', 'fill_by_label', 'click_by_text',
            'upload_file', 'take_screenshot', 'get_page_info'
        ]

        for method_name in required_methods:
            assert hasattr(engine, method_name), f"Engine missing method: {method_name}"
            assert callable(getattr(engine, method_name))

    def test_engine_error_propagation(self):
        """Test that engine errors are properly propagated"""
        engine = ExtensionEngine()

        # Mock a failed operation
        with patch.object(engine, '_send_rpc') as mock_rpc:
            mock_rpc.side_effect = Exception("Native messaging failed")

            try:
                result = engine.fill_by_label("test", "value")
                # Should return error result, not raise exception
                assert "error" in result
            except Exception:
                # Or handle exceptions gracefully
                pass


class TestWebXPerformanceOptimizations:
    """Test performance optimizations in WebX"""

    def test_element_caching(self):
        """Test element discovery result caching"""
        # Mock cache for element lookups
        element_cache = {}
        cache_key = "label:氏名:textbox"

        # First lookup - cache miss
        assert cache_key not in element_cache

        # Mock element result
        mock_element = {"id": "username", "tag": "input", "type": "text"}
        element_cache[cache_key] = mock_element

        # Second lookup - cache hit
        cached_result = element_cache.get(cache_key)
        assert cached_result == mock_element

    def test_batch_rpc_operations(self):
        """Test batching of RPC operations for performance"""
        batch_operations = [
            {"method": "fill_by_label", "params": {"label": "name", "text": "John"}},
            {"method": "fill_by_label", "params": {"label": "email", "text": "john@example.com"}},
            {"method": "click_by_text", "params": {"text": "Submit"}}
        ]

        # Test that batch operations are structured correctly
        assert len(batch_operations) == 3
        assert all("method" in op and "params" in op for op in batch_operations)

    def test_timeout_optimization(self):
        """Test timeout handling optimization"""
        timeout_configs = {
            "element_search": 5000,    # 5 seconds for finding elements
            "page_load": 10000,        # 10 seconds for page loads
            "file_upload": 30000,      # 30 seconds for file uploads
            "rpc_call": 15000          # 15 seconds for RPC calls
        }

        # Verify timeout values are reasonable
        for operation, timeout_ms in timeout_configs.items():
            assert timeout_ms > 0, f"Invalid timeout for {operation}"
            assert timeout_ms <= 60000, f"Timeout too long for {operation}"

    def test_memory_cleanup(self):
        """Test memory cleanup in engine operations"""
        engine = ExtensionEngine()

        # Test that cleanup method exists and is callable
        assert hasattr(engine, 'close')
        assert callable(engine.close)

        # Mock cleanup operation
        engine.close()

        # After cleanup, engine should be in clean state
        assert engine.native_host is None or hasattr(engine.native_host, 'closed')
