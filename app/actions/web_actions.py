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


def open_browser(url: str, context: str = "default", wait_for_load: bool = True, visible: Optional[bool] = None) -> Dict[str, Any]:
    """
    Open browser and navigate to URL.

    Args:
        url: Target URL
        context: Browser context name (for isolation)
        wait_for_load: Wait for network idle after navigation

    Returns:
        Dict with navigation info
    """
    if not url:
        raise ValueError("URL is required")

    # Validate URL
    parsed = urlparse(url)
    if not parsed.scheme:
        url = f"http://{url}"

    # Apply headless override if requested BEFORE session init
    # visible=True => headless=False
    if visible is not None:
        try:
            set_headless_override(not bool(visible))
        except Exception:
            pass

    # Ensure session is available (may launch browser)
    get_web_session()
    return _execute_in_web_thread(_open_browser_sync, url, context, wait_for_load)


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


def fill_by_label(label: str, text: str, context: str = "default") -> Dict[str, Any]:
    """
    Fill form field by label text.

    Args:
        label: Label text to find (e.g., "氏名", "Email")
        text: Text to fill
        context: Browser context name

    Returns:
        Dict with fill result
    """
    if not label or text is None:
        raise ValueError("Label and text are required")

    # Ensure session is available
    get_web_session()
    return _execute_in_web_thread(_fill_by_label_sync, label, text, context)


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


def click_by_text(text: str, role: Optional[str] = None, context: str = "default") -> Dict[str, Any]:
    """
    Click element by text content.

    Args:
        text: Text content to find and click
        role: Optional ARIA role (e.g., "button", "link")
        context: Browser context name

    Returns:
        Dict with click result
    """
    if not text:
        raise ValueError("Text is required")

    # Ensure session is available
    get_web_session()
    return _execute_in_web_thread(_click_by_text_sync, text, role, context)


def _screenshot_sync(context: str = "default", path: Optional[str] = None) -> str:
    session = get_web_session()
    return session.screenshot(context, path)


def take_screenshot(context: str = "default", path: Optional[str] = None) -> str:
    """Capture a web page screenshot from the web worker thread.

    This avoids cross-thread Playwright access by routing the screenshot
    through the worker and returns the saved path.
    """
    return _execute_in_web_thread(_screenshot_sync, context, path)


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
    "Remove", "Confirm"
]


def is_destructive_action(text: str) -> bool:
    """Check if click text contains destructive keywords."""
    return any(keyword.lower() in text.lower() for keyword in DESTRUCTIVE_KEYWORDS)


def get_destructive_keywords() -> List[str]:
    """Get list of destructive keywords for risk analysis."""
    return DESTRUCTIVE_KEYWORDS.copy()
