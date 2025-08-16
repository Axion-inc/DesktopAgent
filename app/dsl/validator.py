from __future__ import annotations

from typing import Any, Dict, List


ALLOWED_STEPS = {
    "find_files",
    "rename",
    "move_to",
    "zip_folder",
    "pdf_merge",
    "pdf_extract_pages",
    "open_preview",
    "compose_mail",
    "attach_files",
    "save_draft",
    "log",
}


def validate_plan(plan: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    if "name" not in plan or not plan["name"]:
        errors.append("name is required")
    if "steps" not in plan or not isinstance(plan["steps"], list):
        errors.append("steps must be a list")
    else:
        for i, step in enumerate(plan["steps"]):
            if not isinstance(step, dict) or len(step) != 1:
                errors.append(f"step {i} must be a single-key mapping")
                continue
            (action, params), = step.items()
            if action not in ALLOWED_STEPS:
                errors.append(f"step {i}: action '{action}' not allowed")
            if not isinstance(params, dict):
                errors.append(f"step {i}: params must be mapping")
    return errors

