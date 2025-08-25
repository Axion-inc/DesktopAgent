from __future__ import annotations
from pathlib import Path
from fastapi import FastAPI, Form, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from .utils import get_logger
from .metrics import compute_metrics
from .models import init_db

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path("./data")
DATA_DIR.mkdir(exist_ok=True, parents=True)

app = FastAPI(title="Desktop Agent API", description="Minimal API for CLI operations")


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    
    # Initialize Phase 4 services
    try:
        from app.orchestrator.scheduler import start_scheduler, start_scheduler_with_config
        from app.orchestrator.watcher import start_watcher
        from app.orchestrator.webhook import setup_webhook_routes
        
        # Setup webhook routes
        setup_webhook_routes(app)
        
        # Start scheduler service with config
        from pathlib import Path
        config_path = Path("configs/schedules.yaml")
        if config_path.exists():
            start_scheduler_with_config(str(config_path))
        else:
            start_scheduler()
        
        # Start watcher service  
        start_watcher()
        
        get_logger().info("Phase 4 services started: scheduler, watcher, webhooks")
    except Exception as e:
        get_logger().warning(f"Phase 4 services startup warning: {e}")
    
    get_logger().info("app.startup")

# RBAC-protected endpoints
from app.middleware.auth import get_current_user, require_admin, require_editor, require_runner
from app.security.rbac import User as RBACUser

@app.get("/api/runs")
async def list_runs(current_user: RBACUser = Depends(get_current_user)):
    """List runs - requires authentication."""
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    # Basic run listing (viewers can see runs)
    from app.models import get_conn
    conn = get_conn()
    cursor = conn.execute(
        "SELECT id, name, status, started_at, finished_at FROM runs ORDER BY id DESC LIMIT 50"
    )
    runs = [dict(row) for row in cursor.fetchall()]
    return {"runs": runs}

@app.post("/api/runs/{run_id}/pause")
@require_editor
async def pause_run(run_id: int, current_user: RBACUser = Depends(get_current_user)):
    """Pause a run - requires Editor role."""
    try:
        from app.orchestrator.resume import get_resume_manager
        resume_manager = get_resume_manager()
        
        # Create manual pause
        resume_manager.create_resume_point(
            run_id=run_id,
            step_index=0,  # Will be updated by actual runner
            step_name="manual_pause",
            runner_state={},
            reason="manual",
            user_id=current_user.id
        )
        
        return {"success": True, "message": f"Run {run_id} paused by {current_user.username}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/runs/{run_id}/resume")
@require_editor
async def resume_run(run_id: int, current_user: RBACUser = Depends(get_current_user)):
    """Resume a paused run - requires Editor role."""
    try:
        from app.orchestrator.resume import get_resume_manager
        resume_manager = get_resume_manager()
        
        success = resume_manager.resume_run(run_id, current_user.id)
        if success:
            return {"success": True, "message": f"Run {run_id} resumed by {current_user.username}"}
        else:
            raise HTTPException(status_code=404, detail="No paused run found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/paused-runs")
@require_runner  
async def list_paused_runs(current_user: RBACUser = Depends(get_current_user)):
    """List paused runs waiting for resume - requires Runner role."""
    try:
        from app.orchestrator.resume import get_resume_manager
        resume_manager = get_resume_manager()
        
        paused_runs = resume_manager.list_paused_runs()
        return {"paused_runs": paused_runs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/admin/users")
@require_admin
async def list_users(current_user: RBACUser = Depends(get_current_user)):
    """List all users - Admin only."""
    try:
        from app.security.rbac import get_rbac_manager
        rbac = get_rbac_manager()
        
        users = rbac.list_users()
        return {"users": [
            {
                "id": u.id,
                "username": u.username,
                "active": u.active,
                "created_at": u.created_at.isoformat() if u.created_at else None
            } for u in users
        ]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/admin/users")
@require_admin 
async def create_user(user_data: dict, current_user: RBACUser = Depends(get_current_user)):
    """Create a new user - Admin only."""
    try:
        from app.security.rbac import get_rbac_manager
        rbac = get_rbac_manager()
        
        user = rbac.create_user(
            username=user_data["username"],
            password=user_data["password"],
            active=user_data.get("active", True)
        )
        
        return {"success": True, "user_id": user.id, "username": user.username}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/admin/audit")
@require_admin
async def get_audit_log(limit: int = 100, current_user: RBACUser = Depends(get_current_user)):
    """Get audit log - Admin only."""
    try:
        from app.security.rbac import get_rbac_manager
        rbac = get_rbac_manager()
        
        audit_entries = rbac.get_audit_log(limit=limit)
        return {"audit_log": audit_entries}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# HITL Approval UI
from fastapi.templating import Jinja2Templates
from fastapi import Form

templates = Jinja2Templates(directory="app/templates")

@app.get("/hitl/approve/{run_id}")
async def hitl_approval_page(run_id: int, request: Request, current_user: RBACUser = Depends(get_current_user)):
    """Show HITL approval page."""
    try:
        from app.orchestrator.resume import get_resume_manager
        from app.models import get_conn
        
        # Check if user has permission to approve
        if not current_user:
            raise HTTPException(status_code=401, detail="Authentication required")
        
        # Get resume point
        resume_manager = get_resume_manager()
        resume_point = resume_manager.get_resume_point(run_id)
        
        if not resume_point or resume_point.reason != "hitl":
            raise HTTPException(status_code=404, detail="No HITL approval pending for this run")
        
        # Get run details
        conn = get_conn()
        cursor = conn.execute(
            "SELECT * FROM runs WHERE id = ?", (run_id,)
        )
        run_data = cursor.fetchone()
        
        if not run_data:
            raise HTTPException(status_code=404, detail="Run not found")
        
        # Get run steps for preview
        cursor = conn.execute(
            "SELECT * FROM run_steps WHERE run_id = ? ORDER BY step_index", (run_id,)
        )
        steps = cursor.fetchall()
        
        # Calculate next steps
        next_steps = []
        if resume_point.step_index < len(steps):
            for i, step in enumerate(steps[resume_point.step_index:resume_point.step_index + 5]):
                next_steps.append({
                    "action": step["name"],
                    "summary": f"{step['name']}: {step.get('input_json', '')[:100]}..."
                })
        
        # Risk analysis (basic)
        risk_analysis = []
        for step in steps[resume_point.step_index:]:
            if step["name"] in ["compose_mail", "click_by_text", "move_to"]:
                risk_analysis.append({
                    "level": "MEDIUM",
                    "description": f"Will execute {step['name']} operation"
                })
        
        return templates.TemplateResponse("hitl_approval.html", {
            "request": request,
            "run_id": run_id,
            "template_name": run_data["template"] or "Unknown",
            "started_at": run_data["started_at"],
            "current_step": resume_point.step_name,
            "step_index": resume_point.step_index,
            "total_steps": len(steps),
            "approval_message": resume_point.state_snapshot.get("message", "Approval required to continue"),
            "risk_analysis": risk_analysis,
            "next_steps": next_steps,
            "current_user": current_user,
            "timeout_info": {
                "remaining_minutes": 30,  # Default timeout
                "auto_action": "deny"
            }
        })
        
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/hitl/approve/{run_id}")
@require_editor
async def hitl_approval_action(
    run_id: int, 
    request: Request,
    action: str = Form(...),
    user_id: str = Form(None),
    current_user: RBACUser = Depends(get_current_user)
):
    """Handle HITL approval action."""
    try:
        from app.orchestrator.resume import get_resume_manager
        from app.orchestrator.queue import get_queue_manager
        
        resume_manager = get_resume_manager()
        
        if action == "approve":
            # Resume the run
            success = resume_manager.resume_run(run_id, current_user.id)
            if success:
                # Re-queue the run for continuation
                queue_manager = get_queue_manager()
                # This would need integration with actual run re-queuing logic
                
                return {
                    "success": True, 
                    "message": f"Run {run_id} approved and resumed",
                    "action": "approved",
                    "approved_by": current_user.username
                }
            else:
                raise HTTPException(status_code=404, detail="No pending approval found")
                
        elif action == "deny":
            # Cancel the run
            success = resume_manager.cancel_resume(run_id, current_user.id)
            if success:
                return {
                    "success": True,
                    "message": f"Run {run_id} denied and cancelled", 
                    "action": "denied",
                    "denied_by": current_user.username
                }
            else:
                raise HTTPException(status_code=404, detail="No pending approval found")
        
        else:
            raise HTTPException(status_code=400, detail="Invalid action")
            
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.get("/metrics")
def metrics():
    return compute_metrics()


# ------------------------
# Mock Form (for E2E tests)
# ------------------------

@app.get("/mock/form", response_class=HTMLResponse)
def mock_form():
    html = """
    <!DOCTYPE html>
    <html lang="ja">
      <head>
        <meta charset="utf-8" />
        <title>お問い合わせフォーム</title>
      </head>
      <body>
        <h1>お問い合わせフォーム</h1>
        <form method="post" action="/mock/form">
          <div>
            <label for="name">氏名</label>
            <input id="name" name="name" type="text" required placeholder="山田太郎" />
          </div>
          <div>
            <label for="email">メール</label>
            <input id="email" name="email" type="email" required placeholder="example@email.com" />
          </div>
          <div>
            <label for="subject">件名</label>
            <input id="subject" name="subject" type="text" required placeholder="お問い合わせの件名" />
          </div>
          <div>
            <label for="message">本文</label>
            <textarea id="message" name="message" required placeholder="お問い合わせ内容をご記入ください..."></textarea>
          </div>
          <button type="submit">送信</button>
        </form>
      </body>
    </html>
    """
    return HTMLResponse(content=html)


@app.post("/mock/form", response_class=HTMLResponse)
def mock_form_post(
    name: str = Form(""),
    email: str = Form(""),
    subject: str = Form(""),
    message: str = Form("")
):
    errors = []
    if not (name or "").strip():
        errors.append("氏名は必須です")
    if not (email or "").strip():
        errors.append("メールアドレスは必須です")
    if not (subject or "").strip():
        errors.append("件名は必須です")
    if not (message or "").strip():
        errors.append("本文は必須です")

    if errors:
        items = "".join(f"<li>{e}</li>" for e in errors)
        err_html = f"""
        <!DOCTYPE html>
        <html lang="ja">
          <head>
            <meta charset="utf-8" />
            <title>お問い合わせフォーム</title>
          </head>
          <body>
            <h1>お問い合わせフォーム</h1>
            <div class="error">入力エラーがあります</div>
            <ul>
              {items}
            </ul>
            <form method="post" action="/mock/form">
              <div>
                <label for="name">氏名</label>
                <input id="name" name="name" type="text" placeholder="山田太郎" value="{name}" />
              </div>
              <div>
                <label for="email">メール</label>
                <input id="email" name="email" type="email" placeholder="example@email.com" value="{email}" />
              </div>
              <div>
                <label for="subject">件名</label>
                <input id="subject" name="subject" type="text" placeholder="お問い合わせの件名" value="{subject}" />
              </div>
              <div>
                <label for="message">本文</label>
                <textarea id="message" name="message" placeholder="お問い合わせ内容をご記入ください...">{message}</textarea>
              </div>
              <button type="submit">送信</button>
            </form>
          </body>
        </html>
        """
        return HTMLResponse(content=err_html)

    # Success page
    ok_html = f"""
    <!DOCTYPE html>
    <html lang=\"ja\">
      <head>
        <meta charset=\"utf-8\" />
        <title>送信完了</title>
      </head>
      <body>
        <h1>送信完了</h1>
        <div>氏名: {name}</div>
        <div>メール: {email}</div>
        <div>件名: {subject}</div>
        <div>本文: {message}</div>
      </body>
    </html>
    """
    return HTMLResponse(content=ok_html)


# ------------------------
# Simple Pages for E2E
# ------------------------

@app.get("/plans/intent", response_class=HTMLResponse)
def plans_intent():
    return HTMLResponse(
        content="""
        <!DOCTYPE html>
        <html lang='en'>
          <head><meta charset='utf-8' /><title>Planner L1</title></head>
          <body><h1>Planner L1</h1></body>
        </html>
        """
    )


@app.get("/public/dashboard", response_class=HTMLResponse)
def public_dashboard():
    m = compute_metrics()
    html = f"""
    <!DOCTYPE html>
    <html lang='en'>
      <head>
        <meta charset='utf-8' />
        <title>Dashboard</title>
        <style>.metric-value{{font-weight:bold}}</style>
      </head>
      <body>
        <h1>Dashboard</h1>
        <div>Success Rate: <span class='metric-value'>{m.get('success_rate_24h', 0)}</span></div>
        <div>Approvals Required: <span class='metric-value'>{m.get('approvals_required_24h', 0)}</span></div>
        <div>Approvals Granted: <span class='metric-value'>{m.get('approvals_granted_24h', 0)}</span></div>
        <div>Web Success Rate: <span class='metric-value'>{m.get('web_step_success_rate_24h', 0)}</span></div>
        <div>Recovery Applied: <span class='metric-value'>{m.get('recovery_applied_24h', 0)}</span></div>

        <h2>Phase 3 Metrics (24h)</h2>
        <div>Verifier Pass Rate: <span class='metric-value'>{m.get('verifier_pass_rate_24h', 0)}</span></div>
        <div>Schema Captures: <span class='metric-value'>{m.get('schema_captures_24h', 0)}</span></div>
        <div>Web Upload Success Rate: <span class='metric-value'>{m.get('web_upload_success_rate_24h', 0)}</span></div>
        <div>OS Capability Misses: <span class='metric-value'>{m.get('os_capability_miss_24h', 0)}</span></div>

        <h2>Phase 4 Metrics (24h)</h2>
        <div>Queue Peak Depth: <span class='metric-value'>{m.get('queue_depth_peak_24h', 0)}</span></div>
        <div>Runs per Hour: <span class='metric-value'>{m.get('runs_per_hour_24h', 0)}</span></div>
        <div>Retry Rate: <span class='metric-value'>{round(m.get('retry_rate_24h', 0) * 100, 1)}%</span></div>
        <div>HITL Interventions: <span class='metric-value'>{m.get('hitl_interventions_24h', 0)}</span></div>
        <div>Scheduled Runs: <span class='metric-value'>{m.get('scheduled_runs_24h', 0)}</span></div>
        <div>RBAC Denials: <span class='metric-value'>{m.get('rbac_denied_24h', 0)}</span></div>

        <h2>Top Failure Clusters (24h)</h2>
        <div>
          {chr(10).join([
              f"<div>{cluster['cluster']}: "
              f"<span class='metric-value'>{cluster['count']}</span></div>"
              for cluster in m.get('top_failure_clusters_24h', [])
          ])}
        </div>

        <h2>Performance (24h)</h2>
        <div>Median Duration: <span class='metric-value'>{m.get('median_duration_ms_24h', 0)}ms</span></div>
        <div>P95 Duration: <span class='metric-value'>{m.get('p95_duration_ms_24h', 0)}ms</span></div>
      </body>
    </html>
    """
    return HTMLResponse(content=html)
