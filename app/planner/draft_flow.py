from __future__ import annotations

from typing import Dict, Any


class DraftPipeline:
    """Draft template pipeline: lint -> dry-run*3 -> sign -> register."""

    def lint(self, draft: Dict[str, Any]) -> None:
        # Minimal static checks
        assert "dsl" in draft, "draft missing dsl"
        assert "risk_flags" in draft, "draft missing risk"

    def dry_run(self, draft: Dict[str, Any]) -> bool:
        # Simulate success
        return True

    def sign(self, draft: Dict[str, Any]) -> Dict[str, Any]:
        out = dict(draft)
        out["signature_verified"] = True
        return out

    def process_and_sign(self, draft: Dict[str, Any]) -> Dict[str, Any]:
        self.lint(draft)
        for _ in range(3):
            assert self.dry_run(draft)
        return self.sign(draft)

    def is_executable(self, draft: Dict[str, Any]) -> bool:
        return bool(draft.get("signature_verified"))

