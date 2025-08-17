from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional, List
from urllib.parse import urlparse

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

        self.playwright = sync_playwright().start()
        # Use headless=False for debugging, headless=True for CI
        headless = os.environ.get('PLAYWRIGHT_HEADLESS', 'true').lower() == 'true'
        self.browser = self.playwright.chromium.launch(headless=headless)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()

    def get_context(self, context_name: str = "default") -> BrowserContext:
        """Get or create a browser context."""
        if context_name not in self.contexts:
            self.contexts[context_name] = self.browser.new_context(
                viewport={'width': 1280, 'height': 720}
            )
        return self.contexts[context_name]

    def get_page(self, context_name: str = "default") -> Page:
        """Get or create a page in the specified context."""
        if context_name not in self.pages:
            context = self.get_context(context_name)
            self.pages[context_name] = context.new_page()
            # Set default timeout
            self.pages[context_name].set_default_timeout(self.default_timeout)
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


# Global session for reuse across steps
_web_session: Optional[WebSession] = None


def get_web_session() -> WebSession:
    """Get or create global web session."""
    global _web_session
    if _web_session is None:
        _web_session = WebSession()
        _web_session.__enter__()
    return _web_session


def close_web_session():
    """Close global web session."""
    global _web_session
    if _web_session:
        _web_session.__exit__(None, None, None)
        _web_session = None


def open_browser(url: str, context: str = "default", wait_for_load: bool = True) -> Dict[str, Any]:
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

    session = get_web_session()
    page = session.get_page(context)

    try:
        # Navigate with network idle wait
        if wait_for_load:
            page.goto(url, wait_until="networkidle")
        else:
            page.goto(url)

        # Additional stability wait
        page.wait_for_load_state("domcontentloaded")

        title = page.title()
        current_url = page.url

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

    session = get_web_session()
    page = session.get_page(context)

    try:
        # Primary strategy: getByLabel (most stable)
        try:
            element = page.get_by_label(label)
            element.wait_for(state="visible", timeout=5000)
            element.fill(text)

            return {
                "label": label,
                "text": text,
                "strategy": "by_label",
                "status": "success"
            }
        except Exception:
            pass

        # Fallback 1: look for input with role textbox near label
        try:
            # Find label element and associated input
            label_element = page.locator(f'label:has-text("{label}")').first
            if label_element.count() > 0:
                # Try to find associated input by for/id
                label_for = label_element.get_attribute("for")
                if label_for:
                    input_element = page.locator(f'#{label_for}')
                    if input_element.count() > 0:
                        input_element.fill(text)
                        return {
                            "label": label,
                            "text": text,
                            "strategy": "by_label_for",
                            "status": "success"
                        }
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
                    input_element.fill(text)
                    return {
                        "label": label,
                        "text": text,
                        "strategy": "by_nearby_input",
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

    session = get_web_session()
    page = session.get_page(context)

    try:
        # Primary strategy: getByRole with text (most stable)
        if role:
            try:
                element = page.get_by_role(role, name=text)
                element.wait_for(state="visible", timeout=5000)
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
            element.wait_for(state="visible", timeout=5000)
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
            element.wait_for(state="visible", timeout=5000)
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


def take_screenshot(context: str = "default", path: Optional[str] = None) -> str:
    """Take screenshot of current page."""
    session = get_web_session()
    return session.screenshot(context, path)


# Risk detection for approval gate
DESTRUCTIVE_KEYWORDS = [
    "送信", "確定", "Submit", "Delete", "削除", "上書き",
    "支払", "送付", "Apply Changes", "Purchase", "Buy",
    "Remove", "Cancel", "Confirm", "Send"
]


def is_destructive_action(text: str) -> bool:
    """Check if click text contains destructive keywords."""
    return any(keyword.lower() in text.lower() for keyword in DESTRUCTIVE_KEYWORDS)


def get_destructive_keywords() -> List[str]:
    """Get list of destructive keywords for risk analysis."""
    return DESTRUCTIVE_KEYWORDS.copy()
