from typing import Iterable

from .base import MailAdapter, PreviewAdapter


class WindowsMailAdapter(MailAdapter):
    def compose(self, to: Iterable[str], subject: str, body: str) -> str:
        raise NotImplementedError("Windows MailAdapter is a stub for future implementation")

    def attach(self, draft_id: str, paths: Iterable[str]) -> None:
        raise NotImplementedError("Windows MailAdapter is a stub for future implementation")

    def save_draft(self, draft_id: str) -> None:
        raise NotImplementedError("Windows MailAdapter is a stub for future implementation")


class WindowsPreviewAdapter(PreviewAdapter):
    def open(self, path: str) -> None:
        raise NotImplementedError("Windows PreviewAdapter is a stub for future implementation")

