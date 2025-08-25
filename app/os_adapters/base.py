from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Iterable, Any, Optional


@dataclass
class Capability:
    name: str
    available: bool
    notes: str = ""


@dataclass
class ScreenElement:
    role: str
    label: Optional[str] = None
    value: Optional[str] = None
    bounds: Optional[Dict[str, float]] = None
    children: Optional[List['ScreenElement']] = None


class OSAdapter(ABC):
    """Unified OS adapter interface for cross-platform operations."""

    @abstractmethod
    def capabilities(self) -> Dict[str, Capability]:
        """Return map of feature capabilities available on this OS."""

    # Screenshot operations
    @abstractmethod
    def take_screenshot(self, dest_path: str) -> None:
        """Take a screenshot and save to dest_path."""

    # Screen accessibility/schema operations
    @abstractmethod
    def capture_screen_schema(self, target: str = "frontmost") -> Dict[str, Any]:
        """Capture accessibility hierarchy of screen/window as JSON.
        Args:
            target: 'frontmost' for active window, 'screen' for full screen
        Returns:
            Dictionary with screen accessibility structure
        """

    # Mail operations
    @abstractmethod
    def compose_mail_draft(self, to: Iterable[str], subject: str, body: str,
                           attachments: Optional[List[str]] = None) -> Dict[str, Any]:
        """Create a mail draft with optional attachments.
        Returns:
            Dictionary with draft_id and status information
        """

    @abstractmethod
    def save_mail_draft(self, draft_id: str) -> None:
        """Persist the mail draft."""

    # File preview operations
    @abstractmethod
    def open_preview(self, path: str) -> None:
        """Open file in system preview/viewer."""

    # File system operations
    @abstractmethod
    def fs_list(self, path: str, pattern: Optional[str] = None) -> List[str]:
        """List files in directory, optionally filtered by pattern."""

    @abstractmethod
    def fs_find(self, root_path: str, name_pattern: str) -> List[str]:
        """Find files matching name pattern recursively from root_path."""

    @abstractmethod
    def fs_move(self, source: str, destination: str) -> None:
        """Move file or directory from source to destination."""

    @abstractmethod
    def fs_exists(self, path: str) -> bool:
        """Check if file or directory exists."""

    # PDF operations
    @abstractmethod
    def pdf_merge(self, input_paths: List[str], output_path: str) -> None:
        """Merge multiple PDF files into single output file."""

    @abstractmethod
    def pdf_extract_pages(self, input_path: str, output_path: str, page_range: str) -> None:
        """Extract pages from PDF. page_range format: '1-3,5,7-9'."""

    @abstractmethod
    def pdf_get_page_count(self, path: str) -> int:
        """Get number of pages in PDF file."""

    # System permissions
    @abstractmethod
    def permissions_status(self) -> Dict[str, bool]:
        """Get status of required system permissions.
        Returns:
            Dictionary mapping permission names to granted status
        """


# Legacy adapters maintained for backward compatibility
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

