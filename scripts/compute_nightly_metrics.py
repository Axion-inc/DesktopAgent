import json
import sys
import os

# Add parent directory to Python path to import app modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.metrics import compute_metrics
from app.models import init_db


def main() -> None:
    # Initialize database to ensure tables exist
    init_db()
    m = compute_metrics()
    summary = {
        "success_rate_24h": m.get("success_rate_24h", 0),
        "median_duration_ms_24h": m.get("median_duration_ms_24h", 0),
        "p95_duration_ms_24h": m.get("p95_duration_ms_24h", 0),
        "top_errors_24h": m.get("top_errors_24h", []),
    }
    with open("nightly_metrics.json", "w", encoding="utf-8") as f:
        json.dump(summary, f)
    print("METRICS:", json.dumps(summary))


if __name__ == "__main__":
    main()

