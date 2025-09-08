from __future__ import annotations

from typing import Any, Dict
from .engine import get_web_engine, take_screenshot


def capture_dom_snapshot() -> Dict[str, Any]:
    """Capture a lightweight DOM snapshot + screenshot.

    Returns keys: schema, tab, scroll, screenshot
    """
    schema = {}
    tab = {}
    scroll = {"x": 0, "y": 0}
    screenshot_path = None
    try:
        eng = get_web_engine('cdp')
        # Try to call internal label builder if available (mocked CDP)
        if hasattr(eng, '_build_dom_tree'):
            resp = eng._build_dom_tree()  # type: ignore[attr-defined]
            schema = {"get_dom_schema": True, "meta": resp}
    except Exception:
        schema = {"get_dom_schema": False}

    try:
        screenshot_path = take_screenshot()
    except Exception:
        screenshot_path = None

    return {
        "schema": schema,
        "tab": tab,
        "scroll": scroll,
        "screenshot": screenshot_path or "<redacted>",
    }

