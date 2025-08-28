"""
Planner L2 - Differential Patch Proposal System
Analyzes screen schema and proposes small changes for execution stability
"""

import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field

from .schema_ops import SchemaAnalyzer, PatchGenerator


logger = logging.getLogger(__name__)


@dataclass
class TextReplacement:
    """Represents a text replacement in differential patch"""
    find: str
    with_text: str
    role: str
    confidence: float = 0.0


@dataclass
class FallbackSearch:
    """Represents a fallback search strategy"""
    goal: str
    synonyms: List[str]
    role: str
    attempts: int = 1
    confidence: float = 0.0


@dataclass
class WaitTuning:
    """Represents wait/timeout adjustments"""
    step: str
    timeout_ms: int
    confidence: float = 0.0


@dataclass
class DifferentialPatch:
    """Represents a differential patch proposal"""
    patch_type: str  # "replace_text", "fallback_search", "wait_tuning", "add_step"
    confidence: float
    risk_level: str = "low"  # "low", "medium", "high"

    # Patch content (one of these will be populated based on patch_type)
    replacements: List[TextReplacement] = field(default_factory=list)
    fallback_search: Optional[FallbackSearch] = None
    wait_tuning: Optional[WaitTuning] = None
    new_step: Optional[Dict[str, Any]] = None

    # Metadata
    generated_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.generated_at is None:
            self.generated_at = datetime.now(timezone.utc)

    def to_json(self) -> str:
        """Serialize patch to JSON"""
        data = {
            "patch_type": self.patch_type,
            "confidence": self.confidence,
            "risk_level": self.risk_level,
            "generated_at": self.generated_at.isoformat() if self.generated_at else None
        }

        if self.replacements:
            data["replacements"] = [
                {
                    "find": r.find,
                    "with": r.with_text,
                    "role": r.role,
                    "confidence": r.confidence
                }
                for r in self.replacements
            ]

        if self.fallback_search:
            data["fallback_search"] = {
                "goal": self.fallback_search.goal,
                "synonyms": self.fallback_search.synonyms,
                "role": self.fallback_search.role,
                "attempts": self.fallback_search.attempts,
                "confidence": self.fallback_search.confidence
            }

        if self.wait_tuning:
            data["wait_tuning"] = {
                "step": self.wait_tuning.step,
                "timeout_ms": self.wait_tuning.timeout_ms,
                "confidence": self.wait_tuning.confidence
            }

        if self.new_step:
            data["new_step"] = self.new_step

        if self.metadata:
            data["metadata"] = self.metadata

        return json.dumps(data, ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> 'DifferentialPatch':
        """Deserialize patch from JSON"""
        data = json.loads(json_str)

        patch = cls(
            patch_type=data["patch_type"],
            confidence=data["confidence"],
            risk_level=data.get("risk_level", "low"),
            metadata=data.get("metadata", {})
        )

        if data.get("generated_at"):
            patch.generated_at = datetime.fromisoformat(data["generated_at"])

        # Restore replacements
        if "replacements" in data:
            patch.replacements = [
                TextReplacement(
                    find=r["find"],
                    with_text=r["with"],
                    role=r["role"],
                    confidence=r.get("confidence", 0.0)
                )
                for r in data["replacements"]
            ]

        # Restore fallback search
        if "fallback_search" in data:
            fs_data = data["fallback_search"]
            patch.fallback_search = FallbackSearch(
                goal=fs_data["goal"],
                synonyms=fs_data["synonyms"],
                role=fs_data["role"],
                attempts=fs_data.get("attempts", 1),
                confidence=fs_data.get("confidence", 0.0)
            )

        # Restore wait tuning
        if "wait_tuning" in data:
            wt_data = data["wait_tuning"]
            patch.wait_tuning = WaitTuning(
                step=wt_data["step"],
                timeout_ms=wt_data["timeout_ms"],
                confidence=wt_data.get("confidence", 0.0)
            )

        # Restore new step
        if "new_step" in data:
            patch.new_step = data["new_step"]

        return patch


@dataclass
class AdoptionDecision:
    """Result of patch adoption policy evaluation"""
    auto_adopt: bool
    requires_confirmation: bool
    blocked: bool = False
    reason: str = ""


@dataclass
class PatchProposal:
    """Complete patch proposal with context"""
    patches: List[DifferentialPatch]
    adoption_decisions: List[AdoptionDecision]
    screen_context: Dict[str, Any]
    failure_context: Dict[str, Any]
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class PlannerL2:
    """
    Planner L2 - Differential Patch Proposal System
    Proposes small incremental changes to improve execution stability
    """

    def __init__(self, config: Dict[str, Any] = None):
        """Initialize Planner L2 with configuration"""
        self.config = config or {}
        self.schema_analyzer = SchemaAnalyzer()
        self.patch_generator = PatchGenerator()

        # Default adoption policy
        self.adoption_policy = {
            "low_risk_auto": True,
            "min_confidence": 0.85,
            "max_auto_changes": 3,
            "require_confirmation_outside_l4": True,
            "block_high_risk": True
        }
        self.adoption_policy.update(self.config.get("adopt_policy", {}))

        logger.info("Planner L2 initialized with differential patch system")

    def analyze_for_text_patches(
        self,
        screen_schema: Dict[str, Any],
        failure_info: Dict[str, Any]
    ) -> Optional[DifferentialPatch]:
        """Analyze screen schema for text replacement opportunities"""

        failed_step = failure_info.get("failed_step")
        failed_params = failure_info.get("failed_params", {})

        if failed_step not in ["click_by_text", "fill_by_label"]:
            return None

        target_text = failed_params.get("text") or failed_params.get("label", "")
        target_role = failed_params.get("role", "button")

        if not target_text:
            return None

        # Find semantically similar elements
        elements = screen_schema.get("elements", [])
        similar_elements = self.schema_analyzer.find_semantic_matches(
            target_text,
            elements,
            threshold=0.7
        )

        if not similar_elements:
            return None

        # Generate text replacements
        replacements = []
        for element in similar_elements[:3]:  # Top 3 matches
            if element["text"] != target_text:
                replacement = TextReplacement(
                    find=target_text,
                    with_text=element["text"],
                    role=target_role,
                    confidence=element.get("similarity", 0.8)
                )
                replacements.append(replacement)

        if not replacements:
            return None

        # Calculate overall confidence
        avg_confidence = sum(r.confidence for r in replacements) / len(replacements)

        patch = DifferentialPatch(
            patch_type="replace_text",
            replacements=replacements,
            confidence=avg_confidence,
            risk_level="low"
        )

        logger.info(f"Generated text replacement patch: {target_text} -> {[r.with_text for r in replacements]}")
        return patch

    def generate_fallback_search(self, failure_info: Dict[str, Any]) -> Optional[DifferentialPatch]:
        """Generate fallback search patch with synonyms"""

        failed_params = failure_info.get("failed_params", {})
        target_text = failed_params.get("text", "")
        target_role = failed_params.get("role", "button")

        if not target_text:
            return None

        # Generate synonyms based on common UI patterns
        synonyms = self._generate_synonyms(target_text)

        if not synonyms:
            return None

        fallback_search = FallbackSearch(
            goal=f"{target_text}ボタン" if target_role == "button" else f"{target_text}{target_role}",
            synonyms=synonyms,
            role=target_role,
            attempts=1,
            confidence=0.88  # Conservative confidence for fallback
        )

        patch = DifferentialPatch(
            patch_type="fallback_search",
            fallback_search=fallback_search,
            confidence=0.88,
            risk_level="low"
        )

        logger.info(f"Generated fallback search patch: {target_text} -> {synonyms}")
        return patch

    def generate_wait_tuning(self, failure_info: Dict[str, Any]) -> Optional[DifferentialPatch]:
        """Generate wait timing adjustment patch"""

        failed_step = failure_info.get("failed_step")
        failed_params = failure_info.get("failed_params", {})
        current_timeout = failed_params.get("timeout_ms", 5000)

        if failed_step != "wait_for_element":
            return None

        # Increase timeout by 50-200% based on current value
        if current_timeout < 5000:
            new_timeout = current_timeout * 2
        elif current_timeout < 10000:
            new_timeout = current_timeout + 5000
        else:
            new_timeout = min(current_timeout + 5000, 30000)  # Cap at 30s

        wait_tuning = WaitTuning(
            step=failed_step,
            timeout_ms=new_timeout,
            confidence=0.85
        )

        patch = DifferentialPatch(
            patch_type="wait_tuning",
            wait_tuning=wait_tuning,
            confidence=0.85,
            risk_level="low"
        )

        logger.info(f"Generated wait tuning patch: {current_timeout}ms -> {new_timeout}ms")
        return patch

    def evaluate_adoption_policy(
        self,
        patch: DifferentialPatch,
        context: Dict[str, Any]
    ) -> AdoptionDecision:
        """Evaluate whether patch should be auto-adopted"""

        autopilot_enabled = context.get("autopilot_enabled", False)
        policy_window = context.get("policy_window", False)
        min_confidence = context.get("min_confidence", self.adoption_policy["min_confidence"])

        # Block high-risk patches
        if patch.risk_level == "high":
            return AdoptionDecision(
                auto_adopt=False,
                requires_confirmation=False,
                blocked=True,
                reason="High-risk operation blocked by policy"
            )

        # Check confidence threshold
        if patch.confidence < min_confidence:
            return AdoptionDecision(
                auto_adopt=False,
                requires_confirmation=True,
                reason=f"Confidence {patch.confidence:.2f} below threshold {min_confidence}"
            )

        # Auto-adopt low-risk patches in L4 window
        if (
            patch.risk_level == "low"
            and autopilot_enabled
            and policy_window
            and patch.confidence >= min_confidence
        ):
            return AdoptionDecision(
                auto_adopt=True,
                requires_confirmation=False,
                reason="Low risk, high confidence, L4 window"
            )

        # Require confirmation outside L4 window
        if not policy_window or not autopilot_enabled:
            return AdoptionDecision(
                auto_adopt=False,
                requires_confirmation=True,
                reason="Outside L4 window - requires confirmation"
            )

        # Default: require confirmation
        return AdoptionDecision(
            auto_adopt=False,
            requires_confirmation=True,
            reason="Default policy - requires confirmation"
        )

    def apply_patches(
        self,
        original_dsl: Dict[str, Any],
        patches: List[DifferentialPatch]
    ) -> Dict[str, Any]:
        """Apply differential patches to DSL template"""

        modified_dsl = json.loads(json.dumps(original_dsl))  # Deep copy
        applied_patches = []

        for patch in patches:
            try:
                if patch.patch_type == "replace_text":
                    self._apply_text_replacements(modified_dsl, patch.replacements)
                elif patch.patch_type == "wait_tuning":
                    self._apply_wait_tuning(modified_dsl, patch.wait_tuning)
                elif patch.patch_type == "fallback_search":
                    self._apply_fallback_search(modified_dsl, patch.fallback_search)
                elif patch.patch_type == "add_step":
                    self._apply_new_step(modified_dsl, patch.new_step)

                applied_patches.append({
                    "type": patch.patch_type,
                    "confidence": patch.confidence,
                    "applied_at": datetime.now(timezone.utc).isoformat()
                })

                logger.info(f"Applied patch: {patch.patch_type} (confidence: {patch.confidence:.2f})")

            except Exception as e:
                logger.error(f"Failed to apply patch {patch.patch_type}: {e}")

        # Track applied patches in DSL metadata
        modified_dsl["_applied_patches"] = applied_patches
        modified_dsl["_modified_at"] = datetime.now(timezone.utc).isoformat()

        return modified_dsl

    def _apply_text_replacements(
        self,
        dsl: Dict[str, Any],
        replacements: List[TextReplacement]
    ):
        """Apply text replacements to DSL steps"""
        steps = dsl.get("steps", [])

        for step in steps:
            for action_name, params in step.items():
                if isinstance(params, dict):
                    for replacement in replacements:
                        # Replace text field
                        if params.get("text") == replacement.find:
                            params["text"] = replacement.with_text

                        # Replace label field
                        if params.get("label") == replacement.find:
                            params["label"] = replacement.with_text

    def _apply_wait_tuning(self, dsl: Dict[str, Any], wait_tuning: WaitTuning):
        """Apply wait timing adjustments to DSL steps"""
        steps = dsl.get("steps", [])

        for step in steps:
            if wait_tuning.step in step:
                params = step[wait_tuning.step]
                if isinstance(params, dict):
                    params["timeout_ms"] = wait_tuning.timeout_ms

    def _apply_fallback_search(self, dsl: Dict[str, Any], fallback: FallbackSearch):
        """Apply fallback search strategy to DSL steps"""
        # This would add fallback search logic to existing steps
        # For now, we'll add metadata to track the fallback strategy
        if "_fallback_searches" not in dsl:
            dsl["_fallback_searches"] = []

        dsl["_fallback_searches"].append({
            "goal": fallback.goal,
            "synonyms": fallback.synonyms,
            "role": fallback.role,
            "attempts": fallback.attempts
        })

    def _apply_new_step(self, dsl: Dict[str, Any], new_step: Dict[str, Any]):
        """Apply new step addition to DSL"""
        if "steps" not in dsl:
            dsl["steps"] = []

        # Add new step at appropriate position (for now, append)
        dsl["steps"].append(new_step)

    def _generate_synonyms(self, text: str) -> List[str]:
        """Generate synonyms for UI text based on common patterns"""
        synonym_map = {
            # Japanese action verbs
            "送信": ["確定", "送出", "提出", "実行"],
            "確定": ["送信", "OK", "決定", "完了"],
            "提出": ["送信", "確定", "送出", "提出"],
            "キャンセル": ["取消", "中止", "戻る", "Cancel"],
            "削除": ["消去", "除去", "削除", "Delete"],

            # English action verbs
            "Submit": ["Send", "Confirm", "OK", "Execute"],
            "Cancel": ["Close", "Abort", "Back", "キャンセル"],
            "Delete": ["Remove", "Clear", "削除"],
            "Save": ["Store", "Keep", "保存"],
            "Edit": ["Modify", "Change", "編集"],

            # Common UI elements
            "Button": ["ボタン", "btn", "link"],
            "Link": ["リンク", "URL", "href"],
            "Form": ["フォーム", "入力", "Input"]
        }

        return synonym_map.get(text, [])
