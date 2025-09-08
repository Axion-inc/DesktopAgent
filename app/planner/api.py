from __future__ import annotations

from typing import Any, Dict, List
from ..metrics import get_metrics_collector


def _mask_pii(text: str) -> str:
    # Minimal PII masking: hide email-like substrings
    import re
    return re.sub(r"[\w\.-]+@[\w\.-]+", "<redacted>", text)


def _confidence_for(instruction: str) -> float:
    base = 0.8 if instruction else 0.2
    # Boost if clear verbs present
    for kw in ["送信", "提出", "受付", "完了", "submit", "send"]:
        if kw in instruction:
            base += 0.1
            break
    return min(0.99, base)


def plan_with_llm_stub(request: Dict[str, Any]) -> Dict[str, Any]:
    """Deterministic planner stub: generate patch suggestions and draft template.

    LLMは使わず、ルールで置換/近傍/待機の候補を返す。
    """
    instr = _mask_pii(str(request.get("instruction", "")))
    conf = _confidence_for(instr)

    patch: Dict[str, Any] = {
        "replace_text": [
            {"find": "送信", "with": "提出", "role": "button", "confidence": round(conf, 2)}
        ],
        "fallback_search": [
            {"goal": "提出ボタン", "synonyms": ["確定", "送出"], "attempts": 1, "confidence": round(conf - 0.02, 2)}
        ],
        "wait_tuning": [
            {"step": "wait_for_element", "timeout_ms": 12000}
        ],
    }

    draft_template = {
        "dsl": "# draft-only, not executable\nsteps:\n  - click_by_text: '提出'\n",
        "risk_flags": ["sends"],
        "notes": "Verifier必須の有無を確認",
        "signature_verified": False,
    }

    # Count planner draft generation
    try:
        get_metrics_collector().mark_planner_draft()
    except Exception:
        pass

    return {
        "patch": patch,
        "draft_template": draft_template,
        "done": False,
        "_confidence": conf,
    }
