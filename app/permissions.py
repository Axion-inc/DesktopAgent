import platform
from typing import Dict

from .os_adapters.macos import _run_osascript  # type: ignore


def check_permissions() -> Dict[str, Dict[str, str]]:
    """Return a dict of permission checks and statuses.
    status: ok | warn | fail | n/a
    """
    if platform.system() != "Darwin":
        return {
            "screen_recording": {"status": "n/a", "message": "macOS only"},
            "automation_mail": {"status": "n/a", "message": "macOS only"},
        }
    results: Dict[str, Dict[str, str]] = {}
    # Screen recording (best-effort): try a one-shot mss grab
    try:
        from mss import mss  # type: ignore
        with mss() as sct:  # type: ignore
            _ = sct.monitors[0]
        results["screen_recording"] = {
            "status": "ok",
            "message": "mss capture available",
        }
    except Exception:
        results["screen_recording"] = {
            "status": "warn",
            "message": "スクリーンショットが取得できません。System Settings → Privacy & Security → Screen Recording を確認してください。",
        }
    # Automation (Mail): try a harmless AppleScript
    try:
        _ = _run_osascript('tell application "Mail" to get 1')
        results["automation_mail"] = {
            "status": "ok",
            "message": "Mail automation reachable",
        }
    except Exception as e:  # noqa: BLE001
        results["automation_mail"] = {
            "status": "fail",
            "message": f"Mail の自動化にアクセスできません: {str(e)}",
        }
    return results

