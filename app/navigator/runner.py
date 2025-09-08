from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..web.engine import exec_batch


class BatchErrorType:
    NO_TAB = "NO_TAB"
    ELEMENT_NOT_FOUND = "ELEMENT_NOT_FOUND"
    TIMEOUT = "TIMEOUT"
    DOMAIN_MISMATCH = "DOMAIN_MISMATCH"
    BATCH_HALTED = "BATCH_HALTED"


class NavigatorRunner:
    def __init__(self, batch_limit: int = 3):
        self.batch_limit = batch_limit

    def exec(self, actions: List[Dict[str, Any]], guards: Dict[str, Any], evidence: Optional[Dict[str, Any]] = None,
             simulate_domain: Optional[str] = None) -> Dict[str, Any]:
        actions = list(actions)[: self.batch_limit]

        # Domain guard enforcement (simple)
        allow = set((guards or {}).get("allowHosts", []) or [])
        if simulate_domain and allow and all(not simulate_domain.endswith(h) and simulate_domain != h for h in allow):
            return {"status": "halted", "error_type": BatchErrorType.DOMAIN_MISMATCH}

        # Call engine batch (mocked in extension)
        resp = exec_batch(guards or {}, actions, evidence or {}, context="default")
        if resp.get("status") == "success":
            return {"status": "ok", "result": resp.get("result")}
        return {"status": "halted", "error_type": BatchErrorType.BATCH_HALTED}

