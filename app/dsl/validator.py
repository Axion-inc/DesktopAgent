from __future__ import annotations

from typing import Any, Dict, List
import re

REQUIRED_DSL_VERSION = "1.1"


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
    # Phase 2: Web Actions
    "open_browser",
    "fill_by_label",
    "click_by_text",
    "download_file",
}


def validate_plan(plan: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    # dsl_version
    dslv = plan.get("dsl_version")
    if dslv != REQUIRED_DSL_VERSION:
        errors.append(f"dsl_version must be '{REQUIRED_DSL_VERSION}'")
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
            # when expression can reference steps[j].key where j < i
            when = params.get("when") if isinstance(params, dict) else None
            if when is not None and not isinstance(when, str):
                errors.append(f"step {i}: when must be a string expression")
            # Static validation for steps references in when: steps[n].field must have n < i
            if isinstance(when, str):
                for m in re.finditer(r"steps\s*\[\s*(\d+)\s*\]", when):
                    try:
                        ref_idx = int(m.group(1))
                        if ref_idx >= i:
                            errors.append(
                                f"step {i}: when references future step index {ref_idx}"
                            )
                    except Exception:
                        errors.append(f"step {i}: invalid steps[] index in when")
    return errors
