from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any, List, Optional


DB_PATH = Path(os.environ.get("DATABASE_URL", "sqlite:///./data/app.db").split("///")[-1])


def ensure_dirs() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def get_conn() -> sqlite3.Connection:
    ensure_dirs()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            yaml TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plan_id INTEGER NOT NULL,
            status TEXT NOT NULL,
            started_at TIMESTAMP,
            finished_at TIMESTAMP,
            approved_by TEXT,
            public_id TEXT,
            FOREIGN KEY(plan_id) REFERENCES plans(id)
        );

        CREATE TABLE IF NOT EXISTS run_steps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            idx INTEGER NOT NULL,
            name TEXT NOT NULL,
            input_json TEXT,
            output_json TEXT,
            status TEXT,
            started_at TIMESTAMP,
            finished_at TIMESTAMP,
            screenshot_path TEXT,
            error_message TEXT,
            FOREIGN KEY(run_id) REFERENCES runs(id)
        );

        CREATE TABLE IF NOT EXISTS metrics_daily (
            day TEXT PRIMARY KEY,
            total_runs INTEGER,
            success_runs INTEGER,
            median_duration_ms INTEGER,
            top_errors_json TEXT
        );

        CREATE TABLE IF NOT EXISTS plan_approvals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plan_id INTEGER NOT NULL,
            risk_analysis_json TEXT,
            approval_status TEXT DEFAULT 'pending',
            approved_by TEXT,
            approved_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(plan_id) REFERENCES plans(id)
        );

        CREATE TABLE IF NOT EXISTS approval_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plan_id INTEGER NOT NULL,
            run_id INTEGER,
            action TEXT NOT NULL,
            risk_level TEXT,
            approved_by TEXT,
            decision TEXT,
            reason TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(plan_id) REFERENCES plans(id),
            FOREIGN KEY(run_id) REFERENCES runs(id)
        );
        """
    )
    conn.commit()
    conn.close()


def insert_plan(name: str, yaml: str) -> int:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT INTO plans (name, yaml) VALUES (?, ?)", (name, yaml))
    plan_id = cur.lastrowid
    conn.commit()
    conn.close()
    return plan_id


def get_plan(plan_id: int) -> Optional[sqlite3.Row]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM plans WHERE id=?", (plan_id,))
    row = cur.fetchone()
    conn.close()
    return row


def list_runs(limit: int = 100) -> List[sqlite3.Row]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT r.*, p.name as plan_name FROM runs r "
        "JOIN plans p ON r.plan_id=p.id ORDER BY r.id DESC LIMIT ?",
        (limit,),
    )
    rows = cur.fetchall()
    conn.close()
    return list(rows)


def insert_run(plan_id: int, status: str = "pending", public_id: Optional[str] = None) -> int:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO runs (plan_id, status, public_id) VALUES (?, ?, ?)",
        (plan_id, status, public_id),
    )
    run_id = cur.lastrowid
    conn.commit()
    conn.close()
    return run_id


def update_run(run_id: int, **fields: Any) -> None:
    if not fields:
        return
    keys = ", ".join([f"{k}=?" for k in fields.keys()])
    values = list(fields.values())
    values.append(run_id)
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(f"UPDATE runs SET {keys} WHERE id=?", values)
    conn.commit()
    conn.close()


def set_run_started_now(run_id: int) -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE runs SET started_at=CURRENT_TIMESTAMP WHERE id=?", (run_id,))
    conn.commit()
    conn.close()


def set_run_finished_now(run_id: int) -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE runs SET finished_at=CURRENT_TIMESTAMP WHERE id=?", (run_id,))
    conn.commit()
    conn.close()


def insert_run_step(
    run_id: int,
    idx: int,
    name: str,
    input_json: Optional[str] = None,
    status: str = "pending",
) -> int:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        (
            "INSERT INTO run_steps (run_id, idx, name, input_json, status, started_at) "
            "VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)"
        ),
        (run_id, idx, name, input_json, status),
    )
    step_id = cur.lastrowid
    conn.commit()
    conn.close()
    return step_id


def finalize_run_step(
    step_id: int,
    status: str,
    output_json: Optional[str] = None,
    screenshot_path: Optional[str] = None,
    error_message: Optional[str] = None,
) -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        (
            "UPDATE run_steps SET status=?, output_json=?, screenshot_path=?, "
            "error_message=?, finished_at=CURRENT_TIMESTAMP WHERE id=?"
        ),
        (status, output_json, screenshot_path, error_message, step_id),
    )
    conn.commit()
    conn.close()


def get_run(run_id: int) -> Optional[sqlite3.Row]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT r.*, p.name as plan_name, p.yaml as plan_yaml FROM runs r "
        "JOIN plans p ON r.plan_id=p.id WHERE r.id=?",
        (run_id,),
    )
    row = cur.fetchone()
    conn.close()
    return row


def get_run_steps(run_id: int) -> List[sqlite3.Row]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM run_steps WHERE run_id=? ORDER BY idx ASC", (run_id,))
    rows = cur.fetchall()
    conn.close()
    return list(rows)


# Approval system functions

def create_plan_approval(plan_id: int, risk_analysis_json: str) -> int:
    """Create a new approval request for a plan."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO plan_approvals (plan_id, risk_analysis_json) VALUES (?, ?)",
        (plan_id, risk_analysis_json)
    )
    approval_id = cur.lastrowid
    conn.commit()
    conn.close()
    return approval_id


def get_plan_approval(plan_id: int) -> Optional[sqlite3.Row]:
    """Get the latest approval request for a plan."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM plan_approvals WHERE plan_id=? ORDER BY created_at DESC LIMIT 1",
        (plan_id,)
    )
    row = cur.fetchone()
    conn.close()
    return row


def approve_plan(approval_id: int, approved_by: str) -> None:
    """Approve a plan."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "UPDATE plan_approvals SET approval_status='approved', approved_by=?, approved_at=CURRENT_TIMESTAMP WHERE id=?",
        (approved_by, approval_id)
    )
    conn.commit()
    conn.close()


def reject_plan(approval_id: int, approved_by: str) -> None:
    """Reject a plan."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "UPDATE plan_approvals SET approval_status='rejected', approved_by=?, approved_at=CURRENT_TIMESTAMP WHERE id=?",
        (approved_by, approval_id)
    )
    conn.commit()
    conn.close()


def log_approval_action(plan_id: int, action: str, risk_level: str,
                        approved_by: str, decision: str,
                        reason: Optional[str] = None,
                        run_id: Optional[int] = None) -> int:
    """Log an approval action."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO approval_logs (plan_id, run_id, action, risk_level, "
        "approved_by, decision, reason) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (plan_id, run_id, action, risk_level, approved_by, decision, reason)
    )
    log_id = cur.lastrowid
    conn.commit()
    conn.close()
    return log_id


def get_approval_logs(plan_id: Optional[int] = None, limit: int = 100) -> List[sqlite3.Row]:
    """Get approval logs, optionally filtered by plan_id."""
    conn = get_conn()
    cur = conn.cursor()
    if plan_id:
        cur.execute(
            "SELECT * FROM approval_logs WHERE plan_id=? ORDER BY created_at DESC LIMIT ?",
            (plan_id, limit)
        )
    else:
        cur.execute(
            "SELECT * FROM approval_logs ORDER BY created_at DESC LIMIT ?",
            (limit,)
        )
    rows = cur.fetchall()
    conn.close()
    return list(rows)


def is_plan_approved(plan_id: int) -> bool:
    """Check if a plan has been approved."""
    approval = get_plan_approval(plan_id)
    return approval and approval['approval_status'] == 'approved'
