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

    def _screenshot(self, run_id: int, idx: int) -> str:
        return take_screenshot(f"{run_id}_{idx}.png")

    def _capture_state_diff(self, action: str, before_state: Dict[str, Any], after_result: Dict[str, Any]) -> Dict[str, Any]:
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
        if not self._should_run(params):
            return {"skipped": True}
        if action == "find_files":
            files = fs_actions.find_files(params.get("query", ""), params.get("roots", []), params.get("limit", 100))
            # Self-healing: widen one level if 0 results
            healed = False
            if len(files) == 0 and params.get("roots"):
                parents = []
                for r in params.get("roots", []):
                    p = Path(r).expanduser()
                    if p.exists() and p.parent != p:
                        parents.append(str(p.parent))
                if parents:
                    files = fs_actions.find_files(params.get("query", ""), parents, params.get("limit", 100))
                    healed = True
            self.state["files"] = files
            self.state.pop("newnames", None)
            out = {"found": len(files), "files": files[:10]}
            if healed:
                out["self_heal"] = {"strategy": "widen_one_level", "effective": True}
            return out
        if action == "rename":
            rule = params.get("rule", "{basename}")
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
            dest = params["dest"]
            
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
                return {"would_zip": params.get("folder")}
            out = fs_actions.zip_folder(params["folder"], params["out"])  # type: ignore
            return {"zip": out}
        if action == "pdf_merge":
            inputs = []
            if "inputs" in params:
                inputs = params["inputs"]
            elif "inputs_from" in params:
                root = Path(params["inputs_from"]).expanduser()
                inputs = [str(p) for p in sorted(root.glob("*.pdf"))]
            if self.dry_run:
                return {"would_merge": len(inputs)}
            from app.actions import pdf_actions  # local import to avoid dependency when dry-run

            out = pdf_actions.pdf_merge(inputs, params["out"])  # type: ignore
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
                return {"would_extract": params.get("pages")}
            from app.actions import pdf_actions  # local import

            out = pdf_actions.pdf_extract_pages(
                params["input"],
                params["pages"],
                params["out"],  # type: ignore
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
                return {"would_open": params.get("path")}
            self.preview.open(params["path"])  # type: ignore
            return {"opened": params.get("path")}
        if action == "compose_mail":
            if self.dry_run:
                return {"would_compose": True}
            draft_id = self.mail.compose(params.get("to", []), params.get("subject", ""), params.get("body", ""))
            self.state["draft_id"] = draft_id
            return {"draft_id": draft_id}
        if action == "attach_files":
            if self.dry_run:
                return {"would_attach": len(params.get("paths", []))}
            did = self.state.get("draft_id")
            # Validate file existence before attempting Mail attach
            paths = list(params.get("paths", []))
            missing = [str(p) for p in paths if not Path(str(p)).expanduser().exists()]
            if missing:
                raise FileNotFoundError(f"attach_files: missing paths: {', '.join(missing)}")
            if did:
                self.mail.attach(did, paths)
            return {"attached": params.get("paths", [])}
        if action == "save_draft":
            if self.dry_run:
                return {"would_save": True}
            did = self.state.get("draft_id")
            if did:
                self.mail.save_draft(did)
            return {"saved": True}
        if action == "log":
            return {"message": params.get("message", "")}
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
        
        return result
