from __future__ import annotations

from typing import Any, Dict, List
import re

REQUIRED_DSL_VERSION = "1.1"


ALLOWED_STEPS = {
    "find_files",
    "rename",
    "move_to",
    "zip_folder",
    "pdf_merge",
    "pdf_extract_pages",
    "open_preview",
    "compose_mail",
    "attach_files",
    "save_draft",
    "log",
    # Phase 2: Web Actions
    "open_browser",
    "fill_by_label",
    "click_by_text",
    "download_file",
    # Phase 3: Verifier DSL Commands
    "wait_for_element",
    "assert_element",
    "assert_text",
    "assert_file_exists",
    "assert_pdf_pages",
    "capture_screen_schema",
    # Phase 3: Web Extensions
    "upload_file",
    "wait_for_download",
    # Phase 4: HITL Commands
    "human_confirm",
}


def validate_plan(plan: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    # dsl_version
    dslv = plan.get("dsl_version")
    if dslv != REQUIRED_DSL_VERSION:
        errors.append(f"dsl_version must be '{REQUIRED_DSL_VERSION}'")
    if "name" not in plan or not plan["name"]:
        errors.append("name is required")

    # Phase 4: Validate execution policy
    if "execution" in plan:
        exec_errors = _validate_execution_policy(plan["execution"])
        errors.extend(exec_errors)

    if "steps" not in plan or not isinstance(plan["steps"], list):
        errors.append("steps must be a list")
    else:
        for i, step in enumerate(plan["steps"]):
            if not isinstance(step, dict) or len(step) != 1:
                errors.append(f"step {i} must be a single-key mapping")
                continue
            (action, params), = step.items()
            if action not in ALLOWED_STEPS:
                errors.append(f"step {i}: action '{action}' not allowed")
            if not isinstance(params, dict):
                errors.append(f"step {i}: params must be mapping")
            # when expression can reference steps[j].key where j < i
            when = params.get("when") if isinstance(params, dict) else None
            if when is not None and not isinstance(when, str):
                errors.append(f"step {i}: when must be a string expression")
            # Static validation for steps references in when: steps[n].field must have n < i
            if isinstance(when, str):
                for m in re.finditer(r"steps\s*\[\s*(\d+)\s*\]", when):
                    try:
                        ref_idx = int(m.group(1))
                        if ref_idx >= i:
                            errors.append(
                                f"step {i}: when references future step index {ref_idx}"
                            )
                    except Exception:
                        errors.append(f"step {i}: invalid steps[] index in when")

            # Phase 4: Validate human_confirm steps
            if action == "human_confirm":
                confirm_errors = _validate_human_confirm(params, i)
                errors.extend(confirm_errors)

    return errors


def _validate_execution_policy(execution: Any) -> List[str]:
    """Validate execution policy configuration."""
    errors: List[str] = []

    if not isinstance(execution, dict):
        errors.append("execution must be an object")
        return errors

    # Validate queue
    if "queue" in execution:
        if not isinstance(execution["queue"], str) or not execution["queue"]:
            errors.append("execution.queue must be a non-empty string")

    # Validate priority
    if "priority" in execution:
        priority = execution["priority"]
        if not isinstance(priority, int) or priority < 1 or priority > 9:
            errors.append("execution.priority must be an integer from 1 to 9")

    # Validate concurrency_tag
    if "concurrency_tag" in execution:
        if not isinstance(execution["concurrency_tag"], str):
            errors.append("execution.concurrency_tag must be a string")

    # Validate retry configuration
    if "retry" in execution:
        retry_errors = _validate_retry_config(execution["retry"])
        errors.extend(["execution.retry." + e for e in retry_errors])

    return errors


def _validate_retry_config(retry: Any) -> List[str]:
    """Validate retry configuration."""
    errors: List[str] = []

    if not isinstance(retry, dict):
        errors.append("must be an object")
        return errors

    # Validate attempts
    if "attempts" in retry:
        attempts = retry["attempts"]
        if not isinstance(attempts, int) or attempts < 1 or attempts > 10:
            errors.append("attempts must be an integer from 1 to 10")

    # Validate backoff_ms
    if "backoff_ms" in retry:
        backoff = retry["backoff_ms"]
        if not isinstance(backoff, int) or backoff < 100:
            errors.append("backoff_ms must be an integer >= 100")

    # Validate backoff_multiplier
    if "backoff_multiplier" in retry:
        multiplier = retry["backoff_multiplier"]
        if not isinstance(multiplier, (int, float)) or multiplier < 1.0:
            errors.append("backoff_multiplier must be a number >= 1.0")

    # Validate only_idempotent
    if "only_idempotent" in retry:
        if not isinstance(retry["only_idempotent"], bool):
            errors.append("only_idempotent must be a boolean")

    return errors


def _validate_human_confirm(params: Any, step_index: int) -> List[str]:
    """Validate human_confirm step parameters."""
    errors: List[str] = []

    if not isinstance(params, dict):
        errors.append(f"step {step_index}: human_confirm params must be an object")
        return errors

    # Validate message (required)
    if "message" not in params:
        errors.append(f"step {step_index}: human_confirm requires 'message' parameter")
    elif not isinstance(params["message"], str) or not params["message"].strip():
        errors.append(f"step {step_index}: human_confirm message must be a non-empty string")

    # Validate timeout_ms (optional)
    if "timeout_ms" in params:
        timeout = params["timeout_ms"]
        if not isinstance(timeout, int) or timeout < 1000 or timeout > 3600000:
            errors.append(f"step {step_index}: human_confirm timeout_ms must be between "
                          f"1000 and 3600000 (1 second to 1 hour)")

    # Validate auto_approve (optional)
    if "auto_approve" in params:
        if not isinstance(params["auto_approve"], bool):
            errors.append(f"step {step_index}: human_confirm auto_approve must be a boolean")

    return errors
