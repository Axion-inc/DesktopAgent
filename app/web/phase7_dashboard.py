"""
Phase 7 Dashboard - Enhanced UI for L4 Autopilot + Policy Engine + Planner L2
"""

from typing import Dict, Any, List
from datetime import datetime, timedelta
import json


class Phase7Dashboard:
    """Phase 7 enhanced dashboard with L4 Autopilot, Policy Engine, and Planner L2 features"""
    
    def __init__(self):
        self.metrics_data = {}
        
    def render_l4_autopilot_widget(self, metrics: Dict[str, Any]) -> str:
        """Render L4 Autopilot status widget"""
        
        l4_autoruns = metrics.get("l4_autoruns_24h", 0)
        policy_blocks = metrics.get("policy_blocks_24h", 0)
        deviation_stops = metrics.get("deviation_stops_24h", 0)
        
        # Calculate autopilot health score
        total_attempts = l4_autoruns + policy_blocks + deviation_stops
        health_score = (l4_autoruns / max(total_attempts, 1)) * 100 if total_attempts > 0 else 100
        
        health_class = "excellent" if health_score >= 90 else "good" if health_score >= 70 else "warning" if health_score >= 50 else "critical"
        
        html = f"""
<div class="l4-autopilot-widget">
    <div class="widget-header">
        <h3>🤖 L4 Autopilot</h3>
        <div class="health-score {health_class}">
            {health_score:.0f}%
        </div>
    </div>
    
    <div class="widget-content">
        <div class="stat-row">
            <div class="stat-item success">
                <div class="stat-value">{l4_autoruns}</div>
                <div class="stat-label">Auto Executions</div>
            </div>
            
            <div class="stat-item blocked">
                <div class="stat-value">{policy_blocks}</div>
                <div class="stat-label">Policy Blocks</div>
            </div>
            
            <div class="stat-item deviation">
                <div class="stat-value">{deviation_stops}</div>
                <div class="stat-label">Deviations</div>
            </div>
        </div>
        
        <div class="autopilot-status">
            <div class="status-indicator {'active' if l4_autoruns > 0 else 'inactive'}"></div>
            <span class="status-text">
                {'L4 Active' if l4_autoruns > 0 else 'Manual Mode'}
            </span>
        </div>
    </div>
</div>
"""
        return html
    
    def render_policy_engine_widget(self, metrics: Dict[str, Any]) -> str:
        """Render Policy Engine v1 status widget"""
        
        templates_verified = metrics.get("templates_verified_24h", 0)
        unsigned_blocked = metrics.get("unsigned_blocked_24h", 0)
        trust_keys_active = metrics.get("trust_keys_active", 0)
        
        verification_rate = (templates_verified / max(templates_verified + unsigned_blocked, 1)) * 100
        
        html = f"""
<div class="policy-engine-widget">
    <div class="widget-header">
        <h3>🔒 Policy Engine v1</h3>
        <div class="verification-rate">
            {verification_rate:.0f}% Verified
        </div>
    </div>
    
    <div class="widget-content">
        <div class="stat-row">
            <div class="stat-item verified">
                <div class="stat-value">{templates_verified}</div>
                <div class="stat-label">Verified</div>
            </div>
            
            <div class="stat-item blocked">
                <div class="stat-value">{unsigned_blocked}</div>
                <div class="stat-label">Blocked</div>
            </div>
            
            <div class="stat-item keys">
                <div class="stat-value">{trust_keys_active}</div>
                <div class="stat-label">Trust Keys</div>
            </div>
        </div>
        
        <div class="policy-status">
            <div class="enforcement-level">
                <span class="level-indicator high"></span>
                <span class="level-text">Strict Enforcement</span>
            </div>
        </div>
    </div>
</div>
"""
        return html
    
    def render_planner_l2_widget(self, metrics: Dict[str, Any]) -> str:
        """Render Planner L2 differential patches widget"""
        
        # These would be tracked by the metrics system
        patches_proposed = metrics.get("patches_proposed_24h", 0)
        patches_applied = metrics.get("patches_applied_24h", 0) 
        patches_auto_adopted = metrics.get("patches_auto_adopted_24h", 0)
        
        adoption_rate = (patches_auto_adopted / max(patches_proposed, 1)) * 100 if patches_proposed > 0 else 0
        
        html = f"""
<div class="planner-l2-widget">
    <div class="widget-header">
        <h3>🔧 Planner L2</h3>
        <div class="adoption-rate">
            {adoption_rate:.0f}% Auto-Adopted
        </div>
    </div>
    
    <div class="widget-content">
        <div class="stat-row">
            <div class="stat-item proposed">
                <div class="stat-value">{patches_proposed}</div>
                <div class="stat-label">Proposed</div>
            </div>
            
            <div class="stat-item applied">
                <div class="stat-value">{patches_applied}</div>
                <div class="stat-label">Applied</div>
            </div>
            
            <div class="stat-item auto">
                <div class="stat-value">{patches_auto_adopted}</div>
                <div class="stat-label">Auto-Adopted</div>
            </div>
        </div>
        
        <div class="patch-types">
            <div class="patch-type-indicator">
                <span class="type-dot text"></span>
                <span class="type-label">Text Replacements</span>
            </div>
            <div class="patch-type-indicator">
                <span class="type-dot wait"></span>
                <span class="type-label">Timeout Adjustments</span>
            </div>
        </div>
    </div>
</div>
"""
        return html
    
    def render_webx_enhancements_widget(self, metrics: Dict[str, Any]) -> str:
        """Render WebX enhancements usage widget"""
        
        frame_switches = metrics.get("webx_frame_switches_24h", 0)
        shadow_hits = metrics.get("webx_shadow_hits_24h", 0)
        webx_steps = metrics.get("webx_steps_24h", 0)
        webx_failures = metrics.get("webx_failures_24h", 0)
        
        webx_success_rate = ((webx_steps - webx_failures) / max(webx_steps, 1)) * 100 if webx_steps > 0 else 100
        
        html = f"""
<div class="webx-enhancements-widget">
    <div class="widget-header">
        <h3>🌐 WebX Enhancements</h3>
        <div class="success-rate">
            {webx_success_rate:.1f}% Success
        </div>
    </div>
    
    <div class="widget-content">
        <div class="stat-row">
            <div class="stat-item frames">
                <div class="stat-icon">🖼️</div>
                <div class="stat-value">{frame_switches}</div>
                <div class="stat-label">Frames</div>
            </div>
            
            <div class="stat-item shadow">
                <div class="stat-icon">👁️‍🗨️</div>
                <div class="stat-value">{shadow_hits}</div>
                <div class="stat-label">Shadow DOM</div>
            </div>
            
            <div class="stat-item total">
                <div class="stat-icon">⚡</div>
                <div class="stat-value">{webx_steps}</div>
                <div class="stat-label">Total Steps</div>
            </div>
        </div>
        
        <div class="enhancement-status">
            <div class="status-bar">
                <div class="status-fill" style="width: {webx_success_rate}%"></div>
            </div>
            <div class="status-details">
                {webx_steps - webx_failures} successful, {webx_failures} failed
            </div>
        </div>
    </div>
</div>
"""
        return html
    
    def render_github_integration_widget(self, metrics: Dict[str, Any]) -> str:
        """Render GitHub integration status widget"""
        
        l4_issues = metrics.get("github_l4_issues_24h", 0)
        policy_violations = metrics.get("github_policy_violations_24h", 0)
        patch_proposals = metrics.get("github_patch_proposals_24h", 0)
        workflow_runs = metrics.get("github_workflow_runs_24h", 0)
        
        html = f"""
<div class="github-integration-widget">
    <div class="widget-header">
        <h3>📋 GitHub Integration</h3>
        <div class="workflow-count">
            {workflow_runs} Workflows
        </div>
    </div>
    
    <div class="widget-content">
        <div class="stat-row">
            <div class="stat-item issues">
                <div class="stat-icon">🤖</div>
                <div class="stat-value">{l4_issues}</div>
                <div class="stat-label">L4 Issues</div>
            </div>
            
            <div class="stat-item violations">
                <div class="stat-icon">🔒</div>
                <div class="stat-value">{policy_violations}</div>
                <div class="stat-label">Violations</div>
            </div>
            
            <div class="stat-item prs">
                <div class="stat-icon">🔧</div>
                <div class="stat-value">{patch_proposals}</div>
                <div class="stat-label">Patches</div>
            </div>
        </div>
    </div>
</div>
"""
        return html
    
    def render_phase7_metrics_overview(self, metrics: Dict[str, Any]) -> str:
        """Render Phase 7 metrics overview section"""
        
        # Core Phase 7 metrics
        l4_autoruns = metrics.get("l4_autoruns_24h", 0)
        policy_blocks = metrics.get("policy_blocks_24h", 0)
        deviation_stops = metrics.get("deviation_stops_24h", 0)
        verifier_pass_rate = metrics.get("verifier_pass_rate_24h", 0.0)
        webx_frame_switches = metrics.get("webx_frame_switches_24h", 0)
        webx_shadow_hits = metrics.get("webx_shadow_hits_24h", 0)
        
        html = f"""
<div class="phase7-metrics-overview">
    <h2>📊 Phase 7 Metrics (24h)</h2>
    
    <div class="metrics-grid">
        <div class="metric-card primary">
            <div class="metric-value">{l4_autoruns}</div>
            <div class="metric-label">L4 Auto Runs</div>
            <div class="metric-description">Limited Full Automation executions</div>
        </div>
        
        <div class="metric-card warning">
            <div class="metric-value">{policy_blocks}</div>
            <div class="metric-label">Policy Blocks</div>
            <div class="metric-description">Policy Engine v1 violations</div>
        </div>
        
        <div class="metric-card danger">
            <div class="metric-value">{deviation_stops}</div>
            <div class="metric-label">Deviation Stops</div>
            <div class="metric-description">Safe-fail autopilot triggers</div>
        </div>
        
        <div class="metric-card success">
            <div class="metric-value">{verifier_pass_rate:.1%}</div>
            <div class="metric-label">Verifier Pass Rate</div>
            <div class="metric-description">Verification success rate</div>
        </div>
        
        <div class="metric-card info">
            <div class="metric-value">{webx_frame_switches}</div>
            <div class="metric-label">Frame Switches</div>
            <div class="metric-description">WebX iframe navigation</div>
        </div>
        
        <div class="metric-card secondary">
            <div class="metric-value">{webx_shadow_hits}</div>
            <div class="metric-label">Shadow DOM Hits</div>
            <div class="metric-description">Shadow DOM piercing operations</div>
        </div>
    </div>
</div>
"""
        return html
    
    def render_recent_deviations_table(self, recent_deviations: List[Dict[str, Any]]) -> str:
        """Render table of recent L4 autopilot deviations"""
        
        if not recent_deviations:
            return """
<div class="no-deviations">
    <p>✅ No recent L4 autopilot deviations</p>
</div>
"""
        
        html = """
<div class="recent-deviations-table">
    <h3>⚠️ Recent L4 Deviations</h3>
    
    <table class="deviations-table">
        <thead>
            <tr>
                <th>Time</th>
                <th>Template</th>
                <th>Type</th>
                <th>Reason</th>
                <th>Action</th>
            </tr>
        </thead>
        <tbody>
"""
        
        for deviation in recent_deviations[:10]:  # Show last 10
            execution_id = deviation.get("execution_id", "")[:8]
            template_name = deviation.get("template_name", "Unknown")
            deviation_type = deviation.get("type", "unknown")
            reason = deviation.get("reason", "")
            occurred_at = deviation.get("occurred_at", "")
            github_issue = deviation.get("github_issue", "")
            
            html += f"""            <tr>
                <td>{occurred_at}</td>
                <td>{template_name}</td>
                <td><span class="deviation-type-tag">{deviation_type}</span></td>
                <td>{reason[:50]}{'...' if len(reason) > 50 else ''}</td>
                <td>
                    {f'<a href="{github_issue}" target="_blank">GitHub Issue</a>' if github_issue else 'Manual Review'}
                </td>
            </tr>
"""
        
        html += """        </tbody>
    </table>
</div>
"""
        return html
    
    def render_complete_phase7_dashboard(self, metrics: Dict[str, Any], recent_deviations: List[Dict[str, Any]] = None) -> str:
        """Render complete Phase 7 dashboard with all widgets and sections"""
        
        recent_deviations = recent_deviations or []
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Desktop Agent - Phase 7 Dashboard</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            margin: 0;
            padding: 20px;
            background: #f8f9fa;
        }}
        
        .dashboard-header {{
            text-align: center;
            margin-bottom: 2rem;
        }}
        
        .phase-badge {{
            display: inline-block;
            padding: 0.5rem 1rem;
            background: linear-gradient(45deg, #007bff, #6f42c1);
            color: white;
            border-radius: 20px;
            font-weight: 600;
            margin-bottom: 1rem;
        }}
        
        .widgets-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 1.5rem;
            margin-bottom: 2rem;
        }}
        
        .widget-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1rem;
        }}
        
        .widget-header h3 {{
            margin: 0;
            color: #333;
        }}
        
        .l4-autopilot-widget, .policy-engine-widget, .planner-l2-widget, 
        .webx-enhancements-widget, .github-integration-widget {{
            background: white;
            padding: 1.5rem;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            border: 1px solid #e1e5e9;
        }}
        
        .health-score {{
            font-size: 1.25rem;
            font-weight: bold;
            padding: 0.25rem 0.5rem;
            border-radius: 4px;
        }}
        
        .health-score.excellent {{ background: #d4edda; color: #155724; }}
        .health-score.good {{ background: #d1ecf1; color: #0c5460; }}
        .health-score.warning {{ background: #fff3cd; color: #856404; }}
        .health-score.critical {{ background: #f8d7da; color: #721c24; }}
        
        .stat-row {{
            display: flex;
            justify-content: space-between;
            margin-bottom: 1rem;
        }}
        
        .stat-item {{
            text-align: center;
            flex: 1;
            margin: 0 0.5rem;
        }}
        
        .stat-value {{
            font-size: 1.5rem;
            font-weight: bold;
            margin-bottom: 0.25rem;
        }}
        
        .stat-item.success .stat-value {{ color: #28a745; }}
        .stat-item.blocked .stat-value {{ color: #dc3545; }}
        .stat-item.deviation .stat-value {{ color: #ffc107; }}
        .stat-item.verified .stat-value {{ color: #17a2b8; }}
        
        .status-indicator {{
            width: 12px;
            height: 12px;
            border-radius: 50%;
            display: inline-block;
            margin-right: 0.5rem;
        }}
        
        .status-indicator.active {{ background: #28a745; }}
        .status-indicator.inactive {{ background: #6c757d; }}
        
        .level-indicator {{
            width: 8px;
            height: 8px;
            border-radius: 50%;
            display: inline-block;
            margin-right: 0.5rem;
        }}
        
        .level-indicator.high {{ background: #dc3545; }}
        
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
            margin: 1.5rem 0;
        }}
        
        .metric-card {{
            background: white;
            padding: 1rem;
            border-radius: 6px;
            text-align: center;
            border-left: 4px solid;
        }}
        
        .metric-card.primary {{ border-left-color: #007bff; }}
        .metric-card.warning {{ border-left-color: #ffc107; }}
        .metric-card.danger {{ border-left-color: #dc3545; }}
        .metric-card.success {{ border-left-color: #28a745; }}
        .metric-card.info {{ border-left-color: #17a2b8; }}
        .metric-card.secondary {{ border-left-color: #6c757d; }}
        
        .metric-value {{
            font-size: 2rem;
            font-weight: bold;
            color: #333;
        }}
        
        .metric-label {{
            font-weight: 600;
            margin: 0.5rem 0 0.25rem;
            color: #555;
        }}
        
        .metric-description {{
            font-size: 0.875rem;
            color: #777;
        }}
        
        .deviations-table {{
            width: 100%;
            border-collapse: collapse;
            background: white;
            border-radius: 6px;
            overflow: hidden;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        
        .deviations-table th {{
            background: #f8f9fa;
            padding: 1rem;
            text-align: left;
            font-weight: 600;
            border-bottom: 2px solid #dee2e6;
        }}
        
        .deviations-table td {{
            padding: 0.75rem 1rem;
            border-bottom: 1px solid #dee2e6;
        }}
        
        .deviation-type-tag {{
            background: #fff3cd;
            color: #856404;
            padding: 0.25rem 0.5rem;
            border-radius: 3px;
            font-size: 0.75rem;
            font-weight: 600;
        }}
        
        .status-bar {{
            background: #e9ecef;
            height: 8px;
            border-radius: 4px;
            overflow: hidden;
            margin-bottom: 0.5rem;
        }}
        
        .status-fill {{
            background: linear-gradient(90deg, #28a745, #20c997);
            height: 100%;
            transition: width 0.3s ease;
        }}
        
        .patch-type-indicator {{
            display: flex;
            align-items: center;
            margin-bottom: 0.25rem;
        }}
        
        .type-dot {{
            width: 8px;
            height: 8px;
            border-radius: 50%;
            margin-right: 0.5rem;
        }}
        
        .type-dot.text {{ background: #007bff; }}
        .type-dot.wait {{ background: #ffc107; }}
        
        .no-deviations {{
            background: white;
            padding: 2rem;
            text-align: center;
            border-radius: 6px;
            border: 1px solid #e1e5e9;
        }}
    </style>
</head>
<body>
    <div class="dashboard-header">
        <div class="phase-badge">Phase 7 — L4 Autopilot + Policy Engine v1 + Planner L2</div>
        <h1>Desktop Agent Dashboard</h1>
        <p>Enhanced automation with differential adaptation and advanced web capabilities</p>
    </div>
    
    <div class="widgets-grid">
        {self.render_l4_autopilot_widget(metrics)}
        {self.render_policy_engine_widget(metrics)}
        {self.render_planner_l2_widget(metrics)}
        {self.render_webx_enhancements_widget(metrics)}
        {self.render_github_integration_widget(metrics)}
    </div>
    
    {self.render_phase7_metrics_overview(metrics)}
    
    {self.render_recent_deviations_table(recent_deviations)}
    
    <div style="text-align: center; margin-top: 2rem; color: #6c757d;">
        <small>Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</small>
    </div>
</body>
</html>
"""
        return html