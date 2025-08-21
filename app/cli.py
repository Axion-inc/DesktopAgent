#!/usr/bin/env python3

import argparse
import os
import secrets
from pathlib import Path
from typing import Dict, Any, Optional, List

from .dsl.parser import parse_yaml, render_value
from .dsl.validator import validate_plan
from .dsl.runner import Runner
from .dsl.parser import render_string
from .models import (
    init_db,
    insert_plan,
    insert_run,
    get_run,
    get_run_steps,
    list_runs,
    update_run,
    set_run_started_now,
    set_run_finished_now,
    create_plan_approval,
    approve_plan,
    log_approval_action,
)
from .approval import analyze_plan_risks, check_plan_approval_required
from .permissions import check_permissions
from .utils import json_dumps, get_logger


def load_templates() -> List[Dict[str, Any]]:
    """Get list of available plan templates."""
    templates_dir = Path("plans/templates")
    if not templates_dir.exists():
        return []

    templates = []
    for file_path in templates_dir.glob("*.yaml"):
        try:
            content = file_path.read_text(encoding="utf-8")
            name = file_path.stem
            if 'name:' in content:
                for line in content.split('\n'):
                    if line.strip().startswith('name:'):
                        name = line.split(':', 1)[1].strip(' "\'')
                        break

            templates.append({
                "filename": file_path.name,
                "name": name,
                "path": str(file_path)
            })
        except Exception:
            continue

    return templates


def load_template(filename: str) -> Optional[str]:
    """Load template content by filename."""
    templates_dir = Path("plans/templates")
    file_path = templates_dir / filename

    if not file_path.exists() or not file_path.is_file():
        return None

    try:
        return file_path.read_text(encoding="utf-8")
    except Exception:
        return None


def validate_yaml(yaml_text: str) -> Dict[str, Any]:
    """Validate YAML plan and return validation result."""
    try:
        plan = parse_yaml(yaml_text)
    except ValueError as e:
        return {"ok": False, "errors": [str(e)]}

    errors = validate_plan(plan)
    if errors:
        return {"ok": False, "errors": errors}

    # Render variables
    variables = plan.get("variables", {})
    rendered_steps = []
    for step in plan.get("steps", []):
        action, params = list(step.items())[0]
        rendered_steps.append({action: render_value(params, variables)})

    # naive estimation: number of steps * 250ms
    est_ms = max(250, 250 * max(1, len(plan.get("steps", []))))
    summary = {"destructive": False, "estimated_ms": est_ms}

    return {
        "ok": True,
        "name": plan.get("name"),
        "steps": rendered_steps,
        "summary": summary,
        "plan": plan
    }


def run_plan(yaml_text: str, auto_approve: bool = False) -> int:
    """Run a plan and return the run ID."""
    logger = get_logger()

    plan = parse_yaml(yaml_text)
    errors = validate_plan(plan)
    if errors:
        print(f"❌ Plan validation failed: {'; '.join(errors)}")
        return -1

    # Check if approval is required
    approval_required = check_plan_approval_required(plan)

    pid = insert_plan(plan.get("name", "Unnamed"), yaml_text)

    # Record approval workflow via CLI (no UI)
    if approval_required and not auto_approve:
        # Log that approval is required and block execution
        risk_analysis = analyze_plan_risks(plan)
        appr_id = create_plan_approval(pid, json_dumps(risk_analysis))
        # Decision is pending; count as required request in metrics via a single log row
        log_approval_action(
            plan_id=pid,
            action="plan_review",
            risk_level=risk_analysis.get("risk_level", "unknown"),
            approved_by="",
            decision="required",
            reason="blocked_by_cli_no_auto_approve",
            run_id=None,
        )
        print("❌ Plan requires approval. Re-run with --auto-approve to proceed.")
        return -1

    if approval_required and auto_approve:
        # Create approval request and auto-approve, then log decision
        risk_analysis = analyze_plan_risks(plan)
        appr_id = create_plan_approval(pid, json_dumps(risk_analysis))
        approver = os.environ.get("CLI_APPROVER", "cli-auto")
        approve_plan(appr_id, approver)
        log_approval_action(
            plan_id=pid,
            action="plan_review",
            risk_level=risk_analysis.get("risk_level", "unknown"),
            approved_by=approver,
            decision="approved",
            reason="auto_approved_by_cli",
            run_id=None,
        )
        print("⚠️  Auto-approved plan with risks (logged by CLI).")

    # Create run
    run_id = insert_run(
        pid,
        status="pending",
        public_id=secrets.token_hex(8),
    )
    # Attach approver info to run if available
    if approval_required and auto_approve:
        update_run(run_id, approved_by=os.environ.get("CLI_APPROVER", "cli-auto"))

    # Check permissions
    perms = check_permissions()
    mail_status = perms.get("automation_mail", {}).get("status")
    strict = os.environ.get("PERMISSIONS_STRICT", "0") in ("1", "true", "True")
    screen_status = perms.get("screen_recording", {}).get("status")

    if mail_status == "fail" or (strict and screen_status != "ok"):
        print("❌ Permission check failed. Cannot run plan.")
        return -1

    # Execute the plan
    update_run(run_id, status="running")
    logger.info("run.start id=%s", run_id)
    set_run_started_now(run_id)

    variables = plan.get("variables", {})
    rendered_steps = []
    for step in plan.get("steps", []):
        action, params = list(step.items())[0]
        rendered_steps.append({action: render_value(params, variables)})

    runner = Runner(plan, variables, dry_run=False)
    from . import models

    ok = True
    for idx, step in enumerate(rendered_steps, start=1):
        action, params = list(step.items())[0]
        print(f"🔄 Step {idx}: {action}")

        step_id = models.insert_run_step(
            run_id,
            idx,
            action,
            input_json=json_dumps(params),
            status="running",
        )

        try:
            result = runner.execute_step_with_diff(action, params)
            shot = runner._screenshot(run_id, idx)

            result_with_diff = {**result}
            if idx <= len(runner.step_diffs):
                result_with_diff["_diff"] = runner.step_diffs[idx - 1]

            models.finalize_run_step(
                step_id,
                "success",
                output_json=json_dumps(result_with_diff),
                screenshot_path=shot,
            )
            print(f"✅ Step {idx} completed")
            logger.info("run.step.success id=%s idx=%s action=%s", run_id, idx, action)
        except Exception as e:
            ok = False
            shot = runner._screenshot(run_id, idx)
            models.finalize_run_step(
                step_id,
                "failed",
                error_message=str(e),
                screenshot_path=shot,
            )
            print(f"❌ Step {idx} failed: {e}")
            logger.error("run.step.failed id=%s idx=%s action=%s err=%s", run_id, idx, action, e)
            break

    if ok:
        update_run(run_id, status="success")
        print("✅ Plan completed successfully")
        logger.info("run.finish id=%s status=success", run_id)
    else:
        update_run(run_id, status="failed")
        print("❌ Plan failed")
        logger.info("run.finish id=%s status=failed", run_id)

    set_run_finished_now(run_id)
    return run_id


def run_csv_form(yaml_text: str, auto_approve: bool = False, limit: int = 100) -> int:
    """Run a CSV→Webフォーム転記（承認つき）テンプレをCSVの各行で反復実行する。

    要件:
      - テンプレの steps は open_browser/fill_by_label/click_by_text を含むこと
      - 文字列内に {{row.<col>}} を含んでよい（行ごとに置換）
    """
    logger = get_logger()

    plan = parse_yaml(yaml_text)
    errors = validate_plan(plan)
    if errors:
        print(f"❌ Plan validation failed: {'; '.join(errors)}")
        return -1

    # 事前承認チェック
    approval_required = check_plan_approval_required(plan)
    pid = insert_plan(plan.get("name", "Unnamed"), yaml_text)

    if approval_required and not auto_approve:
        risk = analyze_plan_risks(plan)
        create_plan_approval(pid, json_dumps(risk))
        log_approval_action(
            plan_id=pid,
            action="plan_review",
            risk_level=risk.get("risk_level", "unknown"),
            approved_by="",
            decision="required",
            reason="blocked_by_cli_no_auto_approve",
            run_id=None,
        )
        print("❌ Plan requires approval. Re-run with --auto-approve to proceed.")
        return -1

    if approval_required and auto_approve:
        risk = analyze_plan_risks(plan)
        appr_id = create_plan_approval(pid, json_dumps(risk))
        approver = os.environ.get("CLI_APPROVER", "cli-auto")
        approve_plan(appr_id, approver)
        log_approval_action(
            plan_id=pid,
            action="plan_review",
            risk_level=risk.get("risk_level", "unknown"),
            approved_by=approver,
            decision="approved",
            reason="auto_approved_by_cli",
            run_id=None,
        )
        print("⚠️  Auto-approved plan with risks (logged by CLI).")

    # Run作成
    run_id = insert_run(pid, status="pending", public_id=secrets.token_hex(8))
    if approval_required and auto_approve:
        update_run(run_id, approved_by=os.environ.get("CLI_APPROVER", "cli-auto"))

    logger.info("run.start id=%s csv_form batch", run_id)
    set_run_started_now(run_id)
    update_run(run_id, status="running")

    # CSVロード
    variables = plan.get("variables", {})
    csv_path = variables.get("csv_file") or variables.get("csv")
    if not csv_path:
        print("❌ variables.csv_file (or csv) が設定されていません")
        update_run(run_id, status="failed")
        set_run_finished_now(run_id)
        return -1

    csv_abspath = Path(render_string(str(csv_path), variables)).expanduser()
    if not csv_abspath.exists():
        print(f"❌ CSVが見つかりません: {csv_abspath}")
        update_run(run_id, status="failed")
        set_run_finished_now(run_id)
        return -1

    # 1レコードあたりに実行するステップを抽出（open→fill×4→click など）
    steps = plan.get("steps", [])

    # Runner初期化
    runner = Runner(plan, variables, dry_run=False)
    from . import models

    import csv
    processed = 0
    idx = 1
    ok = True

    try:
        with csv_abspath.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if processed >= limit:
                    break

                # 各レコードでフォームを開く（再現性重視）
                for step in steps:
                    action, params = list(step.items())[0]
                    # レコード用の変数コンテキスト
                    ctx_vars = {**variables, "row": row}
                    rendered_params = render_value(params, ctx_vars)

                    # when条件（文字列）に対応: render_string後にsafe_evalはRunner側で処理
                    step_id = models.insert_run_step(
                        run_id,
                        idx,
                        action,
                        input_json=json_dumps(rendered_params),
                        status="running",
                    )

                    try:
                        result = runner.execute_step_with_diff(action, rendered_params)
                        shot = runner._screenshot(run_id, idx)
                        result_with_diff = {**result}
                        if idx <= len(runner.step_diffs):
                            result_with_diff["_diff"] = runner.step_diffs[idx - 1]
                        models.finalize_run_step(
                            step_id,
                            "success",
                            output_json=json_dumps(result_with_diff),
                            screenshot_path=shot,
                        )
                    except Exception as e:
                        ok = False
                        shot = runner._screenshot(run_id, idx)
                        models.finalize_run_step(
                            step_id,
                            "failed",
                            error_message=str(e),
                            screenshot_path=shot,
                        )
                        print(f"❌ Row {processed+1} step failed: {e}")
                        break

                    idx += 1

                if not ok:
                    break
                processed += 1

    except Exception as e:
        ok = False
        print(f"❌ CSV処理中にエラー: {e}")

    if ok:
        update_run(run_id, status="success")
        print(f"✅ CSV to Form completed. processed={processed}")
        logger.info("run.finish id=%s status=success processed=%s", run_id, processed)
    else:
        update_run(run_id, status="failed")
        print("❌ Plan failed during CSV processing")
        logger.info("run.finish id=%s status=failed", run_id)

    set_run_finished_now(run_id)
    return run_id


def show_run_details(run_id: int):
    """Show details of a specific run."""
    run = get_run(run_id)
    if not run:
        print(f"❌ Run {run_id} not found")
        return

    steps = get_run_steps(run_id)

    print(f"\n📋 Run {run_id} - {run['status'].upper()}")
    print(f"Plan: {run['plan_name']}")
    print(f"Started: {run['started_at'] or 'Not started'}")
    print(f"Finished: {run['finished_at'] or 'Not finished'}")

    if steps:
        print("\n📝 Steps:")
        for step in steps:
            status_icon = {"success": "✅", "failed": "❌", "running": "🔄"}.get(step["status"], "⚪")
            print(f"  {status_icon} {step['idx']}. {step['name']}")
            if step["status"] == "failed" and step["error_message"]:
                print(f"     Error: {step['error_message']}")


def list_all_runs():
    """List all runs."""
    runs = list_runs()

    if not runs:
        print("📭 No runs found")
        return

    print("📋 All Runs:")
    print(f"{'ID':<5} {'Status':<12} {'Plan Name':<30} {'Started':<20}")
    print("-" * 70)

    for run in runs:
        started = run['started_at'][:19] if run['started_at'] else 'Not started'
        print(f"{run['id']:<5} {run['status']:<12} {run['plan_name'][:29]:<30} {started:<20}")


def main():
    """CLI entry point."""
    init_db()

    parser = argparse.ArgumentParser(description="Desktop Agent CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Templates command
    subparsers.add_parser("templates", help="List available templates")

    # Template command
    template_parser = subparsers.add_parser("template", help="Show template content")
    template_parser.add_argument("filename", help="Template filename")

    # Validate command
    validate_parser = subparsers.add_parser("validate", help="Validate a YAML plan")
    validate_parser.add_argument("file", help="YAML file path")

    # Run command
    run_parser = subparsers.add_parser("run", help="Run a YAML plan")
    run_parser.add_argument("file", help="YAML file path")
    run_parser.add_argument("--auto-approve", action="store_true", help="Auto-approve plans requiring approval")

    # Run CSV→Form command
    run_csv_parser = subparsers.add_parser("run-csv-form", help="Run CSV→Form template over each CSV row")
    run_csv_parser.add_argument("file", help="YAML file path (e.g., plans/templates/csv_to_form.yaml)")
    run_csv_parser.add_argument("--limit", type=int, default=100, help="Max records to process")
    run_csv_parser.add_argument("--auto-approve", action="store_true", help="Auto-approve risky steps (Submit)")

    # Show command
    show_parser = subparsers.add_parser("show", help="Show run details")
    show_parser.add_argument("run_id", type=int, help="Run ID")

    # List command
    subparsers.add_parser("list", help="List all runs")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    if args.command == "templates":
        templates = load_templates()
        if not templates:
            print("📭 No templates found")
        else:
            print("📁 Available Templates:")
            for template in templates:
                print(f"  • {template['name']} ({template['filename']})")

    elif args.command == "template":
        content = load_template(args.filename)
        if content is None:
            print(f"❌ Template '{args.filename}' not found")
        else:
            print(content)

    elif args.command == "validate":
        if not os.path.exists(args.file):
            print(f"❌ File '{args.file}' not found")
            return

        yaml_text = Path(args.file).read_text(encoding="utf-8")
        result = validate_yaml(yaml_text)

        if result["ok"]:
            print("✅ Plan is valid")
            print(f"Name: {result['name']}")
            print(f"Steps: {len(result['steps'])}")
            print(f"Estimated duration: {result['summary']['estimated_ms']}ms")
        else:
            print("❌ Plan validation failed:")
            for error in result["errors"]:
                print(f"  • {error}")

    elif args.command == "run":
        if not os.path.exists(args.file):
            print(f"❌ File '{args.file}' not found")
            return

        yaml_text = Path(args.file).read_text(encoding="utf-8")
        run_id = run_plan(yaml_text, args.auto_approve)

        if run_id > 0:
            print(f"\n🔗 Run ID: {run_id}")

    elif args.command == "run-csv-form":
        if not os.path.exists(args.file):
            print(f"❌ File '{args.file}' not found")
            return

        yaml_text = Path(args.file).read_text(encoding="utf-8")
        run_id = run_csv_form(yaml_text, args.auto_approve, args.limit)
        if run_id > 0:
            print(f"\n🔗 Run ID: {run_id}")

    elif args.command == "show":
        show_run_details(args.run_id)

    elif args.command == "list":
        list_all_runs()


if __name__ == "__main__":
    main()
