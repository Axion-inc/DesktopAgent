"""
Capability Analysis for Review Screen
Analyzes templates and provides risk/capability highlighting for review
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from pathlib import Path

from ..security.template_manifest import CapabilityAnalyzer as BaseAnalyzer, ManifestManager
from ..utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class CapabilityInfo:
    name: str
    description: str
    risk_level: str  # "low", "medium", "high"
    icon: str


@dataclass 
class RiskInfo:
    flag: str
    description: str
    severity: str  # "low", "medium", "high", "critical"
    icon: str
    requires_approval: bool


class CapabilityAnalyzer(BaseAnalyzer):
    """Extended capability analyzer for review screen"""
    
    CAPABILITY_INFO = {
        "webx": CapabilityInfo(
            name="Web拡張機能",
            description="ブラウザ操作、フォーム入力、クリック操作",
            risk_level="medium",
            icon="🌐"
        ),
        "fs": CapabilityInfo(
            name="ファイルシステム",
            description="ファイルの読み書き、添付ファイル操作",
            risk_level="medium", 
            icon="📁"
        ),
        "pdf": CapabilityInfo(
            name="PDF操作",
            description="PDFファイルの読み取り、処理",
            risk_level="low",
            icon="📄"
        ),
        "mail_draft": CapabilityInfo(
            name="メール作成",
            description="メールの下書き作成、送信",
            risk_level="high",
            icon="📧"
        ),
        "system": CapabilityInfo(
            name="システム操作",
            description="コマンド実行、環境変数アクセス",
            risk_level="high",
            icon="⚙️"
        )
    }
    
    RISK_INFO = {
        "sends": RiskInfo(
            flag="sends",
            description="外部へのデータ送信",
            severity="critical",
            icon="📤",
            requires_approval=True
        ),
        "deletes": RiskInfo(
            flag="deletes", 
            description="ファイル・データの削除",
            severity="high",
            icon="🗑️",
            requires_approval=True
        ),
        "overwrites": RiskInfo(
            flag="overwrites",
            description="ファイル・データの上書き",
            severity="high", 
            icon="✏️",
            requires_approval=True
        )
    }
    
    def get_capability_info(self, capability: str) -> Optional[CapabilityInfo]:
        """Get detailed capability information"""
        return self.CAPABILITY_INFO.get(capability)
    
    def get_risk_info(self, risk_flag: str) -> Optional[RiskInfo]:
        """Get detailed risk information"""
        return self.RISK_INFO.get(risk_flag)
    
    def analyze_template_for_review(self, template_content: str) -> Dict[str, Any]:
        """Comprehensive template analysis for review screen"""
        capabilities = self.detect_capabilities(template_content)
        risk_flags = self.detect_risk_flags(template_content)
        webx_urls = self.extract_webx_urls(template_content)
        
        # Get detailed info for each capability
        capability_details = []
        max_capability_risk = "low"
        
        for capability in capabilities:
            info = self.get_capability_info(capability)
            if info:
                capability_details.append({
                    "name": capability,
                    "display_name": info.name,
                    "description": info.description,
                    "risk_level": info.risk_level,
                    "icon": info.icon
                })
                
                # Track highest risk level
                if info.risk_level == "high":
                    max_capability_risk = "high"
                elif info.risk_level == "medium" and max_capability_risk != "high":
                    max_capability_risk = "medium"
        
        # Get detailed info for each risk flag
        risk_details = []
        requires_approval = False
        max_risk_severity = "low"
        
        for risk_flag in risk_flags:
            info = self.get_risk_info(risk_flag)
            if info:
                risk_details.append({
                    "flag": risk_flag,
                    "description": info.description,
                    "severity": info.severity,
                    "icon": info.icon,
                    "requires_approval": info.requires_approval
                })
                
                if info.requires_approval:
                    requires_approval = True
                
                # Track highest severity
                severity_order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
                if severity_order.get(info.severity, 0) > severity_order.get(max_risk_severity, 0):
                    max_risk_severity = info.severity
        
        # Overall assessment
        overall_risk = "low"
        if max_risk_severity in ["critical", "high"]:
            overall_risk = "high"
        elif max_risk_severity == "medium" or max_capability_risk == "high":
            overall_risk = "medium"
        elif max_capability_risk == "medium":
            overall_risk = "medium"
        
        return {
            "capabilities": capabilities,
            "capability_details": capability_details,
            "risk_flags": risk_flags,
            "risk_details": risk_details,
            "webx_urls": webx_urls,
            "overall_risk": overall_risk,
            "max_capability_risk": max_capability_risk,
            "max_risk_severity": max_risk_severity,
            "requires_approval": requires_approval
        }