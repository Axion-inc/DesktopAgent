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
from .langgraph_graph import LangGraphRuntime


class LangGraphOrchestrator:
    """Facade for a LangGraph-based orchestrator; falls back to built-in one.

    Interface: run(thread_id, instruction, simulate_interrupt=False) -> dict
               resume(thread_id) -> dict
    """

    def __init__(self):
        # Prefer LangGraph runtime if available; otherwise fallback
        if _HAS_LANGGRAPH:
            try:
                self._fb = LangGraphRuntime()
                return
            except Exception:
                pass
        self._fb = _FallbackOrchestrator(MemoryCheckpointer())

    def run(self, thread_id: str, instruction: str, simulate_interrupt: bool = False) -> Dict[str, Any]:
        return self._fb.run(thread_id, instruction, simulate_interrupt=simulate_interrupt)

    def resume(self, thread_id: str) -> Dict[str, Any]:
        return self._fb.resume(thread_id)

    # Recorded variants are supported when LangGraphRuntime is used; fallback orchestrator also supports them
    def run_recorded(self, thread_id: str, instruction: str, simulate_interrupt: bool = False) -> Dict[str, Any]:
        if hasattr(self._fb, 'run_recorded'):
            return self._fb.run_recorded(thread_id, instruction, simulate_interrupt=simulate_interrupt)  # type: ignore[attr-defined]
        # Fallback to non-recorded if unavailable
        return self.run(thread_id, instruction, simulate_interrupt=simulate_interrupt)

    def resume_recorded(self, thread_id: str) -> Dict[str, Any]:
        if hasattr(self._fb, 'resume_recorded'):
            return self._fb.resume_recorded(thread_id)  # type: ignore[attr-defined]
        return self.resume(thread_id)
