"""
Approval Gate Manager
Manages approval requirements for high-risk templates
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from ..utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ApprovalRequirement:
    reason: str
    severity: str
    auto_approvable: bool = False


class ApprovalGateManager:
    """Manages approval gate logic for template execution"""
    
    HIGH_RISK_FLAGS = ["sends", "deletes", "overwrites"]
    HIGH_RISK_CAPABILITIES = ["system"]
    
    def __init__(self):
        pass
    
    def requires_approval(self, manifest: Dict[str, Any]) -> bool:
        """Check if manifest requires manual approval"""
        risk_flags = manifest.get("risk_flags", [])
        capabilities = manifest.get("required_capabilities", [])
        
        # Check for high-risk flags
        for flag in risk_flags:
            if flag in self.HIGH_RISK_FLAGS:
                return True
        
        # Check for high-risk capabilities
        for capability in capabilities:
            if capability in self.HIGH_RISK_CAPABILITIES:
                return True
        
        return False
    
    def get_approval_requirements(self, manifest: Dict[str, Any]) -> List[ApprovalRequirement]:
        """Get list of approval requirements for a manifest"""
        requirements = []
        risk_flags = manifest.get("risk_flags", [])
        capabilities = manifest.get("required_capabilities", [])
        
        # Check risk flags
        if "sends" in risk_flags:
            requirements.append(ApprovalRequirement(
                reason="テンプレートが外部にデータを送信します",
                severity="critical"
            ))
        
        if "deletes" in risk_flags:
            requirements.append(ApprovalRequirement(
                reason="テンプレートがファイルやデータを削除します",
                severity="high"
            ))
        
        if "overwrites" in risk_flags:
            requirements.append(ApprovalRequirement(
                reason="テンプレートがファイルやデータを上書きします", 
                severity="high"
            ))
        
        # Check capabilities
        if "system" in capabilities:
            requirements.append(ApprovalRequirement(
                reason="テンプレートがシステムレベルの操作を実行します",
                severity="critical"
            ))
        
        return requirements
    
    def can_auto_approve(self, manifest: Dict[str, Any], user_role: str) -> bool:
        """Check if template can be auto-approved based on user role"""
        if not self.requires_approval(manifest):
            return True
        
        # Only admins can auto-approve high-risk templates
        if user_role == "admin":
            requirements = self.get_approval_requirements(manifest)
            # Check if all requirements are auto-approvable
            return all(req.auto_approvable for req in requirements)
        
        return False
    
    def create_approval_message(self, manifest: Dict[str, Any]) -> str:
        """Create approval message for review UI"""
        requirements = self.get_approval_requirements(manifest)
        
        if not requirements:
            return "このテンプレートは自動承認されました。"
        
        message_parts = ["このテンプレートは以下の理由で手動承認が必要です:", ""]
        
        for i, req in enumerate(requirements, 1):
            severity_icon = {
                "low": "ℹ️",
                "medium": "⚠️", 
                "high": "🔴",
                "critical": "🚨"
            }.get(req.severity, "❓")
            
            message_parts.append(f"{i}. {severity_icon} {req.reason}")
        
        message_parts.extend([
            "",
            "承認するには管理者権限が必要です。",
            "実行前にテンプレートの内容を十分に確認してください。"
        ])
        
        return "\\n".join(message_parts)


# Global approval gate manager
_approval_gate_manager: Optional[ApprovalGateManager] = None


def get_approval_gate_manager() -> ApprovalGateManager:
    """Get global approval gate manager instance"""
    global _approval_gate_manager
    if _approval_gate_manager is None:
        _approval_gate_manager = ApprovalGateManager()
    return _approval_gate_manager