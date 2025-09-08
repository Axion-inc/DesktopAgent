from __future__ import annotations

from typing import List, Dict, Any


def aggregate_verification(steps: List[Dict[str, Any]], planner_done: bool) -> Dict[str, Any]:
    """Aggregate verification steps; finalize only if all passed."""
    all_ok = all(s.get("status") == "success" for s in steps)
    return {
        "finalized": bool(all_ok and planner_done or all_ok),
        "passed": bool(all_ok),
    }

