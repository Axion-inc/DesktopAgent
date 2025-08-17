from app.metrics import compute_metrics
from app.models import init_db


def test_compute_metrics_schema_keys():
    # Initialize database before computing metrics
    init_db()
    m = compute_metrics()
    # Keys exist (values may be zero on empty DB)
    assert "success_rate_24h" in m
    assert "median_duration_ms_24h" in m
    assert "p95_duration_ms_24h" in m
    assert "top_errors_24h" in m
    assert "rolling_7d" in m

