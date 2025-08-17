from __future__ import annotations

from typing import Dict, List

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
    if "found":
        # caution: generic mapping
        return "NO_FILES_FOUND" if "0" in m else "FILES_FOUND"
    return "OTHER"


def compute_metrics() -> Dict[str, float]:
    conn = get_conn()
    cur = conn.cursor()
    # 24h
    cur.execute("SELECT id,status,started_at,finished_at FROM runs WHERE started_at >= datetime('now','-1 day')")
    rows = cur.fetchall()
    total24 = len(rows)
    succ24 = sum(1 for r in rows if r["status"] == "success")
    durations: List[float] = []
    for r in rows:
        if r["started_at"] and r["finished_at"]:
            cur.execute("SELECT (julianday(?) - julianday(?)) * 24*60*60*1000", (r["finished_at"], r["started_at"]))
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

    median24 = percentile(0.5)
    p95_24 = percentile(0.95)
    # error clusters 24h
    cur.execute("SELECT error_message FROM run_steps WHERE status='failed' AND finished_at >= datetime('now','-1 day')")
    errs = [_cluster_error(r[0]) for r in cur.fetchall()]
    clusters: Dict[str, int] = {}
    for e in errs:
        clusters[e] = clusters.get(e, 0) + 1
    top_errors = sorted(([k, v] for k, v in clusters.items()), key=lambda x: x[1], reverse=True)[:3]

    # 7d rolling
    cur.execute("SELECT id,status,started_at,finished_at FROM runs WHERE started_at >= datetime('now','-7 day')")
    rows7 = cur.fetchall()
    total7 = len(rows7)
    succ7 = sum(1 for r in rows7 if r["status"] == "success")
    durs7: List[float] = []
    for r in rows7:
        if r["started_at"] and r["finished_at"]:
            cur.execute("SELECT (julianday(?) - julianday(?)) * 24*60*60*1000", (r["finished_at"], r["started_at"]))
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

    out = {
        "success_rate_24h": round((succ24) / (total24 or 1), 2),
        "median_duration_ms_24h": round(median24 or 0),
        "p95_duration_ms_24h": round(p95_24 or 0),
        "top_errors_24h": [{"cluster": k, "count": v} for k, v in top_errors],
        "rolling_7d": {
            "success_rate": round((succ7) / (total7 or 1), 2),
            "median_duration_ms": round(med(durs7) or 0),
        },
    }
    conn.close()
    return out
