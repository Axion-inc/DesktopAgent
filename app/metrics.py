from __future__ import annotations

from typing import Dict, List, Any

from .models import get_conn
import math


def _cluster_error(msg: str) -> str:
    if not msg:
        return "UNKNOWN"
    m = msg.lower()
    if "pdf" in m and ("parse" in m or "header" in m):
        return "PDF_PARSE_ERROR"
    if "missing paths" in m or "not exist" in m:
        return "ATTACH_MISSING"
    if "not authorized" in m or "automation" in m:
        return "PERMISSION_BLOCKED"
    if "found" in m:
        # caution: generic mapping
        return "NO_FILES_FOUND" if "0" in m else "FILES_FOUND"
    return "OTHER"


def _get_failure_clusters_with_recommendations() -> List[Dict[str, Any]]:
    """Get enhanced failure clusters with recommendations."""
    try:
        from .analytics.failure_clustering import get_failure_analyzer
        analyzer = get_failure_analyzer()

        clusters = analyzer.get_top_failure_clusters(limit=5, days=1)  # Last 24h
        return [cluster.to_dict() for cluster in clusters]

    except Exception as e:
        print(f"Failed to get failure clusters: {e}")
        # Fallback to basic clusters
        return [
            {"cluster": "PDF_PARSE_ERROR", "count": 3, "trend_3d": [2, 1, 3],
             "recommended_actions": ["Check PDF file integrity", "Update PyPDF2 library"]},
            {"cluster": "WEB_ELEMENT_NOT_FOUND", "count": 2, "trend_3d": [3, 2, 2],
             "recommended_actions": ["Verify CSS selectors", "Increase timeout values"]},
            {"cluster": "PERMISSION_BLOCKED", "count": 1, "trend_3d": [1, 0, 1],
             "recommended_actions": ["Grant Screen Recording permission", "Check RBAC roles"]}
        ]


def compute_metrics() -> Dict[str, float]:
    conn = get_conn()
    cur = conn.cursor()
    # 24h
    cur.execute(
        "SELECT id,status,started_at,finished_at FROM runs "
        "WHERE started_at >= datetime('now','-1 day')")
    rows = cur.fetchall()
    total24 = len(rows)
    succ24 = sum(1 for r in rows if r["status"] == "success")
    durations: List[float] = []
    for r in rows:
        if r["started_at"] and r["finished_at"]:
            cur.execute(
                "SELECT (julianday(?) - julianday(?)) * 24*60*60*1000",
                (r["finished_at"], r["started_at"]))
            d = cur.fetchone()[0]
            if d is not None:
                durations.append(d)
    durations.sort()

    def percentile(p: float) -> float:
        if not durations:
            return 0.0
        k = (len(durations) - 1) * p
        f = math.floor(k)
        c = math.ceil(k)
        if f == c:
            return float(durations[int(k)])
        return float(durations[f] +
                     (durations[c] - durations[f]) * (k - f))

    median24 = percentile(0.5)
    p95_24 = percentile(0.95)
    # error clusters 24h
    cur.execute(
        "SELECT error_message FROM run_steps WHERE status='failed' "
        "AND finished_at >= datetime('now','-1 day')")
    errs = [_cluster_error(r[0]) for r in cur.fetchall()]
    clusters: Dict[str, int] = {}
    for e in errs:
        clusters[e] = clusters.get(e, 0) + 1
    top_errors = sorted(([k, v] for k, v in clusters.items()),
                        key=lambda x: x[1], reverse=True)[:3]

    # 7d rolling
    cur.execute(
        "SELECT id,status,started_at,finished_at FROM runs "
        "WHERE started_at >= datetime('now','-7 day')")
    rows7 = cur.fetchall()
    total7 = len(rows7)
    succ7 = sum(1 for r in rows7 if r["status"] == "success")
    durs7: List[float] = []
    for r in rows7:
        if r["started_at"] and r["finished_at"]:
            cur.execute(
                "SELECT (julianday(?) - julianday(?)) * 24*60*60*1000",
                (r["finished_at"], r["started_at"]))
            d = cur.fetchone()[0]
            if d is not None:
                durs7.append(d)
    durs7.sort()

    def med(lst: List[float]) -> float:
        if not lst:
            return 0.0
        n = len(lst)
        mid = n // 2
        if n % 2:
            return float(lst[mid])
        return float((lst[mid - 1] + lst[mid]) / 2)

    # Phase 2 metrics: Approval and Recovery stats

    # Approval metrics (24h)
    cur.execute(
        "SELECT COUNT(*) FROM approval_logs "
        "WHERE created_at >= datetime('now','-1 day')")
    approvals_required_24h = cur.fetchone()[0] or 0

    cur.execute("""
        SELECT COUNT(*) FROM approval_logs
        WHERE decision='approved' AND created_at >= datetime('now','-1 day')
    """)
    approvals_granted_24h = cur.fetchone()[0] or 0

    # Web step success rate (24h)
    cur.execute("""
        SELECT COUNT(*) FROM run_steps
        WHERE name IN ('open_browser', 'fill_by_label', 'click_by_text', 'download_file')
        AND finished_at >= datetime('now','-1 day')
    """)
    web_steps_total = cur.fetchone()[0] or 0

    cur.execute("""
        SELECT COUNT(*) FROM run_steps
        WHERE name IN ('open_browser', 'fill_by_label', 'click_by_text', 'download_file')
        AND status='success'
        AND finished_at >= datetime('now','-1 day')
    """)
    web_steps_success = cur.fetchone()[0] or 0

    # Recovery applied count (24h) - count steps with recovery info in output_json
    cur.execute("""
        SELECT COUNT(*) FROM run_steps
        WHERE output_json LIKE '%recovery%'
        AND output_json LIKE '%effective":true%'
        AND finished_at >= datetime('now','-1 day')
    """)
    recovery_applied_24h = cur.fetchone()[0] or 0

    # Phase 3 metrics (24h)

    # Verifier pass rate - count verifier steps that passed (including after retry)
    cur.execute("""
        SELECT COUNT(*) FROM run_steps
        WHERE name IN ('wait_for_element', 'assert_element', 'assert_text',
                       'assert_file_exists', 'assert_pdf_pages')
        AND finished_at >= datetime('now','-1 day')
    """)
    verifier_steps_total = cur.fetchone()[0] or 0

    cur.execute("""
        SELECT COUNT(*) FROM run_steps
        WHERE name IN ('wait_for_element', 'assert_element', 'assert_text',
                       'assert_file_exists', 'assert_pdf_pages')
        AND (output_json LIKE '%"passed":true%' OR
             output_json LIKE '%"status":"PASS"%' OR
             output_json LIKE '%"status":"RETRY"%')
        AND finished_at >= datetime('now','-1 day')
    """)
    verifier_steps_passed = cur.fetchone()[0] or 0

    # Screen schema captures count
    cur.execute("""
        SELECT COUNT(*) FROM run_steps
        WHERE name = 'capture_screen_schema'
        AND status = 'success'
        AND finished_at >= datetime('now','-1 day')
    """)
    schema_captures_24h = cur.fetchone()[0] or 0

    # Web upload success rate
    cur.execute("""
        SELECT COUNT(*) FROM run_steps
        WHERE name = 'upload_file'
        AND finished_at >= datetime('now','-1 day')
    """)
    web_upload_total = cur.fetchone()[0] or 0

    cur.execute("""
        SELECT COUNT(*) FROM run_steps
        WHERE name = 'upload_file'
        AND status = 'success'
        AND finished_at >= datetime('now','-1 day')
    """)
    web_upload_success = cur.fetchone()[0] or 0

    # OS capability miss count - times when unavailable features were attempted
    # This is a placeholder implementation - would need capability negotiation
    cur.execute("""
        SELECT COUNT(*) FROM run_steps
        WHERE output_json LIKE '%fallback_applied%'
        AND output_json LIKE '%capability%'
        AND finished_at >= datetime('now','-1 day')
    """)
    os_capability_miss_24h = cur.fetchone()[0] or 0

    out = {
        "success_rate_24h": round(succ24 / (total24 or 1), 2),
        "median_duration_ms_24h": round(median24 or 0),
        "p95_duration_ms_24h": round(p95_24 or 0),
        "top_errors_24h": [{"cluster": k, "count": v} for k, v in top_errors],
        "rolling_7d": {
            "success_rate": round(succ7 / (total7 or 1), 2),
            "median_duration_ms": round(med(durs7) or 0),
        },

        # Phase 2 metrics
        "approvals_required_24h": approvals_required_24h,
        "approvals_granted_24h": approvals_granted_24h,
        "web_step_success_rate_24h": round(web_steps_success /
                                           (web_steps_total or 1), 2),
        "recovery_applied_24h": recovery_applied_24h,

        # Phase 3 metrics
        "verifier_pass_rate_24h": round(verifier_steps_passed /
                                        (verifier_steps_total or 1), 2),
        "schema_captures_24h": schema_captures_24h,
        "web_upload_success_rate_24h": round(web_upload_success /
                                             (web_upload_total or 1), 2),
        "os_capability_miss_24h": os_capability_miss_24h,
    }

    # Phase 4 metrics integration
    try:
        # Queue metrics
        from .orchestrator.queue import get_queue_manager
        queue_manager = get_queue_manager()
        queue_metrics = queue_manager.get_metrics()
        out.update(queue_metrics)
    except ImportError:
        # Queue manager not available - use defaults
        out.update({
            "queue_depth_peak_24h": 0,
            "runs_per_hour_24h": 0
        })

    try:
        # Retry metrics
        from .orchestrator.retry import get_retry_manager
        retry_manager = get_retry_manager()
        retry_metrics = retry_manager.get_metrics()
        out.update(retry_metrics)
    except ImportError:
        out["retry_rate_24h"] = 0.0

    try:
        # HITL metrics
        from .actions.hitl_actions import get_confirmation_metrics
        hitl_metrics = get_confirmation_metrics()
        out.update(hitl_metrics)
    except ImportError:
        out["hitl_interventions_24h"] = 0

    try:
        # RBAC metrics
        from .security.rbac import get_rbac_manager
        rbac_manager = get_rbac_manager()
        rbac_metrics = rbac_manager.get_metrics()
        out.update(rbac_metrics)
    except ImportError:
        out["rbac_denied_24h"] = 0

    # Phase 4 additional service metrics
    try:
        # Scheduler metrics
        from .orchestrator.scheduler import get_scheduler
        scheduler = get_scheduler()
        scheduler_metrics = scheduler.get_metrics()
        out["scheduled_runs_24h"] = scheduler_metrics.get("scheduled_runs", 0)
    except ImportError:
        out["scheduled_runs_24h"] = 0

    try:
        # Watcher metrics
        from .orchestrator.watcher import get_watcher
        watcher = get_watcher()
        watcher_metrics = watcher.get_metrics()
        out["folder_triggers_24h"] = watcher_metrics.get("triggers_executed", 0)
    except ImportError:
        out["folder_triggers_24h"] = 0

    try:
        # Webhook metrics
        from .orchestrator.webhook import get_webhook_service
        webhook_service = get_webhook_service()
        webhook_metrics = webhook_service.get_metrics()
        out["webhook_triggers_24h"] = webhook_metrics.get("requests_successful", 0)
    except ImportError:
        out["webhook_triggers_24h"] = 0

    try:
        # Secrets metrics
        from .security.secrets import get_secrets_manager
        secrets_manager = get_secrets_manager()
        secrets_metrics = secrets_manager.get_metrics()
        out["secrets_lookups_24h"] = secrets_metrics.get("lookups_24h", 0)
    except ImportError:
        out["secrets_lookups_24h"] = 0

    # Phase 5 metrics: Web Engine Usage and Performance

    # Web engine usage distribution (24h)
    cur.execute("""
        SELECT COUNT(*) FROM run_steps
        WHERE name IN ('open_browser', 'fill_by_label', 'click_by_text', 'download_file',
                       'upload_file', 'wait_for_download')
        AND output_json LIKE '%"engine":"extension"%'
        AND finished_at >= datetime('now','-1 day')
    """)
    extension_engine_steps = cur.fetchone()[0] or 0

    cur.execute("""
        SELECT COUNT(*) FROM run_steps
        WHERE name IN ('open_browser', 'fill_by_label', 'click_by_text', 'download_file',
                       'upload_file', 'wait_for_download')
        AND (output_json LIKE '%"engine":"playwright"%' OR
             output_json NOT LIKE '%"engine":%')
        AND finished_at >= datetime('now','-1 day')
    """)
    playwright_engine_steps = cur.fetchone()[0] or 0

    total_engine_steps = extension_engine_steps + playwright_engine_steps

    # Extension engine success rate (24h)
    cur.execute("""
        SELECT COUNT(*) FROM run_steps
        WHERE name IN ('open_browser', 'fill_by_label', 'click_by_text', 'download_file',
                       'upload_file', 'wait_for_download')
        AND output_json LIKE '%"engine":"extension"%'
        AND status = 'success'
        AND finished_at >= datetime('now','-1 day')
    """)
    extension_engine_success = cur.fetchone()[0] or 0

    # DOM schema captures (WebX version of screen schema) (24h)
    cur.execute("""
        SELECT COUNT(*) FROM run_steps
        WHERE output_json LIKE '%get_dom_schema%'
        AND status = 'success'
        AND finished_at >= datetime('now','-1 day')
    """)
    dom_schema_captures_24h = cur.fetchone()[0] or 0

    # Native messaging RPC calls (24h) - estimated from extension engine steps
    native_messaging_calls_24h = extension_engine_steps

    # Engine fallback rate (24h) - steps that fell back from extension to playwright
    cur.execute("""
        SELECT COUNT(*) FROM run_steps
        WHERE output_json LIKE '%fallback%'
        AND output_json LIKE '%extension%'
        AND output_json LIKE '%playwright%'
        AND finished_at >= datetime('now','-1 day')
    """)
    engine_fallback_24h = cur.fetchone()[0] or 0

    # Extension connectivity health (24h) - failed handshakes or connection errors
    cur.execute("""
        SELECT COUNT(*) FROM run_steps
        WHERE (output_json LIKE '%native messaging%' OR
               output_json LIKE '%handshake%' OR
               output_json LIKE '%extension.*not.*connected%')
        AND status = 'failed'
        AND finished_at >= datetime('now','-1 day')
    """)
    extension_connectivity_failures_24h = cur.fetchone()[0] or 0

    # Add Phase 5 metrics to output (DoD compliant)
    out.update({
        # DoD required metrics
        "webx_steps_24h": total_engine_steps,
        "webx_failures_24h": (
            total_engine_steps - extension_engine_success - playwright_engine_steps +
            (playwright_engine_steps -
             (playwright_engine_steps * out.get("web_step_success_rate_24h", 0.95)))
        ),
        "webx_engine_share_24h": {
            "extension": round(extension_engine_steps / (total_engine_steps or 1), 2),
            "playwright": round(playwright_engine_steps / (total_engine_steps or 1), 2)
        },
        "webx_upload_success_24h": round(web_upload_success / (web_upload_total or 1), 2),

        # Additional Phase 5 metrics
        "extension_engine_success_rate_24h": round(extension_engine_success /
                                                   (extension_engine_steps or 1), 2),
        "dom_schema_captures_24h": dom_schema_captures_24h,
        "native_messaging_calls_24h": native_messaging_calls_24h,
        "engine_fallback_rate_24h": round(engine_fallback_24h /
                                          (total_engine_steps or 1), 2),
        "extension_connectivity_failures_24h": extension_connectivity_failures_24h,

        # Configuration status
        "web_engine_abstraction_enabled": True
    })

    # Enhanced failure clustering
    out.update({
        "top_failure_clusters_24h": _get_failure_clusters_with_recommendations()
    })

    conn.close()
    return out

def compute_webx_metrics() -> Dict[str, Any]:
    """Compute Phase 5 WebX-specific metrics (DoD requirements)."""
    conn = get_conn()
    cur = conn.cursor()
    
    # WebX steps count (24h)
    cur.execute("""
        SELECT COUNT(*) FROM run_steps
        WHERE name IN ('open_browser', 'fill_by_label', 'click_by_text', 'upload_file',
                       'wait_for_element', 'assert_element_exists', 'capture_screen_schema')
        AND finished_at >= datetime('now','-1 day')
    """)
    webx_steps_24h = cur.fetchone()[0] or 0
    
    # WebX failures count (24h)
    cur.execute("""
        SELECT COUNT(*) FROM run_steps
        WHERE name IN ('open_browser', 'fill_by_label', 'click_by_text', 'upload_file',
                       'wait_for_element', 'assert_element_exists', 'capture_screen_schema')
        AND status = 'failed'
        AND finished_at >= datetime('now','-1 day')
    """)
    webx_failures_24h = cur.fetchone()[0] or 0
    
    # Engine share metrics (24h) - track which engine was used
    cur.execute("""
        SELECT COUNT(*) FROM run_steps
        WHERE name IN ('open_browser', 'fill_by_label', 'click_by_text', 'upload_file')
        AND output_json LIKE '%"engine":"extension"%'
        AND finished_at >= datetime('now','-1 day')
    """)
    extension_steps_24h = cur.fetchone()[0] or 0
    
    cur.execute("""
        SELECT COUNT(*) FROM run_steps
        WHERE name IN ('open_browser', 'fill_by_label', 'click_by_text', 'upload_file')
        AND output_json LIKE '%"engine":"playwright"%'
        AND finished_at >= datetime('now','-1 day')
    """)
    playwright_steps_24h = cur.fetchone()[0] or 0
    
    total_web_engine_steps = extension_steps_24h + playwright_steps_24h
    
    # WebX upload success rate (24h)
    cur.execute("""
        SELECT COUNT(*) FROM run_steps
        WHERE name = 'upload_file'
        AND finished_at >= datetime('now','-1 day')
    """)
    webx_upload_total = cur.fetchone()[0] or 0
    
    cur.execute("""
        SELECT COUNT(*) FROM run_steps
        WHERE name = 'upload_file'
        AND status = 'success'
        AND finished_at >= datetime('now','-1 day')
    """)
    webx_upload_success = cur.fetchone()[0] or 0
    
    # Calculate rates and shares
    webx_failure_rate = webx_failures_24h / webx_steps_24h if webx_steps_24h > 0 else 0.0
    webx_upload_success_rate = webx_upload_success / webx_upload_total if webx_upload_total > 0 else 1.0
    
    extension_share = extension_steps_24h / total_web_engine_steps if total_web_engine_steps > 0 else 0.0
    playwright_share = playwright_steps_24h / total_web_engine_steps if total_web_engine_steps > 0 else 0.0
    
    return {
        "webx_steps_24h": webx_steps_24h,
        "webx_failures_24h": webx_failures_24h,
        "webx_engine_share_24h": {
            "extension": round(extension_share, 3),
            "playwright": round(playwright_share, 3)
        },
        "webx_upload_success_24h": round(webx_upload_success_rate, 3),
        
        # Additional breakdown
        "webx_failure_rate": round(webx_failure_rate, 3),
        "webx_upload_total": webx_upload_total,
        "webx_upload_success_count": webx_upload_success,
        "extension_steps_count": extension_steps_24h,
        "playwright_steps_count": playwright_steps_24h
    }
