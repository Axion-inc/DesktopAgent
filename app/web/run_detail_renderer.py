"""
Run Detail Renderer - Show manifest and security info for executed templates
"""

from typing import Dict, Any


class RunDetailRenderer:
    """Renders run detail page with manifest information and Phase 7 features"""

    def render_manifest_section(self, run_data: Dict[str, Any]) -> str:
        """Render manifest information section for run detail page"""

        manifest = run_data.get("manifest", {})
        if not manifest:
            return "<p>No manifest information available</p>"

        html = f"""
<div class="manifest-section">
    <h3>🔒 Security Information</h3>

    <div class="signature-status">
        {"✅ Signature Verified" if manifest.get("signature_verified") else "⚠️ No Signature"}
    </div>

    <div class="capabilities-used">
        <h4>Required Capabilities</h4>
        <ul>
"""

        for capability in manifest.get("required_capabilities", []):
            html += f"            <li>{capability}</li>\n"

        html += """        </ul>
    </div>

    <div class="risk-flags-detected">
        <h4>Risk Flags</h4>
        <ul>
"""

        for risk_flag in manifest.get("risk_flags", []):
            html += f"            <li class='risk-flag-{risk_flag}'>{risk_flag}</li>\n"

        html += """        </ul>
    </div>
</div>
"""

        return html

    def render_l4_autopilot_section(self, run_data: Dict[str, Any]) -> str:
        """Render L4 Autopilot status section for Phase 7"""

        autopilot_data = run_data.get("autopilot", {})
        policy_data = run_data.get("policy_check", {})

        if not autopilot_data and not policy_data:
            return ""

        # L4 Autopilot status badge
        autopilot_enabled = autopilot_data.get("enabled", False)
        autopilot_status = autopilot_data.get("status", "manual")
        deviation_count = autopilot_data.get("deviation_count", 0)

        status_badge_class = {
            "active": "badge-success",
            "monitoring": "badge-warning",
            "deviation": "badge-error",
            "manual": "badge-secondary"
        }.get(autopilot_status, "badge-secondary")

        html = f"""
<div class="l4-autopilot-section">
    <h3>🤖 L4 Autopilot Status</h3>

    <div class="autopilot-status">
        <span class="badge {status_badge_class}">
            {"🟢" if autopilot_enabled else "⚫"} {autopilot_status.title()}
        </span>

        <div class="deviation-counter">
            <span class="deviation-count">{deviation_count}</span>
            <span class="deviation-label">Deviations</span>
        </div>
    </div>

    <div class="policy-compliance">
        <h4>Policy Compliance</h4>
        <div class="policy-checks">
"""

        # Policy check results
        policy_checks = policy_data.get("checks", {})
        for check_name, check_result in policy_checks.items():
            status_icon = "✅" if check_result.get("passed", False) else "❌"
            html += f"""            <div class="policy-check">
                <span class="check-icon">{status_icon}</span>
                <span class="check-name">{check_name.replace('_', ' ').title()}</span>
                <span class="check-detail">{check_result.get("message", "")}</span>
            </div>
"""

        html += """        </div>
    </div>
</div>
"""

        return html

    def render_differential_patches_section(self, run_data: Dict[str, Any]) -> str:
        """Render Planner L2 differential patches section for Phase 7"""

        patches = run_data.get("applied_patches", [])
        if not patches:
            return ""

        html = """
<div class="differential-patches-section">
    <h3>🔧 Applied Patches</h3>

    <div class="patches-list">
"""

        for patch in patches:
            patch_type = patch.get("type", "unknown")
            confidence = patch.get("confidence", 0.0)
            applied_at = patch.get("applied_at", "")

            # Format patch type for display
            patch_display = {
                "replace_text": "Text Replacement",
                "fallback_search": "Fallback Search",
                "wait_tuning": "Timeout Adjustment",
                "add_step": "Step Addition"
            }.get(patch_type, patch_type.title())

            confidence_class = "high" if confidence >= 0.85 else "medium" if confidence >= 0.7 else "low"

            html += f"""        <div class="patch-item">
            <div class="patch-header">
                <span class="patch-type">{patch_display}</span>
                <span class="patch-confidence confidence-{confidence_class}">
                    {confidence:.2f}
                </span>
            </div>
            <div class="patch-details">
                <small>Applied: {applied_at}</small>
            </div>
        </div>
"""

        html += """    </div>
</div>
"""

        return html

    def render_webx_enhancements_section(self, run_data: Dict[str, Any]) -> str:
        """Render WebX enhancements usage section for Phase 7"""

        webx_data = run_data.get("webx_usage", {})
        if not webx_data:
            return ""

        html = """
<div class="webx-enhancements-section">
    <h3>🌐 WebX Enhancements</h3>

    <div class="webx-stats">
"""

        # Frame switches
        frame_switches = webx_data.get("frame_switches", 0)
        if frame_switches > 0:
            html += f"""        <div class="webx-stat">
            <span class="stat-icon">🖼️</span>
            <span class="stat-value">{frame_switches}</span>
            <span class="stat-label">Frame Switches</span>
        </div>
"""

        # Shadow DOM hits
        shadow_hits = webx_data.get("shadow_hits", 0)
        if shadow_hits > 0:
            html += f"""        <div class="webx-stat">
            <span class="stat-icon">👁️‍🗨️</span>
            <span class="stat-value">{shadow_hits}</span>
            <span class="stat-label">Shadow DOM</span>
        </div>
"""

        # Downloads
        downloads = webx_data.get("downloads_verified", 0)
        if downloads > 0:
            html += f"""        <div class="webx-stat">
            <span class="stat-icon">⬇️</span>
            <span class="stat-value">{downloads}</span>
            <span class="stat-label">Downloads</span>
        </div>
"""

        # Cookie transfers
        cookie_transfers = webx_data.get("cookie_transfers", 0)
        if cookie_transfers > 0:
            html += f"""        <div class="webx-stat">
            <span class="stat-icon">🍪</span>
            <span class="stat-value">{cookie_transfers}</span>
            <span class="stat-label">Cookie Transfers</span>
        </div>
"""

        html += """    </div>
</div>
"""

        return html

    def render_deviation_details_section(self, run_data: Dict[str, Any]) -> str:
        """Render deviation details section for L4 autopilot deviations"""

        deviations = run_data.get("deviations", [])
        if not deviations:
            return ""

        html = """
<div class="deviation-details-section">
    <h3>⚠️ Deviation Details</h3>

    <div class="deviations-list">
"""

        for deviation in deviations:
            deviation_type = deviation.get("type", "unknown")
            step_number = deviation.get("step", 0)
            reason = deviation.get("reason", "")
            severity = deviation.get("severity", "medium")

            severity_class = f"deviation-{severity}"
            severity_icon = {
                "low": "🟡",
                "medium": "🟠",
                "high": "🔴",
                "critical": "🚨"
            }.get(severity, "⚠️")

            html += f"""        <div class="deviation-item {severity_class}">
            <div class="deviation-header">
                <span class="deviation-icon">{severity_icon}</span>
                <span class="deviation-type">{deviation_type.replace('_', ' ').title()}</span>
                <span class="deviation-step">Step {step_number}</span>
            </div>
            <div class="deviation-reason">
                {reason}
            </div>
        </div>
"""

        html += """    </div>
</div>
"""

        return html

    def render_complete_run_detail(self, run_data: Dict[str, Any]) -> str:
        """Render complete run detail page with all Phase 7 sections"""

        sections = [
            self.render_manifest_section(run_data),
            self.render_l4_autopilot_section(run_data),
            self.render_differential_patches_section(run_data),
            self.render_webx_enhancements_section(run_data),
            self.render_deviation_details_section(run_data)
        ]

        # Filter out empty sections
        active_sections = [section for section in sections if section.strip()]

        if not active_sections:
            return "<div class='run-detail-empty'>No additional details available</div>"

        html = f"""
<div class="run-detail-container">
    <style>
        .manifest-section, .l4-autopilot-section, .differential-patches-section,
        .webx-enhancements-section, .deviation-details-section {{
            margin-bottom: 2rem;
            padding: 1rem;
            border: 1px solid #e1e5e9;
            border-radius: 6px;
            background: #f8f9fa;
        }}

        .badge {{
            padding: 0.25em 0.5em;
            font-size: 0.875em;
            border-radius: 3px;
            font-weight: 600;
        }}

        .badge-success {{ background: #d4edda; color: #155724; }}
        .badge-warning {{ background: #fff3cd; color: #856404; }}
        .badge-error {{ background: #f8d7da; color: #721c24; }}
        .badge-secondary {{ background: #e2e3e5; color: #383d41; }}

        .autopilot-status {{
            display: flex;
            align-items: center;
            gap: 1rem;
            margin-bottom: 1rem;
        }}

        .deviation-counter {{
            display: flex;
            flex-direction: column;
            align-items: center;
        }}

        .deviation-count {{
            font-size: 1.5rem;
            font-weight: bold;
            color: #dc3545;
        }}

        .policy-check {{
            display: flex;
            align-items: center;
            gap: 0.5rem;
            margin-bottom: 0.5rem;
        }}

        .patch-item {{
            padding: 0.75rem;
            margin-bottom: 0.5rem;
            background: white;
            border-radius: 4px;
            border: 1px solid #dee2e6;
        }}

        .patch-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}

        .confidence-high {{ color: #28a745; }}
        .confidence-medium {{ color: #ffc107; }}
        .confidence-low {{ color: #dc3545; }}

        .webx-stats {{
            display: flex;
            flex-wrap: wrap;
            gap: 1rem;
        }}

        .webx-stat {{
            display: flex;
            flex-direction: column;
            align-items: center;
            padding: 1rem;
            background: white;
            border-radius: 4px;
            min-width: 80px;
        }}

        .stat-value {{
            font-size: 1.25rem;
            font-weight: bold;
            color: #007bff;
        }}

        .deviation-item {{
            padding: 0.75rem;
            margin-bottom: 0.5rem;
            background: white;
            border-radius: 4px;
            border-left: 4px solid #ffc107;
        }}

        .deviation-high {{ border-left-color: #dc3545; }}
        .deviation-critical {{ border-left-color: #6f42c1; }}

        .deviation-header {{
            display: flex;
            align-items: center;
            gap: 0.5rem;
            margin-bottom: 0.5rem;
            font-weight: 600;
        }}

        .risk-flag-sends {{ color: #dc3545; }}
        .risk-flag-deletes {{ color: #6f42c1; }}
        .risk-flag-overwrites {{ color: #fd7e14; }}
    </style>

    {"".join(active_sections)}
</div>
"""

        return html
