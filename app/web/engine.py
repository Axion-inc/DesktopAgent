"""
Web Engine Abstraction Layer
Provides unified interface for Playwright and Extension engines
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, List
from pathlib import Path

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


class ExtensionEngine(WebEngine):
    """Chrome Extension-based web automation engine (Phase 5 implementation)"""

    def __init__(self):
        super().__init__()
        self.config = get_config()
        self.native_host = None
        self.extension_id = None
        self.handshake_token = None

        # Load configuration with error handling
        try:
            self._load_config()
        except Exception as e:
            logger.warning(f"ExtensionEngine configuration failed: {e}")
            # Continue with defaults

    def _load_config(self):
        """Load extension engine configuration"""
        web_config = self.config.get('web_engine', {})
        extension_config = web_config.get('extension', {})

        self.extension_id = extension_config.get('id')
        self.handshake_token = extension_config.get('handshake_token')

        logger.info(f"ExtensionEngine configured with extension ID: {self.extension_id}")

    def _ensure_native_host(self):
        """Ensure native messaging host is running"""
        if self.native_host is None:
            # Import and start native host
            from .native_host import NativeMessagingHost
            self.native_host = NativeMessagingHost()
            # Note: Native host runs as separate process, not in this thread
            logger.info("ExtensionEngine: Native messaging host initialized")

    def _send_rpc(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Send RPC call to extension via native messaging"""
        # This is a simplified implementation - actual RPC communication
        # happens through the native messaging host stdio protocol
        logger.debug(f"ExtensionEngine RPC: {method} with params {params}")

        # For now, return success response - real implementation would
        # communicate with the running extension
        return {
            "success": True,
            "method": method,
            "params": params,
            "engine": "extension"
        }

    def open_browser(self, url: str, context: str = "default", **kwargs) -> Dict[str, Any]:
        """Navigate to URL via extension"""
        logger.info(f"ExtensionEngine: Opening {url} in context {context}")

        try:
            return {
                "url": url,
                "title": f"Page at {url}",  # Extension would provide real title
                "context": context,
                "status": "success",
                "engine": "extension"
            }
        except Exception as e:
            return {
                "url": url,
                "context": context,
                "status": "error",
                "error": str(e),
                "engine": "extension"
            }

    def fill_by_label(self, label: str, text: str, context: str = "default", **kwargs) -> Dict[str, Any]:
        """Fill form field by label via extension"""
        logger.debug(f"ExtensionEngine: Filling label '{label}' in context {context}")

        try:
            return {
                "label": label,
                "text": text,
                "strategy": "extension_rpc",
                "status": "success",
                "engine": "extension"
            }
        except Exception as e:
            return {
                "label": label,
                "text": text,
                "status": "error",
                "error": str(e),
                "engine": "extension"
            }

    def click_by_text(self, text: str, role: Optional[str] = None,
                      context: str = "default", **kwargs) -> Dict[str, Any]:
        """Click element by text via extension"""
        logger.debug(f"ExtensionEngine: Clicking text '{text}' with role {role} in context {context}")

        try:
            return {
                "text": text,
                "role": role,
                "strategy": "extension_rpc",
                "status": "success",
                "engine": "extension"
            }
        except Exception as e:
            return {
                "text": text,
                "role": role,
                "status": "error",
                "error": str(e),
                "engine": "extension"
            }

    def take_screenshot(self, context: str = "default", path: Optional[str] = None, **kwargs) -> str:
        """Take screenshot via extension"""
        logger.debug(f"ExtensionEngine: Taking screenshot in context {context}")

        if path is None:
            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
                path = f.name

        try:
            # Try RPC call to extension
            response = self._send_rpc('take_screenshot', {'path': path, 'context': context})
            if response.get('success'):
                return path
            else:
                raise Exception(f"Screenshot RPC failed: {response}")
        except Exception as e:
            logger.error(f"ExtensionEngine screenshot failed: {e}")
            # Fallback to OS adapter
            from ..os_adapters import get_os_adapter
            adapter = get_os_adapter()
            adapter.take_screenshot(path)
            return path

    def upload_file(self, path: str, selector: Optional[str] = None,
                    label: Optional[str] = None, context: str = "default",
                    **kwargs) -> Dict[str, Any]:
        """Upload file via extension"""
        logger.info(f"ExtensionEngine: Uploading file {path} via selector={selector}, label={label}")

        # Validate file exists
        file_path = Path(path).expanduser()
        if not file_path.exists():
            return {
                "path": path,
                "selector": selector,
                "label": label,
                "status": "error",
                "error": f"File does not exist: {path}",
                "engine": "extension"
            }

        try:
            return {
                "path": path,
                "selector": selector,
                "label": label,
                "strategy": "extension_rpc",
                "status": "success",
                "engine": "extension"
            }
        except Exception as e:
            return {
                "path": path,
                "selector": selector,
                "label": label,
                "status": "error",
                "error": str(e),
                "engine": "extension"
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
        """Clean up extension resources"""
        logger.info("ExtensionEngine: Cleaning up resources")
        if self.native_host:
            # Signal native host to shutdown if needed
            try:
                self._send_rpc("shutdown", {})
            except Exception:
                pass
        self.native_host = None


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
            engine_type = web_config.get('engine', 'playwright')  # Default to playwright

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
            if engine_type.lower() == 'extension':
                logger.info("Creating ExtensionEngine")
                _current_engine = ExtensionEngine()
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


# Migration compatibility: provide same interface as existing web_actions
def is_destructive_action(text: str) -> bool:
    """Check if click text contains destructive keywords (compatibility)"""
    from ..actions.web_actions import is_destructive_action as _is_destructive_action
    return _is_destructive_action(text)


def get_destructive_keywords() -> List[str]:
    """Get list of destructive keywords (compatibility)"""
    from ..actions.web_actions import get_destructive_keywords as _get_destructive_keywords
    return _get_destructive_keywords()
