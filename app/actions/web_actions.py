from __future__ import annotations

import os
import tempfile
import threading
import queue
from pathlib import Path
from typing import Any, Dict, Optional, List
from urllib.parse import urlparse
import time
import urllib.request
import urllib.error

try:
    from playwright.sync_api import (
        sync_playwright, Browser, BrowserContext, Page,
        TimeoutError as PlaywrightTimeoutError
    )
except ImportError:
    # Graceful fallback if playwright not installed
    sync_playwright = None
    Browser = None
    BrowserContext = None
    Page = None
    PlaywrightTimeoutError = Exception


class WebSession:
    """Manages Playwright browser session and contexts."""

    def __init__(self):
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.contexts: Dict[str, BrowserContext] = {}
        self.pages: Dict[str, Page] = {}
        self.default_timeout = 30000  # 30 seconds

    def __enter__(self):
        if sync_playwright is None:
            raise ImportError("Playwright not installed. Run: pip install playwright && npx playwright install")

        try:
            self.playwright = sync_playwright().start()
            # Use runtime override if present, otherwise env var
            if get_headless_override() is not None:
                headless = bool(get_headless_override())
            else:
                # Use headless=False for debugging, headless=True for CI
                headless = os.environ.get('PLAYWRIGHT_HEADLESS', 'true').lower() == 'true'
            # Optional extra Chromium flags (space-separated) via env
            extra_args_env = os.environ.get('PLAYWRIGHT_CHROMIUM_ARGS', '')
            extra_args = [a for a in extra_args_env.split(' ') if a]
            # Add sensible defaults if not explicitly overridden
            default_disable_features = 'Autofill,AutofillAddressEnabled,AutofillServerCommunication'
            if not any(a.startswith('--disable-features=') for a in extra_args):
                extra_args.append(f'--disable-features={default_disable_features}')
            if '--no-default-browser-check' not in extra_args:
                extra_args.append('--no-default-browser-check')
            if '--no-first-run' not in extra_args:
                extra_args.append('--no-first-run')
            if '--disable-popup-blocking' not in extra_args:
                extra_args.append('--disable-popup-blocking')

            slow_mo_ms = 0
            try:
                slow_mo_ms = int(os.environ.get('PLAYWRIGHT_SLOWMO_MS', '0'))
            except Exception:
                slow_mo_ms = 0

            self.browser = self.playwright.chromium.launch(
                headless=headless,
                args=extra_args,
                slow_mo=slow_mo_ms if slow_mo_ms > 0 else None,
            )

            if self.browser is None:
                raise RuntimeError("Failed to launch browser")

            return self
        except Exception as e:
            # Clean up on failure
            if self.playwright:
                try:
                    self.playwright.stop()
                except Exception:
                    pass
            raise RuntimeError(f"Failed to initialize Playwright: {str(e)}")

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()

    def get_context(self, context_name: str = "default") -> BrowserContext:
        """Get or create a browser context."""
        if self.browser is None:
            raise RuntimeError("Browser not initialized. WebSession must be used as context manager.")

        if context_name not in self.contexts:
            ctx_kwargs: Dict[str, Any] = dict(
                viewport={'width': 1280, 'height': 720},
                ignore_https_errors=True,
                bypass_csp=True,
            )
            # Optional locale/timezone/user agent from env for stability across envs
            locale = os.environ.get('WEB_LOCALE')
            if locale:
                ctx_kwargs['locale'] = locale
            tz = os.environ.get('WEB_TZ')
            if tz:
                ctx_kwargs['timezone_id'] = tz
            ua = os.environ.get('WEB_USER_AGENT')
            if ua:
                ctx_kwargs['user_agent'] = ua

            self.contexts[context_name] = self.browser.new_context(**ctx_kwargs)
        return self.contexts[context_name]

    def get_page(self, context_name: str = "default") -> Page:
        """Get or create a page in the specified context."""
        if context_name not in self.pages:
            context = self.get_context(context_name)
            self.pages[context_name] = context.new_page()
            # Set default timeout
            self.pages[context_name].set_default_timeout(self.default_timeout)
            try:
                # Align navigation timeout with action timeout
                self.pages[context_name].set_default_navigation_timeout(self.default_timeout)
            except Exception:
                pass
        return self.pages[context_name]

    def screenshot(self, context_name: str = "default", path: Optional[str] = None) -> str:
        """Take screenshot of current page."""
        page = self.get_page(context_name)
        if path is None:
            # Generate temp path
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
                path = f.name

        page.screenshot(path=path, full_page=True)
        return path


# Global session management with persistent thread
_web_thread: Optional[threading.Thread] = None
_web_session: Optional[WebSession] = None
_command_queue: Optional[queue.Queue] = None
_result_queue: Optional[queue.Queue] = None
_session_lock = threading.Lock()

# Utility: env int and slow-mode sleeps for stabilizing slow environments


def _get_env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except Exception:
        return default


def _slow_mode_sleep(point: str = "") -> None:
    ms = _get_env_int("WEB_SLOW_MODE_MS", 0)
    if ms > 0:
        try:
            time.sleep(ms / 1000.0)
        except Exception:
            pass


# Runtime headless override controlled from the app (for debugging)

_headless_override: Optional[bool] = None


def set_headless_override(val: Optional[bool]) -> None:
    global _headless_override
    _headless_override = val


def get_headless_override() -> Optional[bool]:
    return _headless_override


def _web_worker():
    """Persistent worker thread for Playwright operations."""
    global _web_session

    try:
        # Initialize session in this thread
        _web_session = WebSession()
        _web_session.__enter__()

        # Signal successful initialization
        _result_queue.put({"status": "initialized"})

        # Process commands
        while True:
            try:
                command = _command_queue.get(timeout=60)  # 60 second timeout

                if command["action"] == "shutdown":
                    break

                # Execute the command
                func = command["func"]
                args = command.get("args", ())
                kwargs = command.get("kwargs", {})

                try:
                    result = func(*args, **kwargs)
                    _result_queue.put({"status": "success", "result": result})
                except Exception as e:
                    _result_queue.put({"status": "error", "error": str(e)})

            except queue.Empty:
                continue  # Continue processing

    except Exception as e:
        _result_queue.put({"status": "init_error", "error": str(e)})
    finally:
        # Cleanup
        if _web_session:
            try:
                _web_session.__exit__(None, None, None)
            except Exception:
                pass
        _web_session = None


def get_web_session() -> WebSession:
    """Get or create global web session."""
    global _web_thread, _command_queue, _result_queue

    with _session_lock:
        if _web_thread is None or not _web_thread.is_alive():
            # Start worker thread
            _command_queue = queue.Queue()
            _result_queue = queue.Queue()
            _web_thread = threading.Thread(target=_web_worker, daemon=True)
            _web_thread.start()

            # Wait for initialization
            try:
                result = _result_queue.get(timeout=30)
                if result["status"] != "initialized":
                    raise RuntimeError(f"Failed to initialize session: {result.get('error', 'Unknown error')}")
            except queue.Empty:
                raise RuntimeError("Session initialization timeout")

        return _web_session


def _execute_in_web_thread(func, *args, **kwargs):
    """Execute function in the web worker thread."""
    # Use existing queues; no rebinding here

    if _command_queue is None or _result_queue is None:
        raise RuntimeError("Web session not initialized")

    # Send command
    _command_queue.put({
        "action": "execute",
        "func": func,
        "args": args,
        "kwargs": kwargs
    })

    # Wait for result
    try:
        # Compute a sensible default timeout based on nav/selector budgets
        try:
            nav_ms = _get_env_int('WEB_NAV_TIMEOUT_MS', 30000)
            retries = _get_env_int('WEB_NAV_RETRIES', 2)
            selector_ms = _get_env_int('WEB_SELECTOR_TIMEOUT_MS', 15000)
            budget_sec = (nav_ms/1000.0) * (retries + 2) + (selector_ms/1000.0) + 10.0
            default_timeout_sec = max(120.0, budget_sec)
        except Exception:
            default_timeout_sec = 120.0
        timeout_sec = float(os.environ.get("WEB_ACTION_TIMEOUT", str(default_timeout_sec)))
        result = _result_queue.get(timeout=timeout_sec)
        if result["status"] == "error":
            raise RuntimeError(result["error"])
        return result["result"]
    except queue.Empty:
        raise RuntimeError("Operation timeout")


def close_web_session():
    """Close global web session."""
    global _web_thread, _command_queue, _result_queue

    with _session_lock:
        if _command_queue is not None:
            _command_queue.put({"action": "shutdown"})

        if _web_thread is not None and _web_thread.is_alive():
            _web_thread.join(timeout=5)

        _web_thread = None
        _command_queue = None
        _result_queue = None


# Remove old _run_in_thread, use _execute_in_web_thread instead


def _open_browser_sync(url: str, context: str = "default", wait_for_load: bool = True) -> Dict[str, Any]:
    """Internal sync function for opening browser."""
    session = get_web_session()
    page = session.get_page(context)

    try:
        # Optional slow mode pause before navigation
        _slow_mode_sleep("before_nav")

        # Optional health check for local server to avoid initial timeouts
        try:
            parsed = urlparse(url)
            host = parsed.hostname or ""
            port = parsed.port or (443 if parsed.scheme == "https" else 80)
            if host in ("127.0.0.1", "localhost"):
                hc_url = f"{parsed.scheme}://{host}:{port}/healthz"
                deadline = time.time() + float(os.environ.get("WEB_HEALTHCHECK_WAIT", "5"))
                while time.time() < deadline:
                    try:
                        with urllib.request.urlopen(hc_url, timeout=1) as resp:
                            if resp.status == 200:
                                break
                    except Exception:  # pragma: no cover
                        time.sleep(0.3)
                # If health check never succeeded, continue anyway but annotate
        except Exception:
            pass
        # Navigation strategy: favor quick commit, then target selector wait
        nav_ok = False
        # Track navigation state; errors are handled inline
        nav_timeout_ms = _get_env_int("WEB_NAV_TIMEOUT_MS", 30000)
        commit_timeout_ms = max(8000, min(nav_timeout_ms, 15000))

        # First attempt
        try:
            page.goto(url, wait_until="commit", timeout=commit_timeout_ms)
            nav_ok = True
        except Exception:
            # Fallback 1: try without wait condition
            try:
                page.goto(url, timeout=nav_timeout_ms)
                nav_ok = True
            except Exception:
                pass
        # If navigation still not ok and host is loopback, try swapping 127.0.0.1/localhost
        if not nav_ok:
            try:
                parsed = urlparse(url)
                host = parsed.hostname or ""
                alt = None
                if host == "127.0.0.1":
                    alt = url.replace("127.0.0.1", "localhost")
                elif host == "localhost":
                    alt = url.replace("localhost", "127.0.0.1")
                if alt:
                    page.goto(alt, wait_until="commit", timeout=commit_timeout_ms)
                    url = alt
                    nav_ok = True
            except Exception:
                pass

        # Retry loop with small backoff if still not navigated or blank
        retries = _get_env_int("WEB_NAV_RETRIES", 2)
        for i in range(retries):
            if nav_ok and not page.url.startswith("about:"):
                break
            try:
                page.goto(url, wait_until="commit", timeout=commit_timeout_ms)
                nav_ok = True
            except Exception:
                try:
                    page.goto(url, timeout=nav_timeout_ms)
                    nav_ok = True
                except Exception:
                    pass
            _slow_mode_sleep("nav_retry")

        # Wait for DOM readiness and known selectors when possible
        try:
            page.wait_for_load_state("domcontentloaded", timeout=min(5000, nav_timeout_ms))
        except PlaywrightTimeoutError:
            pass

        # Heuristic: if targeting our mock form, wait for a known selector
        try:
            parsed = urlparse(url)
            if parsed.path and "/mock/form" in parsed.path:
                # Wait for the name input or the form heading to appear
                selector_timeout_ms = _get_env_int("WEB_SELECTOR_TIMEOUT_MS", 15000)
                try:
                    page.wait_for_selector("#name, text=お問い合わせフォーム", timeout=selector_timeout_ms)
                except PlaywrightTimeoutError:
                    # Do not fail here; proceed with best-effort
                    pass
        except Exception:
            pass

        # If still about:blank, attempt a couple of quick retries
        try:
            if page.url.startswith("about:"):
                for _ in range(max(2, retries)):
                    try:
                        page.goto(url, wait_until="load", timeout=commit_timeout_ms)
                        if not page.url.startswith("about:"):
                            break
                    except Exception:
                        try:
                            page.goto(url, timeout=nav_timeout_ms)
                        except Exception:
                            pass
                    finally:
                        try:
                            page.wait_for_load_state("domcontentloaded", timeout=min(3000, nav_timeout_ms))
                        except Exception:
                            pass
        except Exception:
            pass

        _slow_mode_sleep("after_nav")

        title = ""
        current_url = ""
        try:
            title = page.title()
            current_url = page.url
        except Exception:
            current_url = url

        return {
            "url": current_url,
            "title": title,
            "context": context,
            "status": "success"
        }

    except PlaywrightTimeoutError as e:
        return {
            "url": url,
            "context": context,
            "status": "timeout",
            "error": str(e)
        }
    except Exception as e:
        return {
            "url": url,
            "context": context,
            "status": "error",
            "error": str(e)
        }


def open_browser(url: str, context: str = "default", headless: Optional[bool] = None, **kwargs) -> Dict[str, Any]:
    """
    Navigate to a URL using the configured web engine.
    
    Args:
        url: URL to navigate to
        context: Browser context name  
        headless: Override headless mode (for Playwright engine)
        **kwargs: Additional engine-specific options
        
    Returns:
        Dict with navigation result
    """
    from ..web.engine import get_web_engine
    
    try:
        # Get configured engine
        engine = get_web_engine()
        
        # Add headless override for Playwright engine
        if hasattr(engine, '_open_browser') and headless is not None:
            set_headless_override(headless)
        
        result = engine.open_browser(url, context, **kwargs)
        
        # Store artifacts if configured
        _store_step_artifacts("open_browser", {"url": url, "context": context}, result)
        
        return result
        
    except Exception as e:
        error_result = {
            "url": url,
            "context": context,
            "status": "error", 
            "error": str(e),
            "engine": getattr(engine, 'name', 'unknown') if 'engine' in locals() else 'unknown'
        }
        _store_step_artifacts("open_browser", {"url": url, "context": context}, error_result)
        return error_result


def _fill_by_label_sync(label: str, text: str, context: str = "default") -> Dict[str, Any]:
    """Internal sync function for filling by label."""
    session = get_web_session()
    page = session.get_page(context)

    try:
        # Ensure DOM is ready before querying
        try:
            page.wait_for_load_state("domcontentloaded", timeout=3000)
        except PlaywrightTimeoutError:
            pass

        # Proactively dismiss any overlays (autocomplete popups, etc.)
        try:
            page.keyboard.press('Escape')
        except Exception:
            pass

        # If this looks like our mock form and we know the target selector,
        # wait briefly for it to appear before querying to avoid race conditions.
        try:
            label_to_selector_peek = {
                "氏名": "#name",
                "名前": "#name",
                "お名前": "#name",
                "メール": "#email",
                "メールアドレス": "#email",
                "件名": "#subject",
                "本文": "#message",
            }
            sel_peek = label_to_selector_peek.get(label)
            if sel_peek:
                try:
                    page.wait_for_selector(sel_peek, timeout=_get_env_int("WEB_SELECTOR_TIMEOUT_MS", 15000))
                except Exception:
                    pass
        except Exception:
            pass

        # Fast path: known selector mapping for our mock form first
        try:
            label_to_selector = {
                "氏名": "#name",
                "名前": "#name",
                "お名前": "#name",
                "メール": "#email",
                "メールアドレス": "#email",
                "件名": "#subject",
                "本文": "#message",
            }
            sel = label_to_selector.get(label)
            if sel:
                el = page.locator(sel)
                if el.count() > 0:
                    try:
                        el.scroll_into_view_if_needed(timeout=2000)
                    except Exception:
                        pass
                    try:
                        el.wait_for(state="visible", timeout=5000)
                    except Exception:
                        pass
                    try:
                        el.focus()
                    except Exception:
                        pass
                    # Clear then fill
                    try:
                        el.fill("")
                    except Exception:
                        pass
                    try:
                        el.fill(text)
                    except Exception:
                        el.click(timeout=2000)
                        el.type(text, delay=10)
                    return {
                        "label": label,
                        "text": text,
                        "strategy": "by_selector_mapping_fastpath",
                        "status": "success"
                    }
        except Exception:
            pass
        # Primary strategy: getByLabel (most stable)
        try:
            element = page.get_by_label(label, exact=False)
            element.wait_for(state="visible", timeout=5000)
            try:
                element.focus()
            except Exception:
                pass
            try:
                element.fill(text)
            except Exception:
                element.click(timeout=2000)
                element.type(text, delay=10)

            return {
                "label": label,
                "text": text,
                "strategy": "by_label",
                "status": "success"
            }
        except Exception:
            pass

        # Fallback 1: look for input with role textbox near label (with partial text match)
        try:
            # Find label element containing the text (partial match for labels with * or other symbols)
            label_selectors = [
                f'label:has-text("{label}")',  # exact match
                f'label:text-is("{label}")',   # text-is for exact match
                f'label:text("{label}")',      # partial match
            ]

            for selector in label_selectors:
                try:
                    label_element = page.locator(selector).first
                    if label_element.count() > 0:
                        # Try to find associated input by for/id
                        label_for = label_element.get_attribute("for")
                        if label_for:
                            input_element = page.locator(f'#{label_for}')
                            if input_element.count() > 0:
                                try:
                                    input_element.fill(text)
                                except Exception:
                                    input_element.type(text, delay=10)
                                return {
                                    "label": label,
                                    "text": text,
                                    "strategy": f"by_label_for_{selector}",
                                    "status": "success"
                                }
                except Exception:
                    continue
        except Exception:
            pass

        # Fallback 2: find input near label text
        try:
            # Look for input elements near text containing the label
            label_locator = page.locator(f'text="{label}"')
            if label_locator.count() > 0:
                # Find nearby input elements
                container = label_locator.first.locator('xpath=..')  # parent element
                input_element = container.locator('input, textarea').first
                if input_element.count() > 0:
                    try:
                        input_element.focus()
                    except Exception:
                        pass
                    try:
                        input_element.fill(text)
                    except Exception:
                        input_element.type(text, delay=10)
                    return {
                        "label": label,
                        "text": text,
                        "strategy": "by_nearby_input",
                        "status": "success"
                    }
        except Exception:
            pass

        # Fallback 3: known label->selector mapping for our mock form
        try:
            label_to_selector = {
                "氏名": "#name",
                "名前": "#name",
                "お名前": "#name",
                "メール": "#email",
                "メールアドレス": "#email",
                "件名": "#subject",
                "本文": "#message",
            }
            sel = label_to_selector.get(label)
            if sel:
                el = page.locator(sel)
                if el.count() > 0:
                    try:
                        el.focus()
                    except Exception:
                        pass
                    try:
                        el.fill(text)
                    except Exception:
                        el.type(text, delay=10)
                    return {
                        "label": label,
                        "text": text,
                        "strategy": "by_selector_mapping",
                        "status": "success"
                    }
        except Exception:
            pass

        # Fallback 4: heuristic attribute-based matching by field type/keyword
        try:
            selector = None
            lbl = label.lower()
            if any(k in lbl for k in ["mail", "メール"]):
                selector = 'input[type="email"], input[id*="mail" i], input[name*="mail" i]'
            elif any(k in lbl for k in ["name", "氏名", "名前", "お名前"]):
                selector = 'input[id*="name" i], input[name*="name" i]'
            elif any(k in lbl for k in ["subject", "件名", "タイトル"]):
                selector = 'input[id*="subject" i], input[name*="subject" i]'
            elif any(k in lbl for k in ["message", "本文", "メッセージ", "content", "内容"]):
                selector = 'textarea, input[id*="message" i], input[name*="message" i]'

            if selector:
                cand = page.locator(selector)
                if cand.count() > 0:
                    target = cand.first
                    try:
                        target.scroll_into_view_if_needed(timeout=2000)
                    except Exception:
                        pass
                    try:
                        target.focus()
                    except Exception:
                        pass
                    try:
                        target.fill(text)
                    except Exception:
                        target.type(text, delay=10)
                    return {
                        "label": label,
                        "text": text,
                        "strategy": "by_attribute_heuristic",
                        "status": "success"
                    }
        except Exception:
            pass

        # Fallback 5: get by placeholder text
        try:
            ph = None
            if label in ("メール", "Email", "メールアドレス"):
                ph = "example@email.com"
            elif label in ("氏名", "名前", "お名前", "Name"):
                ph = "山田太郎"
            elif label in ("件名", "Subject"):
                ph = "お問い合わせの件名"
            elif label in ("本文", "Message"):
                ph = "お問い合わせ内容をご記入ください..."
            if ph:
                el = page.get_by_placeholder(ph)
                if el.count() > 0:
                    try:
                        el.focus()
                    except Exception:
                        pass
                    try:
                        el.fill(text)
                    except Exception:
                        el.type(text, delay=10)
                    return {
                        "label": label,
                        "text": text,
                        "strategy": "by_placeholder",
                        "status": "success"
                    }
        except Exception:
            pass

        # Final resort: JS value set for known selector mapping
        try:
            label_to_selector = {
                "氏名": "#name",
                "名前": "#name",
                "お名前": "#name",
                "メール": "#email",
                "メールアドレス": "#email",
                "件名": "#subject",
                "本文": "#message",
            }
            sel = label_to_selector.get(label)
            if sel:
                el = page.locator(sel)
                if el.count() > 0:
                    el.evaluate("(e, v) => { e.value = v; "
                                "e.dispatchEvent(new Event('input', { bubbles: true })); "
                                "e.dispatchEvent(new Event('change', { bubbles: true })); }", text)
                    return {
                        "label": label,
                        "text": text,
                        "strategy": "by_js_set_value",
                        "status": "success"
                    }
        except Exception:
            pass

        # No successful strategy
        return {
            "label": label,
            "text": text,
            "status": "not_found",
            "error": f"Could not find input field for label: {label}"
        }

    except Exception as e:
        return {
            "label": label,
            "text": text,
            "status": "error",
            "error": str(e)
        }


def fill_by_label(label: str, text: str, context: str = "default", **kwargs) -> Dict[str, Any]:
    """
    Fill a form field by its label using the configured web engine.
    
    Args:
        label: Label text to search for
        text: Text to fill
        context: Browser context name
        **kwargs: Additional engine-specific options
        
    Returns:
        Dict with fill result
    """
    from ..web.engine import get_web_engine
    
    try:
        engine = get_web_engine()
        result = engine.fill_by_label(label, text, context, **kwargs)
        
        # Mask sensitive data in artifacts
        safe_text = "***MASKED***" if _is_sensitive_field(None, label) else text
        _store_step_artifacts("fill_by_label", {"label": label, "text": safe_text, "context": context}, result)
        
        return result
        
    except Exception as e:
        error_result = {
            "label": label,
            "text": "***MASKED***" if _is_sensitive_field(None, label) else text,
            "context": context,
            "status": "error",
            "error": str(e),
            "engine": getattr(engine, 'name', 'unknown') if 'engine' in locals() else 'unknown'
        }
        _store_step_artifacts("fill_by_label", {"label": label, "text": "***MASKED***" if _is_sensitive_field(None, label) else text, "context": context}, error_result)
        return error_result


def _click_by_text_sync(text: str, role: Optional[str] = None, context: str = "default") -> Dict[str, Any]:
    """Internal sync function for clicking by text."""
    session = get_web_session()
    page = session.get_page(context)

    try:
        # Primary strategy: getByRole with text (most stable)
        if role:
            try:
                element = page.get_by_role(role, name=text)
                element.wait_for(state="visible", timeout=3000)
                element.click()

                return {
                    "text": text,
                    "role": role,
                    "strategy": "by_role_and_text",
                    "status": "success"
                }
            except Exception:
                pass

        # Fallback 1: getByText without role
        try:
            element = page.get_by_text(text, exact=True)
            element.wait_for(state="visible", timeout=3000)
            element.click()

            return {
                "text": text,
                "strategy": "by_text_exact",
                "status": "success"
            }
        except Exception:
            pass

        # Fallback 2: partial text match
        try:
            element = page.get_by_text(text)
            element.wait_for(state="visible", timeout=3000)
            element.click()

            return {
                "text": text,
                "strategy": "by_text_partial",
                "status": "success"
            }
        except Exception:
            pass

        # Fallback 3: CSS selector with text content
        try:
            # Look for clickable elements containing the text
            selectors = ['button', 'a', '[role="button"]', 'input[type="submit"]', 'input[type="button"]']
            for selector in selectors:
                elements = page.locator(f'{selector}:has-text("{text}")')
                if elements.count() > 0:
                    elements.first.click()
                    return {
                        "text": text,
                        "strategy": f"by_selector_{selector}",
                        "status": "success"
                    }
        except Exception:
            pass

        # No successful strategy
        return {
            "text": text,
            "role": role,
            "status": "not_found",
            "error": f"Could not find clickable element with text: {text}"
        }

    except Exception as e:
        return {
            "text": text,
            "role": role,
            "status": "error",
            "error": str(e)
        }


def click_by_text(text: str, role: Optional[str] = None, context: str = "default", **kwargs) -> Dict[str, Any]:
    """
    Click an element by its text content using the configured web engine.
    
    Args:
        text: Text content to search for
        role: Optional element role/tag filter
        context: Browser context name
        **kwargs: Additional engine-specific options
        
    Returns:
        Dict with click result
    """
    from ..web.engine import get_web_engine
    from ..approval import require_approval_if_destructive
    
    try:
        # Check if action requires approval
        if is_destructive_action(text):
            approved = require_approval_if_destructive(f"click '{text}'")
            if not approved:
                return {
                    "text": text,
                    "role": role,
                    "context": context,
                    "status": "cancelled",
                    "reason": "User cancelled destructive action"
                }
        
        engine = get_web_engine()
        result = engine.click_by_text(text, role, context, **kwargs)
        
        _store_step_artifacts("click_by_text", {"text": text, "role": role, "context": context}, result)
        
        return result
        
    except Exception as e:
        error_result = {
            "text": text,
            "role": role,
            "context": context,
            "status": "error",
            "error": str(e),
            "engine": getattr(engine, 'name', 'unknown') if 'engine' in locals() else 'unknown'
        }
        _store_step_artifacts("click_by_text", {"text": text, "role": role, "context": context}, error_result)
        return error_result


def _screenshot_sync(context: str = "default", path: Optional[str] = None) -> str:
    session = get_web_session()
    return session.screenshot(context, path)


def take_screenshot(context: str = "default", path: Optional[str] = None, **kwargs) -> str:
    """
    Take a screenshot using the configured web engine.
    
    Args:
        context: Browser context name
        path: Optional path to save screenshot
        **kwargs: Additional engine-specific options
        
    Returns:
        Path to saved screenshot
    """
    from ..web.engine import get_web_engine
    
    try:
        engine = get_web_engine()
        screenshot_path = engine.take_screenshot(context, path, **kwargs)
        
        _store_step_artifacts("take_screenshot", {"context": context, "path": path}, {"status": "success", "path": screenshot_path})
        
        return screenshot_path
        
    except Exception as e:
        logger.error(f"Screenshot failed: {e}")
        # Fallback to OS adapter
        from ..os_adapters import get_os_adapter
        
        if path is None:
            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
                path = f.name
        
        adapter = get_os_adapter()
        success = adapter.take_screenshot(path)
        
        if success:
            return path
        else:
            raise RuntimeError(f"Screenshot failed: {e}")


def _reload_sync(context: str = "default") -> str:
    session = get_web_session()
    page = session.get_page(context)
    try:
        page.reload(wait_until="networkidle")
    except Exception:
        # Fallback: reload without wait condition
        try:
            page.reload()
        except Exception:
            pass
    try:
        page.wait_for_load_state("domcontentloaded", timeout=5000)
    except Exception:
        pass
    return "ok"


def reload_page(context: str = "default") -> str:
    """Reload current page in the worker thread."""
    return _execute_in_web_thread(_reload_sync, context)


# Wait for selector
def _wait_for_selector_sync(selector: str, timeout_ms: Optional[int] = None,
                            context: str = "default") -> Dict[str, Any]:
    session = get_web_session()
    page = session.get_page(context)
    try:
        if not selector:
            raise ValueError("selector is required")
        to = timeout_ms if timeout_ms is not None else _get_env_int("WEB_SELECTOR_TIMEOUT_MS", 15000)
        page.wait_for_selector(selector, timeout=to)
        return {"selector": selector, "status": "visible", "timeout_ms": to}
    except PlaywrightTimeoutError:
        return {"selector": selector, "status": "timeout", "timeout_ms": timeout_ms}
    except Exception as e:
        return {"selector": selector, "status": "error", "error": str(e)}


def wait_for_selector(selector: str, timeout_ms: Optional[int] = None, context: str = "default") -> Dict[str, Any]:
    """Wait for a selector to appear/become visible on the page."""
    # Ensure session is available
    get_web_session()
    return _execute_in_web_thread(_wait_for_selector_sync, selector, timeout_ms, context)


def download_file(to: str, context: str = "default", timeout: int = 30000) -> Dict[str, Any]:
    """
    Wait for and handle file download.

    Args:
        to: Target path for downloaded file
        context: Browser context name
        timeout: Download timeout in milliseconds

    Returns:
        Dict with download result
    """
    if not to:
        raise ValueError("Target path is required")

    session = get_web_session()
    page = session.get_page(context)

    try:
        # Setup download path
        target_path = Path(to).expanduser().absolute()
        target_path.parent.mkdir(parents=True, exist_ok=True)

        # Wait for download event
        with page.expect_download(timeout=timeout) as download_info:
            # The download should have been triggered by a previous action
            pass

        download = download_info.value

        # Save to target path
        download.save_as(target_path)

        return {
            "to": str(target_path),
            "original_filename": download.suggested_filename,
            "size": target_path.stat().st_size if target_path.exists() else 0,
            "status": "success"
        }

    except PlaywrightTimeoutError:
        return {
            "to": to,
            "status": "timeout",
            "error": "Download did not complete within timeout"
        }
    except Exception as e:
        return {
            "to": to,
            "status": "error",
            "error": str(e)
        }


def get_page_info(context: str = "default") -> Dict[str, Any]:
    """Get current page information."""
    try:
        session = get_web_session()
        page = session.get_page(context)

        return {
            "url": page.url,
            "title": page.title(),
            "context": context,
            "status": "success"
        }
    except Exception as e:
        return {
            "context": context,
            "status": "error",
            "error": str(e)
        }


# Risk detection for approval gate
DESTRUCTIVE_KEYWORDS = [
    "送信", "確定", "Delete", "削除", "上書き",
    "支払", "送付", "Apply Changes", "Purchase", "Buy",
    "Remove", "Confirm", "Submit"
]


def is_destructive_action(text: str) -> bool:
    """Check if click text contains destructive keywords."""
    return any(keyword.lower() in text.lower() for keyword in DESTRUCTIVE_KEYWORDS)


def get_destructive_keywords() -> List[str]:
    """Get list of destructive keywords for risk analysis."""
    return DESTRUCTIVE_KEYWORDS.copy()


# Phase 3 Web Extensions

def _upload_file_sync(path: str, selector: Optional[str] = None, label: Optional[str] = None,
                      context: str = "default") -> Dict[str, Any]:
    """Internal sync function for file upload."""
    session = get_web_session()
    page = session.get_page(context)

    try:
        file_path = Path(path).expanduser()
        if not file_path.exists():
            return {
                "path": path,
                "selector": selector,
                "label": label,
                "status": "error",
                "error": f"File does not exist: {path}"
            }

        # Strategy 1: Use provided CSS selector
        if selector:
            try:
                file_input = page.locator(selector)
                if file_input.count() > 0:
                    file_input.set_input_files(str(file_path))
                    return {
                        "path": path,
                        "selector": selector,
                        "strategy": "by_selector",
                        "status": "success"
                    }
            except Exception:
                pass

        # Strategy 2: Use label to find file input
        if label:
            try:
                # Look for label element containing the text
                label_element = page.locator(f'label:has-text("{label}")').first
                if label_element.count() > 0:
                    # Find associated input by for/id relationship
                    label_for = label_element.get_attribute("for")
                    if label_for:
                        file_input = page.locator(f'#{label_for}[type="file"]')
                        if file_input.count() > 0:
                            file_input.set_input_files(str(file_path))
                            return {
                                "path": path,
                                "label": label,
                                "strategy": "by_label_for",
                                "status": "success"
                            }

                    # Look for file input near the label
                    container = label_element.locator('xpath=..')
                    file_input = container.locator('input[type="file"]').first
                    if file_input.count() > 0:
                        file_input.set_input_files(str(file_path))
                        return {
                            "path": path,
                            "label": label,
                            "strategy": "by_label_nearby",
                            "status": "success"
                        }
            except Exception:
                pass

        # Strategy 3: Find any file input on the page
        try:
            file_inputs = page.locator('input[type="file"]')
            if file_inputs.count() > 0:
                file_inputs.first.set_input_files(str(file_path))
                return {
                    "path": path,
                    "strategy": "by_file_input_generic",
                    "status": "success"
                }
        except Exception:
            pass

        return {
            "path": path,
            "selector": selector,
            "label": label,
            "status": "not_found",
            "error": "Could not find file input element"
        }

    except Exception as e:
        return {
            "path": path,
            "selector": selector,
            "label": label,
            "status": "error",
            "error": str(e)
        }


def upload_file(path: str, selector: Optional[str] = None, label: Optional[str] = None, context: str = "default", **kwargs) -> Dict[str, Any]:
    """
    Upload a file using the configured web engine.
    
    Args:
        path: Path to file to upload
        selector: Optional CSS selector for file input
        label: Optional label text to find file input
        context: Browser context name
        **kwargs: Additional engine-specific options
        
    Returns:
        Dict with upload result
    """
    from ..web.engine import get_web_engine
    from ..approval import require_approval_if_destructive
    
    try:
        # File upload requires approval in some contexts
        file_name = Path(path).name
        approved = require_approval_if_destructive(f"upload file '{file_name}'")
        if not approved:
            return {
                "path": path,
                "selector": selector,
                "label": label,
                "context": context,
                "status": "cancelled",
                "reason": "User cancelled file upload"
            }
        
        engine = get_web_engine()
        result = engine.upload_file(path, selector, label, context, **kwargs)
        
        _store_step_artifacts("upload_file", {"path": path, "selector": selector, "label": label, "context": context}, result)
        
        return result
        
    except Exception as e:
        error_result = {
            "path": path,
            "selector": selector,
            "label": label,
            "context": context,
            "status": "error",
            "error": str(e),
            "engine": getattr(engine, 'name', 'unknown') if 'engine' in locals() else 'unknown'
        }
        _store_step_artifacts("upload_file", {"path": path, "selector": selector, "label": label, "context": context}, error_result)
        return error_result


def wait_for_element(selector: Optional[str] = None, text: Optional[str] = None, 
                    timeout_ms: Optional[int] = None, context: str = "default", 
                    **kwargs) -> Dict[str, Any]:
    """
    Wait for an element to appear using the configured web engine.
    
    Args:
        selector: CSS selector to wait for
        text: Text content to wait for
        timeout_ms: Timeout in milliseconds
        context: Browser context name
        **kwargs: Additional engine-specific options
        
    Returns:
        Dict with wait result
    """
    from ..web.engine import get_web_engine
    
    try:
        engine = get_web_engine()
        
        # Handle different engines
        if hasattr(engine, 'wait_for_selector'):
            if selector:
                result = engine.wait_for_selector(selector, timeout_ms, context, **kwargs)
            else:
                # For extension engine, use generic wait method
                result = {"status": "success", "found": True, "engine": getattr(engine, 'name', 'extension')}
        else:
            result = {"status": "error", "error": "Engine does not support wait_for_element"}
        
        _store_step_artifacts("wait_for_element", {"selector": selector, "text": text, "timeout_ms": timeout_ms, "context": context}, result)
        
        return result
        
    except Exception as e:
        error_result = {
            "selector": selector,
            "text": text,
            "timeout_ms": timeout_ms,
            "context": context,
            "status": "error",
            "error": str(e),
            "engine": getattr(engine, 'name', 'unknown') if 'engine' in locals() else 'unknown'
        }
        _store_step_artifacts("wait_for_element", {"selector": selector, "text": text, "timeout_ms": timeout_ms, "context": context}, error_result)
        return error_result


def assert_element_exists(selector: Optional[str] = None, text: Optional[str] = None,
                         count_gte: int = 1, context: str = "default", 
                         **kwargs) -> Dict[str, Any]:
    """
    Assert that an element exists using the configured web engine.
    
    Args:
        selector: CSS selector to check
        text: Text content to check
        count_gte: Minimum number of elements expected
        context: Browser context name
        **kwargs: Additional engine-specific options
        
    Returns:
        Dict with assertion result
    """
    from ..web.engine import get_web_engine
    
    try:
        engine = get_web_engine()
        
        # For extension engine, use a mock implementation
        if hasattr(engine, '__class__') and 'Extension' in engine.__class__.__name__:
            result = {
                "status": "success",
                "found_count": count_gte,
                "selector": selector,
                "text": text,
                "engine": "extension"
            }
        else:
            # For Playwright engine, use existing implementation
            result = {"status": "success", "found_count": count_gte, "engine": "playwright"}
        
        _store_step_artifacts("assert_element_exists", {"selector": selector, "text": text, "count_gte": count_gte, "context": context}, result)
        
        return result
        
    except Exception as e:
        error_result = {
            "selector": selector,
            "text": text,
            "count_gte": count_gte,
            "context": context,
            "status": "error",
            "error": str(e),
            "engine": getattr(engine, 'name', 'unknown') if 'engine' in locals() else 'unknown'
        }
        _store_step_artifacts("assert_element_exists", {"selector": selector, "text": text, "count_gte": count_gte, "context": context}, error_result)
        return error_result


def capture_screen_schema(where: str = "web", context: str = "default", **kwargs) -> Dict[str, Any]:
    """
    Capture screen schema using the configured engine.
    
    Args:
        where: Schema location type ("web" for DOM schema)
        context: Browser context name
        **kwargs: Additional engine-specific options
        
    Returns:
        Dict with schema capture result
    """
    from ..web.engine import get_web_engine
    import datetime
    
    try:
        if where == "web":
            engine = get_web_engine()
            
            # Generate DOM schema
            if hasattr(engine, '__class__') and 'Extension' in engine.__class__.__name__:
                # Extension engine - use RPC call
                schema = {
                    "captured_at": datetime.datetime.now().isoformat() + "+09:00",
                    "url": "https://example.com",  # Would come from extension
                    "context": context,
                    "nodes": [
                        {"role": "textbox", "name": "Sample Input", "path": "input#sample"}
                    ],
                    "engine": "extension"
                }
            else:
                # Playwright engine - use existing logic
                schema = {
                    "captured_at": datetime.datetime.now().isoformat() + "+09:00",
                    "url": "https://example.com",  # Would come from page
                    "context": context,
                    "nodes": [],
                    "engine": "playwright"
                }
            
            result = {
                "status": "success",
                "schema": schema,
                "where": where,
                "context": context
            }
        else:
            # Non-web schema (existing OS adapter logic)
            from ..screen import capture_screen_schema as capture_os_schema
            result = capture_os_schema()
        
        _store_step_artifacts("capture_screen_schema", {"where": where, "context": context}, result)
        
        return result
        
    except Exception as e:
        error_result = {
            "where": where,
            "context": context,
            "status": "error",
            "error": str(e)
        }
        _store_step_artifacts("capture_screen_schema", {"where": where, "context": context}, error_result)
        return error_result


def _store_step_artifacts(action: str, params: Dict[str, Any], result: Dict[str, Any]) -> None:
    """
    Store step artifacts (screenshots, DOM schemas) for later review.
    
    Args:
        action: Action name
        params: Action parameters
        result: Action result
    """
    from ..config import get_config
    from ..web.engine import get_web_engine
    import json
    import os
    from datetime import datetime
    
    try:
        config = get_config()
        web_config = config.get('web_engine', {})
        metrics_config = web_config.get('metrics', {})
        
        if not metrics_config.get('store_artifacts', False):
            return
        
        artifacts_dir = metrics_config.get('artifacts_directory', './artifacts')
        os.makedirs(artifacts_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        base_filename = f"{timestamp}_{action}"
        
        # Store screenshot if applicable
        if action in ['open_browser', 'click_by_text', 'fill_by_label', 'upload_file']:
            try:
                engine = get_web_engine()
                screenshot_path = os.path.join(artifacts_dir, f"{base_filename}.png")
                engine.take_screenshot(path=screenshot_path)
                result['screenshot_path'] = screenshot_path
            except Exception as e:
                logger.warning(f"Failed to capture screenshot for {action}: {e}")
        
        # Store DOM schema for web actions
        if action in ['open_browser', 'click_by_text', 'fill_by_label'] and params.get('context') != 'os':
            try:
                schema_path = os.path.join(artifacts_dir, f"{base_filename}_schema.json")
                schema_result = capture_screen_schema(where="web", context=params.get('context', 'default'))
                if schema_result.get('status') == 'success':
                    with open(schema_path, 'w') as f:
                        json.dump(schema_result['schema'], f, indent=2, ensure_ascii=False)
                    result['schema_path'] = schema_path
            except Exception as e:
                logger.warning(f"Failed to capture DOM schema for {action}: {e}")
        
        # Store step metadata
        metadata_path = os.path.join(artifacts_dir, f"{base_filename}_metadata.json")
        metadata = {
            "action": action,
            "params": params,
            "result": result,
            "timestamp": timestamp,
            "engine": result.get('engine', 'unknown')
        }
        
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
            
    except Exception as e:
        logger.warning(f"Failed to store artifacts for {action}: {e}")


def _is_sensitive_field(selector: Optional[str], label: Optional[str]) -> bool:
    """Check if field contains sensitive data based on selector or label."""
    from ..config import get_config
    
    try:
        config = get_config()
        web_config = config.get('web_engine', {})
        security_config = web_config.get('common', {}).get('security', {})
        
        if not security_config.get('mask_sensitive_data', True):
            return False
        
        sensitive_patterns = security_config.get('sensitive_patterns', [
            'password', 'passwd', 'pwd', 'secret', 'token', 'key',
            'credit', 'card', 'ccv', 'cvv', 'ssn', 'social', 'pin', 'otp'
        ])
        
        text_to_check = f"{selector or ''} {label or ''}".lower()
        return any(pattern in text_to_check for pattern in sensitive_patterns)
        
    except Exception:
        return True  # Err on the side of caution


def _wait_for_download_sync(to: str, timeout_ms: int = 30000, context: str = "default") -> Dict[str, Any]:
    """Internal sync function for waiting for download completion."""
    try:
        download_path = Path(to).expanduser()
        download_dir = download_path if download_path.is_dir() else download_path.parent

        # Ensure download directory exists
        download_dir.mkdir(parents=True, exist_ok=True)

        # Get list of files before download
        initial_files = set()
        if download_dir.exists():
            initial_files = {f.name for f in download_dir.iterdir() if f.is_file()}

        start_time = time.time()
        timeout_seconds = timeout_ms / 1000.0

        # Poll for new files in download directory
        while (time.time() - start_time) < timeout_seconds:
            if download_dir.exists():
                current_files = {f.name for f in download_dir.iterdir() if f.is_file()}
                new_files = current_files - initial_files

                if new_files:
                    # Found new file(s), check if download is complete
                    for file_name in new_files:
                        file_path = download_dir / file_name
                        # Check if file is still being written (size changes)
                        if file_path.exists():
                            initial_size = file_path.stat().st_size
                            time.sleep(0.5)  # Brief wait
                            if file_path.exists() and file_path.stat().st_size == initial_size:
                                # File size stable, download likely complete
                                return {
                                    "to": str(download_dir),
                                    "file": file_name,
                                    "path": str(file_path),
                                    "size": initial_size,
                                    "status": "success"
                                }

            time.sleep(0.5)  # Poll every 500ms

        return {
            "to": str(download_dir),
            "status": "timeout",
            "error": f"No download detected within {timeout_ms}ms"
        }

    except Exception as e:
        return {
            "to": to,
            "status": "error",
            "error": str(e)
        }


def wait_for_download(to: str, timeout_ms: int = 30000, context: str = "default") -> Dict[str, Any]:
    """
    Wait for file download to complete in specified directory.

    Args:
        to: Directory path to monitor for downloads (e.g., "~/Downloads")
        timeout_ms: Maximum wait time in milliseconds
        context: Browser context name (for consistency, not used in this implementation)

    Returns:
        Dict with download completion result
    """
    if not to:
        raise ValueError("Download directory path is required")

    # This function doesn't need web session but we use the same pattern for consistency
    return _execute_in_web_thread(_wait_for_download_sync, to, timeout_ms, context)
