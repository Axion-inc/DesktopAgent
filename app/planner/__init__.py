"""Planner package aggregator.

Expose L1 planner interfaces so callers can import from `app.planner`.
This bridges newer modular files under `app/planner/` and legacy imports
expected by tests (`from app.planner import IntentMatcher`, etc.).
"""

from __future__ import annotations

from typing import Any, Dict, Tuple

# Core L1 implementations live in l1.py
from .l1 import IntentMatcher, DSLGenerator, PlannerL1

# Package-level singleton for convenience functions
_planner_l1 = PlannerL1(enabled=False)


def generate_plan_from_intent(intent_text: str) -> Tuple[bool, Dict[str, Any], str]:
    """Convenience function mirroring legacy module API."""
    return _planner_l1.generate_plan_from_intent(intent_text)


def is_planner_enabled() -> bool:
    """Return whether the L1 planner is enabled."""
    return _planner_l1.is_enabled()


def set_planner_enabled(enabled: bool) -> None:
    """Enable or disable the L1 planner."""
    _planner_l1.set_enabled(enabled)


__all__ = [
    "IntentMatcher",
    "DSLGenerator",
    "PlannerL1",
    "generate_plan_from_intent",
    "is_planner_enabled",
    "set_planner_enabled",
]
