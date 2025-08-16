from __future__ import annotations

import platform
from pathlib import Path
from typing import Any, Dict, Tuple

from app.actions import fs_actions
from app.os_adapters.base import MailAdapter, PreviewAdapter
from app.os_adapters.macos import MacMailAdapter, MacPreviewAdapter
from app.os_adapters.windows import WindowsMailAdapter, WindowsPreviewAdapter
from app.utils import take_screenshot


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

    def _screenshot(self, run_id: int, idx: int) -> str:
        return take_screenshot(f"{run_id}_{idx}.png")

    def execute_step(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if action == "find_files":
            files = fs_actions.find_files(params.get("query", ""), params.get("roots", []), params.get("limit", 100))
            self.state["files"] = files
            self.state.pop("newnames", None)
            return {"found": len(files), "files": files[:10]}
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
            return {"renamed_previews": newnames[:10]}
        if action == "move_to":
            if self.dry_run:
                return {"would_move": len(self.state.get("files", []))}
            dest = params["dest"]
            moved = fs_actions.move_to(
                self.state.get("files", []),
                dest,
                newnames=self.state.get("newnames"),
            )
            self.state["files"] = moved
            self.state.pop("newnames", None)
            return {"moved": len(moved)}
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
            return {"merged": out}
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
            return {"extracted": out}
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
            if did:
                self.mail.attach(did, params.get("paths", []))
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
