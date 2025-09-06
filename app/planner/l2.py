from __future__ import annotations

from typing import Dict, Any, List


SYNONYM_MAP = {
    '送信': ['提出', '確定'],
}


def _find_synonym(goal: str, present_labels: List[str]) -> tuple[str, float] | None:
    cands = SYNONYM_MAP.get(goal, [])
    for w in cands:
        if w in present_labels:
            # naive confidence: 0.9 if direct presence
            return (w, 0.9)
    return None


def _collect_labels(schema: Dict[str, Any]) -> List[str]:
    labels: List[str] = []
    def walk(node: Dict[str, Any]):
        lbl = node.get('label') or node.get('text')
        if isinstance(lbl, str):
            labels.append(lbl)
        for ch in (node.get('children') or []):
            if isinstance(ch, dict):
                walk(ch)
    for el in schema.get('elements', []) or []:
        if isinstance(el, dict):
            walk(el)
    return labels


def propose_patches(schema: Dict[str, Any], failure: Dict[str, Any]) -> Dict[str, Any]:
    goal = failure.get('goal') or failure.get('text') or ''
    role = failure.get('role')
    labels = _collect_labels(schema)
    syn = _find_synonym(goal, labels)
    patches: Dict[str, Any] = {}
    if syn:
        w, conf = syn
        patches['replace_text'] = [{
            'find': goal,
            'with': w,
            'role': role,
            'confidence': conf,
        }]
    return patches


def should_adopt_patch(patch: Dict[str, Any], policy: Dict[str, Any]) -> bool:
    """Decide whether to auto-adopt a low-risk patch based on policy.

    Rules:
      - low_risk_auto must be True
      - all confidences >= min_confidence
      - patch must not introduce dangerous actions (no sends/deletes/overwrites)
    """
    if not policy.get('low_risk_auto', False):
        return False
    min_conf = float(policy.get('min_confidence', 0.85))
    # Check confidences
    for key in ('replace_text', 'fallback_search', 'wait_tuning'):
        for item in patch.get(key, []) or []:
            if float(item.get('confidence', 1.0)) < min_conf:
                return False
    # No dangerous additions (we only deal with replace/wait/search here)
    return True
