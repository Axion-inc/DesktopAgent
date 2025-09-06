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

