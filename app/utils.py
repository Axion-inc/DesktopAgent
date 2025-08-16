import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from mss import mss  # type: ignore
except Exception:  # pragma: no cover
    mss = None  # fallback


SCREENSHOT_DIR = Path(os.environ.get("SCREENSHOT_DIR", "./data/screenshots"))
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


def now_iso() -> str:
    return datetime.utcnow().isoformat()


def take_screenshot(filename: str) -> str:
    """Capture full screen screenshot; fallback to placeholder if not available."""
    path = SCREENSHOT_DIR / filename
    try:
        if mss is None:
            raise RuntimeError("mss not available")
        with mss() as sct:  # type: ignore
            monitor = sct.monitors[0]
            sct_img = sct.grab(monitor)
            # Save as PNG
            from mss.tools import to_png  # type: ignore

            img_bytes = to_png(sct_img.rgb, sct_img.size)
            with open(path, "wb") as f:
                f.write(img_bytes)
    except Exception:
        # Create a tiny placeholder file to keep pipeline moving
        path.write_text("screenshot placeholder: " + now_iso())
    return str(path)


def json_dumps(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def safe_filename(basename: str) -> str:
    return "".join(c for c in basename if c.isalnum() or c in ("-", "_", "."))
