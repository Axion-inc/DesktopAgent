"""
Minimal stub of pyperclip for test environments.
Provides copy(text) and paste() backed by in-memory storage.
"""

_CLIPBOARD = ""


def copy(text: str) -> None:
    global _CLIPBOARD
    _CLIPBOARD = str(text)


def paste() -> str:
    return _CLIPBOARD

