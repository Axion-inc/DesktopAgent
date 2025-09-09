from __future__ import annotations

"""
LangGraph node scaffolding (safe fallback).

If `langgraph` is available at runtime, this module provides a thin runtime
wrapper that mimics a node-based execution. For now, nodes delegate to the
existing Orchestrator logic to keep behavior identical while we land the
interfaces and tests. This allows us to switch to real LangGraph nodes later
without breaking callers.
"""

from typing import Any, Dict

try:
    import langgraph  # type: ignore  # noqa: F401
    _HAS_LANGGRAPH = True
except Exception:
    _HAS_LANGGRAPH = False

from .graph import Orchestrator as _FallbackOrchestrator
from .checkpoint import MemoryCheckpointer


class LangGraphRuntime:
    """Node-style orchestrator façade.

    For now it forwards to the fallback Orchestrator while we shape the API.
    """

    def __init__(self) -> None:
        self._fb = _FallbackOrchestrator(MemoryCheckpointer())

    def run(self, thread_id: str, instruction: str, simulate_interrupt: bool = False) -> Dict[str, Any]:
        return self._fb.run(thread_id, instruction, simulate_interrupt=simulate_interrupt)

    def resume(self, thread_id: str) -> Dict[str, Any]:
        return self._fb.resume(thread_id)

