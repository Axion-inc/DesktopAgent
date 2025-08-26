from app.approval import (
    RiskAnalyzer,
    ApprovalGate,
    analyze_plan_risks,
    check_plan_approval_required,
    format_approval_summary,
    get_approval_ui_message
)


class TestRiskAnalyzer:
    """Test risk analysis functionality."""

    def test_analyze_plan_low_risk(self):
        """Test analysis of low-risk plan."""
        analyzer = RiskAnalyzer()

        plan = {
            "dsl_version": "1.1",
            "name": "Safe Plan",
            "steps": [
                {"find_files": {"query": "*.pdf", "roots": ["./data"]}},
                {"log": {"message": "Found files"}}
            ]
        }

        result = analyzer.analyze_plan(plan)

        assert result["approval_required"] is False
        assert result["risk_level"] == "low"
        assert result["total_risks"] == 0
        assert result["high_risk_count"] == 0
        assert result["medium_risk_count"] == 0
        assert len(result["risks"]) == 0

    def test_analyze_plan_high_risk_destructive_click(self):
        """Test analysis of plan with destructive click action."""
        analyzer = RiskAnalyzer()

        plan = {
            "dsl_version": "1.1",
            "name": "Risky Plan",
            "steps": [
                {"open_browser": {"url": "http://example.com"}},
                {"click_by_text": {"text": "送信", "role": "button"}}
            ]
        }

        result = analyzer.analyze_plan(plan)

        assert result["approval_required"] is True
        assert result["risk_level"] == "high"
        assert result["total_risks"] == 1
        assert result["high_risk_count"] == 1
        assert result["medium_risk_count"] == 0

        risk = result["risks"][0]
        assert risk["step_index"] == 1
        assert risk["action"] == "click_by_text"
        assert risk["level"] == "high"
        assert risk["category"] == "destructive_click"
        assert "送信" in risk["description"]

    def test_analyze_plan_medium_risk_file_operations(self):
        """Test analysis of plan with medium-risk file operations."""
        analyzer = RiskAnalyzer()

        plan = {
            "dsl_version": "1.1",
            "name": "File Operations Plan",
            "steps": [
                {"find_files": {"query": "*.pdf", "roots": ["./data"]}},
                {"move_to": {"dest": "./backup"}},
                {"compose_mail": {"to": ["test@example.com"], "subject": "Test"}}
            ]
        }

        result = analyzer.analyze_plan(plan)

        assert result["approval_required"] is True
        assert result["risk_level"] == "medium"
        assert result["total_risks"] == 2
        assert result["high_risk_count"] == 0
        assert result["medium_risk_count"] == 2

        # Check file move risk
        move_risk = next(r for r in result["risks"] if r["action"] == "move_to")
        assert move_risk["level"] == "medium"
        assert move_risk["category"] == "file_modification"

        # Check email risk
        mail_risk = next(r for r in result["risks"] if r["action"] == "compose_mail")
        assert mail_risk["level"] == "medium"
        assert mail_risk["category"] == "data_transmission"

    def test_analyze_step_click_by_text_variations(self):
        """Test click_by_text analysis with various destructive keywords."""
        analyzer = RiskAnalyzer()

        destructive_cases = [
            ("送信", "送信"),
            ("Submit Form", "Submit"),
            ("Delete File", "Delete"),
            ("確定する", "確定"),
            ("Apply Changes", "Apply Changes")
        ]

        for text, expected_keyword in destructive_cases:
            risk = analyzer._analyze_click_by_text(0, "click_by_text", {"text": text})

            assert risk is not None
            assert risk["level"] == "high"
            assert risk["category"] == "destructive_click"
            assert expected_keyword.lower() in risk["description"].lower()
            assert risk["details"]["text"] == text
            assert risk["details"]["keyword"] == expected_keyword

    def test_analyze_step_click_by_text_form_submission(self):
        """Test click_by_text analysis with form submission patterns."""
        analyzer = RiskAnalyzer()

        # Submit is now high risk due to being in destructive keywords
        high_risk_cases = ["submit"]
        medium_risk_cases = ["send", "post", "save", "update"]

        for pattern in high_risk_cases:
            risk = analyzer._analyze_click_by_text(0, "click_by_text", {"text": f"Click to {pattern}"})

            assert risk is not None
            assert risk["level"] == "high"
            assert risk["category"] == "form_submission"
            assert pattern in risk["description"].lower()

        for pattern in medium_risk_cases:
            risk = analyzer._analyze_click_by_text(0, "click_by_text", {"text": f"Click to {pattern}"})

            assert risk is not None
            assert risk["level"] == "medium"
            assert risk["category"] == "form_submission"
            assert pattern in risk["description"].lower()

    def test_analyze_step_click_by_text_safe(self):
        """Test click_by_text analysis with safe actions."""
        analyzer = RiskAnalyzer()

        safe_cases = ["Cancel", "Back", "キャンセル", "戻る", "Close", "View Details"]

        for text in safe_cases:
            risk = analyzer._analyze_click_by_text(0, "click_by_text", {"text": text})
            assert risk is None


class TestApprovalGate:
    """Test approval gate functionality."""

    def test_check_approval_required_safe_plan(self):
        """Test approval check for safe plan."""
        gate = ApprovalGate()

        plan = {
            "steps": [
                {"find_files": {"query": "*.pdf"}},
                {"log": {"message": "Safe operation"}}
            ]
        }

        required, analysis = gate.check_approval_required(plan)

        assert required is False
        assert analysis["approval_required"] is False
        assert analysis["risk_level"] == "low"

    def test_check_approval_required_risky_plan(self):
        """Test approval check for risky plan."""
        gate = ApprovalGate()

        plan = {
            "steps": [
                {"open_browser": {"url": "http://example.com"}},
                {"click_by_text": {"text": "Delete All", "role": "button"}}
            ]
        }

        required, analysis = gate.check_approval_required(plan)

        assert required is True
        assert analysis["approval_required"] is True
        assert analysis["risk_level"] == "high"

    def test_format_risk_summary_no_risks(self):
        """Test risk summary formatting with no risks."""
        gate = ApprovalGate()

        analysis = {
            "risk_level": "low",
            "total_risks": 0,
            "high_risk_count": 0,
            "medium_risk_count": 0,
            "risks": []
        }

        summary = gate.format_risk_summary(analysis)
        assert "No risks detected" in summary

    def test_format_risk_summary_with_risks(self):
        """Test risk summary formatting with risks."""
        gate = ApprovalGate()

        analysis = {
            "risk_level": "high",
            "total_risks": 2,
            "high_risk_count": 1,
            "medium_risk_count": 1,
            "risks": [
                {
                    "step_index": 0,
                    "action": "click_by_text",
                    "level": "high",
                    "description": "Destructive action detected"
                },
                {
                    "step_index": 1,
                    "action": "move_to",
                    "level": "medium",
                    "description": "File modification operation"
                }
            ]
        }

        summary = gate.format_risk_summary(analysis)

        assert "Risk Level: HIGH" in summary
        assert "Total Risks: 2" in summary
        assert "High Risk Actions: 1" in summary
        assert "Medium Risk Actions: 1" in summary
        assert "Step 0: Destructive action detected" in summary
        assert "Step 1: File modification operation" in summary

    def test_get_approval_message_variations(self):
        """Test approval message generation for different risk levels."""
        gate = ApprovalGate()

        # No approval required
        analysis = {"approval_required": False}
        message = gate.get_approval_message(analysis)
        assert "No approval required" in message

        # High risk
        analysis = {"approval_required": True, "risk_level": "high"}
        message = gate.get_approval_message(analysis)
        assert "HIGH RISK" in message
        assert "Manual approval required" in message

        # Medium risk
        analysis = {"approval_required": True, "risk_level": "medium"}
        message = gate.get_approval_message(analysis)
        assert "MEDIUM RISK" in message
        assert "Approval recommended" in message

        # Low risk (edge case)
        analysis = {"approval_required": True, "risk_level": "low"}
        message = gate.get_approval_message(analysis)
        assert "LOW RISK" in message


class TestApprovalConvenienceFunctions:
    """Test convenience functions for approval system."""

    def test_analyze_plan_risks_function(self):
        """Test standalone plan risk analysis function."""
        plan = {
            "steps": [
                {"click_by_text": {"text": "Submit", "role": "button"}}
            ]
        }

        result = analyze_plan_risks(plan)

        assert isinstance(result, dict)
        assert "approval_required" in result
        assert "risk_level" in result
        assert "risks" in result
        assert result["approval_required"] is True

    def test_check_plan_approval_required_function(self):
        """Test standalone approval check function."""
        safe_plan = {
            "steps": [{"log": {"message": "Safe"}}]
        }

        risky_plan = {
            "steps": [{"click_by_text": {"text": "Delete"}}]
        }

        assert check_plan_approval_required(safe_plan) is False
        assert check_plan_approval_required(risky_plan) is True

    def test_format_approval_summary_function(self):
        """Test standalone approval summary formatting function."""
        analysis = {
            "risk_level": "medium",
            "total_risks": 1,
            "high_risk_count": 0,
            "medium_risk_count": 1,
            "risks": [
                {
                    "step_index": 0,
                    "description": "Test risk"
                }
            ]
        }

        summary = format_approval_summary(analysis)

        assert isinstance(summary, str)
        assert "MEDIUM" in summary
        assert "Test risk" in summary

    def test_get_approval_ui_message_function(self):
        """Test standalone approval UI message function."""
        analysis = {"approval_required": True, "risk_level": "high"}

        message = get_approval_ui_message(analysis)

        assert isinstance(message, str)
        assert "HIGH RISK" in message


class TestRiskAnalysisEdgeCases:
    """Test edge cases in risk analysis."""

    def test_empty_plan(self):
        """Test analysis of empty plan."""
        analyzer = RiskAnalyzer()

        plan = {"steps": []}

        result = analyzer.analyze_plan(plan)

        assert result["approval_required"] is False
        assert result["risk_level"] == "low"
        assert result["total_risks"] == 0

    def test_plan_without_steps(self):
        """Test analysis of plan without steps key."""
        analyzer = RiskAnalyzer()

        plan = {"name": "Test"}

        result = analyzer.analyze_plan(plan)

        assert result["approval_required"] is False
        assert result["risk_level"] == "low"
        assert result["total_risks"] == 0

    def test_malformed_steps(self):
        """Test analysis with malformed step structure."""
        analyzer = RiskAnalyzer()

        plan = {
            "steps": [
                {"invalid_action": {}},  # No known action
                {},  # Empty step
                {"click_by_text": {"text": "Submit"}}  # Valid step
            ]
        }

        result = analyzer.analyze_plan(plan)

        # Should still detect the valid risky step
        assert result["approval_required"] is True
        assert result["total_risks"] >= 1

    def test_click_without_text(self):
        """Test click analysis with missing text parameter."""
        analyzer = RiskAnalyzer()

        risk = analyzer._analyze_click_by_text(0, "click_by_text", {})
        assert risk is None

        risk = analyzer._analyze_click_by_text(0, "click_by_text", {"text": ""})
        assert risk is None

    def test_mixed_risk_levels(self):
        """Test plan with mixed risk levels."""
        analyzer = RiskAnalyzer()

        plan = {
            "steps": [
                {"click_by_text": {"text": "Submit"}},  # Medium risk (form submission)
                {"click_by_text": {"text": "Delete"}},  # High risk (destructive)
                {"move_to": {"dest": "./backup"}},      # Medium risk (file operation)
            ]
        }

        result = analyzer.analyze_plan(plan)

        # Should be high risk due to Delete action
        assert result["risk_level"] == "high"
        assert result["approval_required"] is True
        assert result["high_risk_count"] >= 1
        assert result["medium_risk_count"] >= 1
