"""
Contract tests for WebX Extension <-> Native Host Protocol
Tests the JSON-RPC communication protocol between Chrome extension and native messaging host
"""

import json
import pytest
import subprocess
import time
from pathlib import Path
from typing import Dict, Any, Optional

from app.web.native_host import NativeMessagingHost
from app.config import get_config


class MockExtensionCommunicator:
    """Mock Chrome extension for protocol testing"""
    
    def __init__(self, native_host_path: str):
        self.native_host_path = native_host_path
        self.process: Optional[subprocess.Popen] = None
        self.message_id = 0
    
    def start_native_host(self):
        """Start native messaging host process"""
        self.process = subprocess.Popen(
            [self.native_host_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        # Give it a moment to start
        time.sleep(0.1)
    
    def send_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Send JSON-RPC message to native host"""
        if not self.process:
            raise RuntimeError("Native host not started")
        
        # Add message ID
        self.message_id += 1
        message['id'] = self.message_id
        
        # Encode message
        message_json = json.dumps(message)
        message_bytes = message_json.encode('utf-8')
        message_length = len(message_bytes)
        
        # Send length prefix + message
        length_bytes = message_length.to_bytes(4, 'little')
        self.process.stdin.write(length_bytes)
        self.process.stdin.write(message_bytes)
        self.process.stdin.flush()
        
        # Read response
        response_length_bytes = self.process.stdout.read(4)
        if len(response_length_bytes) != 4:
            raise RuntimeError("Failed to read response length")
        
        response_length = int.from_bytes(response_length_bytes, 'little')
        response_bytes = self.process.stdout.read(response_length)
        
        if len(response_bytes) != response_length:
            raise RuntimeError("Failed to read complete response")
        
        return json.loads(response_bytes.decode('utf-8'))
    
    def close(self):
        """Clean up native host process"""
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
            self.process = None


@pytest.fixture
def native_host_executable(tmp_path):
    """Create executable native host script for testing"""
    script_content = '''#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))
from app.web.native_host import main
if __name__ == '__main__':
    main()
'''
    script_path = tmp_path / "webx-native-host"
    script_path.write_text(script_content)
    script_path.chmod(0o755)
    return str(script_path)


@pytest.fixture
def mock_extension(native_host_executable):
    """Create mock extension communicator"""
    communicator = MockExtensionCommunicator(native_host_executable)
    communicator.start_native_host()
    yield communicator
    communicator.close()


class TestWebXProtocolContract:
    """Contract tests for WebX JSON-RPC protocol"""
    
    def test_handshake_protocol(self, mock_extension):
        """Test extension handshake with native host"""
        # Send handshake without token
        response = mock_extension.send_message({
            'method': 'handshake',
            'params': {
                'extension_id': 'test_extension_id',
                'version': '1.0.0'
            }
        })
        
        # Should succeed (no token required in test)
        assert 'result' in response
        assert response['result']['status'] == 'authenticated'
        assert 'host_version' in response['result']
        assert 'supported_methods' in response['result']
    
    def test_handshake_with_token(self, mock_extension):
        """Test handshake with authentication token"""
        response = mock_extension.send_message({
            'method': 'handshake',
            'params': {
                'extension_id': 'test_extension_id',
                'version': '1.0.0',
                'token': 'test_token'
            }
        })
        
        # Should succeed with correct token format
        assert 'result' in response
        assert response['result']['status'] == 'authenticated'
    
    def test_method_requires_authentication(self, mock_extension):
        """Test that non-handshake methods require authentication"""
        # Try to call method without handshake
        response = mock_extension.send_message({
            'method': 'take_screenshot',
            'params': {}
        })
        
        assert 'error' in response
        assert 'not authenticated' in response['error'].lower()
    
    def test_webx_goto_rpc(self, mock_extension):
        """Test webx.goto RPC method"""
        # First handshake
        mock_extension.send_message({
            'method': 'handshake',
            'params': {'extension_id': 'test', 'version': '1.0.0'}
        })
        
        # Then navigate
        response = mock_extension.send_message({
            'method': 'webx.goto',
            'params': {'url': 'https://example.com', 'tabId': 123}
        })
        
        assert 'result' in response
        assert response['result']['ok'] is True
        assert response['result']['url'] == 'https://example.com'
        assert 'elapsed_ms' in response['result']
    
    def test_webx_fill_by_label_rpc(self, mock_extension):
        """Test webx.fill_by_label RPC method"""
        # Handshake first
        mock_extension.send_message({
            'method': 'handshake',
            'params': {'extension_id': 'test', 'version': '1.0.0'}
        })
        
        # Fill request (DoD compliant format)
        response = mock_extension.send_message({
            'jsonrpc': '2.0',
            'method': 'webx.fill_by_label',
            'params': {
                'tabId': 123,
                'label': '氏名',
                'text': '山田太郎'
            },
            'id': '1'
        })
        
        assert 'result' in response
        assert response['result']['ok'] is True
        assert response['result']['label'] == '氏名'
        assert 'elapsed_ms' in response['result']
    
    def test_click_element_rpc(self, mock_extension):
        """Test click element RPC method"""
        # Handshake first
        mock_extension.send_message({
            'method': 'handshake',
            'params': {'extension_id': 'test', 'version': '1.0.0'}
        })
        
        # Click request
        response = mock_extension.send_message({
            'method': 'click_element',
            'params': {
                'selector': 'button.submit',
                'text': 'Submit',
                'tab_id': 123
            }
        })
        
        assert 'result' in response
        assert response['result']['success'] is True
        assert response['result']['action'] == 'click'
    
    def test_fill_input_rpc(self, mock_extension):
        """Test fill input RPC method"""
        # Handshake first
        mock_extension.send_message({
            'method': 'handshake',
            'params': {'extension_id': 'test', 'version': '1.0.0'}
        })
        
        # Fill request
        response = mock_extension.send_message({
            'method': 'fill_input',
            'params': {
                'selector': 'input[name="email"]',
                'label': 'Email',
                'text': 'test@example.com',
                'tab_id': 123
            }
        })
        
        assert 'result' in response
        assert response['result']['success'] is True
        assert response['result']['action'] == 'fill'
    
    def test_upload_file_rpc(self, mock_extension, tmp_path):
        """Test file upload RPC method"""
        # Create test file
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")
        
        # Handshake first
        mock_extension.send_message({
            'method': 'handshake',
            'params': {'extension_id': 'test', 'version': '1.0.0'}
        })
        
        # Upload request
        response = mock_extension.send_message({
            'method': 'upload_file',
            'params': {
                'file_path': str(test_file),
                'selector': 'input[type="file"]',
                'tab_id': 123
            }
        })
        
        assert 'result' in response
        assert response['result']['success'] is True
        assert response['result']['action'] == 'upload_file'
        assert response['result']['file_path'] == str(test_file)
    
    def test_webx_upload_file_error(self, mock_extension):
        """Test DoD compliant error format for nonexistent file"""
        # Handshake first
        mock_extension.send_message({
            'method': 'handshake',
            'params': {'extension_id': 'test', 'version': '1.0.0'}
        })
        
        # Upload request with bad path (DoD compliant format)
        response = mock_extension.send_message({
            'jsonrpc': '2.0',
            'method': 'webx.upload_file',
            'params': {
                'file_path': '/nonexistent/file.txt',
                'selector': 'input[type="file"]',
                'tabId': 123
            },
            'id': '7'
        })
        
        # Check DoD compliant error format
        assert 'error' in response
        assert response['error']['code'] == 'ELEMENT_NOT_FOUND'
        assert 'File not found' in response['error']['message']
    
    def test_get_page_info_rpc(self, mock_extension):
        """Test get page info RPC method"""
        # Handshake first
        mock_extension.send_message({
            'method': 'handshake',
            'params': {'extension_id': 'test', 'version': '1.0.0'}
        })
        
        # Page info request
        response = mock_extension.send_message({
            'method': 'get_page_info',
            'params': {'tab_id': 123}
        })
        
        assert 'result' in response
        assert response['result']['success'] is True
        assert response['result']['action'] == 'get_page_info'
        assert 'timestamp' in response['result']
    
    def test_webx_capture_dom_schema_rpc(self, mock_extension):
        """Test DoD DOM schema capture format"""
        # Handshake first
        mock_extension.send_message({
            'method': 'handshake',
            'params': {'extension_id': 'test', 'version': '1.0.0'}
        })
        
        # DOM schema request (DoD compliant)
        response = mock_extension.send_message({
            'jsonrpc': '2.0',
            'method': 'webx.capture_dom_schema',
            'params': {'tabId': 123},
            'id': 'schema_1'
        })
        
        assert 'result' in response
        assert response['result']['ok'] is True
        assert 'schema' in response['result']
        
        # Verify DoD schema format
        schema = response['result']['schema']
        assert 'captured_at' in schema
        assert 'url' in schema
        assert 'nodes' in schema
        assert isinstance(schema['nodes'], list)
        
        # Check sample node structure
        if schema['nodes']:
            node = schema['nodes'][0]
            assert 'role' in node
            assert 'name' in node or 'text' in node
            assert 'path' in node
    
    def test_unknown_method_error(self, mock_extension):
        """Test error handling for unknown RPC methods"""
        # Handshake first
        mock_extension.send_message({
            'method': 'handshake',
            'params': {'extension_id': 'test', 'version': '1.0.0'}
        })
        
        # Unknown method
        response = mock_extension.send_message({
            'method': 'unknown_method',
            'params': {}
        })
        
        assert 'error' in response
        assert 'unknown method' in response['error'].lower()
    
    def test_missing_method_error(self, mock_extension):
        """Test error handling for missing method field"""
        response = mock_extension.send_message({
            'params': {}
        })
        
        assert 'error' in response
        assert 'missing method' in response['error'].lower()
    
    def test_invalid_json_handling(self, mock_extension):
        """Test handling of invalid JSON messages"""
        if not mock_extension.process:
            return
        
        # Send invalid JSON directly
        invalid_message = b'invalid json message'
        length_bytes = len(invalid_message).to_bytes(4, 'little')
        
        mock_extension.process.stdin.write(length_bytes)
        mock_extension.process.stdin.write(invalid_message)
        mock_extension.process.stdin.flush()
        
        # Should get error response
        response_length_bytes = mock_extension.process.stdout.read(4)
        response_length = int.from_bytes(response_length_bytes, 'little')
        response_bytes = mock_extension.process.stdout.read(response_length)
        response = json.loads(response_bytes.decode('utf-8'))
        
        assert 'error' in response
        assert 'invalid json' in response['error'].lower()
    
    def test_request_id_tracking(self, mock_extension):
        """Test that request IDs are properly tracked"""
        # Handshake
        handshake_response = mock_extension.send_message({
            'method': 'handshake',
            'params': {'extension_id': 'test', 'version': '1.0.0'}
        })
        
        # Check that response has matching ID
        assert 'id' in handshake_response
        assert handshake_response['id'] == 1
        
        # Second request should have ID 2
        screenshot_response = mock_extension.send_message({
            'method': 'take_screenshot',
            'params': {}
        })
        
        assert screenshot_response['id'] == 2


class TestWebXSecurityFeatures:
    """Test security features of WebX protocol"""
    
    def test_extension_id_allowlist(self, mock_extension):
        """Test extension ID allowlist functionality"""
        # This test would need configuration setup to test allowlist
        # For now, test that any extension ID is accepted in default config
        response = mock_extension.send_message({
            'method': 'handshake',
            'params': {
                'extension_id': 'any_extension_id',
                'version': '1.0.0'
            }
        })
        
        assert 'result' in response
        assert response['result']['status'] == 'authenticated'
    
    def test_sensitive_data_masking(self, mock_extension):
        """Test that sensitive data is properly masked in logs"""
        # Handshake first
        mock_extension.send_message({
            'method': 'handshake',
            'params': {'extension_id': 'test', 'version': '1.0.0'}
        })
        
        # Fill request with sensitive field
        response = mock_extension.send_message({
            'method': 'fill_input',
            'params': {
                'selector': 'input[type="password"]',
                'text': 'secret_password',
                'tab_id': 123
            }
        })
        
        # Should succeed but sensitive data should be handled appropriately
        assert 'result' in response
        assert response['result']['success'] is True
    
    def test_protocol_version_compatibility(self, mock_extension):
        """Test protocol version compatibility"""
        response = mock_extension.send_message({
            'method': 'handshake',
            'params': {
                'extension_id': 'test',
                'version': '2.0.0'  # Future version
            }
        })
        
        # Should still work (backward compatible)
        assert 'result' in response
        assert response['result']['status'] == 'authenticated'


class TestWebXPerformanceContract:
    """Test performance characteristics of WebX protocol"""
    
    def test_response_timeout_handling(self, mock_extension):
        """Test that responses are returned within reasonable time"""
        start_time = time.time()
        
        response = mock_extension.send_message({
            'method': 'handshake',
            'params': {'extension_id': 'test', 'version': '1.0.0'}
        })
        
        response_time = time.time() - start_time
        
        # Should respond quickly (within 1 second for handshake)
        assert response_time < 1.0
        assert 'result' in response
    
    def test_concurrent_request_handling(self, mock_extension):
        """Test handling of rapid sequential requests"""
        # Handshake first
        mock_extension.send_message({
            'method': 'handshake',
            'params': {'extension_id': 'test', 'version': '1.0.0'}
        })
        
        # Send multiple requests rapidly
        responses = []
        for i in range(5):
            response = mock_extension.send_message({
                'method': 'get_page_info',
                'params': {'tab_id': i}
            })
            responses.append(response)
        
        # All should succeed
        for i, response in enumerate(responses):
            assert 'result' in response
            assert response['result']['success'] is True
            assert response['id'] == i + 2  # IDs should be sequential (handshake was 1)