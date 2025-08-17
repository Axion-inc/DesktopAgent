from __future__ import annotations
import os
import secrets
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from .utils import json_dumps, get_logger
from .metrics import compute_metrics
from .permissions import check_permissions

from .dsl.parser import parse_yaml, render_value
from .dsl.validator import validate_plan
from .dsl.runner import Runner
from .models import (
    get_run,
    get_run_steps,
    init_db,
    insert_plan,
    insert_run,
    list_runs,
    update_run,
    set_run_started_now,
    set_run_finished_now,
    create_plan_approval,
    get_plan_approval,
    approve_plan,
    reject_plan,
    log_approval_action,
    is_plan_approved,
)
from .security import mask
from .approval import analyze_plan_risks, check_plan_approval_required, format_approval_summary, get_approval_ui_message
from .planner import generate_plan_from_intent, is_planner_enabled, set_planner_enabled
import json as _json


BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
DATA_DIR = Path("./data")
DATA_DIR.mkdir(exist_ok=True, parents=True)

app = FastAPI()
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


# Add custom Jinja2 filters
def from_json_filter(json_str: str) -> dict:
    """Convert JSON string to dict for template access."""
    try:
        return _json.loads(json_str) if isinstance(json_str, str) else json_str
    except Exception:
        return {}


templates.env.filters["from_json"] = from_json_filter


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    get_logger().info("app.startup")


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.get("/plans/new", response_class=HTMLResponse)
def plans_new(request: Request):
    template_yaml = (
        BASE_DIR.parent / "plans" / "templates" / "weekly_report.yaml"
    ).read_text(encoding="utf-8")
    return templates.TemplateResponse("plans_new.html", {"request": request, "template_yaml": template_yaml})


@app.post("/plans/validate")
async def plans_validate(yaml_text: str = Form(...)):
    try:
        plan = parse_yaml(yaml_text)
    except ValueError as e:
        return JSONResponse({"ok": False, "errors": [str(e)]})
    errors = validate_plan(plan)
    if errors:
        return JSONResponse({"ok": False, "errors": errors})
    # Render variables
    variables = plan.get("variables", {})
    rendered_steps = []
    for step in plan.get("steps", []):
        action, params = list(step.items())[0]
        rendered_steps.append({action: render_value(params, variables)})
    # naive estimation: number of steps * 250ms
    est_ms = max(250, 250 * max(1, len(plan.get("steps", []))))
    summary = {"destructive": False, "estimated_ms": est_ms}
    return {"ok": True, "name": plan.get("name"), "steps": rendered_steps, "summary": summary}


@app.post("/plans/run")
async def plans_run(request: Request, yaml_text: str = Form(...)):
    plan = parse_yaml(yaml_text)
    errors = validate_plan(plan)
    if errors:
        raise HTTPException(400, "; ".join(errors))

    # Check if approval is required
    approval_required = check_plan_approval_required(plan)

    pid = insert_plan(plan.get("name", "Unnamed"), yaml_text)

    if approval_required:
        # Create approval request
        risk_analysis = analyze_plan_risks(plan)
        create_plan_approval(pid, json_dumps(risk_analysis))

        # Create run in pending_approval status
        run_id = insert_run(
            pid,
            status="pending_approval",
            public_id=secrets.token_hex(8),
        )

        # Log approval requirement
        log_approval_action(
            pid,
            "plan_submission",
            risk_analysis["risk_level"],
            "system",
            "approval_required",
            "Plan requires approval due to detected risks"
        )

        return RedirectResponse(url=f"/plans/{pid}/approve", status_code=303)
    else:
        # No approval required, proceed normally
        run_id = insert_run(
            pid,
            status="pending",
            public_id=secrets.token_hex(8),
        )
        return RedirectResponse(url=f"/runs/{run_id}", status_code=303)


@app.get("/plans/{plan_id}/approve", response_class=HTMLResponse)
async def plans_approve_get(request: Request, plan_id: int):
    """Show approval page for a plan."""
    from .models import get_plan

    plan_data = get_plan(plan_id)
    if not plan_data:
        raise HTTPException(404, "Plan not found")

    approval = get_plan_approval(plan_id)
    if not approval:
        raise HTTPException(404, "Approval request not found")

    # Parse plan for display
    plan = parse_yaml(plan_data["yaml"])
    risk_analysis = _json.loads(approval["risk_analysis_json"])

    return templates.TemplateResponse(
        "plan_approval.html",
        {
            "request": request,
            "plan": plan,
            "plan_id": plan_id,
            "approval": approval,
            "risk_analysis": risk_analysis,
            "approval_message": get_approval_ui_message(risk_analysis),
            "risk_summary": format_approval_summary(risk_analysis)
        }
    )


@app.post("/plans/{plan_id}/approve")
async def plans_approve_post(request: Request, plan_id: int, action: str = Form(...), reason: str = Form("")):
    """Process approval decision for a plan."""
    approval = get_plan_approval(plan_id)
    if not approval:
        raise HTTPException(404, "Approval request not found")

    if approval["approval_status"] != "pending":
        raise HTTPException(400, "Approval already processed")

    # Get user identifier (in real app, this would come from authentication)
    user_id = "admin"  # Placeholder for MVP

    if action == "approve":
        approve_plan(approval["id"], user_id)

        # Log approval action
        risk_analysis = _json.loads(approval["risk_analysis_json"])
        log_approval_action(
            plan_id,
            "plan_approval",
            risk_analysis["risk_level"],
            user_id,
            "approved",
            reason if reason else "Manual approval granted"
        )

        # Create approved run
        run_id = insert_run(
            plan_id,
            status="pending",
            public_id=secrets.token_hex(8),
        )

        return RedirectResponse(url=f"/runs/{run_id}", status_code=303)

    elif action == "reject":
        reject_plan(approval["id"], user_id)

        # Log rejection action
        risk_analysis = _json.loads(approval["risk_analysis_json"])
        log_approval_action(
            plan_id,
            "plan_approval",
            risk_analysis["risk_level"],
            user_id,
            "rejected",
            reason if reason else "Manual approval denied"
        )

        return RedirectResponse(url=f"/plans/{plan_id}/approve?rejected=1", status_code=303)
    else:
        raise HTTPException(400, "Invalid action")


@app.post("/runs/{run_id}/approve")
async def runs_approve(run_id: int):
    log = get_logger()
    run = get_run(run_id)
    if not run:
        raise HTTPException(404, "run not found")

    # Check if plan requires approval and is approved
    plan = parse_yaml(run["plan_yaml"])  # type: ignore
    if check_plan_approval_required(plan):
        if not is_plan_approved(run["plan_id"]):
            raise HTTPException(403, "Plan execution requires approval. Please complete approval process first.")

    # Permission preflight (block on Mail automation failure)
    perms = check_permissions()
    mail_status = perms.get("automation_mail", {}).get("status")
    strict = os.environ.get("PERMISSIONS_STRICT", "0") in ("1", "true", "True")
    screen_status = perms.get("screen_recording", {}).get("status")
    if mail_status == "fail" or (strict and screen_status != "ok"):
        # Show blocking page with guidance
        return templates.TemplateResponse(
            "permissions_block.html",
            {"request": Request, "perms": perms, "run_id": run_id},
            status_code=403,
        )
    update_run(run_id, status="running")
    log.info("run.start id=%s", run_id)
    set_run_started_now(run_id)
    # Execute synchronously for MVP
    plan = parse_yaml(run["plan_yaml"])  # type: ignore
    variables = plan.get("variables", {})
    # Render all params
    rendered_steps = []
    for step in plan.get("steps", []):
        action, params = list(step.items())[0]
        rendered_steps.append({action: render_value(params, variables)})
    runner = Runner(plan, variables, dry_run=False)
    from . import models

    ok = True
    for idx, step in enumerate(rendered_steps, start=1):
        action, params = list(step.items())[0]
        step_id = models.insert_run_step(
            run_id,
            idx,
            action,
            input_json=json_dumps(params),
            status="running",
        )
        try:
            result = runner.execute_step_with_diff(action, params)
            shot = runner._screenshot(run_id, idx)
            # Include diff data in the step output for replay UI
            result_with_diff = {**result}
            if idx <= len(runner.step_diffs):
                result_with_diff["_diff"] = runner.step_diffs[idx - 1]
            models.finalize_run_step(
                step_id,
                "success",
                output_json=json_dumps(result_with_diff),
                screenshot_path=shot,
            )
            log.info("run.step.success id=%s idx=%s action=%s", run_id, idx, action)
        except Exception as e:
            ok = False
            shot = runner._screenshot(run_id, idx)
            models.finalize_run_step(
                step_id,
                "failed",
                error_message=str(e),
                screenshot_path=shot,
            )
            log.error("run.step.failed id=%s idx=%s action=%s err=%s", run_id, idx, action, e)
            break
    if ok:
        update_run(run_id, status="success")
        log.info("run.finish id=%s status=success", run_id)
    else:
        update_run(run_id, status="failed")
        log.info("run.finish id=%s status=failed", run_id)
    set_run_finished_now(run_id)
    return RedirectResponse(url=f"/runs/{run_id}", status_code=303)


@app.get("/runs", response_class=HTMLResponse)
def runs(request: Request):
    return templates.TemplateResponse("runs.html", {"request": request, "runs": list_runs()})


@app.get("/runs/{run_id}", response_class=HTMLResponse)
def runs_detail(request: Request, run_id: int):
    run = get_run(run_id)
    if not run:
        raise HTTPException(404, "not found")
    steps = get_run_steps(run_id)
    any_failed = False
    first_error = None
    zero_found = False
    diffs = []
    for s in steps:
        if s["status"] == "failed" and not any_failed:
            any_failed = True
            first_error = s["error_message"]
        if s["name"] == "find_files" and s["output_json"]:
            try:
                out = _json.loads(s["output_json"])  # type: ignore
                if isinstance(out, dict) and out.get("found") == 0:
                    zero_found = True
            except Exception:
                pass
        try:
            out = s["output_json"] and _json.loads(s["output_json"]) or {}
            if isinstance(out, dict):
                if "before_count" in out or "after_count" in out:
                    diffs.append({
                        "idx": s["idx"],
                        "name": s["name"],
                        "before": out.get("before_count"),
                        "after": out.get("after_count"),
                    })
                if "page_count" in out:
                    diffs.append({"idx": s["idx"], "name": s["name"], "pages": out.get("page_count")})
        except Exception:
            pass
    return templates.TemplateResponse(
        "run_detail.html",
        {
            "request": request,
            "run": run,
            "steps": steps,
            "any_failed": any_failed,
            "first_error": first_error,
            "zero_found": zero_found,
            "diffs": diffs,
        },
    )


@app.get("/permissions", response_class=HTMLResponse)
def permissions_page(request: Request, run_id: int = None):
    """Permission diagnostics page."""
    perms = check_permissions()
    return templates.TemplateResponse(
        "permissions.html",
        {
            "request": request,
            "perms": perms,
            "run_id": run_id,
        },
    )


@app.get("/public/runs/{public_id}", response_class=HTMLResponse)
def runs_public(request: Request, public_id: str):
    # naive lookup by public_id
    from .models import get_conn

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id FROM runs WHERE public_id=?", (public_id,))
    r = cur.fetchone()
    conn.close()
    if not r:
        raise HTTPException(404, "not found")
    rid = r[0]
    run = get_run(rid)
    steps = get_run_steps(rid)
    # mask PII in rendered page
    masked_steps = []
    for s in steps:
        ms = dict(s)
        for k in ("input_json", "output_json", "error_message"):
            if ms.get(k):
                ms[k] = mask(str(ms[k]))
        masked_steps.append(ms)
    run_masked = dict(run)
    for k in ("approved_by",):
        if run_masked.get(k):
            run_masked[k] = mask(str(run_masked[k]))
    return templates.TemplateResponse("run_public.html", {"request": request, "run": run_masked, "steps": masked_steps})


@app.get("/public/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    m = compute_metrics()
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "success_rate": round(m.get("success_rate_24h", 0) * 100, 2),
            "total_runs": None,
            "median_ms": m.get("median_duration_ms_24h", 0),
            "p95_ms": m.get("p95_duration_ms_24h", 0),
            "top_errors": [(e.get("cluster"), e.get("count")) for e in m.get("top_errors_24h", [])],
            "rolling_7d": m.get("rolling_7d", {}),

            # Phase 2 metrics
            "approvals_required": m.get("approvals_required_24h", 0),
            "approvals_granted": m.get("approvals_granted_24h", 0),
            "web_success_rate": m.get("web_step_success_rate_24h", 0),
            "recovery_applied": m.get("recovery_applied_24h", 0),
        },
    )


@app.get("/permissions", response_class=HTMLResponse)
def permissions(request: Request):
    perms = check_permissions()
    return templates.TemplateResponse("permissions.html", {"request": request, "perms": perms})


@app.get("/metrics")
def metrics():
    return compute_metrics()


# Mock SaaS endpoints for testing

@app.get("/mock/form", response_class=HTMLResponse)
async def mock_form_get(request: Request):
    """Mock SaaS form for testing web automation."""
    return templates.TemplateResponse(
        "mock_form.html",
        {"request": request}
    )


@app.post("/mock/form")
async def mock_form_post(
    request: Request,
    name: str = Form(None),
    email: str = Form(None),
    subject: str = Form(None),
    message: str = Form(None)
):
    """Handle mock form submission."""

    # Simulate processing
    submission_data = {
        "name": name or "",
        "email": email or "",
        "subject": subject or "",
        "message": message or "",
        "timestamp": _json.dumps({"submitted_at": "2023-01-01T00:00:00Z"}),
        "status": "success"
    }

    # Validate required fields
    errors = []
    if not name or not name.strip():
        errors.append("氏名は必須です")
    if not email or not email.strip():
        errors.append("メールアドレスは必須です")
    if not subject or not subject.strip():
        errors.append("件名は必須です")
    if not message or not message.strip():
        errors.append("本文は必須です")

    if errors:
        return templates.TemplateResponse(
            "mock_form.html",
            {
                "request": request,
                "errors": errors,
                "form_data": submission_data
            },
            status_code=400
        )

    # Success response
    return templates.TemplateResponse(
        "mock_form_success.html",
        {
            "request": request,
            "submission_data": submission_data
        }
    )


# Planner L1 endpoints

@app.get("/plans/intent", response_class=HTMLResponse)
async def plans_intent_get(request: Request):
    """Show intent input page for Planner L1."""
    return templates.TemplateResponse(
        "plan_intent.html",
        {
            "request": request,
            "planner_enabled": is_planner_enabled()
        }
    )


@app.post("/plans/intent")
async def plans_intent_post(request: Request, intent_text: str = Form(...), enable_planner: bool = Form(False)):
    """Process natural language intent and generate DSL plan."""

    # Handle planner enable/disable
    if enable_planner and not is_planner_enabled():
        set_planner_enabled(True)
    elif not enable_planner and is_planner_enabled():
        set_planner_enabled(False)

    if not is_planner_enabled():
        return templates.TemplateResponse(
            "plan_intent.html",
            {
                "request": request,
                "planner_enabled": False,
                "error": "Planner L1 is disabled. Enable it to generate plans from natural language."
            },
            status_code=400
        )

    # Generate plan from intent
    success, plan, message = generate_plan_from_intent(intent_text)

    if not success:
        return templates.TemplateResponse(
            "plan_intent.html",
            {
                "request": request,
                "planner_enabled": is_planner_enabled(),
                "intent_text": intent_text,
                "error": message,
                "plan": plan if plan else None
            },
            status_code=400
        )

    # Success - show generated plan for editing
    import yaml
    plan_yaml = yaml.dump(plan, default_flow_style=False, allow_unicode=True)

    return templates.TemplateResponse(
        "plan_intent_result.html",
        {
            "request": request,
            "intent_text": intent_text,
            "plan": plan,
            "plan_yaml": plan_yaml,
            "message": message,
            "confidence": plan.get('_confidence', 0.0)
        }
    )
