from __future__ import annotations

import re
from typing import Dict, List, Tuple, Any


class IntentMatcher:
    """Lightweight intent and entity extractor for L1 planning.

    Provides a rules-based approach sufficient for unit tests:
    - Detects basic intents: CSV→Form, PDF Merge + Email, File Organization
    - Extracts entities: file types, actions, numeric quantities
    - Returns a confidence score based on matched signals
    """

    def __init__(self) -> None:
        # Intent keyword patterns (EN/JA)
        self.patterns: Dict[str, List[re.Pattern]] = {
            "csv_process": [
                re.compile(r"csv", re.I),  # allow adjacent non-ascii chars
            ],
            "web_form": [
                re.compile(r"\b(form|web\s*form)\b", re.I),
                re.compile(r"フォーム", re.I),
                re.compile(r"送信", re.I),
            ],
            "pdf_merge": [
                re.compile(r"\bpdf\b", re.I),
                re.compile(r"\bmerge|combine\b", re.I),
                re.compile(r"結合", re.I),
            ],
            "email_compose": [
                re.compile(r"\bemail|mail\b", re.I),
                re.compile(r"メール", re.I),
                re.compile(r"送信", re.I),
            ],
            "file_find": [
                re.compile(r"\b(find|search|locate)\b", re.I),
                re.compile(r"探(す|索)", re.I),
            ],
            "file_move": [
                re.compile(r"\bmove|organize|arrange|sort\b", re.I),
                re.compile(r"移動|整理", re.I),
            ],
        }

        # Entities
        self.file_type_patterns: Dict[str, List[re.Pattern]] = {
            "pdf": [re.compile(r"pdf", re.I)],
            "csv": [re.compile(r"csv", re.I)],
            "excel": [re.compile(r"excel|xlsx|xls", re.I)],
        }
        # (label, patterns) pairs; labels may be EN or JA
        self.action_patterns_labeled: List[Tuple[str, List[re.Pattern]]] = [
            ("send", [re.compile(r"\bsend\b", re.I)]),
            ("merge", [re.compile(r"\bmerge\b", re.I)]),
            ("combine", [re.compile(r"\bcombine\b", re.I)]),
            ("move", [re.compile(r"\bmove\b", re.I)]),
            ("送信", [re.compile(r"送信", re.I)]),
            ("結合", [re.compile(r"結合", re.I)]),
            ("移動", [re.compile(r"移動", re.I)]),
        ]

    def analyze_intent(self, text: str) -> Dict[str, Any]:
        t = text or ""

        matched_intents: List[str] = []
        if self.patterns:
            for name, pats in self.patterns.items():
                if any(p.search(t) for p in pats):
                    matched_intents.append(name)

        file_types: List[str] = []
        for ft, pats in self.file_type_patterns.items():
            if any(p.search(t) for p in pats):
                file_types.append(ft)

        actions: List[str] = []
        for label, pats in self.action_patterns_labeled:
            if any(p.search(t) for p in pats):
                actions.append(label)

        quantities = re.findall(r"\b\d+\b", t)

        # Primary intent heuristic
        primary = "unknown"
        if self.patterns:
            if "csv_process" in matched_intents and "web_form" in matched_intents:
                primary = "csv_to_form"
            elif "pdf_merge" in matched_intents and "email_compose" in matched_intents:
                primary = "pdf_merge_email"
            elif "file_find" in matched_intents or "file_move" in matched_intents:
                primary = "file_organization"

        # Confidence scoring: base on matched intents and entity richness
        if not self.patterns:
            score = 0.0
        else:
            score = 0.0
            score += min(0.6, 0.25 * len(matched_intents))
            if primary in ("csv_to_form", "pdf_merge_email"):
                score += 0.2  # paired signal bonus
            score += 0.05 * len(file_types)
            score += 0.05 * len(actions)
            score = max(0.0, min(1.0, score))

        return {
            "text": t,
            "primary_intent": primary,
            "confidence": score,
            "matched_intents": matched_intents,
            "entities": {
                "file_types": file_types,
                "actions": actions,
                "quantities": quantities,
            },
        }


class DSLGenerator:
    """Generate template-like DSL plans for simple workflows."""

    def _base(self, name: str) -> Dict[str, Any]:
        return {"dsl_version": "1.1", "name": name}

    def _generate_csv_to_form_plan(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        plan = self._base("CSV → フォーム送信フロー")
        plan["variables"] = {
            "csv_dir": "./data",
            "form_url": "https://example.com/form",
        }
        plan["steps"] = [
            {"find_files": {"query": "ext:csv in:${csv_dir}"}},
            {"open_browser": {"url": "${form_url}"}},
            {"fill_by_label": {"label": "Name", "value": "${row.name}"}},
            {"fill_by_label": {"label": "Email", "value": "${row.email}"}},
            {"click_by_text": {"text": "送信"}},
        ]
        return plan

    def _generate_pdf_merge_email_plan(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        plan = self._base("PDF結合してメール下書き保存")
        plan["variables"] = {
            "pdf_dir": "./data",
            "recipient": "user@example.com",
            "subject": "Merged PDFs",
        }
        plan["steps"] = [
            {"find_files": {"query": "ext:pdf in:${pdf_dir}"}},
            {"pdf_merge": {"output": "${pdf_dir}/merged.pdf"}},
            {"compose_mail": {"to": "${recipient}", "subject": "${subject}", "body": "See attachment"}},
            {"attach_files": {"files": ["${pdf_dir}/merged.pdf"]}},
            {"save_draft": {}},
        ]
        return plan

    def _generate_file_organization_plan(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        plan = self._base("ファイル整理ワークフロー")
        ft = (analysis.get("entities", {}).get("file_types") or ["*"])[0]
        plan["variables"] = {"source": "./downloads", "dest": "./backup"}
        plan["steps"] = [
            {"find_files": {"query": f"ext:{ft} in:${{source}}"}},
            {"move_to": {"destination": "${dest}"}},
            {"log": {"message": "ファイル整理が完了しました"}},
        ]
        return plan

    def _generate_generic_plan(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        plan = self._base("汎用アシストプラン")
        plan["steps"] = [
            {"log": {"message": "要求の内容を詳しく教えてください"}},
        ]
        return plan

    def generate_plan(self, text: str) -> Dict[str, Any]:
        matcher = IntentMatcher()
        analysis = matcher.analyze_intent(text)
        intent = analysis["primary_intent"]
        if intent == "csv_to_form":
            plan = self._generate_csv_to_form_plan(analysis)
        elif intent == "pdf_merge_email":
            plan = self._generate_pdf_merge_email_plan(analysis)
        elif intent == "file_organization":
            plan = self._generate_file_organization_plan(analysis)
        else:
            plan = self._generate_generic_plan(analysis)

        plan["_generated"] = True
        plan["_source_intent"] = text
        plan["_analysis"] = analysis
        plan["_confidence"] = float(analysis.get("confidence", 0.0))
        return plan


class PlannerL1:
    """Facade over DSLGenerator with enable/disable controls."""

    def __init__(self, enabled: bool = False) -> None:
        self._enabled = enabled
        self.generator = DSLGenerator()

    def is_enabled(self) -> bool:
        return bool(self._enabled)

    def set_enabled(self, value: bool) -> None:
        self._enabled = bool(value)

    def generate_plan_from_intent(self, text: str) -> Tuple[bool, Dict[str, Any] | None, str]:
        if text is None or str(text).strip() == "":
            return False, None, "Input intent is empty"
        if not self._enabled:
            return False, None, "Planner is disabled"
        try:
            plan = self.generator.generate_plan(text)
            conf = plan.get("_confidence", 0.0)
            return True, plan, f"Generated plan with confidence: {conf:.2f}"
        except Exception as e:  # pragma: no cover (defensive)
            return False, None, f"Error generating plan: {e}"


# Module-level convenience API with a singleton-like state
_planner_state = PlannerL1(enabled=False)


def generate_plan_from_intent(text: str) -> Tuple[bool, Dict[str, Any] | None, str]:
    return _planner_state.generate_plan_from_intent(text)


def is_planner_enabled() -> bool:
    return _planner_state.is_enabled()


def set_planner_enabled(value: bool) -> None:
    _planner_state.set_enabled(value)
