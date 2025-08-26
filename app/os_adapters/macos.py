import subprocess
import tempfile
import textwrap
import os
import glob
import shutil
import fnmatch
from pathlib import Path
from typing import Iterable, Dict, List, Any, Optional

from .base import OSAdapter, MailAdapter, PreviewAdapter, Capability
from .capabilities import get_platform_capability_map


def _run_osascript(script: str) -> str:
    # Write to a temp file to avoid encoding/escaping issues with -e
    content = textwrap.dedent(script)
    with tempfile.NamedTemporaryFile("w", suffix=".applescript", delete=False) as tf:
        tf.write(content)
        path = tf.name
    proc = subprocess.run(["/usr/bin/osascript", path], capture_output=True, text=True)
    if proc.returncode != 0:
        stderr = proc.stderr.strip()
        hint = _hint_for_error(stderr)
        raise RuntimeError(stderr + (f"\nHINT: {hint}" if hint else "") + "\nSCRIPT:\n" + content)
    return proc.stdout.strip()


def _hint_for_error(stderr: str) -> str:
    # Map common AppleScript errors to actionable hints
    # -2741: syntax error / automation blocked often shows up as parse error depending on env
    if "(-2741)" in stderr:
        return "AppleScript のパース/自動化エラーです。Automation の許可とクォート/改行を確認してください。"
    if "Not authorized to send Apple events" in stderr or "Not authorized" in stderr:
        return "System Settings → Privacy & Security → Automation で Terminal/Python に Mail の許可を付与してください。"
    return ""


class MacOSAdapter(OSAdapter):
    """macOS implementation of unified OS adapter interface."""

    def __init__(self):
        self.capability_map = get_platform_capability_map("macos")

    def capabilities(self) -> Dict[str, Capability]:
        """Return macOS capability map."""
        return self.capability_map.capabilities

    def take_screenshot(self, dest_path: str) -> None:
        """Take screenshot using macOS screencapture command."""
        try:
            result = subprocess.run(["screencapture", "-x", dest_path],
                                    check=False, capture_output=True, text=True)

            # Check if file was actually created (screencapture returns 0 even on errors)
            if not Path(dest_path).exists():
                error_msg = result.stderr.strip() if result.stderr else "Unknown error"
                raise RuntimeError(f"Screenshot failed: {error_msg}")

        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Screenshot failed: {e}")

    def capture_screen_schema(self, target: str = "frontmost") -> Dict[str, Any]:
        """Capture accessibility hierarchy using macOS AX API.

        Note: This is a placeholder implementation. Full AX API integration
        would require PyObjC and Cocoa/ApplicationServices frameworks.
        """
        # TODO: Implement full AX API integration
        # For now, return a basic structure that can be expanded
        return {
            "platform": "macos",
            "target": target,
            "timestamp": subprocess.run(["date", "+%Y-%m-%dT%H:%M:%S"],
                                        capture_output=True, text=True).stdout.strip(),
            "elements": [],
            "implementation_note": "Placeholder - requires PyObjC for full AX API access"
        }

    def compose_mail_draft(self, to: Iterable[str], subject: str, body: str,
                           attachments: Optional[List[str]] = None) -> Dict[str, Any]:
        """Create mail draft using AppleScript."""
        to_array = ", ".join([f'"{t}"' for t in to])
        subject_q = subject.replace('"', '\\"')
        body_q = body.replace('"', '\\"')
        subject_safe = subject_q.encode("ascii", "ignore").decode("ascii")
        body_safe = body_q.encode("ascii", "ignore").decode("ascii")

        script = f'''
            tell application "Mail"
              set theMessage to make new outgoing message with properties {{visible:false}}
              set subject of theMessage to "{subject_safe}"
              set content of theMessage to "{body_safe}"
              repeat with addr in {{{to_array}}}
                set _addr to addr as text
                tell theMessage to make new to recipient at end of to recipients with properties {{address:_addr}}
              end repeat
              get id of theMessage
            end tell
        '''

        try:
            draft_id = _run_osascript(script)

            # Attach files if provided
            if attachments:
                self._attach_files_to_draft(draft_id, attachments)

            return {
                "draft_id": draft_id,
                "status": "created",
                "attachments_count": len(attachments) if attachments else 0
            }
        except Exception as e:
            return {
                "draft_id": None,
                "status": "failed",
                "error": str(e)
            }

    def _attach_files_to_draft(self, draft_id: str, paths: List[str]) -> None:
        """Internal method to attach files to draft."""
        if not paths:
            return
        list_items = ", ".join([f'POSIX file "{p}"' for p in paths])
        script = f'''
            tell application "Mail"
              set theMessage to (first outgoing message whose id is {draft_id})
              tell content of theMessage
                repeat with f in {{{list_items}}}
                  make new attachment with properties {{file name:f}} at after the last paragraph
                end repeat
              end tell
            end tell
        '''
        _run_osascript(script)

    def save_mail_draft(self, draft_id: str) -> None:
        """Save mail draft using AppleScript."""
        script = f'''
            tell application "Mail"
              set theMessage to (first outgoing message whose id is {draft_id})
              save theMessage
            end tell
        '''
        _run_osascript(script)

    def open_preview(self, path: str) -> None:
        """Open file in macOS preview/default application."""
        subprocess.run(["/usr/bin/open", path], check=False)

    def fs_list(self, path: str, pattern: Optional[str] = None) -> List[str]:
        """List files in directory with optional pattern filtering."""
        try:
            if pattern:
                search_path = os.path.join(path, pattern)
                return glob.glob(search_path)
            else:
                return [os.path.join(path, f) for f in os.listdir(path)]
        except (OSError, FileNotFoundError):
            return []

    def fs_find(self, root_path: str, name_pattern: str) -> List[str]:
        """Find files matching pattern recursively."""
        result = []
        try:
            for root, dirs, files in os.walk(root_path):
                for file in files:
                    if fnmatch.fnmatch(file, name_pattern):
                        result.append(os.path.join(root, file))
        except (OSError, FileNotFoundError):
            pass
        return result

    def fs_move(self, source: str, destination: str) -> None:
        """Move file or directory."""
        shutil.move(source, destination)

    def fs_exists(self, path: str) -> bool:
        """Check if file or directory exists."""
        return os.path.exists(path)

    def pdf_merge(self, input_paths: List[str], output_path: str) -> None:
        """Merge PDF files using PyPDF2."""
        try:
            from PyPDF2 import PdfMerger
            merger = PdfMerger()
            for pdf_path in input_paths:
                merger.append(pdf_path)
            merger.write(output_path)
            merger.close()
        except ImportError:
            raise RuntimeError("PyPDF2 not installed. Run: pip install PyPDF2")
        except Exception as e:
            raise RuntimeError(f"PDF merge failed: {e}")

    def pdf_extract_pages(self, input_path: str, output_path: str, page_range: str) -> None:
        """Extract pages from PDF. Format: '1-3,5,7-9'."""
        try:
            from PyPDF2 import PdfReader, PdfWriter
            reader = PdfReader(input_path)
            writer = PdfWriter()

            # Parse page range
            pages_to_extract = set()
            for part in page_range.split(','):
                if '-' in part:
                    start, end = map(int, part.split('-'))
                    pages_to_extract.update(range(start-1, end))  # Convert to 0-based
                else:
                    pages_to_extract.add(int(part) - 1)  # Convert to 0-based

            for page_num in sorted(pages_to_extract):
                if page_num < len(reader.pages):
                    writer.add_page(reader.pages[page_num])

            with open(output_path, 'wb') as output_file:
                writer.write(output_file)

        except ImportError:
            raise RuntimeError("PyPDF2 not installed. Run: pip install PyPDF2")
        except Exception as e:
            raise RuntimeError(f"PDF page extraction failed: {e}")

    def pdf_get_page_count(self, path: str) -> int:
        """Get number of pages in PDF."""
        try:
            from PyPDF2 import PdfReader
            reader = PdfReader(path)
            return len(reader.pages)
        except ImportError:
            raise RuntimeError("PyPDF2 not installed. Run: pip install PyPDF2")
        except Exception as e:
            raise RuntimeError(f"PDF page count failed: {e}")

    def permissions_status(self) -> Dict[str, bool]:
        """Check macOS system permissions status."""
        permissions = {}

        # Check accessibility permissions (approximation)
        try:
            result = subprocess.run(
                ["sqlite3",
                 "/Library/Application Support/com.apple.TCC/TCC.db",
                 "SELECT service FROM access WHERE client LIKE '%Terminal%' OR "
                 "client LIKE '%Python%';"],
                capture_output=True, text=True, timeout=5)
            permissions["accessibility"] = "kTCCServiceAccessibility" in result.stdout
        except Exception:
            permissions["accessibility"] = False  # Assume false if can't check

        # Check automation permissions (approximation)
        try:
            result = subprocess.run(
                ["osascript", "-e", "tell application \"System Events\" to get name"],
                capture_output=True, text=True, timeout=5)
            permissions["automation"] = result.returncode == 0
        except Exception:
            permissions["automation"] = False

        # Screen recording permissions (check if we can take screenshot)
        try:
            test_path = "/tmp/test_screenshot.png"
            result = subprocess.run(
                ["screencapture", "-x", test_path],
                capture_output=True, text=True, timeout=5)
            permissions["screen_recording"] = (result.returncode == 0 and
                                               os.path.exists(test_path))
            if os.path.exists(test_path):
                os.remove(test_path)
        except Exception:
            permissions["screen_recording"] = False

        return permissions


class MacMailAdapter(MailAdapter):
    def compose(self, to: Iterable[str], subject: str, body: str) -> str:
        to_array = ", ".join([f'"{t}"' for t in to])
        subject_q = subject.replace("\"", "\\\"")
        body_q = body.replace("\"", "\\\"")
        subject_safe = subject_q.encode("ascii", "ignore").decode("ascii")
        body_safe = body_q.encode("ascii", "ignore").decode("ascii")
        script = f'''
            tell application "Mail"
              set theMessage to make new outgoing message with properties {{visible:false}}
              set subject of theMessage to "{subject_safe}"
              set content of theMessage to "{body_safe}"
              repeat with addr in {{{to_array}}}
                set _addr to addr as text
                tell theMessage to make new to recipient at end of to recipients with properties {{address:_addr}}
              end repeat
              get id of theMessage
            end tell
        '''
        return _run_osascript(script)

    def attach(self, draft_id: str, paths: Iterable[str]) -> None:
        items = list(paths)
        if not items:
            return
        list_items = ", ".join([f'POSIX file "{p}"' for p in items])
        script = f'''
            tell application "Mail"
              set theMessage to (first outgoing message whose id is {draft_id})
              tell content of theMessage
                repeat with f in {{{list_items}}}
                  make new attachment with properties {{file name:f}} at after the last paragraph
                end repeat
              end tell
            end tell
        '''
        _run_osascript(script)

    def save_draft(self, draft_id: str) -> None:
        script = f'''
            tell application "Mail"
              set theMessage to (first outgoing message whose id is {draft_id})
              save theMessage
            end tell
        '''
        _run_osascript(script)


class MacPreviewAdapter(PreviewAdapter):
    def open(self, path: str) -> None:
        subprocess.run(["/usr/bin/open", path], check=False)
