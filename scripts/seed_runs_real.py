#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Ensure repository root on path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_plan import main as run_once  # reuse CLI


def main() -> None:
    ap = argparse.ArgumentParser(description="Seed multiple REAL runs for stability checks")
    ap.add_argument("yaml_path", type=str, help="Path to plan YAML")
    ap.add_argument("--n", type=int, default=20, help="Number of runs (default: 20)")
    ap.add_argument("--sleep", type=float, default=1.0, help="Sleep seconds between runs")
    ap.add_argument("--var", action="append", default=[], help="Variable overrides (key=value)")
    args = ap.parse_args()

    for i in range(args.n):
        print(f"== REAL Run {i+1}/{args.n} ==")
        argv = [args.yaml_path]
        for v in args.var:
            argv.extend(["--var", v])
        old_argv = sys.argv
        try:
            sys.argv = [old_argv[0]] + argv
            run_once()
        finally:
            sys.argv = old_argv
        time.sleep(args.sleep)


if __name__ == "__main__":
    main()

