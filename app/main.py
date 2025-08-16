from __future__ import annotations
import os
import secrets
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from .utils import json_dumps, get_logger
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
)
from .security import mask


BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
DATA_DIR = Path("./data")
DATA_DIR.mkdir(exist_ok=True, parents=True)

app = FastAPI()
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


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
    pid = insert_plan(plan.get("name", "Unnamed"), yaml_text)
    run_id = insert_run(
        pid,
        status="pending",
        public_id=secrets.token_hex(8),
    )
    return RedirectResponse(url=f"/runs/{run_id}", status_code=303)


@app.post("/runs/{run_id}/approve")
async def runs_approve(run_id: int):
    log = get_logger()
    run = get_run(run_id)
    if not run:
        raise HTTPException(404, "run not found")
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
            result = runner.execute_step(action, params)
            shot = runner._screenshot(run_id, idx)
            models.finalize_run_step(
                step_id,
                "success",
                output_json=json_dumps(result),
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
    import json as _json
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
    return templates.TemplateResponse(
        "run_detail.html",
        {
            "request": request,
            "run": run,
            "steps": steps,
            "any_failed": any_failed,
            "first_error": first_error,
            "zero_found": zero_found,
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
    # Stats from last 24h; compute median and p95 in Python
    from .models import get_conn
    import math

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, status, started_at, finished_at FROM runs WHERE started_at >= datetime('now','-1 day')"
    )
    rows = cur.fetchall()
    total = len(rows)
    success = sum(1 for r in rows if r["status"] == "success")
    # durations in ms
    durations = []
    for r in rows:
        if r["started_at"] and r["finished_at"]:
            cur.execute(
                "SELECT (julianday(?) - julianday(?)) * 24 * 60 * 60 * 1000",
                (r["finished_at"], r["started_at"]),
            )
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
        return float(durations[f] + (durations[c] - durations[f]) * (k - f))

    median = percentile(0.5)
    p95 = percentile(0.95)
    cur.execute(
        "SELECT error_message, COUNT(*) c FROM run_steps WHERE status='failed' "
        "GROUP BY error_message ORDER BY c DESC LIMIT 3"
    )
    top_errors = cur.fetchall()
    conn.close()
    success_rate = round((success or 0) / (total or 1) * 100, 2)
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "success_rate": success_rate,
            "total_runs": total or 0,
            "median_ms": round(median or 0),
            "p95_ms": round(p95 or 0),
            "top_errors": top_errors,
        },
    )


@app.get("/permissions", response_class=HTMLResponse)
def permissions(request: Request):
    perms = check_permissions()
    return templates.TemplateResponse("permissions.html", {"request": request, "perms": perms})


@app.get("/metrics")
def metrics():
    # minimal metrics for Shields
    runs = list_runs(limit=1000)
    total = len(runs)
    success = sum(1 for r in runs if r["status"] == "success")
    success_rate = round((success) / (total or 1) * 100, 2)
    return {"total_runs": total, "success_runs": success, "success_rate": success_rate}
