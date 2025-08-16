from __future__ import annotations

from typing import Dict

from .models import get_conn


def compute_metrics() -> Dict[str, float]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM runs")
    total = cur.fetchone()[0] or 0
    cur.execute("SELECT COUNT(*) FROM runs WHERE status='success'")
    success = cur.fetchone()[0] or 0
    conn.close()
    rate = round((success) / (total or 1) * 100, 2)
    return {"total_runs": float(total), "success_runs": float(success), "success_rate": rate}

