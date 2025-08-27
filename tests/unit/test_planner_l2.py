"""
Unit tests for Planner L2 - Differential Patch Proposal System
Red tests first (TDD) - should fail initially
"""

import pytest
import json
from unittest.mock import patch, MagicMock
from pathlib import Path

# These imports will fail initially - that's expected for TDD
try:
    from app.planner.l2 import PlannerL2, DifferentialPatch, PatchProposal
    from app.planner.schema_ops import SchemaAnalyzer, PatchGenerator
except ImportError:
    # Expected during TDD red phase
    PlannerL2 = None
    DifferentialPatch = None
    PatchProposal = None
    SchemaAnalyzer = None
    PatchGenerator = None


class TestPlannerL2:
    """Test Planner L2 differential patch generation"""
    
    def test_analyze_screen_schema_for_text_variants(self):
        """Should analyze screen schema and identify text variant opportunities"""
        # RED: Will fail - PlannerL2 doesn't exist yet
        if PlannerL2 is None:
            pytest.skip("PlannerL2 not implemented yet")
            
        planner = PlannerL2()
        
        # Mock screen schema with button that user failed to find
        screen_schema = {
            "elements": [
                {"text": "確定", "role": "button", "selector": "#confirm-btn"},
                {"text": "キャンセル", "role": "button", "selector": "#cancel-btn"},
                {"text": "送信", "role": "link", "selector": "#submit-link"}
            ]
        }
        
        # Mock failure info - user tried to find "送信" button but it's a link
        failure_info = {
            "failed_step": "click_by_text",
            "failed_params": {"text": "送信", "role": "button"},
            "error": "Button with text '送信' not found"
        }
        
        patch = planner.analyze_for_text_patches(screen_schema, failure_info)
        
        assert patch is not None
        assert patch.patch_type == "replace_text"
        assert any(p.find == "送信" and p.with_text == "確定" for p in patch.replacements)
        assert patch.confidence > 0.8
    
    def test_generate_fallback_search_patch(self):
        """Should generate fallback search patches with synonyms"""
        # RED: Will fail - fallback search not implemented
        if PlannerL2 is None:
            pytest.skip("PlannerL2 not implemented yet")
            
        planner = PlannerL2()
        
        failure_info = {
            "failed_step": "click_by_text",
            "failed_params": {"text": "提出", "role": "button"},
            "error": "Element not found"
        }
        
        patch = planner.generate_fallback_search(failure_info)
        
        assert patch.patch_type == "fallback_search"
        assert patch.fallback_search.goal == "提出ボタン"
        assert "確定" in patch.fallback_search.synonyms
        assert "送信" in patch.fallback_search.synonyms
        assert "送出" in patch.fallback_search.synonyms
        assert patch.fallback_search.attempts == 1
        assert patch.confidence > 0.85
    
    def test_wait_tuning_patch_generation(self):
        """Should generate wait timing adjustment patches"""
        # RED: Will fail - wait tuning not implemented
        if PlannerL2 is None:
            pytest.skip("PlannerL2 not implemented yet")
            
        planner = PlannerL2()
        
        failure_info = {
            "failed_step": "wait_for_element",
            "failed_params": {"selector": "#loading", "timeout_ms": 5000},
            "error": "Timeout waiting for element",
            "duration_ms": 5000
        }
        
        patch = planner.generate_wait_tuning(failure_info)
        
        assert patch.patch_type == "wait_tuning"
        assert patch.wait_tuning.step == "wait_for_element"
        assert patch.wait_tuning.timeout_ms > 5000  # Should increase timeout
        assert patch.wait_tuning.timeout_ms <= 15000  # But not too much
        assert patch.confidence > 0.8
    
    def test_patch_adoption_policy_low_risk_auto(self):
        """Should auto-adopt low-risk patches in L4 window with high confidence"""
        # RED: Will fail - adoption policy not implemented
        if PlannerL2 is None:
            pytest.skip("PlannerL2 not implemented yet")
            
        planner = PlannerL2()
        
        # Mock low-risk, high-confidence patch
        patch = DifferentialPatch(
            patch_type="replace_text",
            replacements=[{"find": "送信", "with": "確定", "role": "button"}],
            confidence=0.92,
            risk_level="low"
        )
        
        # Mock L4 window context
        context = {
            "autopilot_enabled": True,
            "policy_window": True,
            "min_confidence": 0.85
        }
        
        adoption_decision = planner.evaluate_adoption_policy(patch, context)
        
        assert adoption_decision.auto_adopt is True
        assert adoption_decision.requires_confirmation is False
        assert adoption_decision.reason == "Low risk, high confidence, L4 window"
    
    def test_patch_adoption_policy_requires_confirmation_outside_window(self):
        """Should require confirmation for patches outside L4 window"""
        # RED: Will fail - adoption policy not implemented
        if PlannerL2 is None:
            pytest.skip("PlannerL2 not implemented yet")
            
        planner = PlannerL2()
        
        patch = DifferentialPatch(
            patch_type="replace_text", 
            confidence=0.90,
            risk_level="low"
        )
        
        # Outside L4 window
        context = {
            "autopilot_enabled": False,
            "policy_window": False,
            "min_confidence": 0.85
        }
        
        adoption_decision = planner.evaluate_adoption_policy(patch, context)
        
        assert adoption_decision.auto_adopt is False
        assert adoption_decision.requires_confirmation is True
        assert "outside l4 window" in adoption_decision.reason.lower()
    
    def test_high_risk_patch_blocked(self):
        """Should block patches that add high-risk operations"""
        # RED: Will fail - risk assessment not implemented
        if PlannerL2 is None:
            pytest.skip("PlannerL2 not implemented yet")
            
        planner = PlannerL2()
        
        # Patch that tries to add dangerous operation
        dangerous_patch = DifferentialPatch(
            patch_type="add_step",
            new_step={"delete_file": {"path": "/important/file.txt"}},
            confidence=0.95,
            risk_level="high"
        )
        
        context = {"autopilot_enabled": True}
        
        adoption_decision = planner.evaluate_adoption_policy(dangerous_patch, context)
        
        assert adoption_decision.auto_adopt is False
        assert adoption_decision.blocked is True
        assert "high-risk operation" in adoption_decision.reason.lower()
    
    def test_schema_analysis_for_nearby_elements(self):
        """Should analyze schema to find nearby alternative elements"""
        # RED: Will fail - schema analyzer not implemented
        if SchemaAnalyzer is None:
            pytest.skip("SchemaAnalyzer not implemented yet")
            
        analyzer = SchemaAnalyzer()
        
        schema = {
            "elements": [
                {"text": "Cancel", "role": "button", "x": 100, "y": 200},
                {"text": "OK", "role": "button", "x": 200, "y": 200},  # Nearby
                {"text": "確定", "role": "button", "x": 210, "y": 205},  # Very nearby
                {"text": "Help", "role": "button", "x": 500, "y": 400}   # Far away
            ]
        }
        
        target_element = {"text": "Submit", "role": "button", "x": 205, "y": 195}
        
        nearby = analyzer.find_nearby_elements(schema, target_element, radius=50)
        
        assert len(nearby) == 2  # OK and 確定
        assert any(e["text"] == "OK" for e in nearby)
        assert any(e["text"] == "確定" for e in nearby)
        assert not any(e["text"] == "Help" for e in nearby)  # Too far
    
    def test_patch_serialization(self):
        """Should serialize patches for storage and execution"""
        # RED: Will fail - patch serialization not implemented
        if DifferentialPatch is None:
            pytest.skip("DifferentialPatch not implemented yet")
            
        from app.planner.l2 import TextReplacement
        patch = DifferentialPatch(
            patch_type="replace_text",
            replacements=[TextReplacement(find="送信", with_text="確定", role="button", confidence=0.92)],
            confidence=0.91,
            risk_level="low",
            metadata={"generated_at": "2025-08-27T14:00:00Z"}
        )
        
        # Should serialize to JSON
        patch_json = patch.to_json()
        assert isinstance(patch_json, str)
        
        # Should deserialize correctly
        restored_patch = DifferentialPatch.from_json(patch_json)
        assert restored_patch.patch_type == "replace_text"
        assert restored_patch.confidence == 0.91
        assert len(restored_patch.replacements) == 1
    
    def test_patch_application_to_dsl(self):
        """Should apply patches to DSL templates"""
        # RED: Will fail - patch application not implemented
        if PlannerL2 is None:
            pytest.skip("PlannerL2 not implemented yet")
            
        planner = PlannerL2()
        
        original_dsl = {
            "steps": [
                {"click_by_text": {"text": "送信", "role": "button"}},
                {"wait_for_element": {"selector": "#result", "timeout_ms": 5000}}
            ]
        }
        
        from app.planner.l2 import TextReplacement, WaitTuning
        patches = [
            DifferentialPatch(
                patch_type="replace_text",
                replacements=[TextReplacement(find="送信", with_text="確定", role="button", confidence=0.9)],
                confidence=0.9
            ),
            DifferentialPatch(
                patch_type="wait_tuning",
                wait_tuning=WaitTuning(step="wait_for_element", timeout_ms=10000, confidence=0.8),
                confidence=0.8
            )
        ]
        
        modified_dsl = planner.apply_patches(original_dsl, patches)
        
        # Should have applied text replacement
        assert modified_dsl["steps"][0]["click_by_text"]["text"] == "確定"
        
        # Should have applied timeout tuning
        assert modified_dsl["steps"][1]["wait_for_element"]["timeout_ms"] == 10000
        
        # Should track applied patches
        assert "_applied_patches" in modified_dsl
        assert len(modified_dsl["_applied_patches"]) == 2


class TestSchemaOperations:
    """Test screen schema analysis and operations"""
    
    def test_extract_ui_vocabulary(self):
        """Should extract UI vocabulary from screen schema"""
        # RED: Will fail - vocabulary extraction not implemented
        if SchemaAnalyzer is None:
            pytest.skip("SchemaAnalyzer not implemented yet")
            
        analyzer = SchemaAnalyzer()
        
        schema = {
            "elements": [
                {"text": "Submit", "role": "button"},
                {"text": "確定", "role": "button"}, 
                {"text": "送信", "role": "link"},
                {"text": "Cancel", "role": "button"},
                {"text": "キャンセル", "role": "button"}
            ]
        }
        
        vocabulary = analyzer.extract_ui_vocabulary(schema)
        
        assert "Submit" in vocabulary["buttons"]
        assert "確定" in vocabulary["buttons"]
        assert "送信" in vocabulary["links"]
        assert len(vocabulary["buttons"]) == 4  # Submit, 確定, Cancel, キャンセル
    
    def test_semantic_similarity_matching(self):
        """Should find semantically similar UI elements"""
        # RED: Will fail - semantic matching not implemented
        if SchemaAnalyzer is None:
            pytest.skip("SchemaAnalyzer not implemented yet")
            
        analyzer = SchemaAnalyzer()
        
        # Mock UI elements
        elements = [
            {"text": "Submit", "role": "button"},
            {"text": "確定", "role": "button"},
            {"text": "送信", "role": "button"},
            {"text": "Cancel", "role": "button"},
            {"text": "OK", "role": "button"}
        ]
        
        similar = analyzer.find_semantic_matches("提出", elements, threshold=0.7)
        
        # Should find Submit, 確定, 送信 as semantically similar to 提出
        assert len(similar) >= 2
        assert any(elem["text"] == "Submit" for elem in similar)
        assert any(elem["text"] == "確定" for elem in similar)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])