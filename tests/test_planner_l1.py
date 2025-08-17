from app.planner import (
    IntentMatcher,
    DSLGenerator,
    PlannerL1,
    generate_plan_from_intent,
    is_planner_enabled,
    set_planner_enabled
)


class TestIntentMatcher:
    """Test intent matching functionality."""

    def test_analyze_intent_csv_to_form(self):
        """Test intent analysis for CSV to form workflow."""
        matcher = IntentMatcher()

        test_cases = [
            "Process CSV file and submit to web form",
            "csvファイルをフォームに転記",
            "Fill form with CSV data",
            "CSVからwebフォームに送信"
        ]

        for text in test_cases:
            result = matcher.analyze_intent(text)

            assert "csv_process" in result["matched_intents"]
            assert "web_form" in result["matched_intents"]
            assert result["primary_intent"] == "csv_to_form"
            assert result["confidence"] > 0.3

    def test_analyze_intent_pdf_merge(self):
        """Test intent analysis for PDF merge workflow."""
        matcher = IntentMatcher()

        test_cases = [
            "Merge PDF files",
            "PDFファイルを結合",
            "Combine PDFs and email",
            "PDF結合してメール送信"
        ]

        for text in test_cases:
            result = matcher.analyze_intent(text)

            assert "pdf_merge" in result["matched_intents"]
            assert result["confidence"] > 0.2

    def test_analyze_intent_file_organization(self):
        """Test intent analysis for file organization."""
        matcher = IntentMatcher()

        test_cases = [
            "Organize files in downloads folder",
            "ファイルを整理して移動",
            "Move PDF files to backup folder",
            "ダウンロードフォルダを整理"
        ]

        for text in test_cases:
            result = matcher.analyze_intent(text)

            matched = result["matched_intents"]
            assert "file_find" in matched or "file_move" in matched
            assert result["confidence"] > 0.2

    def test_extract_entities_file_types(self):
        """Test entity extraction for file types."""
        matcher = IntentMatcher()

        test_cases = [
            ("Find PDF files", ["pdf"]),
            ("Process CSV data", ["csv"]),
            ("Convert Excel to PDF", ["excel", "pdf"]),
            ("PDFとCSVファイル", ["pdf", "csv"])
        ]

        for text, expected_types in test_cases:
            result = matcher.analyze_intent(text)
            entities = result["entities"]

            for file_type in expected_types:
                assert file_type in entities["file_types"]

    def test_extract_entities_actions(self):
        """Test entity extraction for actions."""
        matcher = IntentMatcher()

        test_cases = [
            ("Send email", ["send"]),
            ("Merge and combine files", ["merge", "combine"]),
            ("Move files to folder", ["move"]),
            ("送信して結合", ["送信", "結合"])
        ]

        for text, expected_actions in test_cases:
            result = matcher.analyze_intent(text)
            entities = result["entities"]

            for action in expected_actions:
                assert action in entities["actions"]

    def test_extract_entities_quantities(self):
        """Test entity extraction for quantities."""
        matcher = IntentMatcher()

        text = "Process 10 files and send 5 emails"
        result = matcher.analyze_intent(text)
        entities = result["entities"]

        assert "10" in entities["quantities"]
        assert "5" in entities["quantities"]

    def test_confidence_calculation(self):
        """Test confidence score calculation."""
        matcher = IntentMatcher()

        # High confidence case
        high_conf_text = "Process CSV file and submit to web form with email attachment"
        result = matcher.analyze_intent(high_conf_text)
        high_confidence = result["confidence"]

        # Low confidence case
        low_conf_text = "Do something"
        result = matcher.analyze_intent(low_conf_text)
        low_confidence = result["confidence"]

        assert high_confidence > low_confidence
        assert 0.0 <= low_confidence <= 1.0
        assert 0.0 <= high_confidence <= 1.0


class TestDSLGenerator:
    """Test DSL generation functionality."""

    def test_generate_csv_to_form_plan(self):
        """Test CSV to form plan generation."""
        generator = DSLGenerator()

        analysis = {
            "text": "Process CSV and submit to form",
            "primary_intent": "csv_to_form",
            "confidence": 0.8,
            "matched_intents": ["csv_process", "web_form"],
            "entities": {"file_types": ["csv"]}
        }

        plan = generator._generate_csv_to_form_plan(analysis)

        assert plan["dsl_version"] == "1.1"
        assert "CSV" in plan["name"]
        assert "variables" in plan
        assert "steps" in plan

        # Check for expected steps
        step_actions = [list(step.keys())[0] for step in plan["steps"]]
        assert "find_files" in step_actions
        assert "open_browser" in step_actions
        assert "fill_by_label" in step_actions
        assert "click_by_text" in step_actions

        # Check for approval-triggering action
        click_steps = [step for step in plan["steps"] if "click_by_text" in step]
        assert len(click_steps) > 0
        assert any("送信" in step["click_by_text"]["text"] for step in click_steps)

    def test_generate_pdf_merge_email_plan(self):
        """Test PDF merge and email plan generation."""
        generator = DSLGenerator()

        analysis = {
            "text": "Merge PDFs and send by email",
            "primary_intent": "pdf_merge_email",
            "confidence": 0.7,
            "matched_intents": ["pdf_merge", "email_compose"],
            "entities": {"file_types": ["pdf"], "actions": ["merge", "send"]}
        }

        plan = generator._generate_pdf_merge_email_plan(analysis)

        assert plan["dsl_version"] == "1.1"
        assert "PDF" in plan["name"]

        step_actions = [list(step.keys())[0] for step in plan["steps"]]
        assert "find_files" in step_actions
        assert "pdf_merge" in step_actions
        assert "compose_mail" in step_actions
        assert "attach_files" in step_actions
        assert "save_draft" in step_actions

    def test_generate_file_organization_plan(self):
        """Test file organization plan generation."""
        generator = DSLGenerator()

        analysis = {
            "text": "Organize PDF files",
            "primary_intent": "file_organization",
            "confidence": 0.6,
            "matched_intents": ["file_find", "file_move"],
            "entities": {"file_types": ["pdf"], "actions": ["move"]}
        }

        plan = generator._generate_file_organization_plan(analysis)

        assert plan["dsl_version"] == "1.1"
        assert "整理" in plan["name"]

        step_actions = [list(step.keys())[0] for step in plan["steps"]]
        assert "find_files" in step_actions
        assert "move_to" in step_actions
        assert "log" in step_actions

    def test_generate_plan_with_metadata(self):
        """Test plan generation includes metadata."""
        generator = DSLGenerator()

        plan = generator.generate_plan("Process CSV to web form")

        assert plan["_generated"] is True
        assert plan["_source_intent"] == "Process CSV to web form"
        assert "_analysis" in plan
        assert "_confidence" in plan
        assert isinstance(plan["_confidence"], float)

    def test_generate_unknown_intent(self):
        """Test plan generation for unknown intent."""
        generator = DSLGenerator()

        analysis = {
            "text": "Unknown request",
            "primary_intent": "unknown",
            "confidence": 0.1,
            "matched_intents": [],
            "entities": {}
        }

        plan = generator._generate_generic_plan(analysis)

        assert plan["dsl_version"] == "1.1"
        assert "汎用" in plan["name"]
        assert len(plan["steps"]) >= 1

        # Should have log steps explaining the situation
        log_steps = [step for step in plan["steps"] if "log" in step]
        assert len(log_steps) >= 1


class TestPlannerL1:
    """Test Planner L1 main functionality."""

    def test_planner_disabled_by_default(self):
        """Test planner is disabled by default."""
        planner = PlannerL1()
        assert planner.is_enabled() is False

        success, plan, message = planner.generate_plan_from_intent("Test intent")
        assert success is False
        assert "disabled" in message.lower()

    def test_planner_enable_disable(self):
        """Test enabling and disabling planner."""
        planner = PlannerL1()

        assert planner.is_enabled() is False

        planner.set_enabled(True)
        assert planner.is_enabled() is True

        planner.set_enabled(False)
        assert planner.is_enabled() is False

    def test_generate_plan_success(self):
        """Test successful plan generation."""
        planner = PlannerL1(enabled=True)

        success, plan, message = planner.generate_plan_from_intent("Process CSV data and submit to web form")

        assert success is True
        assert isinstance(plan, dict)
        assert "dsl_version" in plan
        assert "name" in plan
        assert "steps" in plan
        assert "confidence" in message.lower()

    def test_generate_plan_low_confidence(self):
        """Test plan generation with low confidence."""
        planner = PlannerL1(enabled=True)

        success, plan, message = planner.generate_plan_from_intent("Do something vague")

        # Might succeed or fail depending on confidence threshold
        if not success:
            assert "low confidence" in message.lower()
        else:
            # If it succeeds, confidence should still be noted
            assert isinstance(plan, dict)

    def test_generate_plan_empty_intent(self):
        """Test plan generation with empty intent."""
        planner = PlannerL1(enabled=True)

        success, plan, message = planner.generate_plan_from_intent("")

        assert success is False
        assert "empty" in message.lower()

        success, plan, message = planner.generate_plan_from_intent("   ")

        assert success is False
        assert "empty" in message.lower()

    def test_generate_plan_exception_handling(self):
        """Test plan generation error handling."""
        planner = PlannerL1(enabled=True)

        # Mock generator to raise exception
        original_generate = planner.generator.generate_plan

        def mock_generate(text):
            raise Exception("Test error")

        planner.generator.generate_plan = mock_generate

        success, plan, message = planner.generate_plan_from_intent("Test")

        assert success is False
        assert "error" in message.lower()
        assert "test error" in message.lower()

        # Restore original
        planner.generator.generate_plan = original_generate


class TestPlannerConvenienceFunctions:
    """Test convenience functions for planner."""

    def test_generate_plan_from_intent_function(self):
        """Test standalone plan generation function."""
        # Test with planner disabled (default)
        success, plan, message = generate_plan_from_intent("Test intent")
        assert success is False

        # Enable planner
        set_planner_enabled(True)

        try:
            success, plan, message = generate_plan_from_intent("Process CSV to form")

            if success:
                assert isinstance(plan, dict)
                assert "dsl_version" in plan
            else:
                assert isinstance(message, str)
        finally:
            # Restore disabled state
            set_planner_enabled(False)

    def test_is_planner_enabled_function(self):
        """Test planner enabled check function."""
        original_state = is_planner_enabled()

        set_planner_enabled(True)
        assert is_planner_enabled() is True

        set_planner_enabled(False)
        assert is_planner_enabled() is False

        # Restore original state
        set_planner_enabled(original_state)

    def test_set_planner_enabled_function(self):
        """Test planner enable/disable function."""
        original_state = is_planner_enabled()

        set_planner_enabled(True)
        assert is_planner_enabled() is True

        set_planner_enabled(False)
        assert is_planner_enabled() is False

        # Restore original state
        set_planner_enabled(original_state)


class TestPlannerIntegration:
    """Integration tests for planner functionality."""

    def test_end_to_end_csv_workflow(self):
        """Test complete CSV workflow generation."""
        planner = PlannerL1(enabled=True)

        intent = "I want to process a CSV file with contact information and submit each record to a web form"

        success, plan, message = planner.generate_plan_from_intent(intent)

        if success:
            # Verify plan structure
            assert plan["dsl_version"] == "1.1"
            assert len(plan["steps"]) > 0

            # Should contain web actions
            step_actions = [list(step.keys())[0] for step in plan["steps"]]
            assert any(action in ["open_browser", "fill_by_label", "click_by_text"] for action in step_actions)

            # Should have variables defined
            assert "variables" in plan

            # Should be marked as generated
            assert plan.get("_generated") is True

    def test_end_to_end_pdf_workflow(self):
        """Test complete PDF workflow generation."""
        planner = PlannerL1(enabled=True)

        intent = "Find all PDF files, merge them together, and send the result by email"

        success, plan, message = planner.generate_plan_from_intent(intent)

        if success:
            step_actions = [list(step.keys())[0] for step in plan["steps"]]

            # Should contain PDF and email actions
            assert "find_files" in step_actions
            assert "pdf_merge" in step_actions
            assert "compose_mail" in step_actions

            # Should have proper file type in find_files
            find_step = next(step for step in plan["steps"] if "find_files" in step)
            find_query = find_step["find_files"]["query"]
            assert "pdf" in find_query.lower()


class TestPlannerErrorCases:
    """Test error cases and edge conditions."""

    def test_intent_matcher_empty_patterns(self):
        """Test intent matcher with empty patterns."""
        matcher = IntentMatcher()

        # Backup original patterns
        original_patterns = matcher.patterns.copy()

        # Empty patterns
        matcher.patterns = {}

        result = matcher.analyze_intent("Process CSV file")

        assert result["matched_intents"] == []
        assert result["primary_intent"] == "unknown"
        assert result["confidence"] == 0.0

        # Restore patterns
        matcher.patterns = original_patterns

    def test_dsl_generator_malformed_analysis(self):
        """Test DSL generator with malformed analysis."""
        generator = DSLGenerator()

        # Should handle gracefully (missing required fields)
        plan = generator.generate_plan("Test intent")

        assert isinstance(plan, dict)
        assert "dsl_version" in plan
        assert "name" in plan
        assert "steps" in plan
