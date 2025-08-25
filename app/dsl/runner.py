from __future__ import annotations

import platform
from pathlib import Path
from typing import Any, Dict, Tuple, List

from app.actions import fs_actions
from app.os_adapters.base import MailAdapter, PreviewAdapter
from app.os_adapters.macos import MacMailAdapter, MacPreviewAdapter
from app.os_adapters.windows import WindowsMailAdapter, WindowsPreviewAdapter
from app.utils import take_screenshot
from .parser import safe_eval


def get_adapters() -> Tuple[MailAdapter, PreviewAdapter]:
    if platform.system() == "Darwin":
        return MacMailAdapter(), MacPreviewAdapter()
    else:
        return WindowsMailAdapter(), WindowsPreviewAdapter()


class Runner:
    def __init__(self, plan: Dict[str, Any], variables: Dict[str, Any], dry_run: bool = False):
        self.plan = plan
        self.vars = variables
        self.dry_run = dry_run
        self.mail, self.preview = get_adapters()
        self.state: Dict[str, Any] = {
            "files": [],
            "draft_id": None,
        }
        self.step_results: List[Dict[str, Any]] = []
        self.step_diffs: List[Dict[str, Any]] = []  # Track before/after state for replay UI

    def _resolve_secrets_in_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve secrets:// references in step parameters."""
        try:
            from app.security.secrets import get_secrets_manager
            secrets_manager = get_secrets_manager()

            # Convert params to JSON string, resolve secrets, then parse back
            import json
            params_str = json.dumps(params)
            resolved_str = secrets_manager.resolve_template(params_str)
            return json.loads(resolved_str)

        except ImportError:
            # Secrets not available, return params as-is
            return params
        except Exception as e:
            # Log error but don't break execution
            print(f"Warning: Failed to resolve secrets in parameters: {e}")
            return params

    def _mask_secrets_in_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Mask secrets:// references in step parameters for safe logging."""
        try:
            from app.security.secrets import get_secrets_manager
            secrets_manager = get_secrets_manager()

            # Convert params to JSON string, mask secrets, then parse back
            import json
            params_str = json.dumps(params)
            masked_str = secrets_manager.resolve_for_logging(params_str)
            return json.loads(masked_str)

        except ImportError:
            # Secrets not available, return params as-is
            return params
        except Exception as e:
            # Log error but don't break execution
            print(f"Warning: Failed to mask secrets in parameters: {e}")
            return params

    def _screenshot(self, run_id: int, idx: int) -> str:
        screenshot_path = take_screenshot(f"{run_id}_{idx}.png")

        # Also take web screenshot if web context is active
        if self.state.get("web_context"):
            try:
                from app.web import engine
                web_screenshot_path = f"data/screenshots/{run_id}_{idx}_web.png"
                engine.take_screenshot(
                    self.state["web_context"], web_screenshot_path)
            except Exception:
                pass  # Continue if web screenshot fails

        return screenshot_path

    def _capture_state_diff(self, action: str, before_state: Dict[str, Any],
                            after_result: Dict[str, Any]) -> Dict[str, Any]:
        """Capture before/after state changes for replay UI."""
        diff = {
            "action": action,
            "before": before_state,
            "after": after_result,
        }

        # Add specific diff details based on action type
        if action == "find_files":
            diff["file_count_change"] = after_result.get("found", 0) - before_state.get("file_count", 0)
        elif action == "move_to":
            diff["moved_count"] = after_result.get("moved", 0)
        elif action == "pdf_merge":
            diff["page_count"] = after_result.get("page_count")
        elif action == "pdf_extract_pages":
            diff["extracted_pages"] = after_result.get("page_count")
        elif action in ["open_browser", "fill_by_label", "click_by_text", "download_file",
                        "upload_file", "wait_for_download"]:
            diff["web_action"] = {
                "status": after_result.get("status"),
                "strategy": after_result.get("strategy"),
                "recovery": after_result.get("recovery")
            }
        elif action in ["wait_for_element", "assert_element", "assert_text", "assert_file_exists", "assert_pdf_pages"]:
            diff["verifier_action"] = {
                "status": after_result.get("status"),
                "passed": after_result.get("passed"),
                "retry_attempted": after_result.get("retry_attempted"),
                "retry_successful": after_result.get("retry_successful")
            }
        elif action == "capture_screen_schema":
            diff["schema_capture"] = {
                "captured": after_result.get("captured"),
                "target": after_result.get("target"),
                "element_count": after_result.get("element_count")
            }

        return diff

    def _should_run(self, params: Dict[str, Any]) -> bool:
        expr = params.get("when")
        if not expr:
            return True
        # Use enhanced template rendering with full context
        from .parser import render_string
        context = {"steps": self.step_results, **self.vars}
        try:
            # Use the enhanced render_string which handles steps references properly
            eval_str = render_string(expr, context)
            return bool(safe_eval(eval_str, context))
        except Exception:
            return False

    def execute_step(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        # Resolve secrets in parameters before execution
        resolved_params = self._resolve_secrets_in_params(params)

        # Store masked version for logging
        # masked_params = self._mask_secrets_in_params(params)  # TODO: Use for logging

        if not self._should_run(resolved_params):
            return {"skipped": True}
        if action == "find_files":
            files = fs_actions.find_files(
                resolved_params.get("query", ""),
                resolved_params.get("roots", []),
                resolved_params.get("limit", 100),
            )
            # Self-healing: widen one level if 0 results
            healed = False
            if len(files) == 0 and resolved_params.get("roots"):
                parents = []
                for r in resolved_params.get("roots", []):
                    p = Path(r).expanduser()
                    if p.exists() and p.parent != p:
                        parents.append(str(p.parent))
                if parents:
                    files = fs_actions.find_files(
                        resolved_params.get("query", ""),
                        parents,
                        resolved_params.get("limit", 100),
                    )
                    healed = True
            self.state["files"] = files
            self.state.pop("newnames", None)
            out = {"found": len(files), "files": files[:10]}
            if healed:
                out["self_heal"] = {"strategy": "widen_one_level", "effective": True}
            return out
        if action == "rename":
            rule = resolved_params.get("rule", "{basename}")
            # No destructive rename here: store target basenames alongside sources
            newnames = []
            for i, f in enumerate(self.state.get("files", []), start=1):
                p = Path(f)
                basename = p.name
                date = self.vars.get("date")
                newname = (
                    rule.replace("{{date}}", str(date))
                    .replace("{{index}}", str(i))
                    .replace("{{basename}}", basename)
                )
                newnames.append(newname)
            self.state["newnames"] = newnames
            return {
                "renamed_previews": newnames[:10],
                "before_count": len(self.state.get("files", [])),
                "after_count": len(newnames),
            }
        if action == "move_to":
            if self.dry_run:
                return {"would_move": len(self.state.get("files", []))}
            dest = resolved_params["dest"]

            # Self-healing: auto-create output directory if it doesn't exist
            dest_path = Path(dest).expanduser()
            healed = False
            if not dest_path.exists():
                try:
                    dest_path.mkdir(parents=True, exist_ok=True)
                    healed = True
                except Exception:
                    pass  # Let move_to handle the error normally

            moved = fs_actions.move_to(
                self.state.get("files", []),
                dest,
                newnames=self.state.get("newnames"),
            )
            self.state["files"] = moved
            self.state.pop("newnames", None)

            result = {"moved": len(moved), "out_paths": moved}
            if healed:
                result["self_heal"] = {"strategy": "auto_create_dir", "effective": True}
            return result
        if action == "zip_folder":
            if self.dry_run:
                return {"would_zip": resolved_params.get("folder")}
            out = fs_actions.zip_folder(resolved_params["folder"], resolved_params["out"])  # type: ignore
            return {"zip": out}
        if action == "pdf_merge":
            inputs = []
            if "inputs" in params:
                inputs = resolved_params["inputs"]
            elif "inputs_from" in params:
                root = Path(resolved_params["inputs_from"]).expanduser()
                inputs = [str(p) for p in sorted(root.glob("*.pdf"))]
            if self.dry_run:
                return {"would_merge": len(inputs)}
            from app.actions import pdf_actions  # local import to avoid dependency when dry-run

            out = pdf_actions.pdf_merge(inputs, resolved_params["out"])  # type: ignore
            self.state["last_pdf"] = out
            # Count pages
            try:
                from pypdf import PdfReader  # type: ignore

                pc = len(PdfReader(out).pages)
            except Exception:
                pc = None
            return {"merged": out, "out_path": out, "page_count": pc}
        if action == "pdf_extract_pages":
            if self.dry_run:
                return {"would_extract": resolved_params.get("pages")}
            from app.actions import pdf_actions  # local import

            out = pdf_actions.pdf_extract_pages(
                resolved_params["input"],
                resolved_params["pages"],
                resolved_params["out"],  # type: ignore
            )
            self.state["last_pdf_extract"] = out
            # Count pages
            try:
                from pypdf import PdfReader  # type: ignore

                pc = len(PdfReader(out).pages)
            except Exception:
                pc = None
            return {"extracted": out, "out_path": out, "page_count": pc}
        if action == "open_preview":
            if self.dry_run:
                return {"would_open": resolved_params.get("path")}
            self.preview.open(resolved_params["path"])  # type: ignore
            return {"opened": resolved_params.get("path")}
        if action == "compose_mail":
            if self.dry_run:
                return {"would_compose": True}
            draft_id = self.mail.compose(
                resolved_params.get("to", []),
                resolved_params.get("subject", ""),
                resolved_params.get("body", ""),
            )
            self.state["draft_id"] = draft_id
            return {"draft_id": draft_id}
        if action == "attach_files":
            if self.dry_run:
                return {"would_attach": len(resolved_params.get("paths", []))}
            did = self.state.get("draft_id")
            # Validate file existence before attempting Mail attach
            paths = list(resolved_params.get("paths", []))
            missing = [str(p) for p in paths if not Path(str(p)).expanduser().exists()]
            if missing:
                raise FileNotFoundError(f"attach_files: missing paths: {', '.join(missing)}")
            if did:
                self.mail.attach(did, paths)
            return {"attached": resolved_params.get("paths", [])}
        if action == "save_draft":
            if self.dry_run:
                return {"would_save": True}
            did = self.state.get("draft_id")
            if did:
                self.mail.save_draft(did)
            return {"saved": True}
        if action == "log":
            return {"message": resolved_params.get("message", "")}

        # Web Actions (Phase 2 + Phase 5 Engine Abstraction)
        if action == "open_browser":
            if self.dry_run:
                return {"would_open": resolved_params.get("url")}
            from app.web import engine
            ctx = resolved_params.get("context", "default")
            engine_type = resolved_params.get("engine")
            result = engine.open_browser(
                resolved_params["url"],
                ctx,
                engine=engine_type,
                wait_for_load=True,
                visible=resolved_params.get("visible")
            )
            # Remember active web context for subsequent steps and screenshots
            self.state["web_context"] = ctx
            return result
        if action == "wait_for_selector":
            if self.dry_run:
                return {"would_wait_for": resolved_params.get("selector")}
            from app.web import engine
            selector = resolved_params.get("selector")
            timeout_ms = resolved_params.get("timeout_ms")
            engine_type = resolved_params.get("engine")
            result = engine.wait_for_selector(
                selector,
                timeout_ms,
                self.state.get("web_context", "default"),
                engine=engine_type
            )
            return result

        if action == "fill_by_label":
            if self.dry_run:
                return {"would_fill": resolved_params.get("label")}
            from app.web import engine

            engine_type = resolved_params.get("engine")
            # First attempt
            result = engine.fill_by_label(
                resolved_params["label"],
                resolved_params["text"],
                self.state.get("web_context", "default"),
                engine=engine_type
            )

            # Self-recovery for fill_by_label
            if result.get("status") == "not_found":
                # Strategy 1: Try common label synonyms
                label_synonyms = {
                    "氏名": ["名前", "お名前", "Name", "Full Name"],
                    "名前": ["氏名", "お名前", "Name"],
                    "メール": ["Email", "メールアドレス", "E-mail", "mail"],
                    "Email": ["メール", "メールアドレス", "E-mail"],
                    "件名": ["Subject", "タイトル", "Title"],
                    "本文": ["Message", "メッセージ", "Content", "内容"]
                }

                original_label = resolved_params["label"]
                synonyms = label_synonyms.get(original_label, [])

                recovery_attempted = False
                for synonym in synonyms:
                    try:
                        recovery_result = engine.fill_by_label(
                            synonym,
                            resolved_params["text"],
                            self.state.get("web_context", "default"),
                            engine=engine_type
                        )
                        if recovery_result.get("status") == "success":
                            result = recovery_result
                            result["recovery"] = {
                                "strategy": "label_synonym",
                                "original_label": original_label,
                                "successful_label": synonym,
                                "effective": True
                            }
                            recovery_attempted = True
                            break
                    except Exception:
                        continue

                if not recovery_attempted or result.get("status") != "success":
                    result["recovery"] = {
                        "strategy": "label_synonym",
                        "original_label": original_label,
                        "attempted_synonyms": synonyms,
                        "effective": False
                    }

            return result

        if action == "click_by_text":
            if self.dry_run:
                return {"would_click": resolved_params.get("text")}
            from app.web import engine

            engine_type = resolved_params.get("engine")
            # First attempt
            result = engine.click_by_text(
                resolved_params["text"],
                resolved_params.get("role"),
                self.state.get("web_context", "default"),
                engine=engine_type
            )

            # Self-recovery for click_by_text
            if result.get("status") in ["not_found", "error"]:
                try:
                    # Strategy: Page reload and retry (for Playwright engine compatibility)
                    from app.actions import web_actions
                    web_actions.reload_page(self.state.get("web_context", "default"))

                    # Retry the click
                    recovery_result = engine.click_by_text(
                        resolved_params["text"],
                        resolved_params.get("role"),
                        self.state.get("web_context", "default"),
                        engine=engine_type
                    )

                    if recovery_result.get("status") == "success":
                        result = recovery_result
                        result["recovery"] = {
                            "strategy": "page_reload_retry",
                            "original_error": result.get("error", "not_found"),
                            "effective": True
                        }
                    else:
                        result["recovery"] = {
                            "strategy": "page_reload_retry",
                            "original_error": result.get("error", "not_found"),
                            "effective": False
                        }

                except Exception as recovery_e:
                    result["recovery"] = {
                        "strategy": "page_reload_retry",
                        "original_error": result.get("error", "not_found"),
                        "recovery_error": str(recovery_e),
                        "effective": False
                    }

            return result

        if action == "download_file":
            if self.dry_run:
                return {"would_download": resolved_params.get("to")}
            from app.web import engine
            engine_type = resolved_params.get("engine")
            result = engine.download_file(
                resolved_params["to"],
                self.state.get("web_context", "default"),
                engine=engine_type
            )
            return result

        # Phase 3: Verifier DSL Commands
        if action == "wait_for_element":
            if self.dry_run:
                return {"would_wait_for": {"text": resolved_params.get("text"), "role": resolved_params.get("role")}}
            from app.actions import verifier_actions
            result = verifier_actions.wait_for_element(
                text=resolved_params.get("text"),
                role=resolved_params.get("role"),
                timeout_ms=resolved_params.get("timeout_ms", 15000),
                where=resolved_params.get("where", "screen")
            )
            return result

        if action == "assert_element":
            if self.dry_run:
                return {"would_assert": {"text": resolved_params.get("text"), "role": resolved_params.get("role")}}
            from app.actions import verifier_actions
            result = verifier_actions.assert_element(
                text=resolved_params.get("text"),
                role=resolved_params.get("role"),
                count_gte=resolved_params.get("count_gte", 1),
                where=resolved_params.get("where", "screen")
            )
            return result

        if action == "assert_text":
            if self.dry_run:
                return {"would_assert_text": resolved_params.get("contains")}
            from app.actions import verifier_actions
            result = verifier_actions.assert_text(
                contains=resolved_params["contains"],
                where=resolved_params.get("where", "screen")
            )
            return result

        if action == "assert_file_exists":
            if self.dry_run:
                return {"would_check_file": resolved_params.get("path")}
            from app.actions import verifier_actions
            result = verifier_actions.assert_file_exists(path=resolved_params["path"])
            return result

        if action == "assert_pdf_pages":
            if self.dry_run:
                return {
                    "would_check_pdf": {
                        "path": resolved_params.get("path"),
                        "pages": resolved_params.get("expected_pages"),
                    }
                }
            from app.actions import verifier_actions
            result = verifier_actions.assert_pdf_pages(
                path=resolved_params["path"],
                expected_pages=resolved_params["expected_pages"]
            )
            return result

        if action == "capture_screen_schema":
            if self.dry_run:
                return {"would_capture_schema": resolved_params.get("target", "frontmost")}
            from app.actions import verifier_actions
            result = verifier_actions.capture_screen_schema(target=resolved_params.get("target", "frontmost"))
            # Store schema in state for other components to use
            if result.get("captured"):
                self.state["last_screen_schema"] = result.get("schema")
            return result

        # Phase 3: Web Extensions
        if action == "upload_file":
            if self.dry_run:
                return {
                    "would_upload": {
                        "path": resolved_params.get("path"),
                        "selector": resolved_params.get("selector"),
                    }
                }
            from app.web import engine
            engine_type = resolved_params.get("engine")
            result = engine.upload_file(
                path=resolved_params["path"],
                selector=resolved_params.get("selector"),
                label=resolved_params.get("label"),
                context=self.state.get("web_context", "default"),
                engine=engine_type
            )
            return result

        if action == "wait_for_download":
            if self.dry_run:
                return {"would_wait_download": resolved_params.get("to")}
            from app.web import engine
            engine_type = resolved_params.get("engine")
            result = engine.wait_for_download(
                to=resolved_params["to"],
                timeout_ms=resolved_params.get("timeout_ms", 30000),
                context=self.state.get("web_context", "default"),
                engine=engine_type
            )
            return result

        # Phase 4: Human-in-the-Loop (HITL)
        if action == "human_confirm":
            if self.dry_run:
                return {"would_confirm": resolved_params.get("message")}
            from app.actions import hitl_actions
            result = hitl_actions.human_confirm(
                message=resolved_params["message"],
                timeout_ms=resolved_params.get("timeout_ms", 600000),
                auto_approve=resolved_params.get("auto_approve", False)
            )
            return result

        raise ValueError(f"Unknown action: {action}")

    def execute_step_with_diff(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a step and capture before/after state for replay UI."""
        # Capture before state
        before_state = {
            "file_count": len(self.state.get("files", [])),
            "state": dict(self.state),
        }

        # Execute the step
        result = self.execute_step(action, params)

        # Store result for future step references
        self.step_results.append(result)

        # Capture diff
        diff = self._capture_state_diff(action, before_state, result)
        self.step_diffs.append(diff)

        # Propagate web-action failures to step status so UI reflects correctly
        try:
            if isinstance(result, dict):
                status = str(result.get("status", "success")).lower()
                if status in ("error", "timeout", "not_found"):
                    msg = result.get("error") or f"{action} returned status={status}"
                    raise RuntimeError(msg)
        except Exception:
            # Re-raise to be caught by caller loop which marks step as failed
            raise

        return result
