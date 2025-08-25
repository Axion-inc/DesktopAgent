#!/usr/bin/env python3
"""
Native Messaging Host for Desktop Agent WebX Extension
Handles JSON-RPC communication with Chrome extension via stdio
"""

import sys
import json
import struct
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path

from ..config import get_config
from ..security.secrets import get_secrets_manager
from ..utils.logging import get_logger

logger = get_logger(__name__)


class NativeMessagingHost:
    """Native messaging host for Chrome extension communication"""

    def __init__(self, config_path: Optional[str] = None):
        self.config = get_config()
        self.secrets_manager = get_secrets_manager()
        self.running = False
        self.authenticated = False

        # Load extension configuration
        self.allowed_extension_ids = self._load_allowed_extensions()
        self.handshake_token = self._load_handshake_token()

        # Standard JSON-RPC method handlers (DoD compliant)
        self.rpc_handlers = {
            'handshake': self._handle_handshake,
            'webx.goto': self._handle_goto,
            'webx.fill_by_label': self._handle_fill_by_label,
            'webx.click_by_text': self._handle_click_by_text,
            'webx.upload_file': self._handle_upload_file,
            'webx.wait_for_element': self._handle_wait_for_element,
            'webx.assert_element': self._handle_assert_element,
            'webx.capture_dom_schema': self._handle_capture_dom_schema,
            'webx.wait_for_download': self._handle_wait_for_download,
            'webx.take_screenshot': self._handle_take_screenshot,
        }

        # Standard error codes (DoD requirement)
        self.ERROR_CODES = {
            'NO_TAB': 'NO_TAB',
            'ELEMENT_NOT_FOUND': 'ELEMENT_NOT_FOUND',
            'PERMISSION_DENIED': 'PERMISSION_DENIED',
            'TIMEOUT': 'TIMEOUT',
            'UPLOAD_UNSUPPORTED': 'UPLOAD_UNSUPPORTED',
            'INVALID_PARAMS': 'INVALID_PARAMS',
            'HANDSHAKE_REQUIRED': 'HANDSHAKE_REQUIRED'
        }

    def _load_allowed_extensions(self) -> List[str]:
        """Load allowed extension IDs from configuration"""
        try:
            web_config = self.config.get('web_engine', {})
            extension_config = web_config.get('extension', {})
            extension_id = extension_config.get('id')

            if extension_id:
                return [extension_id]
            else:
                logger.warning("No extension ID configured, allowing any extension")
                return []
        except Exception as e:
            logger.error(f"Failed to load extension configuration: {e}")
            return []

    def _load_handshake_token(self) -> Optional[str]:
        """Load handshake token from secrets or configuration"""
        try:
            # Try to get from secrets first
            token = self.secrets_manager.get_secret('webx_handshake_token')
            if token:
                return token

            # Fall back to configuration
            web_config = self.config.get('web_engine', {})
            extension_config = web_config.get('extension', {})
            return extension_config.get('handshake_token')

        except Exception as e:
            logger.error(f"Failed to load handshake token: {e}")
            return None

    def start(self):
        """Start the native messaging host"""
        logger.info("Starting Desktop Agent WebX Native Messaging Host")
        self.running = True

        try:
            # Set up stdio in binary mode for message framing
            input_stream = sys.stdin.buffer
            output_stream = sys.stdout.buffer

            while self.running:
                # Read message length (4 bytes, little-endian)
                raw_length = input_stream.read(4)
                if len(raw_length) == 0:
                    logger.info("Input stream closed")
                    break

                message_length = struct.unpack('<I', raw_length)[0]

                # Read message content
                message_data = input_stream.read(message_length)
                if len(message_data) != message_length:
                    logger.error("Incomplete message received")
                    break

                try:
                    # Parse JSON message
                    message = json.loads(message_data.decode('utf-8'))
                    logger.debug(f"Received message: {message}")

                    # Process message and send response
                    response = self._process_message(message)
                    self._send_message(output_stream, response)

                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON received: {e}")
                    error_response = {
                        'error': 'Invalid JSON',
                        'id': None
                    }
                    self._send_message(output_stream, error_response)

                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    error_response = {
                        'error': str(e),
                        'id': message.get('id') if 'message' in locals() else None
                    }
                    self._send_message(output_stream, error_response)

        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
        except Exception as e:
            logger.error(f"Fatal error in native messaging host: {e}")
        finally:
            self.running = False
            logger.info("Native messaging host stopped")

    def _send_message(self, output_stream, message: Dict[str, Any]):
        """Send a message to the extension"""
        try:
            message_json = json.dumps(message)
            message_bytes = message_json.encode('utf-8')
            message_length = len(message_bytes)

            # Send length (4 bytes, little-endian) followed by message
            output_stream.write(struct.pack('<I', message_length))
            output_stream.write(message_bytes)
            output_stream.flush()

            logger.debug(f"Sent message: {message}")

        except Exception as e:
            logger.error(f"Failed to send message: {e}")

    def _process_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Process an incoming message and return response"""
        method = message.get('method')
        params = message.get('params', {})
        message_id = message.get('id')

        if not method:
            return {
                'error': 'Missing method in request',
                'id': message_id
            }

        # Special handling for handshake - no authentication required
        if method == 'handshake':
            result = self._handle_handshake(params)
            return {
                'result': result,
                'id': message_id
            }

        # All other methods require authentication
        if not self.authenticated:
            return {
                'jsonrpc': '2.0',
                'error': {
                    'code': self.ERROR_CODES['HANDSHAKE_REQUIRED'],
                    'message': 'Handshake required before calling methods'
                },
                'id': message_id
            }

        if method not in self.rpc_handlers:
            return {
                'jsonrpc': '2.0',
                'error': {
                    'code': 'METHOD_NOT_FOUND',
                    'message': f'Unknown method: {method}'
                },
                'id': message_id
            }

        try:
            handler = self.rpc_handlers[method]
            result = handler(params)
            return {
                'jsonrpc': '2.0',
                'result': result,
                'id': message_id
            }
        except Exception as e:
            logger.error(f"Error executing {method}: {e}")
            # Determine appropriate error code
            error_code = 'INTERNAL_ERROR'
            if 'not found' in str(e).lower():
                error_code = self.ERROR_CODES['ELEMENT_NOT_FOUND']
            elif 'timeout' in str(e).lower():
                error_code = self.ERROR_CODES['TIMEOUT']
            elif 'permission' in str(e).lower():
                error_code = self.ERROR_CODES['PERMISSION_DENIED']

            return {
                'jsonrpc': '2.0',
                'error': {
                    'code': error_code,
                    'message': str(e)
                },
                'id': message_id
            }

    def _handle_handshake(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle extension handshake and authentication"""
        extension_id = params.get('extension_id')
        version = params.get('version')
        token = params.get('token')

        logger.info(f"Handshake from extension {extension_id} version {version}")

        # Verify extension ID if configured
        if self.allowed_extension_ids and extension_id not in self.allowed_extension_ids:
            logger.error(f"Extension {extension_id} not in allowlist")
            raise Exception("Extension not authorized")

        # Verify handshake token if configured
        if self.handshake_token:
            if not token or token != self.handshake_token:
                logger.error("Invalid handshake token")
                raise Exception("Invalid authentication token")

        self.authenticated = True
        logger.info("Extension authenticated successfully")

        return {
            'status': 'authenticated',
            'host_version': '1.0.0',
            'supported_methods': list(self.rpc_handlers.keys())
        }

    def _handle_goto(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Navigate to URL (webx.goto)"""
        url = params.get('url')
        tab_id = params.get('tabId')

        if not url:
            raise Exception("URL parameter required")

        logger.info(f"Navigate to {url} in tab {tab_id}")

        return {
            'ok': True,
            'url': url,
            'tabId': tab_id,
            'elapsed_ms': 150  # Mock timing
        }

    def _handle_take_screenshot(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Take a screenshot (webx.take_screenshot)"""
        from ..os_adapters import get_os_adapter

        output_path = params.get('path', '/tmp/webx_screenshot.png')
        tab_id = params.get('tabId')

        adapter = get_os_adapter()
        success = adapter.take_screenshot(output_path)

        if success:
            return {
                'ok': True,
                'path': output_path,
                'tabId': tab_id,
                'elapsed_ms': 85
            }
        else:
            raise Exception("Screenshot failed")

    def _handle_fill_by_label(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Fill form field by label (webx.fill_by_label)"""
        label = params.get('label')
        text = params.get('text')
        tab_id = params.get('tabId')

        if not label or text is None:
            raise Exception("label and text parameters required")

        logger.info(f"Fill label '{label}' in tab {tab_id}")

        # Mask sensitive data in logs
        display_text = "***MASKED***" if self._is_sensitive_field(None, label) else text
        logger.debug(f"Fill text: {display_text}")

        return {
            'ok': True,
            'label': label,
            'tabId': tab_id,
            'elapsed_ms': 84
        }

    def _handle_click_by_text(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Click element by text (webx.click_by_text)"""
        text = params.get('text')
        role = params.get('role')
        tab_id = params.get('tabId')

        if not text:
            raise Exception("text parameter required")

        logger.info(f"Click text '{text}' with role {role} in tab {tab_id}")

        return {
            'ok': True,
            'text': text,
            'role': role,
            'tabId': tab_id,
            'elapsed_ms': 92
        }

    def _handle_upload_file(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle file upload (webx.upload_file)"""
        file_path = params.get('file_path')
        selector = params.get('selector')
        label = params.get('label')
        tab_id = params.get('tabId')

        if not file_path:
            raise Exception("file_path parameter required")

        # Validate file exists
        path = Path(file_path).expanduser()
        if not path.exists():
            raise Exception(f"File not found: {file_path}")

        logger.info(f"File upload request: {file_path} to {selector or label} in tab {tab_id}")

        return {
            'ok': True,
            'file_path': str(path),
            'selector': selector,
            'label': label,
            'tabId': tab_id,
            'elapsed_ms': 156
        }

    def _handle_wait_for_element(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Wait for element to appear (webx.wait_for_element)"""
        selector = params.get('selector')
        text = params.get('text')
        timeout_ms = params.get('timeout_ms', 10000)
        tab_id = params.get('tabId')

        if not selector and not text:
            raise Exception("selector or text parameter required")

        logger.info(f"Wait for element: selector={selector}, text={text}, timeout={timeout_ms}ms in tab {tab_id}")

        # Mock successful wait
        return {
            'ok': True,
            'found': True,
            'selector': selector,
            'text': text,
            'tabId': tab_id,
            'elapsed_ms': min(timeout_ms // 10, 500)  # Mock timing
        }

    def _handle_assert_element(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Assert element exists (webx.assert_element)"""
        selector = params.get('selector')
        text = params.get('text')
        count_gte = params.get('count_gte', 1)
        tab_id = params.get('tabId')

        if not selector and not text:
            raise Exception("selector or text parameter required")

        logger.info(f"Assert element: selector={selector}, text={text}, count>={count_gte} in tab {tab_id}")

        # Mock assertion - could throw ELEMENT_NOT_FOUND error
        return {
            'ok': True,
            'found_count': count_gte,  # Mock count
            'selector': selector,
            'text': text,
            'tabId': tab_id,
            'elapsed_ms': 45
        }

    def _handle_capture_dom_schema(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Capture DOM schema (webx.capture_dom_schema)"""
        tab_id = params.get('tabId')

        logger.info(f"Capture DOM schema in tab {tab_id}")

        # Generate mock DOM schema
        import datetime
        schema = {
            "captured_at": datetime.datetime.now().isoformat() + "+09:00",
            "url": "https://example.com/form",
            "tab_id": tab_id,
            "nodes": [
                {"role": "textbox", "name": "氏名", "value": "", "path": "input#name"},
                {"role": "textbox", "name": "メール", "value": "", "path": "input#email"},
                {"role": "button", "name": "送信", "path": "button.submit"}
            ]
        }

        return {
            'ok': True,
            'schema': schema,
            'tabId': tab_id,
            'elapsed_ms': 234
        }

    def _handle_wait_for_download(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Wait for download completion (webx.wait_for_download)"""
        target_dir = params.get('target_dir') or params.get('to')
        timeout_ms = params.get('timeout_ms', 30000)
        tab_id = params.get('tabId')

        if not target_dir:
            raise Exception("target_dir parameter required")

        logger.info(f"Wait for download to {target_dir} with timeout {timeout_ms}ms in tab {tab_id}")

        # Mock download completion
        return {
            'ok': True,
            'downloaded': True,
            'file_path': f"{target_dir}/downloaded_file.pdf",
            'file_size': 1024567,
            'tabId': tab_id,
            'elapsed_ms': min(timeout_ms // 5, 2000)
        }

    def _is_sensitive_field(self, selector: Optional[str], label: Optional[str]) -> bool:
        """Check if field contains sensitive data"""
        if not selector and not label:
            return False

        sensitive_patterns = [
            'password', 'passwd', 'pwd',
            'secret', 'token', 'key',
            'credit', 'card', 'ccv', 'cvv',
            'ssn', 'social',
            'pin', 'otp'
        ]

        text_to_check = f"{selector or ''} {label or ''}".lower()
        return any(pattern in text_to_check for pattern in sensitive_patterns)

    def _get_timestamp(self) -> int:
        """Get current timestamp"""
        import time
        return int(time.time() * 1000)


def main():
    """Main entry point for native messaging host"""
    import argparse

    parser = argparse.ArgumentParser(description='Desktop Agent WebX Native Messaging Host')
    parser.add_argument('--config', help='Configuration file path')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    args = parser.parse_args()

    # Configure logging
    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('/tmp/webx_native_host.log'),
            logging.StreamHandler(sys.stderr)
        ]
    )

    # Create and start host
    host = NativeMessagingHost(config_path=args.config)
    try:
        host.start()
    except KeyboardInterrupt:
        logger.info("Shutdown requested")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
