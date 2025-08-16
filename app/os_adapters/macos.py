import subprocess
import tempfile
import textwrap
from typing import Iterable

from .base import MailAdapter, PreviewAdapter


def _run_osascript(script: str) -> str:
    # Write to a temp file to avoid encoding/escaping issues with -e
    content = textwrap.dedent(script)
    with tempfile.NamedTemporaryFile("w", suffix=".applescript", delete=False) as tf:
        tf.write(content)
        path = tf.name
    proc = subprocess.run(["/usr/bin/osascript", path], capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() + "\nSCRIPT:\n" + content)
    return proc.stdout.strip()


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
