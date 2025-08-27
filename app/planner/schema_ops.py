"""
Schema Operations for Planner L2
Screen schema analysis and patch generation utilities
"""

import logging
import math
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass


logger = logging.getLogger(__name__)


@dataclass
class ElementMatch:
    """Represents a matched UI element with similarity score"""
    element: Dict[str, Any]
    similarity: float
    distance: Optional[float] = None


class SchemaAnalyzer:
    """Analyzes screen schema for patch generation opportunities"""
    
    def __init__(self):
        """Initialize schema analyzer"""
        self.semantic_mappings = self._load_semantic_mappings()
    
    def extract_ui_vocabulary(self, schema: Dict[str, Any]) -> Dict[str, List[str]]:
        """Extract UI vocabulary categorized by element type"""
        vocabulary = {
            "buttons": [],
            "links": [],
            "inputs": [],
            "labels": []
        }
        
        elements = schema.get("elements", [])
        
        for element in elements:
            text = element.get("text", "").strip()
            role = element.get("role", "").lower()
            
            if not text:
                continue
            
            if role in ["button", "submit"]:
                vocabulary["buttons"].append(text)
            elif role in ["link", "a"]:
                vocabulary["links"].append(text)
            elif role in ["textbox", "input", "textarea"]:
                vocabulary["inputs"].append(text)
            elif role in ["label", "text"]:
                vocabulary["labels"].append(text)
        
        # Remove duplicates while preserving order
        for category in vocabulary:
            vocabulary[category] = list(dict.fromkeys(vocabulary[category]))
        
        return vocabulary
    
    def find_semantic_matches(
        self, 
        target_text: str, 
        elements: List[Dict[str, Any]], 
        threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """Find semantically similar UI elements"""
        matches = []
        
        for element in elements:
            element_text = element.get("text", "").strip()
            if not element_text or element_text == target_text:
                continue
            
            similarity = self._calculate_semantic_similarity(target_text, element_text)
            
            if similarity >= threshold:
                element_with_similarity = dict(element)
                element_with_similarity["similarity"] = similarity
                matches.append(element_with_similarity)
        
        # Sort by similarity descending
        matches.sort(key=lambda x: x["similarity"], reverse=True)
        
        return matches
    
    def find_nearby_elements(
        self, 
        schema: Dict[str, Any], 
        target_element: Dict[str, Any], 
        radius: float = 50
    ) -> List[Dict[str, Any]]:
        """Find UI elements within spatial proximity"""
        target_x = target_element.get("x", 0)
        target_y = target_element.get("y", 0)
        
        nearby = []
        
        for element in schema.get("elements", []):
            element_x = element.get("x", 0)
            element_y = element.get("y", 0)
            
            # Calculate Euclidean distance
            distance = math.sqrt((element_x - target_x) ** 2 + (element_y - target_y) ** 2)
            
            if distance <= radius and distance > 0:  # Exclude self
                element_with_distance = dict(element)
                element_with_distance["distance"] = distance
                nearby.append(element_with_distance)
        
        # Sort by distance ascending
        nearby.sort(key=lambda x: x["distance"])
        
        return nearby
    
    def analyze_element_context(
        self, 
        schema: Dict[str, Any], 
        target_element: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze context around a UI element"""
        context = {
            "nearby_elements": self.find_nearby_elements(schema, target_element),
            "same_role_elements": [],
            "parent_container": None,
            "sibling_elements": []
        }
        
        target_role = target_element.get("role", "")
        
        # Find elements with same role
        for element in schema.get("elements", []):
            if element.get("role") == target_role and element != target_element:
                context["same_role_elements"].append(element)
        
        # Additional context analysis could be added here
        # (parent/child relationships, container analysis, etc.)
        
        return context
    
    def _load_semantic_mappings(self) -> Dict[str, List[str]]:
        """Load semantic similarity mappings for UI text"""
        return {
            # Japanese action mappings
            "送信": ["submit", "send", "確定", "送出", "提出", "実行"],
            "確定": ["confirm", "ok", "submit", "送信", "決定", "完了"],
            "提出": ["submit", "send", "送信", "確定", "送出"],
            "キャンセル": ["cancel", "close", "abort", "取消", "中止", "戻る"],
            "削除": ["delete", "remove", "消去", "除去"],
            "保存": ["save", "store", "keep"],
            "編集": ["edit", "modify", "change"],
            
            # English action mappings
            "submit": ["send", "confirm", "ok", "execute", "送信", "確定", "提出"],
            "cancel": ["close", "abort", "back", "キャンセル", "取消"],
            "delete": ["remove", "clear", "削除", "消去"],
            "save": ["store", "keep", "保存"],
            "edit": ["modify", "change", "編集"],
            "ok": ["confirm", "accept", "yes", "確定", "OK"],
            "close": ["cancel", "dismiss", "閉じる", "キャンセル"],
            
            # Form-related mappings
            "name": ["名前", "氏名", "ユーザー名", "username"],
            "email": ["メール", "メールアドレス", "mail", "e-mail"],
            "password": ["パスワード", "暗証番号", "pwd"],
            "login": ["ログイン", "サインイン", "sign in"],
            "register": ["登録", "新規登録", "signup", "sign up"],
            
            # Navigation mappings
            "next": ["次へ", "進む", "forward", "続行"],
            "previous": ["前へ", "戻る", "back", "prev"],
            "home": ["ホーム", "トップ", "top", "メイン"],
            "menu": ["メニュー", "一覧", "list", "navigation"]
        }
    
    def _calculate_semantic_similarity(self, text1: str, text2: str) -> float:
        """Calculate semantic similarity between two UI text strings"""
        text1_lower = text1.lower().strip()
        text2_lower = text2.lower().strip()
        
        # Exact match
        if text1_lower == text2_lower:
            return 1.0
        
        # Check semantic mappings
        similarity = 0.0
        
        # Check if text1 maps to text2
        for key, values in self.semantic_mappings.items():
            if key.lower() == text1_lower and text2_lower in [v.lower() for v in values]:
                similarity = max(similarity, 0.9)
            elif key.lower() == text2_lower and text1_lower in [v.lower() for v in values]:
                similarity = max(similarity, 0.9)
        
        # Check if both texts are in same semantic group
        for key, values in self.semantic_mappings.items():
            values_lower = [v.lower() for v in values]
            if (text1_lower in values_lower or text1_lower == key.lower()) and \
               (text2_lower in values_lower or text2_lower == key.lower()):
                similarity = max(similarity, 0.8)
        
        # Simple lexical similarity (edit distance-based)
        if similarity == 0.0:
            similarity = self._calculate_lexical_similarity(text1_lower, text2_lower)
        
        return min(similarity, 1.0)
    
    def _calculate_lexical_similarity(self, text1: str, text2: str) -> float:
        """Calculate lexical similarity using edit distance"""
        if not text1 or not text2:
            return 0.0
        
        # Simple normalized edit distance
        max_len = max(len(text1), len(text2))
        edit_distance = self._levenshtein_distance(text1, text2)
        
        similarity = 1.0 - (edit_distance / max_len)
        return max(0.0, similarity)
    
    def _levenshtein_distance(self, s1: str, s2: str) -> int:
        """Calculate Levenshtein distance between two strings"""
        if len(s1) < len(s2):
            return self._levenshtein_distance(s2, s1)
        
        if len(s2) == 0:
            return len(s1)
        
        previous_row = list(range(len(s2) + 1))
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
        
        return previous_row[-1]


class PatchGenerator:
    """Generates differential patches based on schema analysis"""
    
    def __init__(self):
        """Initialize patch generator"""
        self.analyzer = SchemaAnalyzer()
    
    def generate_text_replacement_patches(
        self, 
        failed_text: str, 
        available_elements: List[Dict[str, Any]],
        max_suggestions: int = 3
    ) -> List[Dict[str, Any]]:
        """Generate text replacement patch suggestions"""
        patches = []
        
        # Find semantic matches
        matches = self.analyzer.find_semantic_matches(
            failed_text, 
            available_elements, 
            threshold=0.7
        )
        
        for match in matches[:max_suggestions]:
            patch = {
                "type": "text_replacement",
                "original": failed_text,
                "replacement": match["text"],
                "confidence": match["similarity"],
                "element": match
            }
            patches.append(patch)
        
        return patches
    
    def generate_proximity_patches(
        self, 
        schema: Dict[str, Any], 
        failed_element: Dict[str, Any],
        radius: float = 100
    ) -> List[Dict[str, Any]]:
        """Generate patches based on nearby elements"""
        patches = []
        
        nearby = self.analyzer.find_nearby_elements(schema, failed_element, radius)
        
        for element in nearby[:5]:  # Top 5 nearest
            # Generate patch suggesting nearby element as alternative
            patch = {
                "type": "proximity_alternative",
                "original_element": failed_element,
                "alternative_element": element,
                "distance": element["distance"],
                "confidence": max(0.5, 1.0 - (element["distance"] / radius))
            }
            patches.append(patch)
        
        return patches
    
    def generate_wait_adjustment_patches(
        self, 
        failed_step: Dict[str, Any],
        failure_duration: float
    ) -> List[Dict[str, Any]]:
        """Generate wait time adjustment patches"""
        patches = []
        
        current_timeout = failed_step.get("timeout_ms", 5000)
        
        # Suggest increasing timeout based on failure pattern
        suggested_timeouts = []
        
        if failure_duration >= current_timeout * 0.9:
            # Timeout was likely the issue
            suggested_timeouts = [
                current_timeout * 1.5,
                current_timeout * 2,
                min(current_timeout * 3, 30000)  # Cap at 30s
            ]
        else:
            # Other timing issue - more conservative increase
            suggested_timeouts = [
                current_timeout + 2000,
                current_timeout + 5000
            ]
        
        for i, timeout in enumerate(suggested_timeouts):
            confidence = 0.8 - (i * 0.1)  # Decreasing confidence
            patch = {
                "type": "wait_adjustment", 
                "original_timeout": current_timeout,
                "suggested_timeout": int(timeout),
                "confidence": confidence,
                "reason": "timeout_extension"
            }
            patches.append(patch)
        
        return patches