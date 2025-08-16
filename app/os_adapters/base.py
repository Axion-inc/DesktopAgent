from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable


class MailAdapter(ABC):
    @abstractmethod
    def compose(self, to: Iterable[str], subject: str, body: str) -> str:
        """Create a draft and return draft_id."""

    @abstractmethod
    def attach(self, draft_id: str, paths: Iterable[str]) -> None:
        """Attach file paths to draft."""

    @abstractmethod
    def save_draft(self, draft_id: str) -> None:
        """Persist the draft."""


class PreviewAdapter(ABC):
    @abstractmethod
    def open(self, path: str) -> None:
        """Open a file in system preview/viewer."""

