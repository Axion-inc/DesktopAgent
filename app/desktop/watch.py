from __future__ import annotations

import time
import hashlib
import json
from typing import Optional
from pathlib import Path

from .inspect import desktop_inspect


def _hash_schema(path: str) -> str:
    try:
        data = Path(path).read_bytes()
        return hashlib.sha256(data).hexdigest()
    except Exception:
        return ""


def desktop_watch(interval_sec: float = 2.0, iterations: int = 10,
                  target: str = "frontmost", output_dir: Optional[str] = None) -> None:
    """
    Poll-based watcher: capture schema/screenshot periodically and print diffs.
    This is a portable alternative to AX notifications.
    """
    prev_hash = None
    for i in range(iterations):
        res = desktop_inspect(output_dir=output_dir, target=target)
        h = _hash_schema(res['schema'])
        changed = (prev_hash is not None and h != prev_hash)
        print(f"[{i+1}/{iterations}] captured -> screenshot={res['screenshot']} schema={res['schema']} changed={changed}")
        prev_hash = h
        time.sleep(interval_sec)

