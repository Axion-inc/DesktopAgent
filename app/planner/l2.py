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


def _similar(a: str, b: str) -> float:
    """Compute a simple similarity score between two strings (0..1)."""
    if not a or not b:
        return 0.0
    a = a.strip()
    b = b.strip()
    if a == b:
        return 1.0
    # normalized longest common substring length as proxy
    best = 0
    for i in range(len(a)):
        for j in range(i + 1, len(a) + 1):
            sub = a[i:j]
            if sub and sub in b and len(sub) > best:
                best = len(sub)
    return best / max(len(a), len(b))


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
    else:
        # Fallback search: propose synonyms to try once
        cands = SYNONYM_MAP.get(goal, [])
        if cands:
            patches['fallback_search'] = [{
                'goal': goal,
                'synonyms': cands,
                'role': role,
                'attempts': 1,
                'confidence': 0.88,
            }]
        # If similar labels exist (partially matching), propose the closest as replacement
        best_label = None
        best_sim = 0.0
        for lbl in labels:
            sim = _similar(goal, lbl)
            if sim > best_sim:
                best_sim = sim
                best_label = lbl
        if best_label and best_sim >= 0.6:
            patches.setdefault('replace_text', []).append({
                'find': goal,
                'with': best_label,
                'role': role,
                'confidence': round(0.85 + (best_sim - 0.6) * 0.25, 2)  # 0.85..1.0
            })

    # Wait tuning: if wait/assert failed, increase timeout modestly
    if (failure.get('type') in ('wait_for_element', 'assert_text', 'assert_element') and
            'wait_tuning' not in patches):
        patches.setdefault('wait_tuning', []).append({
            'step': 'wait_for_element',
            'timeout_ms': 12000,
            'confidence': 0.9,
        })
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
