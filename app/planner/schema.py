from __future__ import annotations

from typing import Dict, Any


PLANNER_REQUEST_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "instruction": {"type": "string"},
        "dom": {"type": "object"},
        "history": {"type": "array"},
        "capabilities": {"type": "array"},
    },
    "required": ["instruction", "dom"],
}


PLANNER_RESPONSE_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "patch": {"type": "object"},
        "draft_template": {"type": "object"},
        "done": {"type": "boolean"},
    },
    "required": ["patch", "draft_template", "done"],
}

