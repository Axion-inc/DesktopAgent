"""
Unit tests for CDP Engine Implementation
Tests the Chrome DevTools Protocol-based web engine functionality
"""

import pytest
import tempfile
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from app.web.engine import CDPEngine


class TestCDPEngine:
    """Test the CDPEngine implementation"""

    @patch('app.web.engine.get_config')
    def test_cdp_engine_initialization(self, mock_config):
        """Test CDPEngine initializes correctly with configuration"""
        mock_config.return_value = {
            'web_engine': {
                'cdp': {
                    'extension_id': 'test_extension_id',
                    'timeout': 25000,
                    'dom_cache_ttl': 3000
                }
            }
        }
        
        engine = CDPEngine()
        
        assert engine.extension_id == 'test_extension_id'
        assert engine.cdp_timeout == 25000
        assert engine.dom_cache_ttl == 3000
        assert engine.name == 'CDPEngine'

    @patch('app.web.engine.get_config')  
    def test_cdp_engine_legacy_config(self, mock_config):
        """Test CDPEngine handles legacy extension configuration"""
        mock_config.return_value = {
            'web_engine': {
                'extension': {
                    'id': 'legacy_extension_id',
                    'handshake_token': 'legacy_token'
                }
            }
        }
        
        engine = CDPEngine()
        
        assert engine.extension_id == 'legacy_extension_id'
        assert engine.handshake_token == 'legacy_token'

    @patch('app.web.engine.get_config')
    def test_cdp_message_success(self, mock_config):
        """Test successful CDP message sending"""
        mock_config.return_value = {}
        engine = CDPEngine()
        
        result = engine._send_cdp_message('test_method', {'param': 'value'})
        
        assert result['success'] is True
        assert result['engine'] == 'cdp'
        assert 'id' in result

    def test_mock_cdp_responses(self):
        """Test CDP response mocking for different methods"""
        with patch('app.web.engine.get_config') as mock_config:
            mock_config.return_value = {}
            engine = CDPEngine()
            
            # Test DOM tree mock
            dom_result = engine._mock_cdp_response('build_dom_tree', {})
            assert 'labelCount' in dom_result
            assert 'interactiveElements' in dom_result
            
            # Test find element mock
            find_result = engine._mock_cdp_response('find_element', {'text': 'Submit'})
            assert find_result['found'] is True
            assert find_result['element']['text'] == 'Submit'
            
            # Test screenshot mock
            screenshot_result = engine._mock_cdp_response('take_screenshot', {})
            assert screenshot_result['success'] is True
            assert 'dataUrl' in screenshot_result

    @patch('app.web.engine.get_config')
    def test_open_browser_success(self, mock_config):
        """Test CDPEngine open_browser success"""
        mock_config.return_value = {}
        engine = CDPEngine()
        
        result = engine.open_browser('https://example.com', 'test_context')
        
        assert result['status'] == 'success'
        assert result['url'] == 'https://example.com'
        assert result['engine'] == 'cdp'

    @patch('app.web.engine.get_config')
    def test_fill_by_label_success(self, mock_config):
        """Test CDPEngine fill_by_label success"""
        mock_config.return_value = {}
        engine = CDPEngine()
        
        # Mock successful element finding and filling
        with patch.object(engine, '_find_element_by_criteria') as mock_find:
            mock_find.return_value = {
                'success': True,
                'result': {
                    'found': True,
                    'element': {'labelId': 1, 'text': 'Email'}
                }
            }
            
            with patch.object(engine, '_send_cdp_message') as mock_send:
                mock_send.return_value = {'success': True}
                
                result = engine.fill_by_label('Email', 'test@example.com')
                
                assert result['status'] == 'success'
                assert result['strategy'] == 'cdp_label_fill'
                assert result['text'] == 'test@example.com'

    @patch('app.web.engine.get_config')
    def test_fill_by_label_element_not_found(self, mock_config):
        """Test CDPEngine fill_by_label when element not found"""
        mock_config.return_value = {}
        engine = CDPEngine()
        
        with patch.object(engine, '_find_element_by_criteria') as mock_find:
            mock_find.return_value = {
                'success': True,
                'result': {'found': False}
            }
            
            result = engine.fill_by_label('NonexistentField', 'value')
            
            assert result['status'] == 'error'
            assert 'not found' in result['error']

    @patch('app.web.engine.get_config')
    def test_click_by_text_success(self, mock_config):
        """Test CDPEngine click_by_text success"""
        mock_config.return_value = {}
        engine = CDPEngine()
        
        with patch.object(engine, '_find_element_by_criteria') as mock_find:
            mock_find.return_value = {
                'success': True,
                'result': {
                    'found': True,
                    'element': {'labelId': 2, 'text': 'Submit'}
                }
            }
            
            with patch.object(engine, '_send_cdp_message') as mock_send:
                mock_send.return_value = {'success': True}
                
                result = engine.click_by_text('Submit', role='button')
                
                assert result['status'] == 'success'
                assert result['strategy'] == 'cdp_text_click'
                assert result['text'] == 'Submit'
                assert result['role'] == 'button'

    @patch('app.web.engine.get_config')
    def test_take_screenshot_success(self, mock_config):
        """Test CDPEngine screenshot success"""
        mock_config.return_value = {}
        engine = CDPEngine()
        
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
            result = engine.take_screenshot('default', temp_file.name)
            
            # Should return the path
            assert result == temp_file.name
            
            # File should exist (mock creates minimal PNG)
            temp_path = Path(temp_file.name)
            assert temp_path.exists()
            
            # Cleanup
            temp_path.unlink()

    @patch('app.web.engine.get_config')  
    @patch('app.web.engine.get_os_adapter')
    def test_take_screenshot_fallback(self, mock_get_adapter, mock_config):
        """Test CDPEngine screenshot fallback to OS adapter"""
        mock_config.return_value = {}
        mock_adapter = Mock()
        mock_get_adapter.return_value = mock_adapter
        
        engine = CDPEngine()
        
        # Mock CDP failure
        with patch.object(engine, '_send_cdp_message') as mock_send:
            mock_send.return_value = {'success': False, 'error': 'CDP failed'}
            
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
                result = engine.take_screenshot('default', temp_file.name)
                
                # Should still return path
                assert result == temp_file.name
                
                # Should have called OS adapter fallback
                mock_adapter.take_screenshot.assert_called_once_with(temp_file.name)
                
                # Cleanup
                Path(temp_file.name).unlink(missing_ok=True)

    @patch('app.web.engine.get_config')
    def test_upload_file_success(self, mock_config):
        """Test CDPEngine file upload success"""
        mock_config.return_value = {}
        engine = CDPEngine()
        
        # Create temporary file to upload
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(b'test content')
            temp_path = temp_file.name
        
        try:
            with patch.object(engine, '_find_element_by_criteria') as mock_find:
                mock_find.return_value = {
                    'success': True,
                    'result': {
                        'found': True,
                        'element': {'labelId': 3, 'tagName': 'input'}
                    }
                }
                
                with patch.object(engine, '_send_cdp_message') as mock_send:
                    mock_send.return_value = {'success': True}
                    
                    result = engine.upload_file(temp_path, label='File Upload')
                    
                    assert result['status'] == 'success'
                    assert result['strategy'] == 'cdp_file_upload'
                    assert result['path'] == temp_path
        finally:
            Path(temp_path).unlink(missing_ok=True)

    @patch('app.web.engine.get_config')
    def test_upload_file_not_found(self, mock_config):
        """Test CDPEngine upload with nonexistent file"""
        mock_config.return_value = {}
        engine = CDPEngine()
        
        result = engine.upload_file('/nonexistent/file.txt')
        
        assert result['status'] == 'error'
        assert 'does not exist' in result['error']

    @patch('app.web.engine.get_config')
    def test_build_dom_tree(self, mock_config):
        """Test CDPEngine DOM tree building"""
        mock_config.return_value = {}
        engine = CDPEngine()
        
        result = engine._build_dom_tree(tab_id=123, options={
            'include_invisible': True,
            'max_depth': 5
        })
        
        assert result['success'] is True
        assert result['result']['labelCount'] > 0

    @patch('app.web.engine.get_config')
    def test_find_element_by_criteria(self, mock_config):
        """Test CDPEngine element finding"""
        mock_config.return_value = {}
        engine = CDPEngine()
        
        # Test finding by text
        result = engine._find_element_by_criteria(text='Submit Button', tab_id=123)
        assert result['success'] is True
        
        # Test finding by label ID
        result = engine._find_element_by_criteria(label_id=5, tab_id=123)
        assert result['success'] is True
        
        # Test finding by selector
        result = engine._find_element_by_criteria(selector='button.submit', tab_id=123)
        assert result['success'] is True

    @patch('app.web.engine.get_config')
    def test_close_cleanup(self, mock_config):
        """Test CDPEngine cleanup on close"""
        mock_config.return_value = {}
        engine = CDPEngine()
        
        # Add some active tabs
        engine.active_tabs.add(123)
        engine.active_tabs.add(456)
        
        with patch.object(engine, '_send_cdp_message') as mock_send:
            engine.close()
            
            # Should have cleared active tabs
            assert len(engine.active_tabs) == 0
            
            # Should have sent cleanup message
            mock_send.assert_called_with('cleanup', {})

    @patch('app.web.engine.get_config')
    def test_error_handling_in_operations(self, mock_config):
        """Test error handling in various CDP operations"""
        mock_config.return_value = {}
        engine = CDPEngine()
        
        # Test navigation error
        with patch.object(engine, '_send_cdp_message') as mock_send:
            mock_send.return_value = {'success': False, 'error': 'Navigation failed'}
            
            result = engine.open_browser('https://example.com')
            assert result['status'] == 'error'
            assert 'Navigation failed' in result['error']
        
        # Test fill error when element found but fill fails
        with patch.object(engine, '_find_element_by_criteria') as mock_find:
            mock_find.return_value = {
                'success': True,
                'result': {
                    'found': True,
                    'element': {'labelId': 1}
                }
            }
            
            with patch.object(engine, '_send_cdp_message') as mock_send:
                mock_send.return_value = {'success': False, 'error': 'Fill failed'}
                
                result = engine.fill_by_label('Email', 'test@example.com')
                assert result['status'] == 'error'
                assert 'Fill failed' in result['error']

    @patch('app.web.engine.get_config')
    def test_wait_for_download(self, mock_config):
        """Test CDPEngine wait_for_download"""
        mock_config.return_value = {}
        engine = CDPEngine()
        
        result = engine.wait_for_download('/downloads/file.pdf', timeout_ms=5000)
        
        assert result['status'] == 'success'
        assert result['engine'] == 'cdp'
        assert result['to'] == '/downloads/file.pdf'

    @patch('app.web.engine.get_config')
    def test_get_page_info(self, mock_config):
        """Test CDPEngine get_page_info"""
        mock_config.return_value = {}
        engine = CDPEngine()
        
        result = engine.get_page_info('test_context')
        
        assert result['status'] == 'success'
        assert result['engine'] == 'cdp'
        assert 'url' in result
        assert 'title' in result

    @patch('app.web.engine.get_config')
    def test_wait_for_selector(self, mock_config):
        """Test CDPEngine wait_for_selector"""
        mock_config.return_value = {}
        engine = CDPEngine()
        
        result = engine.wait_for_selector('.loading-spinner', timeout_ms=15000)
        
        assert result['status'] == 'visible'
        assert result['engine'] == 'cdp'
        assert result['selector'] == '.loading-spinner'


class TestCDPEngineIntegration:
    """Test CDPEngine integration scenarios"""

    @patch('app.web.engine.get_config')
    def test_complete_form_workflow(self, mock_config):
        """Test complete form filling workflow"""
        mock_config.return_value = {}
        engine = CDPEngine()
        
        # Mock successful element finding for all fields
        mock_elements = [
            {'labelId': 1, 'text': 'Email'},
            {'labelId': 2, 'text': 'Password'},
            {'labelId': 3, 'text': 'Submit'}
        ]
        
        with patch.object(engine, '_find_element_by_criteria') as mock_find:
            mock_find.side_effect = [
                {'success': True, 'result': {'found': True, 'element': elem}}
                for elem in mock_elements
            ]
            
            with patch.object(engine, '_send_cdp_message') as mock_send:
                mock_send.return_value = {'success': True}
                
                # Navigate
                nav_result = engine.open_browser('https://login.example.com')
                assert nav_result['status'] == 'success'
                
                # Fill form
                email_result = engine.fill_by_label('Email', 'user@example.com')
                assert email_result['status'] == 'success'
                
                password_result = engine.fill_by_label('Password', 'secret123')
                assert password_result['status'] == 'success'
                
                # Submit
                submit_result = engine.click_by_text('Submit')
                assert submit_result['status'] == 'success'

    @patch('app.web.engine.get_config')
    def test_error_recovery_workflow(self, mock_config):
        """Test error recovery in CDP operations"""
        mock_config.return_value = {}
        engine = CDPEngine()
        
        # Test retry logic for transient failures
        with patch.object(engine, '_send_cdp_message') as mock_send:
            # First call fails, second succeeds
            mock_send.side_effect = [
                {'success': False, 'error': 'Temporary failure'},
                {'success': True}
            ]
            
            # This would normally implement retry logic
            # For now, just test that errors are handled gracefully
            result = engine.open_browser('https://example.com')
            assert result['status'] == 'error'
            assert 'Temporary failure' in result['error']


# Integration with engine factory tests would be added to existing TestEngineFactory
class TestCDPEngineFactory:
    """Test engine factory integration with CDP"""
    
    @patch('app.web.engine.get_config')
    def test_factory_creates_cdp_engine(self, mock_config):
        """Test factory creates CDPEngine for 'cdp' type"""
        from app.web.engine import get_web_engine
        
        mock_config.return_value = {
            'web_engine': {'engine': 'cdp'}
        }
        
        engine = get_web_engine()
        assert isinstance(engine, CDPEngine)
        assert engine.name == 'CDPEngine'
    
    @patch('app.web.engine.get_config')
    def test_factory_backward_compatibility(self, mock_config):
        """Test factory creates CDPEngine for legacy 'extension' type"""
        from app.web.engine import get_web_engine
        
        mock_config.return_value = {
            'web_engine': {'engine': 'extension'}
        }
        
        engine = get_web_engine()
        assert isinstance(engine, CDPEngine)
        assert engine.name == 'CDPEngine'

    def test_explicit_cdp_engine_request(self):
        """Test requesting CDP engine explicitly"""
        from app.web.engine import get_web_engine
        
        engine = get_web_engine(engine_type='cdp')
        assert isinstance(engine, CDPEngine)
        assert engine.name == 'CDPEngine'