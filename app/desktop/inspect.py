from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Callable

from ..config import get_config


def _default_get_adapter():
    from ..os_adapters import get_os_adapter
    return get_os_adapter()


def desktop_inspect(output_dir: Optional[str] = None, target: str = "frontmost",
                    get_adapter: Callable[[], Any] = _default_get_adapter) -> Dict[str, Any]:
    """
    Capture a desktop inspection snapshot: screenshot + screen schema.

    Args:
        output_dir: directory to save artifacts; defaults to metrics.artifacts_directory/desktop/YYYYMMDD
        target: 'frontmost' or 'screen' for schema capture granularity
        get_adapter: injection point for testing (returns OS adapter)

    Returns:
        Dict with 'screenshot', 'schema', 'dir'
    """
    cfg = get_config()
    base = output_dir
    if not base:
        base = cfg.get('metrics', {}).get('artifacts_directory', './artifacts')
        date_dir = datetime.now().strftime('%Y%m%d')
        base = str(Path(base) / 'desktop' / date_dir)

    out_dir = Path(base)
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime('%H%M%S')
    shot_path = out_dir / f'screenshot_{ts}.png'
    schema_path = out_dir / f'schema_{ts}.json'

    adapter = get_adapter()
    # Take screenshot (may raise)
    adapter.take_screenshot(str(shot_path))
    # Capture schema (should not throw fatally)
    try:
        schema = adapter.capture_screen_schema(target=target)
    except Exception as e:
        schema = {"error": str(e), "target": target}

    import json
    with open(schema_path, 'w', encoding='utf-8') as f:
        json.dump(schema, f, ensure_ascii=False, indent=2)

    return {
        'dir': str(out_dir),
        'screenshot': str(shot_path),
        'schema': str(schema_path)
    }

