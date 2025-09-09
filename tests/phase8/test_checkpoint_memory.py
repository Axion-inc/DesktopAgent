from __future__ import annotations

from app.orch.checkpoint import MemoryCheckpointer


def test_memory_checkpointer_save_get_clear():
    ck = MemoryCheckpointer()
    tid = "thread-xyz"
    state = {"phase": "after_plan", "k": 1}

    assert ck.get(tid) is None
    ck.save(tid, state)
    got = ck.get(tid)
    assert got == state
    ck.clear(tid)
    assert ck.get(tid) is None

