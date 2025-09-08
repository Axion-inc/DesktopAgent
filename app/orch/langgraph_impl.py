from __future__ import annotations

from typing import Any, Dict

try:
    # Attempt to import LangGraph (optional dependency)
    import langgraph  # type: ignore
    _HAS_LANGGRAPH = True
except Exception:
    _HAS_LANGGRAPH = False

from .graph import Orchestrator as _FallbackOrchestrator
from .checkpoint import MemoryCheckpointer


class LangGraphOrchestrator:
    """Facade for a LangGraph-based orchestrator; falls back to built-in one.

    Interface: run(thread_id, instruction, simulate_interrupt=False) -> dict
               resume(thread_id) -> dict
    """

    def __init__(self):
        if _HAS_LANGGRAPH:
            # Here we would wire actual LangGraph nodes and checkpointer.
            # For now, use fallback orchestrator to keep behavior consistent.
            pass
        self._fb = _FallbackOrchestrator(MemoryCheckpointer())

    def run(self, thread_id: str, instruction: str, simulate_interrupt: bool = False) -> Dict[str, Any]:
        return self._fb.run(thread_id, instruction, simulate_interrupt=simulate_interrupt)

    def resume(self, thread_id: str) -> Dict[str, Any]:
        return self._fb.resume(thread_id)

