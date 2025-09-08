from __future__ import annotations

from typing import Any, Dict, Tuple, List


_DANGEROUS = {"delete_files", "shell", "run_script", "format_disk"}


def apply_patch(plan: Dict[str, Any], patch: Dict[str, Any]) -> Tuple[bool, Dict[str, Any], str]:
    """Apply a planner patch to a plan dict while forbidding dangerous actions."""
    new_plan = {**plan}
    steps: List[Dict[str, Any]] = list(new_plan.get("steps", []))

    # Add steps
    for step in patch.get("add_steps", []) or []:
        if not isinstance(step, dict):
            continue
        name = next(iter(step.keys()), "")
        if name in _DANGEROUS:
            return False, plan, f"Dangerous action blocked: {name}"
        steps.append(step)

    # Replace text in existing steps
    for rep in patch.get("replace_text", []) or []:
        find = rep.get("find")
        new = rep.get("with")
        for st in steps:
            key = next(iter(st.keys()))
            val = st[key]
            if isinstance(val, dict) and "text" in val and val["text"] == find:
                val["text"] = new

    new_plan["steps"] = steps
    return True, new_plan, "patched"

