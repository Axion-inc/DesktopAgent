#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Ensure repository root is importable
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_plan import main as run_once  # reuse CLI


def main():
    ap = argparse.ArgumentParser(description="Seed multiple runs for stability checks")
    ap.add_argument("yaml_path", type=str, help="Path to plan YAML")
    ap.add_argument("--n", type=int, default=20, help="Number of runs (default: 20)")
    ap.add_argument("--dry-run", action="store_true", help="Dry-run mode")
    ap.add_argument("--sleep", type=float, default=0.5, help="Sleep seconds between runs")
    ap.add_argument("--var", action="append", default=[], help="Variable overrides")
    args, rest = ap.parse_known_args()

    # Build argv for run_plan
    for i in range(args.n):
        print(f"== Run {i+1}/{args.n} ==")
        argv = [args.yaml_path]
        if args.dry_run:
            argv.append("--dry-run")
        for v in args.var:
            argv.extend(["--var", v])
        # emulate CLI call
        old_argv = sys.argv
        try:
            sys.argv = [old_argv[0]] + argv
            run_once()
        finally:
            sys.argv = old_argv
        time.sleep(args.sleep)


if __name__ == "__main__":
    main()
