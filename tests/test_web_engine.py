"""
Unit tests for Web Engine Abstraction
Tests the unified interface and engine switching functionality
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from app.web.engine import (
    WebEngine, PlaywrightEngine, ExtensionEngine,
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
    
    def test_extension_engine_interface(self):
        """Test ExtensionEngine implements WebEngine interface"""
        with patch('app.web.engine.get_config') as mock_config:
            mock_config.return_value = {
                'web_engine': {
                    'extension': {
                        'id': 'test_extension_id',
                        'handshake_token': 'test_token'
                    }
                }
            }
            
            engine = ExtensionEngine()
            
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
            assert engine.name == 'ExtensionEngine'


class TestPlaywrightEngine:
    """Test PlaywrightEngine implementation"""
    
    @patch('app.web.engine.open_browser')
    def test_playwright_open_browser(self, mock_open):
        """Test PlaywrightEngine delegates to web_actions"""
        mock_open.return_value = {'status': 'success', 'url': 'https://example.com'}
        
        engine = PlaywrightEngine()
        result = engine.open_browser('https://example.com', 'test_context')
        
        mock_open.assert_called_once_with(
            'https://example.com', 'test_context', wait_for_load=True, visible=None
        )
        assert result['status'] == 'success'
    
    @patch('app.web.engine.fill_by_label')
    def test_playwright_fill_by_label(self, mock_fill):
        """Test PlaywrightEngine fill_by_label delegation"""
        mock_fill.return_value = {'status': 'success', 'strategy': 'by_label'}
        
        engine = PlaywrightEngine()
        result = engine.fill_by_label('Email', 'test@example.com')
        
        mock_fill.assert_called_once_with('Email', 'test@example.com', 'default')
        assert result['strategy'] == 'by_label'
    
    @patch('app.web.engine.click_by_text')
    def test_playwright_click_by_text(self, mock_click):
        """Test PlaywrightEngine click_by_text delegation"""
        mock_click.return_value = {'status': 'success', 'strategy': 'by_text_exact'}
        
        engine = PlaywrightEngine()
        result = engine.click_by_text('Submit', role='button')
        
        mock_click.assert_called_once_with('Submit', 'button', 'default')
        assert result['strategy'] == 'by_text_exact'
    
    @patch('app.web.engine.take_screenshot')
    def test_playwright_take_screenshot(self, mock_screenshot):
        """Test PlaywrightEngine screenshot delegation"""
        mock_screenshot.return_value = '/tmp/screenshot.png'
        
        engine = PlaywrightEngine()
        result = engine.take_screenshot('default', '/tmp/screenshot.png')
        
        mock_screenshot.assert_called_once_with('default', '/tmp/screenshot.png')
        assert result == '/tmp/screenshot.png'
    
    @patch('app.web.engine.close_web_session')
    def test_playwright_close(self, mock_close):
        """Test PlaywrightEngine cleanup"""
        engine = PlaywrightEngine()
        engine.close()
        
        mock_close.assert_called_once()


class TestExtensionEngine:
    """Test ExtensionEngine implementation"""
    
    @pytest.fixture
    def mock_config(self):
        """Mock configuration for ExtensionEngine"""
        return {
            'web_engine': {
                'extension': {
                    'id': 'test_extension_id',
                    'handshake_token': 'test_token'
                }
            }
        }
    
    def test_extension_engine_config_loading(self, mock_config):
        """Test ExtensionEngine loads configuration correctly"""
        with patch('app.web.engine.get_config', return_value=mock_config):
            engine = ExtensionEngine()
            
            assert engine.extension_id == 'test_extension_id'
            assert engine.handshake_token == 'test_token'
    
    def test_extension_engine_missing_config(self):
        """Test ExtensionEngine handles missing configuration"""
        with patch('app.web.engine.get_config', return_value={}):
            engine = ExtensionEngine()
            
            assert engine.extension_id is None
            assert engine.handshake_token is None
    
    def test_extension_open_browser(self, mock_config):
        """Test ExtensionEngine open_browser implementation"""
        with patch('app.web.engine.get_config', return_value=mock_config):
            engine = ExtensionEngine()
            
            with patch.object(engine, '_send_rpc', return_value={'success': True}):
                result = engine.open_browser('https://example.com', 'test_context')
                
                assert result['status'] == 'success'
                assert result['engine'] == 'extension'
                assert result['url'] == 'https://example.com'
    
    def test_extension_fill_by_label(self, mock_config):
        """Test ExtensionEngine fill_by_label implementation"""
        with patch('app.web.engine.get_config', return_value=mock_config):
            engine = ExtensionEngine()
            
            with patch.object(engine, '_send_rpc', return_value={'success': True}):
                result = engine.fill_by_label('Email', 'test@example.com')
                
                assert result['status'] == 'success'
                assert result['engine'] == 'extension'
                assert result['strategy'] == 'extension_rpc'
    
    def test_extension_click_by_text(self, mock_config):
        """Test ExtensionEngine click_by_text implementation"""
        with patch('app.web.engine.get_config', return_value=mock_config):
            engine = ExtensionEngine()
            
            with patch.object(engine, '_send_rpc', return_value={'success': True}):
                result = engine.click_by_text('Submit', role='button')
                
                assert result['status'] == 'success'
                assert result['engine'] == 'extension'
                assert result['strategy'] == 'extension_rpc'
    
    def test_extension_upload_file_validation(self, mock_config, tmp_path):
        """Test ExtensionEngine validates file existence for uploads"""
        with patch('app.web.engine.get_config', return_value=mock_config):
            engine = ExtensionEngine()
            
            # Test with nonexistent file
            result = engine.upload_file('/nonexistent/file.txt')
            assert result['status'] == 'error'
            assert 'does not exist' in result['error']
            
            # Test with existing file
            test_file = tmp_path / 'test.txt'
            test_file.write_text('test content')
            
            with patch.object(engine, '_send_rpc', return_value={'success': True}):
                result = engine.upload_file(str(test_file))
                assert result['status'] == 'success'
                assert result['engine'] == 'extension'
    
    def test_extension_take_screenshot_fallback(self, mock_config):
        """Test ExtensionEngine falls back to OS adapter for screenshots"""
        with patch('app.web.engine.get_config', return_value=mock_config):
            engine = ExtensionEngine()
            
            # Mock RPC failure
            with patch.object(engine, '_send_rpc', side_effect=Exception('RPC failed')):
                with patch('app.web.engine.get_os_adapter') as mock_get_adapter:
                    mock_adapter = Mock()
                    mock_adapter.take_screenshot.return_value = True
                    mock_get_adapter.return_value = mock_adapter
                    
                    result = engine.take_screenshot(path='/tmp/test.png')
                    
                    assert result == '/tmp/test.png'
                    mock_adapter.take_screenshot.assert_called_once_with('/tmp/test.png')
    
    def test_extension_error_handling(self, mock_config):
        """Test ExtensionEngine handles RPC errors gracefully"""
        with patch('app.web.engine.get_config', return_value=mock_config):
            engine = ExtensionEngine()
            
            # Mock RPC failure
            with patch.object(engine, '_send_rpc', side_effect=Exception('Connection failed')):
                result = engine.open_browser('https://example.com')
                
                assert result['status'] == 'error'
                assert result['engine'] == 'extension'
                assert 'Connection failed' in result['error']


class TestEngineFactory:
    """Test engine factory and management functions"""
    
    def test_get_web_engine_default(self):
        """Test get_web_engine returns PlaywrightEngine by default"""
        with patch('app.web.engine.get_config', return_value={}):
            engine = get_web_engine()
            assert isinstance(engine, PlaywrightEngine)
    
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
    
    def test_get_web_engine_extension(self):
        """Test get_web_engine creates ExtensionEngine when configured"""
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
            assert isinstance(engine, ExtensionEngine)
    
    def test_get_web_engine_explicit_type(self):
        """Test get_web_engine respects explicit engine type parameter"""
        with patch('app.web.engine.get_config', return_value={}):
            # Request playwright explicitly
            engine = get_web_engine('playwright')
            assert isinstance(engine, PlaywrightEngine)
            
            # Request extension explicitly
            with patch('app.web.engine.ExtensionEngine.__init__', return_value=None):
                engine = get_web_engine('extension')
                assert isinstance(engine, ExtensionEngine)
    
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
            
            result = fill_by_label('Email', 'test@example.com', engine='extension')
            
            mock_get_engine.assert_called_once_with('extension')
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
            
            # Switch to extension engine  
            close_web_engine()
            set_web_engine_type('extension')
            
            with patch('app.web.engine.ExtensionEngine.__init__', return_value=None):
                with patch('app.web.engine.ExtensionEngine.open_browser') as mock_ext_open:
                    mock_ext_open.return_value = {'status': 'success', 'engine': 'extension'}
                    
                    result = open_browser('https://example.com')
                    assert result['status'] == 'success'
                    mock_ext_open.assert_called_once()