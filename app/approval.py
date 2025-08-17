from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from app.actions.web_actions import DESTRUCTIVE_KEYWORDS


class RiskAnalyzer:
    """Analyzes DSL plans for risk and approval requirements."""

    def __init__(self):
        self.destructive_keywords = DESTRUCTIVE_KEYWORDS

    def analyze_plan(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze a DSL plan for security risks and approval requirements.

        Returns:
            Dict containing risk analysis results
        """
        risks = []
        approval_required = False
        risk_level = "low"

        steps = plan.get("steps", [])

        for i, step in enumerate(steps):
            step_risks = self._analyze_step(i, step)
            if step_risks:
                risks.extend(step_risks)

        # Determine overall risk level and approval requirement
        if risks:
            high_risk_count = sum(1 for r in risks if r["level"] == "high")
            medium_risk_count = sum(1 for r in risks if r["level"] == "medium")

            if high_risk_count > 0:
                risk_level = "high"
                approval_required = True
            elif medium_risk_count > 0:
                risk_level = "medium"
                approval_required = True

        return {
            "approval_required": approval_required,
            "risk_level": risk_level,
            "risks": risks,
            "total_risks": len(risks),
            "high_risk_count": sum(1 for r in risks if r["level"] == "high"),
            "medium_risk_count": sum(1 for r in risks if r["level"] == "medium"),
            "analysis_version": "1.0"
        }

    def _analyze_step(self, step_index: int, step: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Analyze a single step for risks."""
        risks = []

        for action, params in step.items():
            if action == "click_by_text":
                risk = self._analyze_click_by_text(step_index, action, params)
                if risk:
                    risks.append(risk)
            elif action in ["move_to", "pdf_merge", "attach_files"]:
                risk = self._analyze_destructive_file_action(step_index, action, params)
                if risk:
                    risks.append(risk)
            elif action == "compose_mail":
                risk = self._analyze_mail_action(step_index, action, params)
                if risk:
                    risks.append(risk)

        return risks

    def _analyze_click_by_text(self, step_index: int, action: str,
                               params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Analyze click_by_text for destructive patterns."""
        text = params.get("text", "")
        if not text:
            return None

        # Check for destructive keywords
        import re
        for keyword in self.destructive_keywords:
            # Use word boundary for English, simple contains for Japanese/non-ASCII
            if any(ord(c) > 127 for c in keyword):
                # Japanese/non-ASCII keywords - use simple contains
                if keyword.lower() in text.lower():
                    match = True
                else:
                    match = False
            else:
                # English keywords - use word boundary
                pattern = r'\b' + re.escape(keyword.lower()) + r'\b'
                match = re.search(pattern, text.lower()) is not None
            if match:
                return {
                    "step_index": step_index,
                    "action": action,
                    "level": "high",
                    "category": "destructive_click",
                    "description": f"Click action contains destructive keyword: '{keyword}'",
                    "details": {
                        "text": text,
                        "keyword": keyword,
                        "role": params.get("role")
                    },
                    "mitigation": "Manual approval required before execution"
                }

        # Special case: Check for Submit forms (high risk)
        form_submit_pattern = r'\bsubmit\b.*\bform\b|\bform\b.*\bsubmit\b'
        has_submit_form = re.search(form_submit_pattern, text.lower())
        has_submit_button = (re.search(r'\bsubmit\b', text.lower())
                             and any(word in text.lower() for word in ['form', 'button']))
        if has_submit_form or has_submit_button:
            return {
                "step_index": step_index,
                "action": action,
                "level": "high",
                "category": "destructive_click",
                "description": "Click action contains destructive keyword: 'Submit'",
                "details": {
                    "text": text,
                    "keyword": "Submit",
                    "role": params.get("role")
                },
                "mitigation": "Manual approval required before execution"
            }

        # Check for form submission patterns
        submission_patterns = ["submit", "send", "post", "save", "update"]
        for pattern in submission_patterns:
            if pattern.lower() in text.lower():
                return {
                    "step_index": step_index,
                    "action": action,
                    "level": "medium",
                    "category": "form_submission",
                    "description": f"Click action appears to be form submission: '{text}'",
                    "details": {
                        "text": text,
                        "pattern": pattern,
                        "role": params.get("role")
                    },
                    "mitigation": "Review form data before submission"
                }

        return None

    def _analyze_destructive_file_action(self, step_index: int, action: str,
                                         params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Analyze file operations for destructive patterns."""
        if action == "move_to":
            return {
                "step_index": step_index,
                "action": action,
                "level": "medium",
                "category": "file_modification",
                "description": "File move operation can alter file locations",
                "details": {
                    "destination": params.get("dest")
                },
                "mitigation": "Verify destination path and file count"
            }
        elif action == "pdf_merge":
            return {
                "step_index": step_index,
                "action": action,
                "level": "low",
                "category": "file_creation",
                "description": "PDF merge creates new file",
                "details": {
                    "output": params.get("out"),
                    "input_count": len(params.get("inputs", []))
                },
                "mitigation": "Review output path and input files"
            }
        elif action == "attach_files":
            return {
                "step_index": step_index,
                "action": action,
                "level": "medium",
                "category": "data_transmission",
                "description": "File attachment may transmit sensitive data",
                "details": {
                    "file_count": len(params.get("paths", []))
                },
                "mitigation": "Review attached files for sensitive content"
            }

        return None

    def _analyze_mail_action(self, step_index: int, action: str,
                             params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Analyze mail composition for risks."""
        recipients = params.get("to", [])
        if recipients:
            return {
                "step_index": step_index,
                "action": action,
                "level": "medium",
                "category": "data_transmission",
                "description": "Email composition with recipients",
                "details": {
                    "recipient_count": len(recipients),
                    "subject": (params.get("subject", "")[:50] + "..." if
                                len(params.get("subject", "")) > 50 else
                                params.get("subject", ""))
                },
                "mitigation": "Review recipients and email content"
            }

        return None


class ApprovalGate:
    """Manages approval workflow for risky operations."""

    def __init__(self):
        self.analyzer = RiskAnalyzer()

    def check_approval_required(self, plan: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        """
        Check if a plan requires approval and return risk analysis.

        Returns:
            Tuple of (approval_required, risk_analysis)
        """
        analysis = self.analyzer.analyze_plan(plan)
        return analysis["approval_required"], analysis

    def format_risk_summary(self, analysis: Dict[str, Any]) -> str:
        """Format risk analysis for display."""
        if not analysis["risks"]:
            return "No risks detected."

        summary = []
        summary.append(f"Risk Level: {analysis['risk_level'].upper()}")
        summary.append(f"Total Risks: {analysis['total_risks']}")

        if analysis["high_risk_count"] > 0:
            summary.append(f"High Risk Actions: {analysis['high_risk_count']}")
        if analysis["medium_risk_count"] > 0:
            summary.append(f"Medium Risk Actions: {analysis['medium_risk_count']}")

        summary.append("\nRisk Details:")
        for risk in analysis["risks"]:
            summary.append(f"- Step {risk['step_index']}: {risk['description']}")

        return "\n".join(summary)

    def get_approval_message(self, analysis: Dict[str, Any]) -> str:
        """Get approval message for UI display."""
        if not analysis["approval_required"]:
            return "No approval required. Plan is safe to execute."

        if analysis["risk_level"] == "high":
            return ("⚠️ HIGH RISK: This plan contains destructive operations. "
                    "Manual approval required.")
        elif analysis["risk_level"] == "medium":
            return ("⚡ MEDIUM RISK: This plan contains potentially risky operations. "
                    "Approval recommended.")
        else:
            return "✅ LOW RISK: Plan appears safe but approval required due to policy."


# Global approval gate instance
approval_gate = ApprovalGate()


def analyze_plan_risks(plan: Dict[str, Any]) -> Dict[str, Any]:
    """Convenience function to analyze plan risks."""
    return approval_gate.analyzer.analyze_plan(plan)


def check_plan_approval_required(plan: Dict[str, Any]) -> bool:
    """Convenience function to check if plan requires approval."""
    required, _ = approval_gate.check_approval_required(plan)
    return required


def format_approval_summary(analysis: Dict[str, Any]) -> str:
    """Convenience function to format approval summary."""
    return approval_gate.format_risk_summary(analysis)


def get_approval_ui_message(analysis: Dict[str, Any]) -> str:
    """Convenience function to get approval UI message."""
    return approval_gate.get_approval_message(analysis)
