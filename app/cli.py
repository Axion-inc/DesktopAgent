#!/usr/bin/env python3

import argparse
import os
import secrets
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

from .dsl.parser import parse_yaml, render_value
from .dsl.validator import validate_plan
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
    insert_run_step,
    finalize_run_step,
)
from .approval import analyze_plan_risks, check_plan_approval_required
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


def run_plan(yaml_text: str, auto_approve: bool = False, template_path: str = None) -> int:
    """Run a plan and return the run ID."""
    logger = get_logger()

    plan = parse_yaml(yaml_text)
    errors = validate_plan(plan)
    if errors:
        print(f"❌ Plan validation failed: {'; '.join(errors)}")
        return -1

    # Phase 6: Template Signature Verification
    if template_path:
        from app.security.policy_engine import verify_template_before_execution
        from pathlib import Path

        template_file_path = (
            Path("plans/templates") / template_path
            if not template_path.startswith('/')
            else Path(template_path)
        )

        try:
            should_execute, policy_decision = verify_template_before_execution(template_file_path)

            # Log security decision
            logger.info(
                "Template signature policy decision: action=%s, trust_level=%s",
                policy_decision.action.value,
                policy_decision.trust_level.value,
            )

            # Handle policy decision
            if not should_execute:
                print("❌ Template execution blocked by security policy:")
                for reason in policy_decision.reasons:
                    print(f"   • {reason}")
                return -1

            # Show warnings if any
            if policy_decision.warnings:
                print("⚠️  Template security warnings:")
                for warning in policy_decision.warnings:
                    print(f"   • {warning}")

            # Handle confirmation requirement
            if policy_decision.requires_confirmation and not auto_approve:
                print(f"🔐 Template requires manual approval due to trust level: {policy_decision.trust_level.value}")
                print("   Use --auto-approve to bypass this requirement.")
                return -1
            elif policy_decision.requires_confirmation and auto_approve:
                print(
                    f"⚠️  Auto-approving template with trust level: {policy_decision.trust_level.value}"
                )

            # Log successful verification
            print(
                f"✅ Template signature verified (trust level: {policy_decision.trust_level.value})"
            )

        except Exception as e:
            logger.error(f"Template security verification failed: {e}")
            print(f"❌ Template security verification failed: {e}")
            return -1

    # Phase 6: Template Manifest Validation (skip in POLICY_ONLY mode)
    if template_path and os.environ.get("POLICY_ONLY", "0") not in ("1", "true", "True"):
        from app.security.template_manifest import get_manifest_manager

        try:
            manifest_manager = get_manifest_manager()

            # Check for manifest file
            template_file_path = (
                Path("plans/templates") / template_path
                if not template_path.startswith('/')
                else Path(template_path)
            )
            manifest_path = template_file_path.parent / f"{template_file_path.stem}.manifest.json"

            if manifest_path.exists():
                # Load and validate manifest
                manifest = manifest_manager.load_manifest(manifest_path)
                if manifest:
                    vm = manifest_manager.validate_manifest(manifest)
                    # Backward-compat: accept ValidationResult or (bool, errors)
                    try:
                        is_valid, errors = vm  # type: ignore[misc]
                    except Exception:
                        is_valid = bool(getattr(vm, 'is_valid', False))
                        err_msg = getattr(vm, 'error_message', None)
                        errors = [e.strip() for e in str(err_msg).split(';') if e.strip()] if err_msg else []
                    if not is_valid:
                        print("❌ Template manifest validation failed:")
                        for error in errors:
                            print(f"   • {error}")
                        return -1

                    # Check capability compliance
                    compliant, violations, warnings = manifest_manager.check_capability_compliance(manifest, yaml_text)

                    if violations:
                        print("❌ Template violates declared capabilities:")
                        for violation in violations:
                            print(f"   • {violation}")
                        return -1

                    if warnings:
                        print("⚠️  Template capability warnings:")
                        for warning in warnings:
                            print(f"   • {warning}")

                    caps = manifest.get('required_capabilities', []) if isinstance(manifest, dict) else []
                    print(f"✅ Template manifest validated ({len(caps)} capabilities declared)")
                else:
                    print("⚠️  Could not load template manifest")
            else:
                # Generate manifest automatically for templates without one
                print("⚠️  No manifest found for template, generating one...")
                success, message, generated_path = manifest_manager.generate_manifest_from_template(template_file_path)
                if success:
                    print(f"📄 Generated manifest: {generated_path}")
                else:
                    print(f"❌ Failed to generate manifest: {message}")

        except Exception as e:
            logger.error(f"Template manifest validation failed: {e}")
            print(f"❌ Template manifest validation failed: {e}")
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

    # Check permissions (skip in POLICY_ONLY mode to allow policy-only runs in sandbox)
    if os.environ.get("POLICY_ONLY", "0") not in ("1", "true", "True"):
        from .permissions import check_permissions  # lazy import to avoid macOS adapter on import
        perms = check_permissions()
        mail_status = perms.get("automation_mail", {}).get("status")
        strict = os.environ.get("PERMISSIONS_STRICT", "0") in ("1", "true", "True")
        screen_status = perms.get("screen_recording", {}).get("status")

        if mail_status == "fail" or (strict and screen_status != "ok"):
            print("❌ Permission check failed. Cannot run plan.")
            return -1

    # Phase 7: Policy evaluation (block-before-exec)
    # Prepare rendered steps first (used to infer URL/risks)
    variables = plan.get("variables", {})
    rendered_steps = []
    for step in plan.get("steps", []):
        action, params = list(step.items())[0]
        rendered_steps.append({action: render_value(params, variables)})

    autopilot_allowed = False
    try:
        # Load policy config
        from app.policy.engine import PolicyEngine
        from app.policy.execution_guard import check_pre_execution
        import yaml as _yaml

        pol_doc: Dict[str, Any] = {}
        pol_path = Path('configs/policy.yaml')
        if pol_path.exists():
            try:
                pol_doc = _yaml.safe_load(pol_path.read_text(encoding='utf-8')) or {}
            except Exception:
                pol_doc = {}

        pe = PolicyEngine.from_file(str(pol_path)) if pol_path.exists() else PolicyEngine({})

        # Best-effort inference from plan for guard checks
        #  - URLs (from open_browser)
        #  - Risks (simple mapping)
        #  - Capabilities (via manifest analyzer as needed)
        url = ''
        urls: List[str] = []
        risks = set()
        caps = set(['webx'])
        for step in rendered_steps:
            action, params = list(step.items())[0]
            if action == 'open_browser':
                u = str(params.get('url', ''))
                if u:
                    url = u
                    urls.append(u)
            if action in ('click_by_text', 'download_file', 'upload_file'):
                risks.add('sends')

        # Signature: rely on prior verification if template_path provided, else assume true for internal templates
        signed = True

        # Evaluate concise policy allow/autopilot decision
        now_iso = datetime.now().astimezone().isoformat()
        decision = pe.evaluate(url=url, risks=risks, now_iso=now_iso, signed=signed, capabilities=caps)

        # Run detailed guard for audit + UI checks
        manifest_for_guard: Dict[str, Any] = {
            'required_capabilities': list(caps),
            'risk_flags': list(risks),
            'signature_verified': signed,
        }
        guard = check_pre_execution(manifest_for_guard, urls, pol_doc)

        # Record policy guard step with full check details
        pol_step_id = insert_run_step(
            run_id,
            0,
            'policy_guard',
            input_json=json_dumps({'url': url, 'risks': list(risks), 'caps': list(caps)}),
            status='running'
        )

        if not decision.allowed or not guard.allowed:
            # guard already increments metrics + writes audit on block
            finalize_run_step(pol_step_id, 'failed', output_json=json_dumps({
                'allowed': False,
                'reason': decision.reason or '; '.join(guard.reasons),
                'checks': guard.checks
            }))
            update_run(run_id, status='blocked')
            print("❌ Blocked by policy:")
            # Prefer detailed reasons if available
            reasons_out = guard.reasons or ([decision.reason] if decision.reason else [])
            for r in reasons_out:
                print(f"   • {r}")
            set_run_finished_now(run_id)
            return -1
        else:
            finalize_run_step(pol_step_id, 'success', output_json=json_dumps({
                'allowed': True,
                'autopilot': decision.autopilot,
                'checks': guard.checks
            }))

        if decision.autopilot:
            autopilot_allowed = True
            from app.metrics import get_metrics_collector
            get_metrics_collector().mark_l4_autorun()
        # Optional: stop after policy guard (no step execution), useful for CI/sandbox
        if os.environ.get("POLICY_ONLY", "0") in ("1", "true", "True"):
            update_run(run_id, status="success")
            set_run_finished_now(run_id)
            print("✅ Policy guard passed; stopping due to POLICY_ONLY=1")
            return run_id
    except Exception as e:
        logger.warning(f"Policy evaluation skipped due to error: {e}")

    # Execute the plan
    update_run(run_id, status="running")
    logger.info("run.start id=%s", run_id)
    set_run_started_now(run_id)

    # rendered_steps/variables are already prepared above for policy; reuse them

    # Lazy import to avoid heavy dependencies before policy passes
    from .dsl.runner import Runner
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

            # Capture DOM schema artifact for this step (best-effort)
            schema_path = None
            try:
                from app.desktop.inspect import desktop_inspect as _desktop_inspect
                insp_obj = _desktop_inspect()
                schema_path = insp_obj.get('schema')
            except Exception:
                schema_path = None

            result_with_diff = {**result}
            if schema_path:
                result_with_diff.setdefault('_artifacts', {})['schema'] = schema_path
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
            print(f"⚠️  Step {idx} failed: {e}")
            logger.error("run.step.failed id=%s idx=%s action=%s err=%s", run_id, idx, action, e)
            # Phase 7: Attempt Planner L2 auto-adoption (low-risk) if autopilot is allowed
            auto_adopted = False
            if autopilot_allowed:
                try:
                    from app.desktop.inspect import desktop_inspect
                    from app.planner.l2 import propose_patches, should_adopt_patch
                    import json as _json, yaml as _yaml
                    insp = desktop_inspect()
                    failure_ctx = {"type": action, "goal": params.get('text') or params.get('label'), "role": params.get('role')}
                    try:
                        schema_obj = _json.loads(Path(insp['schema']).read_text(encoding='utf-8'))
                    except Exception:
                        schema_obj = {"elements": []}
                    patch = propose_patches(schema_obj, failure_ctx)
                    # load adopt policy
                    adopt_policy = {"low_risk_auto": True, "min_confidence": 0.85}
                    pol_path = Path('configs/policy.yaml')
                    if pol_path.exists():
                        try:
                            pol_doc = _yaml.safe_load(pol_path.read_text(encoding='utf-8')) or {}
                            ap = pol_doc.get('adopt_policy') or {}
                            if isinstance(ap, dict):
                                adopt_policy.update(ap)
                        except Exception:
                            pass
                    adopt = should_adopt_patch(patch, adopt_policy)
                    if adopt:
                        # Apply minimal, safe substitutions then retry once
                        for repl in patch.get('replace_text', []) or []:
                            if action in ('click_by_text', 'fill_by_label') and params.get('text') == repl.get('find'):
                                params['text'] = repl.get('with')
                        for wt in patch.get('wait_tuning', []) or []:
                            if action == 'wait_for_element' and wt.get('timeout_ms'):
                                params['timeout_ms'] = wt.get('timeout_ms')
                        # Retry
                        retry_result = runner.execute_step_with_diff(action, params)
                        shot2 = runner._screenshot(run_id, idx)
                        out2 = {**retry_result, "_adopted": True, "_patch": patch}
                        if idx <= len(runner.step_diffs):
                            out2["_diff"] = runner.step_diffs[idx - 1]
                        models.finalize_run_step(step_id, "success", output_json=json_dumps(out2), screenshot_path=shot2)
                        print(f"✅ Step {idx} recovered via Planner L2 adoption")
                        auto_adopted = True
                    # Save artifact regardless
                    artifacts_dir = Path("artifacts/patches")
                    artifacts_dir.mkdir(parents=True, exist_ok=True)
                    (artifacts_dir / f"run_{run_id}_step_{idx}_patch.json").write_text(
                        _json.dumps({
                            "version": 1,
                            "saved_at": datetime.now().astimezone().isoformat(),
                            "run_id": run_id,
                            "step_index": idx,
                            "failure": failure_ctx,
                            "proposal": patch,
                            "adopt_policy": adopt_policy,
                            "adopt": adopt,
                            "evidence": {"screenshot": insp.get('screenshot'), "schema": insp.get('schema')}
                        }, ensure_ascii=False, indent=2), encoding='utf-8')
                except Exception as _e:
                    logger.warning(f"planner L2 auto-adopt skipped: {_e}")
            if auto_adopted:
                continue
            # Finalize as failed and proceed to pause
            ok = False
            shot = runner._screenshot(run_id, idx)
            # Attempt to capture DOM schema as artifact
            fail_schema_path = None
            try:
                from app.desktop.inspect import desktop_inspect as _desktop_inspect
                finsp = _desktop_inspect()
                fail_schema_path = finsp.get('schema')
            except Exception:
                fail_schema_path = None
            fail_out = {"_failed": True}
            if fail_schema_path:
                fail_out["_artifacts"] = {"schema": fail_schema_path}
            models.finalize_run_step(step_id, "failed", output_json=json_dumps(fail_out), screenshot_path=shot, error_message=str(e))
            print(f"❌ Step {idx} failed: {e}")
            # Phase 7: L4 deviation operational wiring - pause & HITL resume
            try:
                from app.autopilot.runner import AutoRunner
                auto = AutoRunner()
                verdict = auto.check_deviation([{"status": "FAIL"}], current_url=variables.get('url', ''), expected_domain='')
                if verdict.should_pause:
                    # Create resume point and mark run paused
                    from app.orchestrator.resume import get_resume_manager, RunStatus
                    resume_manager = get_resume_manager()
                    resume_manager.create_resume_point(
                        run_id=run_id,
                        step_index=idx,
                        step_name=action,
                        runner_state=runner.state,
                        reason='hitl'
                    )
                    # Persist deviation classification
                    try:
                        from . import models as _models
                        _models.insert_deviation(run_id, idx, deviation_type=verdict.reason or 'unknown', reason=str(e))
                    except Exception:
                        pass
                    # Planner L2 artifact capture (schema/screenshot/patch JSON)
                    try:
                        from app.desktop.inspect import desktop_inspect
                        from app.planner.l2 import propose_patches, should_adopt_patch
                        import json as _json
                        # Capture desktop snapshot for context
                        insp = desktop_inspect()
                        # Build failure context
                        failure_ctx = {"type": action, "goal": params.get('text') or params.get('label'), "role": params.get('role')}
                        # Load schema JSON
                        schema_obj = {}
                        try:
                            import json as __json
                            schema_obj = __json.loads(Path(insp['schema']).read_text(encoding='utf-8'))
                        except Exception:
                            schema_obj = {"elements": []}
                        patch = propose_patches(schema_obj, failure_ctx)
                        # Adoption policy from policy.yaml
                        adopt_policy = {"low_risk_auto": True, "min_confidence": 0.85}
                        try:
                            import yaml as __yaml
                            pol_path = Path('configs/policy.yaml')
                            if pol_path.exists():
                                p = __yaml.safe_load(pol_path.read_text(encoding='utf-8')) or {}
                                adopt_policy.update(p.get('adopt_policy', {}))
                        except Exception:
                            pass
                        adopt = should_adopt_patch(patch, adopt_policy)
                        # Save artifact JSON
                        artifacts_dir = Path("artifacts/patches")
                        artifacts_dir.mkdir(parents=True, exist_ok=True)
                        out_json = artifacts_dir / f"run_{run_id}_step_{idx}_patch.json"
                        out_json.write_text(_json.dumps({
                            "run_id": run_id,
                            "step_index": idx,
                            "failure": failure_ctx,
                            "proposal": patch,
                            "adopt_policy": adopt_policy,
                            "adopt": adopt,
                            "evidence": {
                                "screenshot": insp.get('screenshot'),
                                "schema": insp.get('schema')
                            }
                        }, ensure_ascii=False, indent=2), encoding='utf-8')
                        print(f"📝 Patch proposal saved: {out_json}")
                    except Exception as __e:
                        logger.warning(f"planner L2 artifact capture skipped: {__e}")
                    update_run(run_id, status="paused")
                    print("⏸️  Run paused for HITL resume (deviation detected)")
                    # Slack/Webhook notification happens in AutoRunner.notify()
            except Exception as _e:
                logger.warning(f"deviation/pausing skipped: {_e}")
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

    # Manifest commands
    manifest_parser = subparsers.add_parser("manifest", help="Template manifest operations")
    manifest_subparsers = manifest_parser.add_subparsers(dest="manifest_command", help="Manifest commands")

    # Generate manifest command
    gen_manifest_parser = manifest_subparsers.add_parser("generate", help="Generate manifest for template")
    gen_manifest_parser.add_argument("template_file", help="Template YAML file path")
    gen_manifest_parser.add_argument("--output-dir", help="Output directory for manifest file")

    # Validate manifest command
    val_manifest_parser = manifest_subparsers.add_parser("validate", help="Validate template manifest")
    val_manifest_parser.add_argument("manifest_file", help="Manifest JSON file path")

    # List capabilities command
    manifest_subparsers.add_parser("capabilities", help="List available capabilities")

    # Desktop inspect (Phase 4 helper)
    insp = subparsers.add_parser("desktop-inspect", help="Capture desktop screenshot and schema")
    insp.add_argument("--output-dir", dest="output_dir", help="Directory to save artifacts")
    insp.add_argument("--target", dest="target", default="frontmost", choices=["frontmost", "screen"], help="Schema target")
    # Desktop watch
    watchp = subparsers.add_parser("desktop-watch", help="Poll desktop schema/screenshot and report changes")
    watchp.add_argument("--interval", type=float, default=2.0, help="Seconds between captures")
    watchp.add_argument("--iterations", type=int, default=10, help="Number of captures")
    watchp.add_argument("--output-dir", dest="output_dir", help="Directory to save artifacts")
    watchp.add_argument("--target", dest="target", default="frontmost", choices=["frontmost", "screen"], help="Schema target")

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
        # Extract template filename for signature verification
        template_path = Path(args.file).name if "plans/templates" in args.file else args.file
        run_id = run_plan(yaml_text, args.auto_approve, template_path)

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

    elif args.command == "manifest":
        if not args.manifest_command:
            print("❌ Please specify a manifest command (generate, validate, capabilities)")
            return

        from app.security.template_manifest import get_manifest_manager
        manifest_manager = get_manifest_manager()

        if args.manifest_command == "generate":
            if not os.path.exists(args.template_file):
                print(f"❌ Template file '{args.template_file}' not found")
                return

            template_path = Path(args.template_file)
            output_dir = Path(args.output_dir) if args.output_dir else None

            success, message, manifest_path = manifest_manager.generate_manifest_from_template(
                template_path, output_dir
            )

            if success:
                print(f"✅ {message}")
                print(f"📄 Manifest saved to: {manifest_path}")
            else:
                print(f"❌ {message}")

        elif args.manifest_command == "validate":
            if not os.path.exists(args.manifest_file):
                print(f"❌ Manifest file '{args.manifest_file}' not found")
                return

            manifest_path = Path(args.manifest_file)
            manifest = manifest_manager.load_manifest(manifest_path)

            if not manifest:
                print("❌ Failed to load manifest file")
                return

            is_valid, errors = manifest_manager.validate_manifest(manifest)

            if is_valid:
                print("✅ Manifest is valid")
                print(f"📦 Template: {manifest.name} v{manifest.version}")
                print(f"👤 Author: {manifest.author} <{manifest.author_email}>")
                print(f"🔧 Capabilities: {len(manifest.capabilities)}")

                # Show capabilities
                for cap in manifest.capabilities:
                    risk_emoji = {"low": "🟢", "medium": "🟡", "high": "🟠", "critical": "🔴"}
                    emoji = risk_emoji.get(cap.risk_level.value, "⚪")
                    print(f"  {emoji} {cap.name} ({cap.risk_level.value}): {cap.description}")

            else:
                print("❌ Manifest validation failed:")
                for error in errors:
                    print(f"  • {error}")

        elif args.manifest_command == "capabilities":
            capabilities = manifest_manager.list_available_capabilities()

            print("🔧 Available Template Capabilities:")
            print()

            for cap in sorted(capabilities, key=lambda x: x["name"]):
                risk_emoji = {"low": "🟢", "medium": "🟡", "high": "🟠", "critical": "🔴"}
                emoji = risk_emoji.get(cap["default_risk_level"], "⚪")
                confirmation = " (requires confirmation)" if cap["requires_confirmation"] else ""

                print(f"{emoji} {cap['name']} ({cap['default_risk_level']}){confirmation}")
                print(f"   {cap['description']}")
                print(f"   Actions: {', '.join(cap['actions'])}")
                print()

    elif args.command == "desktop-inspect":
        from .desktop.inspect import desktop_inspect
        try:
            res = desktop_inspect(output_dir=args.output_dir, target=args.target)
            print("✅ Desktop inspection captured")
            print(f"  Dir: {res['dir']}")
            print(f"  Screenshot: {res['screenshot']}")
            print(f"  Schema: {res['schema']}")
        except Exception as e:
            print(f"❌ Desktop inspection failed: {e}")

    elif args.command == "desktop-watch":
        from .desktop.watch import desktop_watch
        try:
            desktop_watch(interval_sec=args.interval, iterations=args.iterations, target=args.target, output_dir=args.output_dir)
        except Exception as e:
            print(f"❌ Desktop watch failed: {e}")


if __name__ == "__main__":
    main()
