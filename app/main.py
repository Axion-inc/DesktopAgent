from __future__ import annotations
from pathlib import Path
from fastapi import FastAPI, Form
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
    get_logger().info("app.startup")


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
    name: str = Form("") ,
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
          {chr(10).join([f"<div>{cluster['cluster']}: <span class='metric-value'>{cluster['count']}</span></div>" for cluster in m.get('top_failure_clusters_24h', [])])}
        </div>
        
        <h2>Performance (24h)</h2>
        <div>Median Duration: <span class='metric-value'>{m.get('median_duration_ms_24h', 0)}ms</span></div>
        <div>P95 Duration: <span class='metric-value'>{m.get('p95_duration_ms_24h', 0)}ms</span></div>
      </body>
    </html>
    """
    return HTMLResponse(content=html)
