#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict

# Ensure repository root is importable
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.dsl.parser import parse_yaml, render_value
from app.dsl.runner import Runner
from app.models import (
    init_db,
    insert_plan,
    insert_run,
    insert_run_step,
    finalize_run_step,
    update_run,
    set_run_started_now,
    set_run_finished_now,
)


def override_vars(plan: Dict[str, Any], overrides: Dict[str, str]) -> Dict[str, Any]:
    vars0 = dict(plan.get("variables", {}))
    vars0.update(overrides)
    return vars0


def render_steps(plan: Dict[str, Any], variables: Dict[str, Any]):
    out = []
    for step in plan.get("steps", []):
        action, params = list(step.items())[0]
        out.append({action: render_value(params, variables)})
    return out


def main():
    ap = argparse.ArgumentParser(description="Run a plan YAML once via CLI")
    ap.add_argument("yaml_path", type=str, help="Path to plan YAML")
    ap.add_argument("--dry-run", action="store_true", help="Do not perform OS/FS mutations")
    ap.add_argument(
        "--var",
        action="append",
        default=[],
        help="Override variable, e.g., --var inbox=./sample_data",
    )
    args = ap.parse_args()

    init_db()
    yaml_text = Path(args.yaml_path).read_text(encoding="utf-8")
    plan = parse_yaml(yaml_text)

    overrides: Dict[str, str] = {}
    for item in args.var:
        if "=" in item:
            k, v = item.split("=", 1)
            overrides[k] = v

    variables = override_vars(plan, overrides)
    steps = render_steps(plan, variables)

    plan_id = insert_plan(plan.get("name", "CLI Plan"), yaml_text)
    run_id = insert_run(plan_id, status="running", public_id=None)
    set_run_started_now(run_id)

    runner = Runner(plan, variables, dry_run=args.dry_run)

    ok = True
    for idx, step in enumerate(steps, start=1):
        action, params = list(step.items())[0]
        step_id = insert_run_step(run_id, idx, action, input_json=str(params), status="running")
        try:
            result = runner.execute_step(action, params)
            shot = runner._screenshot(run_id, idx)
            finalize_run_step(step_id, "success", output_json=str(result), screenshot_path=shot)
        except Exception as e:  # noqa: BLE001
            ok = False
            shot = runner._screenshot(run_id, idx)
            finalize_run_step(step_id, "failed", error_message=str(e), screenshot_path=shot)
            break

    update_run(run_id, status="success" if ok else "failed")
    set_run_finished_now(run_id)
    print(f"Run #{run_id} finished: {'success' if ok else 'failed'}")


if __name__ == "__main__":
    main()
