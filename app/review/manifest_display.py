"""
Manifest Display Components for Review Screen
Renders capability and risk information in review UI
"""

from typing import Dict, Any, List
from ..review.capability_analyzer import CapabilityAnalyzer


class ReviewManifestDisplay:
    """Handles manifest information display in review screens"""
    
    def __init__(self):
        self.analyzer = CapabilityAnalyzer()
    
    def render_capability_warnings(self, manifest: Dict[str, Any]) -> str:
        """Render capability warnings HTML for review screen"""
        capabilities = manifest.get("required_capabilities", [])
        risk_flags = manifest.get("risk_flags", [])
        
        html_parts = []
        
        # Capabilities section
        if capabilities:
            html_parts.append('<div class="capabilities-section">')
            html_parts.append('<h3>🔧 必要な機能・権限</h3>')
            html_parts.append('<div class="capabilities-grid">')
            
            for capability in capabilities:
                info = self.analyzer.get_capability_info(capability)
                if info:
                    risk_class = f"capability-{info.risk_level}"
                    html_parts.append(f'''
                    <div class="capability-card {risk_class}">
                        <div class="capability-icon">{info.icon}</div>
                        <div class="capability-name">{info.name}</div>
                        <div class="capability-desc">{info.description}</div>
                        <div class="capability-risk">リスク: {info.risk_level.upper()}</div>
                    </div>
                    ''')
            
            html_parts.append('</div>')
            html_parts.append('</div>')
        
        # Risk flags section  
        if risk_flags:
            html_parts.append('<div class="risk-flags-section">')
            html_parts.append('<h3>⚠️ リスク分析</h3>')
            html_parts.append('<div class="risk-flags-list">')
            
            for risk_flag in risk_flags:
                info = self.analyzer.get_risk_info(risk_flag)
                if info:
                    severity_class = f"risk-{info.severity}"
                    approval_badge = "🔒 承認必須" if info.requires_approval else ""
                    
                    html_parts.append(f'''
                    <div class="risk-flag-item {severity_class}">
                        <div class="risk-icon">{info.icon}</div>
                        <div class="risk-content">
                            <div class="risk-title">{info.flag.upper()}: {info.description}</div>
                            <div class="risk-severity">深刻度: {info.severity.upper()}</div>
                            {f'<div class="approval-required">{approval_badge}</div>' if approval_badge else ''}
                        </div>
                    </div>
                    ''')
            
            html_parts.append('</div>')
            html_parts.append('</div>')
        
        return '\\n'.join(html_parts)
    
    def render_template_analysis_summary(self, analysis: Dict[str, Any]) -> str:
        """Render template analysis summary for review"""
        overall_risk = analysis.get("overall_risk", "low")
        requires_approval = analysis.get("requires_approval", False)
        
        risk_colors = {
            "low": "#28a745",
            "medium": "#ffc107", 
            "high": "#dc3545"
        }
        
        risk_icons = {
            "low": "✅",
            "medium": "⚠️",
            "high": "🚨"
        }
        
        color = risk_colors.get(overall_risk, "#6c757d")
        icon = risk_icons.get(overall_risk, "❓")
        
        html = f'''
        <div class="analysis-summary" style="border-left: 4px solid {color}; padding: 1rem; background: #f8f9fa; margin-bottom: 1rem;">
            <div class="summary-header">
                <span class="risk-icon" style="font-size: 1.5rem;">{icon}</span>
                <span class="risk-level" style="font-weight: 700; color: {color};">
                    {overall_risk.upper()} リスクテンプレート
                </span>
            </div>
            <div class="summary-details" style="margin-top: 0.5rem;">
                <div>機能要求: {len(analysis.get("capabilities", []))} 項目</div>
                <div>リスクフラグ: {len(analysis.get("risk_flags", []))} 項目</div>
                {f'<div style="color: #dc3545; font-weight: 600;">🔒 管理者承認が必要です</div>' if requires_approval else ''}
            </div>
        </div>
        '''
        
        return html
    
    def generate_review_css(self) -> str:
        """Generate CSS for review display components"""
        return '''
        <style>
        .capabilities-section, .risk-flags-section {
            margin: 1.5rem 0;
            padding: 1rem;
            border: 1px solid #e9ecef;
            border-radius: 8px;
        }
        
        .capabilities-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 1rem;
            margin-top: 1rem;
        }
        
        .capability-card {
            padding: 1rem;
            border-radius: 8px;
            border: 2px solid;
            text-align: center;
        }
        
        .capability-low {
            border-color: #28a745;
            background-color: #d4edda;
        }
        
        .capability-medium {
            border-color: #ffc107;
            background-color: #fff3cd;
        }
        
        .capability-high {
            border-color: #dc3545;
            background-color: #f8d7da;
        }
        
        .capability-icon {
            font-size: 2rem;
            margin-bottom: 0.5rem;
        }
        
        .capability-name {
            font-weight: 700;
            margin-bottom: 0.5rem;
        }
        
        .capability-desc {
            font-size: 0.875rem;
            color: #6c757d;
            margin-bottom: 0.5rem;
        }
        
        .capability-risk {
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
        }
        
        .risk-flags-list {
            margin-top: 1rem;
        }
        
        .risk-flag-item {
            display: flex;
            align-items: center;
            padding: 1rem;
            margin-bottom: 0.5rem;
            border-radius: 8px;
            border-left: 4px solid;
        }
        
        .risk-low {
            border-left-color: #28a745;
            background-color: #d4edda;
        }
        
        .risk-medium {
            border-left-color: #ffc107;
            background-color: #fff3cd;
        }
        
        .risk-high {
            border-left-color: #fd7e14;
            background-color: #ffe5cc;
        }
        
        .risk-critical {
            border-left-color: #dc3545;
            background-color: #f8d7da;
        }
        
        .risk-icon {
            font-size: 1.5rem;
            margin-right: 1rem;
        }
        
        .risk-content {
            flex: 1;
        }
        
        .risk-title {
            font-weight: 700;
            margin-bottom: 0.25rem;
        }
        
        .risk-severity {
            font-size: 0.875rem;
            color: #6c757d;
            margin-bottom: 0.25rem;
        }
        
        .approval-required {
            background: #dc3545;
            color: white;
            padding: 0.25rem 0.5rem;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: 600;
            display: inline-block;
            margin-top: 0.5rem;
        }
        </style>
        '''