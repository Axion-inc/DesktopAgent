"""Planner Module for Desktop Agent

Contains:
- L1 Planner: Template-based DSL generation from natural language
- L2 Planner: Differential patch proposal system for execution stability
"""

from .l1 import (
    IntentMatcher,
    DSLGenerator,
    PlannerL1,
    generate_plan_from_intent,
    is_planner_enabled,
    set_planner_enabled,
)
from .l2 import PlannerL2, DifferentialPatch, PatchProposal, AdoptionDecision
from .schema_ops import SchemaAnalyzer, PatchGenerator


__all__ = [
    # L1
    'IntentMatcher',
    'DSLGenerator',
    'PlannerL1',
    'generate_plan_from_intent',
    'is_planner_enabled',
    'set_planner_enabled',
    # L2
    'PlannerL2',
    'DifferentialPatch',
    'PatchProposal',
    'AdoptionDecision',
    # Schema ops
    'SchemaAnalyzer',
    'PatchGenerator',
]
