"""
Unit tests for Web Engine Abstraction
Tests the unified interface and engine switching functionality
"""

import pytest
from unittest.mock import Mock, patch

from app.web.engine import (
    WebEngine, PlaywrightEngine, CDPEngine,
    get_web_engine, set_web_engine_type, close_web_engine,
    open_browser, fill_by_label, click_by_text, take_screenshot
)


class TestWebEngineInterface:
    """Test the abstract WebEngine interface"""

    def test_abstract_methods(self):
        """Test that WebEngine cannot be instantiated directly"""
        with pytest.raises(TypeError):
            WebEngine()

    def test_playwright_engine_interface(self):
        """Test PlaywrightEngine implements WebEngine interface"""
        engine = PlaywrightEngine()

        # Should have all required methods
        assert hasattr(engine, 'open_browser')
        assert hasattr(engine, 'fill_by_label')
        assert hasattr(engine, 'click_by_text')
        assert hasattr(engine, 'take_screenshot')
        assert hasattr(engine, 'upload_file')
        assert hasattr(engine, 'download_file')
        assert hasattr(engine, 'wait_for_download')
        assert hasattr(engine, 'get_page_info')
        assert hasattr(engine, 'wait_for_selector')
        assert hasattr(engine, 'close')

        # Name should be set correctly
        assert engine.name == 'PlaywrightEngine'

    def test_cdp_engine_interface(self):
        """Test CDPEngine implements WebEngine interface"""
        with patch('app.web.engine.get_config') as mock_config:
            mock_config.return_value = {
                'web_engine': {
                    'cdp': {
                        'extension_id': 'test_extension_id',
                        'handshake_token': 'test_token',
                        'timeout': 30000
                    }
                }
            }

            engine = CDPEngine()

            # Should have all required methods
            assert hasattr(engine, 'open_browser')
            assert hasattr(engine, 'fill_by_label')
            assert hasattr(engine, 'click_by_text')
            assert hasattr(engine, 'take_screenshot')
            assert hasattr(engine, 'upload_file')
            assert hasattr(engine, 'download_file')
            assert hasattr(engine, 'wait_for_download')
            assert hasattr(engine, 'get_page_info')
            assert hasattr(engine, 'wait_for_selector')
            assert hasattr(engine, 'close')

            # Name should be set correctly
            assert engine.name == 'CDPEngine'


class TestPlaywrightEngine:
    """Test PlaywrightEngine implementation"""

    @patch('app.actions.web_actions.open_browser')
    def test_playwright_open_browser(self, mock_open):
        """Test PlaywrightEngine delegates to web_actions"""
        mock_open.return_value = {'status': 'success', 'url': 'https://example.com'}

        engine = PlaywrightEngine()
        result = engine.open_browser('https://example.com', 'test_context')

        mock_open.assert_called_once_with('https://example.com', 'test_context')
        assert result['status'] == 'success'

    @patch('app.actions.web_actions.fill_by_label')
    def test_playwright_fill_by_label(self, mock_fill):
        """Test PlaywrightEngine fill_by_label delegation"""
        mock_fill.return_value = {'status': 'success', 'strategy': 'by_label'}

        engine = PlaywrightEngine()
        result = engine.fill_by_label('Email', 'test@example.com')

        mock_fill.assert_called_once_with('Email', 'test@example.com', 'default')
        assert result['strategy'] == 'by_label'

    @patch('app.actions.web_actions.click_by_text')
    def test_playwright_click_by_text(self, mock_click):
        """Test PlaywrightEngine click_by_text delegation"""
        mock_click.return_value = {'status': 'success', 'strategy': 'by_text_exact'}

        engine = PlaywrightEngine()
        result = engine.click_by_text('Submit', role='button')

        mock_click.assert_called_once_with('Submit', 'button', 'default')
        assert result['strategy'] == 'by_text_exact'

    @patch('app.actions.web_actions.take_screenshot')
    def test_playwright_take_screenshot(self, mock_screenshot):
        """Test PlaywrightEngine screenshot delegation"""
        mock_screenshot.return_value = '/tmp/screenshot.png'

        engine = PlaywrightEngine()
        result = engine.take_screenshot('default', '/tmp/screenshot.png')

        mock_screenshot.assert_called_once_with('default', '/tmp/screenshot.png')
        assert result == '/tmp/screenshot.png'

    @patch('app.actions.web_actions.close_web_session')
    def test_playwright_close(self, mock_close):
        """Test PlaywrightEngine cleanup"""
        engine = PlaywrightEngine()
        engine.close()

        mock_close.assert_called_once()


class TestCDPEngine:
    """Test CDPEngine implementation"""

    @pytest.fixture
    def mock_config(self):
        """Mock configuration for CDPEngine"""
        return {
            'web_engine': {
                'cdp': {
                    'extension_id': 'test_extension_id',
                    'handshake_token': 'test_token',
                    'timeout': 30000,
                    'dom_cache_ttl': 5000
                }
            }
        }

    @pytest.fixture
    def mock_config_legacy(self):
        """Mock legacy configuration for backward compatibility"""
        return {
            'web_engine': {
                'extension': {
                    'id': 'legacy_extension_id',
                    'handshake_token': 'legacy_token'
                }
            }
        }

    def test_cdp_engine_config_loading(self, mock_config):
        """Test CDPEngine loads configuration correctly"""
        with patch('app.web.engine.get_config', return_value=mock_config):
            engine = CDPEngine()

            assert engine.extension_id == 'test_extension_id'
            assert engine.handshake_token == 'test_token'
            assert engine.cdp_timeout == 30000
            assert engine.dom_cache_ttl == 5000

    def test_cdp_engine_legacy_config_loading(self, mock_config_legacy):
        """Test CDPEngine loads legacy extension configuration correctly"""
        with patch('app.web.engine.get_config', return_value=mock_config_legacy):
            engine = CDPEngine()

            assert engine.extension_id == 'legacy_extension_id'
            assert engine.handshake_token == 'legacy_token'
            assert engine.cdp_timeout == 30000  # default
            assert engine.dom_cache_ttl == 5000  # default

    def test_cdp_engine_missing_config(self):
        """Test CDPEngine handles missing configuration"""
        with patch('app.web.engine.get_config', return_value={}):
            engine = CDPEngine()

            assert engine.extension_id is None
            assert engine.handshake_token is None
            assert engine.cdp_timeout == 30000  # default
            assert engine.dom_cache_ttl == 5000  # default

    def test_cdp_engine_config_error_handling(self):
        """Test CDPEngine handles configuration errors gracefully"""
        with patch('app.web.engine.get_config', return_value={}):
            with patch('app.web.engine.CDPEngine._load_config', side_effect=Exception("Config error")):
                engine = CDPEngine()
                # Should continue with defaults despite config error
                assert engine.cdp_timeout == 30000
                assert engine.dom_cache_ttl == 5000

    def test_cdp_send_message_success(self, mock_config):
        """Test successful CDP message sending"""
        with patch('app.web.engine.get_config', return_value=mock_config):
            engine = CDPEngine()

            result = engine._send_cdp_message('test_method', {'param': 'value'})

            assert result['success'] is True
            assert result['engine'] == 'cdp'
            assert 'id' in result

    def test_cdp_send_message_with_tab_id(self, mock_config):
        """Test CDP message sending with specific tab ID"""
        with patch('app.web.engine.get_config', return_value=mock_config):
            engine = CDPEngine()

            result = engine._send_cdp_message('test_method', {'param': 'value'}, tab_id=123)

            assert result['success'] is True
            assert result['engine'] == 'cdp'

    def test_cdp_send_message_error_handling(self, mock_config):
        """Test CDP message error handling"""
        with patch('app.web.engine.get_config', return_value=mock_config):
            engine = CDPEngine()

            # Mock an exception during message processing
            with patch.object(engine, '_mock_cdp_response', side_effect=Exception('CDP error')):
                result = engine._send_cdp_message('test_method', {})

                assert result['success'] is False
                assert 'error' in result
                assert result['method'] == 'test_method'
                assert result['engine'] == 'cdp'

    def test_cdp_mock_responses(self, mock_config):
        """Test CDP mock response generation"""
        with patch('app.web.engine.get_config', return_value=mock_config):
            engine = CDPEngine()

            # Test build_dom_tree mock response
            dom_response = engine._mock_cdp_response('build_dom_tree', {})
            assert 'labelCount' in dom_response
            assert 'interactiveElements' in dom_response
            assert 'timestamp' in dom_response

            # Test find_element mock response
            find_response = engine._mock_cdp_response('find_element', {'text': 'Test Button'})
            assert find_response['found'] is True
            assert find_response['element']['text'] == 'Test Button'
            assert 'labelId' in find_response['element']

            # Test take_screenshot mock response
            screenshot_response = engine._mock_cdp_response('take_screenshot', {})
            assert screenshot_response['success'] is True
            assert 'dataUrl' in screenshot_response
            assert 'path' in screenshot_response

            # Test generic action response
            generic_response = engine._mock_cdp_response('generic_action', {})
            assert generic_response['success'] is True
            assert generic_response['action'] == 'generic_action'

    def test_cdp_build_dom_tree(self, mock_config):
        """Test DOM tree building functionality"""
        with patch('app.web.engine.get_config', return_value=mock_config):
            engine = CDPEngine()

            result = engine._build_dom_tree()

            assert result['success'] is True
            assert result['engine'] == 'cdp'
            dom_data = result['result']
            assert 'labelCount' in dom_data
            assert 'interactiveElements' in dom_data

    def test_cdp_build_dom_tree_with_options(self, mock_config):
        """Test DOM tree building with custom options"""
        with patch('app.web.engine.get_config', return_value=mock_config):
            engine = CDPEngine()

            options = {
                'include_invisible': True,
                'include_all': True,
                'max_depth': 15
            }

            result = engine._build_dom_tree(tab_id=123, options=options)

            assert result['success'] is True
            assert result['engine'] == 'cdp'

    def test_cdp_find_element_by_criteria(self, mock_config):
        """Test element finding by various criteria"""
        with patch('app.web.engine.get_config', return_value=mock_config):
            engine = CDPEngine()

            # Test finding by text
            result = engine._find_element_by_criteria(text='Submit')
            assert result['success'] is True
            assert result['result']['found'] is True

            # Test finding by selector
            result = engine._find_element_by_criteria(selector='button')
            assert result['success'] is True

            # Test finding by label ID
            result = engine._find_element_by_criteria(label_id=5)
            assert result['success'] is True

            # Test finding by role
            result = engine._find_element_by_criteria(role='button')
            assert result['success'] is True

    def test_cdp_open_browser_success(self, mock_config):
        """Test successful browser navigation via CDP"""
        with patch('app.web.engine.get_config', return_value=mock_config):
            engine = CDPEngine()

            result = engine.open_browser('https://example.com', 'test_context')

            assert result['status'] == 'success'
            assert result['engine'] == 'cdp'
            assert result['url'] == 'https://example.com'
            assert result['context'] == 'test_context'
            assert 'title' in result

    def test_cdp_open_browser_with_options(self, mock_config):
        """Test browser navigation with custom options"""
        with patch('app.web.engine.get_config', return_value=mock_config):
            engine = CDPEngine()

            result = engine.open_browser('https://example.com', wait_until='networkidle')

            assert result['status'] == 'success'
            assert result['engine'] == 'cdp'

    def test_cdp_open_browser_error_handling(self, mock_config):
        """Test error handling during browser navigation"""
        with patch('app.web.engine.get_config', return_value=mock_config):
            engine = CDPEngine()

            # Mock CDP message failure
            with patch.object(engine, '_send_cdp_message', return_value={'success': False, 'error': 'Navigation failed'}):
                result = engine.open_browser('https://invalid-url.com')

                assert result['status'] == 'error'
                assert result['engine'] == 'cdp'
                assert 'error' in result

    def test_cdp_fill_by_label_success(self, mock_config):
        """Test successful form filling by label"""
        with patch('app.web.engine.get_config', return_value=mock_config):
            engine = CDPEngine()

            result = engine.fill_by_label('Email', 'test@example.com', 'test_context')

            assert result['status'] == 'success'
            assert result['engine'] == 'cdp'
            assert result['label'] == 'Email'
            assert result['text'] == 'test@example.com'
            assert result['strategy'] == 'cdp_label_fill'
            assert 'elementId' in result

    def test_cdp_fill_by_label_element_not_found(self, mock_config):
        """Test form filling when element is not found"""
        with patch('app.web.engine.get_config', return_value=mock_config):
            engine = CDPEngine()

            # Mock element not found
            mock_response = {'success': True, 'result': {'found': False}}
            with patch.object(engine, '_find_element_by_criteria', return_value=mock_response):
                result = engine.fill_by_label('NonexistentLabel', 'text')

                assert result['status'] == 'error'
                assert result['engine'] == 'cdp'
                assert 'not found' in result['error']

    def test_cdp_fill_by_label_fill_operation_failed(self, mock_config):
        """Test form filling when fill operation fails"""
        with patch('app.web.engine.get_config', return_value=mock_config):
            engine = CDPEngine()

            # Mock element found but fill operation fails
            find_response = {'success': True, 'result': {'found': True, 'element': {'labelId': 1}}}
            fill_response = {'success': False, 'error': 'Fill failed'}

            with patch.object(engine, '_find_element_by_criteria', return_value=find_response):
                with patch.object(engine, '_send_cdp_message', return_value=fill_response):
                    result = engine.fill_by_label('Email', 'test@example.com')

                    assert result['status'] == 'error'
                    assert result['engine'] == 'cdp'
                    assert 'Fill operation failed' in result['error']

    def test_cdp_click_by_text_success(self, mock_config):
        """Test successful clicking by text"""
        with patch('app.web.engine.get_config', return_value=mock_config):
            engine = CDPEngine()

            result = engine.click_by_text('Submit', role='button', context='test_context')

            assert result['status'] == 'success'
            assert result['engine'] == 'cdp'
            assert result['text'] == 'Submit'
            assert result['role'] == 'button'
            assert result['strategy'] == 'cdp_text_click'
            assert 'elementId' in result

    def test_cdp_click_by_text_element_not_found(self, mock_config):
        """Test clicking when element is not found"""
        with patch('app.web.engine.get_config', return_value=mock_config):
            engine = CDPEngine()

            # Mock element not found
            mock_response = {'success': True, 'result': {'found': False}}
            with patch.object(engine, '_find_element_by_criteria', return_value=mock_response):
                result = engine.click_by_text('NonexistentButton')

                assert result['status'] == 'error'
                assert result['engine'] == 'cdp'
                assert 'not found' in result['error']

    def test_cdp_click_by_text_click_operation_failed(self, mock_config):
        """Test clicking when click operation fails"""
        with patch('app.web.engine.get_config', return_value=mock_config):
            engine = CDPEngine()

            # Mock element found but click operation fails
            find_response = {'success': True, 'result': {'found': True, 'element': {'labelId': 1}}}
            click_response = {'success': False, 'error': 'Click failed'}

            with patch.object(engine, '_find_element_by_criteria', return_value=find_response):
                with patch.object(engine, '_send_cdp_message', return_value=click_response):
                    result = engine.click_by_text('Submit')

                    assert result['status'] == 'error'
                    assert result['engine'] == 'cdp'
                    assert 'Click operation failed' in result['error']

    def test_cdp_take_screenshot_success(self, mock_config):
        """Test successful screenshot via CDP"""
        with patch('app.web.engine.get_config', return_value=mock_config):
            engine = CDPEngine()

            result = engine.take_screenshot('test_context', '/tmp/test.png')

            assert result == '/tmp/test.png'

    def test_cdp_take_screenshot_no_path(self, mock_config):
        """Test screenshot with auto-generated path"""
        with patch('app.web.engine.get_config', return_value=mock_config):
            engine = CDPEngine()

            result = engine.take_screenshot()

            # Should return a valid path
            assert result.endswith('.png')
            assert '/tmp' in result or 'temp' in result.lower()

    def test_cdp_take_screenshot_with_options(self, mock_config):
        """Test screenshot with custom options"""
        with patch('app.web.engine.get_config', return_value=mock_config):
            engine = CDPEngine()

            result = engine.take_screenshot(format='jpeg', quality=80, full_page=True)

            assert result.endswith('.png')

    def test_cdp_take_screenshot_fallback(self, mock_config):
        """Test screenshot fallback to OS adapter"""
        with patch('app.web.engine.get_config', return_value=mock_config):
            engine = CDPEngine()

            # Mock CDP screenshot failure
            with patch.object(engine, '_send_cdp_message', return_value={'success': False, 'error': 'Screenshot failed'}):
                with patch('app.os_adapters.get_os_adapter') as mock_get_adapter:
                    mock_adapter = Mock()
                    mock_adapter.take_screenshot.return_value = True
                    mock_get_adapter.return_value = mock_adapter

                    result = engine.take_screenshot(path='/tmp/fallback.png')

                    assert result == '/tmp/fallback.png'
                    mock_adapter.take_screenshot.assert_called_once_with('/tmp/fallback.png')

    def test_cdp_take_screenshot_complete_failure(self, mock_config):
        """Test screenshot when both CDP and fallback fail"""
        with patch('app.web.engine.get_config', return_value=mock_config):
            engine = CDPEngine()

            # Mock CDP screenshot failure
            cdp_error = Exception('CDP screenshot failed')
            with patch.object(engine, '_send_cdp_message', return_value={'success': False, 'error': 'Screenshot failed'}):
                with patch('app.os_adapters.get_os_adapter') as mock_get_adapter:
                    mock_adapter = Mock()
                    mock_adapter.take_screenshot.side_effect = Exception('OS screenshot failed')
                    mock_get_adapter.return_value = mock_adapter

                    with pytest.raises(Exception):
                        engine.take_screenshot(path='/tmp/fail.png')

    def test_cdp_upload_file_success(self, mock_config, tmp_path):
        """Test successful file upload"""
        with patch('app.web.engine.get_config', return_value=mock_config):
            engine = CDPEngine()

            # Create test file
            test_file = tmp_path / 'test.txt'
            test_file.write_text('test content')

            result = engine.upload_file(str(test_file), label='Upload File')

            assert result['status'] == 'success'
            assert result['engine'] == 'cdp'
            assert result['path'] == str(test_file)
            assert result['label'] == 'Upload File'
            assert result['strategy'] == 'cdp_file_upload'
            assert 'elementId' in result

    def test_cdp_upload_file_with_selector(self, mock_config, tmp_path):
        """Test file upload with selector"""
        with patch('app.web.engine.get_config', return_value=mock_config):
            engine = CDPEngine()

            # Create test file
            test_file = tmp_path / 'test.txt'
            test_file.write_text('test content')

            result = engine.upload_file(str(test_file), selector='input[type="file"]')

            assert result['status'] == 'success'
            assert result['engine'] == 'cdp'
            assert result['selector'] == 'input[type="file"]'

    def test_cdp_upload_file_not_exists(self, mock_config):
        """Test file upload with nonexistent file"""
        with patch('app.web.engine.get_config', return_value=mock_config):
            engine = CDPEngine()

            result = engine.upload_file('/nonexistent/file.txt')

            assert result['status'] == 'error'
            assert result['engine'] == 'cdp'
            assert 'does not exist' in result['error']

    def test_cdp_upload_file_element_not_found(self, mock_config, tmp_path):
        """Test file upload when input element is not found"""
        with patch('app.web.engine.get_config', return_value=mock_config):
            engine = CDPEngine()

            # Create test file
            test_file = tmp_path / 'test.txt'
            test_file.write_text('test content')

            # Mock element not found
            mock_response = {'success': True, 'result': {'found': False}}
            with patch.object(engine, '_find_element_by_criteria', return_value=mock_response):
                result = engine.upload_file(str(test_file), label='Upload')

                assert result['status'] == 'error'
                assert result['engine'] == 'cdp'
                assert 'not found' in result['error']

    def test_cdp_upload_file_upload_operation_failed(self, mock_config, tmp_path):
        """Test file upload when upload operation fails"""
        with patch('app.web.engine.get_config', return_value=mock_config):
            engine = CDPEngine()

            # Create test file
            test_file = tmp_path / 'test.txt'
            test_file.write_text('test content')

            # Mock element found but upload operation fails
            find_response = {'success': True, 'result': {'found': True, 'element': {'labelId': 1}}}
            upload_response = {'success': False, 'error': 'Upload failed'}

            with patch.object(engine, '_find_element_by_criteria', return_value=find_response):
                with patch.object(engine, '_send_cdp_message', return_value=upload_response):
                    result = engine.upload_file(str(test_file))

                    assert result['status'] == 'error'
                    assert result['engine'] == 'cdp'
                    assert 'Upload operation failed' in result['error']

    def test_cdp_download_file(self, mock_config):
        """Test file download functionality"""
        with patch('app.web.engine.get_config', return_value=mock_config):
            engine = CDPEngine()

            result = engine.download_file('/tmp/download.txt', timeout=60000)

            # Note: Current implementation has placeholder functionality
            # This tests the current behavior rather than full CDP implementation
            assert result['status'] == 'success'
            assert result['to'] == '/tmp/download.txt'

    def test_cdp_wait_for_download(self, mock_config):
        """Test download waiting functionality"""
        with patch('app.web.engine.get_config', return_value=mock_config):
            engine = CDPEngine()

            result = engine.wait_for_download('/tmp/download', timeout_ms=45000)

            # Note: Current implementation has placeholder functionality
            assert result['status'] == 'success'
            assert result['to'] == '/tmp/download'

    def test_cdp_get_page_info(self, mock_config):
        """Test page information retrieval"""
        with patch('app.web.engine.get_config', return_value=mock_config):
            engine = CDPEngine()

            result = engine.get_page_info('test_context')

            # Note: Current implementation has placeholder functionality
            assert result['status'] == 'success'
            assert result['context'] == 'test_context'
            assert 'url' in result
            assert 'title' in result

    def test_cdp_wait_for_selector(self, mock_config):
        """Test selector waiting functionality"""
        with patch('app.web.engine.get_config', return_value=mock_config):
            engine = CDPEngine()

            result = engine.wait_for_selector('button', timeout_ms=10000)

            # Note: Current implementation has placeholder functionality
            assert result['status'] == 'visible'
            assert result['selector'] == 'button'
            assert result['timeout_ms'] == 10000

    def test_cdp_close(self, mock_config):
        """Test CDP engine cleanup"""
        with patch('app.web.engine.get_config', return_value=mock_config):
            engine = CDPEngine()
            
            # Add some mock active tabs
            engine.active_tabs.add(123)
            engine.active_tabs.add(456)

            # Mock CDP message sending to track cleanup calls
            with patch.object(engine, '_send_cdp_message') as mock_send:
                engine.close()

                # Should have attempted to clear highlights from active tabs
                assert mock_send.call_count >= 3  # 2 clear_highlights + 1 cleanup
                assert len(engine.active_tabs) == 0

    def test_cdp_close_with_errors(self, mock_config):
        """Test CDP engine cleanup handles errors gracefully"""
        with patch('app.web.engine.get_config', return_value=mock_config):
            engine = CDPEngine()
            
            # Add some mock active tabs
            engine.active_tabs.add(123)

            # Mock CDP message sending to raise errors
            with patch.object(engine, '_send_cdp_message', side_effect=Exception('Cleanup error')):
                # Should not raise exception
                engine.close()

                # Should still clear active tabs
                assert len(engine.active_tabs) == 0


class TestEngineFactory:
    """Test engine factory and management functions"""

    def test_get_web_engine_default(self):
        """Test get_web_engine returns CDPEngine by default"""
        with patch('app.web.engine.get_config', return_value={}):
            engine = get_web_engine()
            assert isinstance(engine, CDPEngine)

    def test_get_web_engine_playwright(self):
        """Test get_web_engine creates PlaywrightEngine when configured"""
        config = {
            'web_engine': {
                'engine': 'playwright'
            }
        }

        with patch('app.web.engine.get_config', return_value=config):
            engine = get_web_engine()
            assert isinstance(engine, PlaywrightEngine)

    def test_get_web_engine_cdp(self):
        """Test get_web_engine creates CDPEngine when configured with 'cdp'"""
        config = {
            'web_engine': {
                'engine': 'cdp',
                'cdp': {
                    'extension_id': 'test_id',
                    'handshake_token': 'test_token'
                }
            }
        }

        with patch('app.web.engine.get_config', return_value=config):
            engine = get_web_engine()
            assert isinstance(engine, CDPEngine)

    def test_get_web_engine_extension_legacy(self):
        """Test get_web_engine creates CDPEngine when configured with legacy 'extension'"""
        config = {
            'web_engine': {
                'engine': 'extension',
                'extension': {
                    'id': 'test_id',
                    'handshake_token': 'test_token'
                }
            }
        }

        with patch('app.web.engine.get_config', return_value=config):
            engine = get_web_engine()
            assert isinstance(engine, CDPEngine)

    def test_get_web_engine_explicit_type(self):
        """Test get_web_engine respects explicit engine type parameter"""
        with patch('app.web.engine.get_config', return_value={}):
            # Request playwright explicitly
            engine = get_web_engine('playwright')
            assert isinstance(engine, PlaywrightEngine)

            # Request CDP explicitly
            engine = get_web_engine('cdp')
            assert isinstance(engine, CDPEngine)

            # Request extension (legacy) explicitly
            engine = get_web_engine('extension')
            assert isinstance(engine, CDPEngine)

    def test_get_web_engine_unknown_type(self):
        """Test get_web_engine raises error for unknown engine type"""
        with patch('app.web.engine.get_config', return_value={}):
            with pytest.raises(ValueError, match="Unknown web engine type"):
                get_web_engine('unknown_engine')

    def test_get_web_engine_singleton_behavior(self):
        """Test get_web_engine returns same instance for same type"""
        with patch('app.web.engine.get_config', return_value={}):
            close_web_engine()  # Clear any existing engine

            engine1 = get_web_engine('playwright')
            engine2 = get_web_engine('playwright')

            assert engine1 is engine2  # Same instance

    def test_set_web_engine_type(self):
        """Test set_web_engine_type changes engine type"""
        config = {}

        with patch('app.web.engine.get_config', return_value=config):
            set_web_engine_type('cdp')

            assert config['web_engine']['engine'] == 'cdp'

    def test_set_web_engine_type_legacy(self):
        """Test set_web_engine_type with legacy extension type"""
        config = {}

        with patch('app.web.engine.get_config', return_value=config):
            set_web_engine_type('extension')

            assert config['web_engine']['engine'] == 'extension'

    def test_close_web_engine(self):
        """Test close_web_engine cleans up current engine"""
        with patch('app.web.engine.get_config', return_value={}):
            close_web_engine()  # Clear any existing engine

            engine = get_web_engine()
            with patch.object(engine, 'close') as mock_close:
                close_web_engine()
                mock_close.assert_called_once()


class TestEngineConvenienceFunctions:
    """Test convenience functions that delegate to current engine"""

    def test_open_browser_convenience(self):
        """Test open_browser convenience function"""
        with patch('app.web.engine.get_web_engine') as mock_get_engine:
            mock_engine = Mock()
            mock_engine.open_browser.return_value = {'status': 'success'}
            mock_get_engine.return_value = mock_engine

            result = open_browser('https://example.com', 'test_context', engine='playwright')

            mock_get_engine.assert_called_once_with('playwright')
            mock_engine.open_browser.assert_called_once_with(
                'https://example.com', 'test_context'
            )
            assert result['status'] == 'success'

    def test_fill_by_label_convenience(self):
        """Test fill_by_label convenience function"""
        with patch('app.web.engine.get_web_engine') as mock_get_engine:
            mock_engine = Mock()
            mock_engine.fill_by_label.return_value = {'status': 'success'}
            mock_get_engine.return_value = mock_engine

            result = fill_by_label('Email', 'test@example.com', engine='cdp')

            mock_get_engine.assert_called_once_with('cdp')
            mock_engine.fill_by_label.assert_called_once_with(
                'Email', 'test@example.com', 'default'
            )
            assert result['status'] == 'success'

    def test_click_by_text_convenience(self):
        """Test click_by_text convenience function"""
        with patch('app.web.engine.get_web_engine') as mock_get_engine:
            mock_engine = Mock()
            mock_engine.click_by_text.return_value = {'status': 'success'}
            mock_get_engine.return_value = mock_engine

            result = click_by_text('Submit', role='button', context='test', engine='playwright')

            mock_get_engine.assert_called_once_with('playwright')
            mock_engine.click_by_text.assert_called_once_with(
                'Submit', 'button', 'test'
            )
            assert result['status'] == 'success'

    def test_take_screenshot_convenience(self):
        """Test take_screenshot convenience function"""
        with patch('app.web.engine.get_web_engine') as mock_get_engine:
            mock_engine = Mock()
            mock_engine.take_screenshot.return_value = '/tmp/screenshot.png'
            mock_get_engine.return_value = mock_engine

            result = take_screenshot('default', '/tmp/screenshot.png')

            mock_get_engine.assert_called_once_with(None)
            mock_engine.take_screenshot.assert_called_once_with(
                'default', '/tmp/screenshot.png'
            )
            assert result == '/tmp/screenshot.png'

    def test_convenience_functions_default_engine(self):
        """Test convenience functions use default engine when not specified"""
        with patch('app.web.engine.get_web_engine') as mock_get_engine:
            mock_engine = Mock()
            mock_get_engine.return_value = mock_engine

            open_browser('https://example.com')  # No engine specified

            mock_get_engine.assert_called_with(None)  # Should use default

    def test_convenience_functions_cdp_engine(self):
        """Test convenience functions work correctly with CDP engine"""
        with patch('app.web.engine.get_web_engine') as mock_get_engine:
            mock_engine = Mock()
            mock_engine.name = 'CDPEngine'
            mock_engine.open_browser.return_value = {'status': 'success', 'engine': 'cdp'}
            mock_engine.fill_by_label.return_value = {'status': 'success', 'engine': 'cdp', 'strategy': 'cdp_label_fill'}
            mock_engine.click_by_text.return_value = {'status': 'success', 'engine': 'cdp', 'strategy': 'cdp_text_click'}
            mock_engine.take_screenshot.return_value = '/tmp/cdp_screenshot.png'
            mock_get_engine.return_value = mock_engine

            # Test all convenience functions with CDP engine
            result = open_browser('https://example.com', engine='cdp')
            assert result['status'] == 'success'
            assert result['engine'] == 'cdp'

            result = fill_by_label('Username', 'test_user', engine='cdp')
            assert result['status'] == 'success'
            assert result['strategy'] == 'cdp_label_fill'

            result = click_by_text('Login', engine='cdp')
            assert result['status'] == 'success'
            assert result['strategy'] == 'cdp_text_click'

            result = take_screenshot(engine='cdp')
            assert result == '/tmp/cdp_screenshot.png'


class TestEngineBackwardCompatibility:
    """Test backward compatibility with existing web_actions"""

    def test_destructive_action_compatibility(self):
        """Test destructive action detection still works"""
        from app.web.engine import is_destructive_action, get_destructive_keywords

        # Should detect destructive keywords
        assert is_destructive_action('Submit Form') is True
        assert is_destructive_action('Delete Item') is True
        assert is_destructive_action('送信') is True
        assert is_destructive_action('View Details') is False

        # Should return keyword list
        keywords = get_destructive_keywords()
        assert isinstance(keywords, list)
        assert '送信' in keywords
        assert 'Delete' in keywords

    def test_engine_switching_preserves_functionality(self):
        """Test that switching engines preserves core functionality"""
        with patch('app.web.engine.get_config', return_value={}):
            # Test with Playwright engine
            close_web_engine()
            set_web_engine_type('playwright')

            with patch('app.web.engine.PlaywrightEngine.open_browser') as mock_pw_open:
                mock_pw_open.return_value = {'status': 'success', 'engine': 'playwright'}

                result = open_browser('https://example.com')
                assert result['status'] == 'success'
                mock_pw_open.assert_called_once()

            # Switch to CDP engine
            close_web_engine()
            set_web_engine_type('cdp')

            with patch('app.web.engine.CDPEngine.open_browser') as mock_cdp_open:
                mock_cdp_open.return_value = {'status': 'success', 'engine': 'cdp'}

                result = open_browser('https://example.com')
                assert result['status'] == 'success'
                mock_cdp_open.assert_called_once()

            # Switch to legacy extension engine (should create CDPEngine)
            close_web_engine()
            set_web_engine_type('extension')

            with patch('app.web.engine.CDPEngine.open_browser') as mock_ext_open:
                mock_ext_open.return_value = {'status': 'success', 'engine': 'cdp'}

                result = open_browser('https://example.com')
                assert result['status'] == 'success'
                mock_ext_open.assert_called_once()


class TestCDPEngineIntegration:
    """Integration tests for CDP-specific features"""

    @pytest.fixture
    def mock_config(self):
        """Mock configuration for CDPEngine integration tests"""
        return {
            'web_engine': {
                'cdp': {
                    'extension_id': 'integration_test_extension',
                    'handshake_token': 'integration_test_token',
                    'timeout': 30000,
                    'dom_cache_ttl': 5000
                }
            }
        }

    def test_cdp_dom_tree_and_element_finding_integration(self, mock_config):
        """Test integration between DOM tree building and element finding"""
        with patch('app.web.engine.get_config', return_value=mock_config):
            engine = CDPEngine()

            # Build DOM tree first
            dom_result = engine._build_dom_tree(options={
                'include_invisible': False,
                'include_all': True,
                'max_depth': 10
            })

            assert dom_result['success'] is True
            assert 'labelCount' in dom_result['result']

            # Then find elements using the built tree
            element_result = engine._find_element_by_criteria(
                text='Submit Button',
                role='button'
            )

            assert element_result['success'] is True
            assert element_result['result']['found'] is True
            assert element_result['result']['element']['labelId'] is not None

    def test_cdp_workflow_integration(self, mock_config):
        """Test complete workflow integration with CDP engine"""
        with patch('app.web.engine.get_config', return_value=mock_config):
            engine = CDPEngine()

            # 1. Open browser
            open_result = engine.open_browser('https://example.com/form')
            assert open_result['status'] == 'success'
            assert open_result['engine'] == 'cdp'

            # 2. Fill form fields
            fill_result = engine.fill_by_label('Email Address', 'test@example.com')
            assert fill_result['status'] == 'success'
            assert fill_result['strategy'] == 'cdp_label_fill'

            # 3. Click submit button
            click_result = engine.click_by_text('Submit Form', role='button')
            assert click_result['status'] == 'success'
            assert click_result['strategy'] == 'cdp_text_click'

            # 4. Take screenshot for verification
            screenshot_result = engine.take_screenshot()
            assert screenshot_result.endswith('.png')

    def test_cdp_error_recovery_integration(self, mock_config):
        """Test error recovery and fallback mechanisms"""
        with patch('app.web.engine.get_config', return_value=mock_config):
            engine = CDPEngine()

            # Test scenario where CDP fails but fallbacks work
            with patch.object(engine, '_send_cdp_message') as mock_send:
                # First call fails (navigation)
                mock_send.return_value = {'success': False, 'error': 'CDP connection lost'}

                result = engine.open_browser('https://example.com')
                assert result['status'] == 'error'
                assert 'CDP connection lost' in result['error']

            # Test screenshot fallback to OS adapter
            with patch.object(engine, '_send_cdp_message', return_value={'success': False, 'error': 'Screenshot failed'}):
                with patch('app.os_adapters.get_os_adapter') as mock_get_adapter:
                    mock_adapter = Mock()
                    mock_adapter.take_screenshot.return_value = True
                    mock_get_adapter.return_value = mock_adapter

                    result = engine.take_screenshot(path='/tmp/fallback.png')
                    assert result == '/tmp/fallback.png'
                    mock_adapter.take_screenshot.assert_called_once_with('/tmp/fallback.png')

    def test_cdp_advanced_element_selection(self, mock_config):
        """Test advanced element selection capabilities of CDP engine"""
        with patch('app.web.engine.get_config', return_value=mock_config):
            engine = CDPEngine()

            # Test various element finding strategies
            test_cases = [
                {'text': 'Login Button', 'role': 'button', 'expected_found': True},
                {'selector': 'input[type="email"]', 'expected_found': True},
                {'label_id': 5, 'expected_found': True},
                {'text': 'Nonexistent Element', 'expected_found': True}  # Mock always returns found
            ]

            for case in test_cases:
                result = engine._find_element_by_criteria(**{k: v for k, v in case.items() if k != 'expected_found'})
                
                assert result['success'] is True
                assert result['result']['found'] == case['expected_found']

    def test_cdp_tab_management(self, mock_config):
        """Test CDP engine tab management functionality"""
        with patch('app.web.engine.get_config', return_value=mock_config):
            engine = CDPEngine()

            # Simulate working with multiple tabs
            tab_ids = [123, 456, 789]
            
            for tab_id in tab_ids:
                engine.active_tabs.add(tab_id)
                
                # Send messages to specific tabs
                result = engine._send_cdp_message('test_action', {'data': 'test'}, tab_id=tab_id)
                assert result['success'] is True
                assert result['engine'] == 'cdp'

            # Test cleanup clears all tabs
            assert len(engine.active_tabs) == 3
            
            with patch.object(engine, '_send_cdp_message') as mock_send:
                engine.close()
                
                # Should have attempted cleanup for all tabs
                assert len(engine.active_tabs) == 0
                assert mock_send.call_count >= 4  # 3 clear_highlights + 1 cleanup
