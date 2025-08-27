"""
Planner Module for Desktop Agent

Contains:
- L1 Planner: Template-based DSL generation from natural language
- L2 Planner: Differential patch proposal system for execution stability
"""

from .l2 import PlannerL2, DifferentialPatch, PatchProposal, AdoptionDecision
from .schema_ops import SchemaAnalyzer, PatchGenerator


__all__ = [
    'PlannerL2',
    'DifferentialPatch', 
    'PatchProposal',
    'AdoptionDecision',
    'SchemaAnalyzer',
    'PatchGenerator'
]