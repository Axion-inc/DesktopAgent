from __future__ import annotations

from typing import Any, Dict, Optional


class MemoryCheckpointer:
    """In-memory checkpointer keyed by thread_id.

    Minimal stand-in for a LangGraph-compatible checkpointer.
    """

    def __init__(self):
        self._store: Dict[str, Dict[str, Any]] = {}

    def save(self, thread_id: str, state: Dict[str, Any]) -> None:
        self._store[thread_id] = dict(state)

    def get(self, thread_id: str) -> Optional[Dict[str, Any]]:
        return self._store.get(thread_id)

    def clear(self, thread_id: str) -> None:
        self._store.pop(thread_id, None)
