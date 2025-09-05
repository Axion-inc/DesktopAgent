"""
Web Engine Abstraction Layer
Provides unified interface for Playwright and Extension engines
"""

from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, List
from pathlib import Path
import tempfile

from ..config import get_config
from ..utils.logging import get_logger

logger = get_logger(__name__)


class WebEngine(ABC):
    """Abstract base class for web automation engines"""

    def __init__(self):
        self.name = self.__class__.__name__
        self.context_name = "default"

    @abstractmethod
    def open_browser(self, url: str, context: str = "default", **kwargs) -> Dict[str, Any]:
        """Navigate to a URL"""
        pass

    @abstractmethod
    def fill_by_label(self, label: str, text: str, context: str = "default", **kwargs) -> Dict[str, Any]:
        """Fill form field by label text"""
        pass

    @abstractmethod
    def click_by_text(self, text: str, role: Optional[str] = None,
                      context: str = "default", **kwargs) -> Dict[str, Any]:
        """Click element by text content"""
        pass

    @abstractmethod
    def take_screenshot(self, context: str = "default", path: Optional[str] = None, **kwargs) -> str:
        """Take a screenshot"""
        pass

    @abstractmethod
    def upload_file(self, path: str, selector: Optional[str] = None,
                    label: Optional[str] = None, context: str = "default",
                    **kwargs) -> Dict[str, Any]:
        """Upload file to input element"""
        pass

    @abstractmethod
    def download_file(self, to: str, context: str = "default", timeout: int = 30000, **kwargs) -> Dict[str, Any]:
        """Wait for and handle file download"""
        pass

    @abstractmethod
    def wait_for_download(self, to: str, timeout_ms: int = 30000,
                          context: str = "default", **kwargs) -> Dict[str, Any]:
        """Wait for download completion"""
        pass

    @abstractmethod
    def get_page_info(self, context: str = "default", **kwargs) -> Dict[str, Any]:
        """Get current page information"""
        pass

    @abstractmethod
    def wait_for_selector(self, selector: str, timeout_ms: Optional[int] = None,
                          context: str = "default", **kwargs) -> Dict[str, Any]:
        """Wait for a selector to appear"""
        pass

    @abstractmethod
    def close(self) -> None:
        """Clean up resources"""
        pass

    # Extension-first batch execution (JSON-RPC style)
    @abstractmethod
    def exec_batch(self, guards: Dict[str, Any], actions: List[Dict[str, Any]],
                   evidence: Optional[Dict[str, Any]] = None,
                   context: str = "default", **kwargs) -> Dict[str, Any]:
        """Execute a batch of actions via engine-native transport"""
        pass


class PlaywrightEngine(WebEngine):
    """Playwright-based web automation engine (existing implementation)"""

    def __init__(self):
        super().__init__()
        # Import existing Playwright functions
        from ..actions.web_actions import (
            open_browser as pw_open_browser,
            fill_by_label as pw_fill_by_label,
            click_by_text as pw_click_by_text,
            take_screenshot as pw_take_screenshot,
            upload_file as pw_upload_file,
            download_file as pw_download_file,
            wait_for_download as pw_wait_for_download,
            get_page_info as pw_get_page_info,
            wait_for_selector as pw_wait_for_selector,
            close_web_session
        )

        # Store references to Playwright functions
        self._open_browser = pw_open_browser
        self._fill_by_label = pw_fill_by_label
        self._click_by_text = pw_click_by_text
        self._take_screenshot = pw_take_screenshot
        self._upload_file = pw_upload_file
        self._download_file = pw_download_file
        self._wait_for_download = pw_wait_for_download
        self._get_page_info = pw_get_page_info
        self._wait_for_selector = pw_wait_for_selector
        self._close_session = close_web_session

    def open_browser(self, url: str, context: str = "default", **kwargs) -> Dict[str, Any]:
        logger.info(f"PlaywrightEngine: Opening {url} in context {context}")
        return self._open_browser(url, context, **kwargs)

    def fill_by_label(self, label: str, text: str, context: str = "default", **kwargs) -> Dict[str, Any]:
        logger.debug(f"PlaywrightEngine: Filling label '{label}' in context {context}")
        return self._fill_by_label(label, text, context)

    def click_by_text(self, text: str, role: Optional[str] = None,
                      context: str = "default", **kwargs) -> Dict[str, Any]:
        logger.debug(f"PlaywrightEngine: Clicking text '{text}' with role {role} in context {context}")
        return self._click_by_text(text, role, context)

    def take_screenshot(self, context: str = "default", path: Optional[str] = None, **kwargs) -> str:
        logger.debug(f"PlaywrightEngine: Taking screenshot in context {context}")
        return self._take_screenshot(context, path)

    def upload_file(self, path: str, selector: Optional[str] = None,
                    label: Optional[str] = None, context: str = "default",
                    **kwargs) -> Dict[str, Any]:
        logger.info(f"PlaywrightEngine: Uploading file {path} via "
                    f"selector={selector}, label={label}")
        return self._upload_file(path, selector, label, context)

    def download_file(self, to: str, context: str = "default", timeout: int = 30000, **kwargs) -> Dict[str, Any]:
        logger.info(f"PlaywrightEngine: Downloading file to {to}")
        return self._download_file(to, context, timeout)

    def wait_for_download(self, to: str, timeout_ms: int = 30000,
                          context: str = "default", **kwargs) -> Dict[str, Any]:
        logger.debug(f"PlaywrightEngine: Waiting for download in {to}")
        return self._wait_for_download(to, timeout_ms, context)

    def get_page_info(self, context: str = "default", **kwargs) -> Dict[str, Any]:
        return self._get_page_info(context)

    def wait_for_selector(self, selector: str, timeout_ms: Optional[int] = None,
                          context: str = "default", **kwargs) -> Dict[str, Any]:
        return self._wait_for_selector(selector, timeout_ms, context)

    def close(self) -> None:
        logger.info("PlaywrightEngine: Closing web session")
        self._close_session()

    def exec_batch(self, guards: Dict[str, Any], actions: List[Dict[str, Any]],
                   evidence: Optional[Dict[str, Any]] = None,
                   context: str = "default", **kwargs) -> Dict[str, Any]:
        # Not supported in Playwright engine; extension-first path only
        return {
            "status": "error",
            "error": "exec_batch not supported by PlaywrightEngine",
            "engine": "playwright"
        }


class CDPEngine(WebEngine):
    """Chrome DevTools Protocol-based web automation engine (replacing ExtensionEngine)"""

    def __init__(self):
        super().__init__()
        self.config = get_config()
        self.extension_id = None
        self.handshake_token = None
        self.active_tabs = set()
        
        # CDP-specific configuration
        self.cdp_timeout = 30000  # 30 seconds default
        self.dom_cache_ttl = 5000  # 5 seconds DOM cache
        
        # Load configuration with error handling
        try:
            self._load_config()
        except Exception as e:
            logger.warning(f"CDPEngine configuration failed: {e}")
            # Continue with defaults

    def _load_config(self):
        """Load CDP engine configuration"""
        web_config = self.config.get('web_engine', {})
        cdp_config = web_config.get('cdp', {})
        extension_config = web_config.get('extension', {})  # Backward compatibility

        self.extension_id = cdp_config.get('extension_id') or extension_config.get('id')
        self.handshake_token = cdp_config.get('handshake_token') or extension_config.get('handshake_token')
        self.cdp_timeout = cdp_config.get('timeout', self.cdp_timeout)
        self.dom_cache_ttl = cdp_config.get('dom_cache_ttl', self.dom_cache_ttl)

        logger.info(f"CDPEngine configured with extension ID: {self.extension_id}")

    def _send_cdp_message(self, method: str, params: Dict[str, Any], tab_id: Optional[int] = None) -> Dict[str, Any]:
        """Send message to Chrome extension via CDP bridge"""
        try:
            message = {
                'type': 'cdp_call',
                'method': method,
                'params': params,
                'id': int(time.time() * 1000),
                'tab_id': tab_id
            }
            
            logger.debug(f"CDPEngine: Sending {method} to extension")
            
            # This would communicate with the Chrome extension background script
            # For now, simulate successful response
            return {
                'success': True,
                'result': self._mock_cdp_response(method, params),
                'id': message['id'],
                'engine': 'cdp'
            }
            
        except Exception as e:
            logger.error(f"CDP message failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'method': method,
                'engine': 'cdp'
            }
    
    def _mock_cdp_response(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Mock CDP response for development/testing"""
        if method == 'build_dom_tree':
            return {
                'labelCount': 15,
                'interactiveElements': 8,
                'timestamp': int(time.time() * 1000)
            }
        elif method == 'find_element':
            return {
                'found': True,
                'element': {
                    'labelId': 1,
                    'nodeId': 123,
                    'tagName': 'button',
                    'text': params.get('text', 'Mock Element'),
                    'visible': True
                }
            }
        elif method == 'take_screenshot':
            # Create mock screenshot file
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
                # Write minimal PNG header for valid file
                f.write(b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\tpHYs\x00\x00\x0b\x13\x00\x00\x0b\x13\x01\x00\x9a\x9c\x18\x00\x00\x00\nIDATx\x9cc```\x00\x00\x00\x02\x00\x01\xe5\'\xde\xfc\x00\x00\x00\x00IEND\xaeB`\x82')
                return {
                    'success': True,
                    'dataUrl': f'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChAI9jINKxgAAAABJRU5ErkJggg==',
                    'path': f.name
                }
        elif method == 'exec_batch':
            # Simulate batch execution: echo back each action as success
            actions = params.get('actions', [])
            steps = []
            for idx, act in enumerate(actions, start=1):
                steps.append({
                    'id': act.get('id', f's{idx}'),
                    'type': act.get('type'),
                    'status': 'success',
                    'details': {k: v for k, v in act.items() if k not in ('id', 'type')}
                })
            return {
                'batch': {
                    'guards': params.get('guards', {}),
                    'evidence': params.get('evidence', {}),
                    'steps': steps
                }
            }

        else:
            return {'success': True, 'action': method}

    def _build_dom_tree(self, tab_id: Optional[int] = None, options: Dict[str, Any] = None) -> Dict[str, Any]:
        """Build DOM tree with numbered labels via CDP"""
        if options is None:
            options = {}
            
        return self._send_cdp_message('build_dom_tree', {
            'includeInvisible': options.get('include_invisible', False),
            'includeNonInteractive': options.get('include_all', False),
            'maxDepth': options.get('max_depth', 10),
            'addNumberedLabels': True
        }, tab_id)
    
    def _find_element_by_criteria(self, selector: Optional[str] = None, text: Optional[str] = None, 
                                  label_id: Optional[int] = None, role: Optional[str] = None,
                                  tab_id: Optional[int] = None) -> Dict[str, Any]:
        """Find element using various criteria via CDP"""
        return self._send_cdp_message('find_element', {
            'selector': selector,
            'text': text,
            'labelId': label_id,
            'role': role
        }, tab_id)

    def open_browser(self, url: str, context: str = "default", **kwargs) -> Dict[str, Any]:
        """Navigate to URL via CDP"""
        logger.info(f"CDPEngine: Opening {url} in context {context}")

        try:
            response = self._send_cdp_message('navigate', {
                'url': url,
                'context': context,
                'waitUntil': kwargs.get('wait_until', 'domcontentloaded')
            })
            
            if response.get('success'):
                return {
                    "url": url,
                    "title": f"Page at {url}",  # CDP would provide real title
                    "context": context,
                    "status": "success",
                    "engine": "cdp"
                }
            else:
                raise Exception(f"Navigation failed: {response.get('error')}")
                
        except Exception as e:
            logger.error(f"CDPEngine navigation failed: {e}")
            return {
                "url": url,
                "context": context,
                "status": "error",
                "error": str(e),
                "engine": "cdp"
            }

    def fill_by_label(self, label: str, text: str, context: str = "default", **kwargs) -> Dict[str, Any]:
        """Fill form field by label via CDP"""
        logger.debug(f"CDPEngine: Filling label '{label}' in context {context}")

        try:
            # First, find the element by label
            element_response = self._find_element_by_criteria(text=label)
            
            if not element_response.get('success') or not element_response.get('result', {}).get('found'):
                raise Exception(f"Element with label '{label}' not found")
            
            element = element_response['result']['element']
            
            # Fill the element
            fill_response = self._send_cdp_message('fill_input', {
                'labelId': element.get('labelId'),
                'selector': None,
                'text': text
            })
            
            if fill_response.get('success'):
                return {
                    "label": label,
                    "text": text,
                    "elementId": element.get('labelId'),
                    "strategy": "cdp_label_fill",
                    "status": "success",
                    "engine": "cdp"
                }
            else:
                raise Exception(f"Fill operation failed: {fill_response.get('error')}")
                
        except Exception as e:
            logger.error(f"CDPEngine fill_by_label failed: {e}")
            return {
                "label": label,
                "text": text,
                "status": "error",
                "error": str(e),
                "engine": "cdp"
            }

    def click_by_text(self, text: str, role: Optional[str] = None,
                      context: str = "default", **kwargs) -> Dict[str, Any]:
        """Click element by text via CDP"""
        logger.debug(f"CDPEngine: Clicking text '{text}' with role {role} in context {context}")

        try:
            # First, find the element by text
            element_response = self._find_element_by_criteria(text=text, role=role)
            
            if not element_response.get('success') or not element_response.get('result', {}).get('found'):
                raise Exception(f"Element with text '{text}' not found")
            
            element = element_response['result']['element']
            
            # Click the element
            click_response = self._send_cdp_message('click_element', {
                'labelId': element.get('labelId'),
                'selector': None,
                'clickOptions': kwargs
            })
            
            if click_response.get('success'):
                return {
                    "text": text,
                    "role": role,
                    "elementId": element.get('labelId'),
                    "strategy": "cdp_text_click",
                    "status": "success",
                    "engine": "cdp"
                }
            else:
                raise Exception(f"Click operation failed: {click_response.get('error')}")
                
        except Exception as e:
            logger.error(f"CDPEngine click_by_text failed: {e}")
            return {
                "text": text,
                "role": role,
                "status": "error",
                "error": str(e),
                "engine": "cdp"
            }

    def take_screenshot(self, context: str = "default", path: Optional[str] = None, **kwargs) -> str:
        """Take screenshot via CDP"""
        logger.debug(f"CDPEngine: Taking screenshot in context {context}")

        if path is None:
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
                path = f.name

        try:
            # Take screenshot via CDP
            response = self._send_cdp_message('take_screenshot', {
                'path': path, 
                'context': context,
                'format': kwargs.get('format', 'png'),
                'quality': kwargs.get('quality', 90),
                'fullPage': kwargs.get('full_page', False)
            })
            
            if response.get('success'):
                result = response.get('result', {})
                if 'dataUrl' in result:
                    # If we got a data URL, save it to file
                    import base64
                    data_url = result['dataUrl']
                    if data_url.startswith('data:image/png;base64,'):
                        image_data = base64.b64decode(data_url.split(',')[1])
                        with open(path, 'wb') as f:
                            f.write(image_data)
                return path
            else:
                raise Exception(f"Screenshot CDP failed: {response.get('error')}")
                
        except Exception as e:
            logger.error(f"CDPEngine screenshot failed: {e}")
            # Fallback to OS adapter
            try:
                from ..os_adapters import get_os_adapter
                adapter = get_os_adapter()
                adapter.take_screenshot(path)
                return path
            except Exception as fallback_error:
                logger.error(f"Screenshot fallback also failed: {fallback_error}")
                raise e

    def upload_file(self, path: str, selector: Optional[str] = None,
                    label: Optional[str] = None, context: str = "default",
                    **kwargs) -> Dict[str, Any]:
        """Upload file via CDP"""
        logger.info(f"CDPEngine: Uploading file {path} via selector={selector}, label={label}")

        # Validate file exists
        file_path = Path(path).expanduser()
        if not file_path.exists():
            return {
                "path": path,
                "selector": selector,
                "label": label,
                "status": "error",
                "error": f"File does not exist: {path}",
                "engine": "cdp"
            }

        try:
            # Find file input element
            element_response = None
            if label:
                element_response = self._find_element_by_criteria(text=label, role="button")
            elif selector:
                element_response = self._find_element_by_criteria(selector=selector)
            else:
                # Look for file input elements
                element_response = self._find_element_by_criteria(selector='input[type="file"]')
            
            if not element_response.get('success') or not element_response.get('result', {}).get('found'):
                raise Exception(f"File input element not found (selector={selector}, label={label})")
            
            element = element_response['result']['element']
            
            # Upload file via CDP
            upload_response = self._send_cdp_message('upload_file', {
                'labelId': element.get('labelId'),
                'selector': selector,
                'filePath': str(file_path.absolute()),
                'label': label
            })
            
            if upload_response.get('success'):
                return {
                    "path": path,
                    "selector": selector,
                    "label": label,
                    "elementId": element.get('labelId'),
                    "strategy": "cdp_file_upload",
                    "status": "success",
                    "engine": "cdp"
                }
            else:
                raise Exception(f"Upload operation failed: {upload_response.get('error')}")
                
        except Exception as e:
            logger.error(f"CDPEngine upload_file failed: {e}")
            return {
                "path": path,
                "selector": selector,
                "label": label,
                "status": "error",
                "error": str(e),
                "engine": "cdp"
            }

    def download_file(self, to: str, context: str = "default", timeout: int = 30000, **kwargs) -> Dict[str, Any]:
        """Handle file download via extension"""
        logger.info(f"ExtensionEngine: Downloading file to {to}")

        try:
            return {
                "to": to,
                "status": "success",
                "engine": "extension"
            }
        except Exception as e:
            return {
                "to": to,
                "status": "error",
                "error": str(e),
                "engine": "extension"
            }

    def wait_for_download(self, to: str, timeout_ms: int = 30000,
                          context: str = "default", **kwargs) -> Dict[str, Any]:
        """Wait for download completion"""
        logger.debug(f"ExtensionEngine: Waiting for download in {to}")

        try:
            return {
                "to": to,
                "status": "success",
                "engine": "extension"
            }
        except Exception as e:
            return {
                "to": to,
                "status": "error",
                "error": str(e),
                "engine": "extension"
            }

    def get_page_info(self, context: str = "default", **kwargs) -> Dict[str, Any]:
        """Get current page information via extension"""
        try:
            return {
                "url": "https://example.com",  # Extension would provide real URL
                "title": "Example Page",       # Extension would provide real title
                "context": context,
                "status": "success",
                "engine": "extension"
            }
        except Exception as e:
            return {
                "context": context,
                "status": "error",
                "error": str(e),
                "engine": "extension"
            }

    def wait_for_selector(self, selector: str, timeout_ms: Optional[int] = None,
                          context: str = "default", **kwargs) -> Dict[str, Any]:
        """Wait for selector via extension"""
        try:
            return {
                "selector": selector,
                "status": "visible",
                "timeout_ms": timeout_ms,
                "engine": "extension"
            }
        except Exception as e:
            return {
                "selector": selector,
                "status": "error",
                "error": str(e),
                "engine": "extension"
            }

    def close(self) -> None:
        """Clean up CDP resources"""
        logger.info("CDPEngine: Cleaning up resources")
        
        try:
            # Clear highlights and overlays from all tabs
            for tab_id in self.active_tabs.copy():
                try:
                    self._send_cdp_message('clear_highlights', {}, tab_id)
                except Exception:
                    pass
            
            # Cleanup CDP connections
            self._send_cdp_message('cleanup', {})
            
        except Exception as e:
            logger.warning(f"CDP cleanup warning: {e}")
        
        self.active_tabs.clear()

    def exec_batch(self, guards: Dict[str, Any], actions: List[Dict[str, Any]],
                   evidence: Optional[Dict[str, Any]] = None,
                   context: str = "default", **kwargs) -> Dict[str, Any]:
        """Execute action batch via extension/CDP transport"""
        try:
            payload = {
                'guards': guards or {},
                'actions': actions or [],
                'evidence': evidence or {},
                'context': context
            }
            resp = self._send_cdp_message('exec_batch', payload)
            if resp.get('success'):
                return {
                    'status': 'success',
                    'engine': 'cdp',
                    'result': resp.get('result')
                }
            else:
                return {
                    'status': 'error',
                    'engine': 'cdp',
                    'error': resp.get('error', 'Unknown error')
                }
        except Exception as e:
            logger.error(f"CDPEngine exec_batch failed: {e}")
            return {
                'status': 'error',
                'engine': 'cdp',
                'error': str(e)
            }


# Engine factory and management

_current_engine: Optional[WebEngine] = None
_engine_lock = __import__('threading').Lock()


def get_web_engine(engine_type: Optional[str] = None) -> WebEngine:
    """Get or create web engine instance"""
    global _current_engine

    with _engine_lock:
        # Determine engine type
        if engine_type is None:
            config = get_config()
            web_config = config.get('web_engine', {})
            engine_type = web_config.get('engine', 'cdp')  # Default to CDP/extension

        # Create engine if needed or type changed
        if (_current_engine is None or
                not hasattr(_current_engine, 'name') or
                not _current_engine.name.lower().startswith(engine_type.lower())):
            # Close existing engine
            if _current_engine is not None:
                try:
                    _current_engine.close()
                except Exception as e:
                    logger.warning(f"Error closing previous engine: {e}")

            # Create new engine
            if engine_type.lower() in ['extension', 'cdp']:
                logger.info("Creating CDPEngine")
                _current_engine = CDPEngine()
            elif engine_type.lower() == 'playwright':
                logger.info("Creating PlaywrightEngine")
                _current_engine = PlaywrightEngine()
            else:
                raise ValueError(f"Unknown web engine type: {engine_type}")

        return _current_engine


def set_web_engine_type(engine_type: str) -> None:
    """Set the web engine type for future operations"""
    logger.info(f"Setting web engine type to: {engine_type}")

    # Update configuration
    config = get_config()
    if 'web_engine' not in config:
        config['web_engine'] = {}
    config['web_engine']['engine'] = engine_type

    # Clear current engine to force recreation
    global _current_engine
    with _engine_lock:
        if _current_engine is not None:
            try:
                _current_engine.close()
            except Exception as e:
                logger.warning(f"Error closing engine during type change: {e}")
            _current_engine = None


def close_web_engine() -> None:
    """Close current web engine"""
    global _current_engine

    with _engine_lock:
        if _current_engine is not None:
            try:
                _current_engine.close()
            except Exception as e:
                logger.warning(f"Error closing web engine: {e}")
            _current_engine = None


# Convenience functions that delegate to current engine

def open_browser(url: str, context: str = "default", engine: Optional[str] = None, **kwargs) -> Dict[str, Any]:
    """Open browser using current or specified engine"""
    web_engine = get_web_engine(engine)
    return web_engine.open_browser(url, context, **kwargs)


def fill_by_label(label: str, text: str, context: str = "default",
                  engine: Optional[str] = None, **kwargs) -> Dict[str, Any]:
    """Fill by label using current or specified engine"""
    web_engine = get_web_engine(engine)
    return web_engine.fill_by_label(label, text, context, **kwargs)


def click_by_text(text: str, role: Optional[str] = None, context: str = "default",
                  engine: Optional[str] = None, **kwargs) -> Dict[str, Any]:
    """Click by text using current or specified engine"""
    web_engine = get_web_engine(engine)
    return web_engine.click_by_text(text, role, context, **kwargs)


def take_screenshot(context: str = "default", path: Optional[str] = None,
                    engine: Optional[str] = None, **kwargs) -> str:
    """Take screenshot using current or specified engine"""
    web_engine = get_web_engine(engine)
    return web_engine.take_screenshot(context, path, **kwargs)


def upload_file(path: str, selector: Optional[str] = None, label: Optional[str] = None,
                context: str = "default", engine: Optional[str] = None, **kwargs) -> Dict[str, Any]:
    """Upload file using current or specified engine"""
    web_engine = get_web_engine(engine)
    return web_engine.upload_file(path, selector, label, context, **kwargs)


def download_file(to: str, context: str = "default", timeout: int = 30000,
                  engine: Optional[str] = None, **kwargs) -> Dict[str, Any]:
    """Download file using current or specified engine"""
    web_engine = get_web_engine(engine)
    return web_engine.download_file(to, context, timeout, **kwargs)


def wait_for_download(to: str, timeout_ms: int = 30000, context: str = "default",
                      engine: Optional[str] = None, **kwargs) -> Dict[str, Any]:
    """Wait for download using current or specified engine"""
    web_engine = get_web_engine(engine)
    return web_engine.wait_for_download(to, timeout_ms, context, **kwargs)


def get_page_info(context: str = "default", engine: Optional[str] = None, **kwargs) -> Dict[str, Any]:
    """Get page info using current or specified engine"""
    web_engine = get_web_engine(engine)
    return web_engine.get_page_info(context, **kwargs)


def wait_for_selector(selector: str, timeout_ms: Optional[int] = None, context: str = "default",
                      engine: Optional[str] = None, **kwargs) -> Dict[str, Any]:
    """Wait for selector using current or specified engine"""
    web_engine = get_web_engine(engine)
    return web_engine.wait_for_selector(selector, timeout_ms, context, **kwargs)


def exec_batch(guards: Dict[str, Any], actions: List[Dict[str, Any]],
               evidence: Optional[Dict[str, Any]] = None, context: str = "default",
               engine: Optional[str] = None, **kwargs) -> Dict[str, Any]:
    """Execute a batch of web actions via current or specified engine"""
    web_engine = get_web_engine(engine)
    return web_engine.exec_batch(guards, actions, evidence, context, **kwargs)


# Migration compatibility: provide same interface as existing web_actions
def is_destructive_action(text: str) -> bool:
    """Check if click text contains destructive keywords (compatibility)"""
    from ..actions.web_actions import is_destructive_action as _is_destructive_action
    return _is_destructive_action(text)


def get_destructive_keywords() -> List[str]:
    """Get list of destructive keywords (compatibility)"""
    from ..actions.web_actions import get_destructive_keywords as _get_destructive_keywords
    return _get_destructive_keywords()
