"""
Clipboard Actions Plugin
Safe clipboard operations for Desktop Agent templates
"""

__version__ = "1.0.0"
__author__ = "Desktop Agent Team"


def register(actions_registry):
    """Register clipboard actions with the actions registry"""
    actions_registry.register('copy_to_clipboard', copy_to_clipboard)
    actions_registry.register('paste_from_clipboard', paste_from_clipboard)
    actions_registry.register('clear_clipboard', clear_clipboard)


def copy_to_clipboard(text: str) -> dict:
    """
    Copy text to system clipboard

    Args:
        text: Text to copy to clipboard

    Returns:
        dict: Result with success status and message
    """
    try:
        import pyperclip
        pyperclip.copy(text)

        return {
            "success": True,
            "message": f"Copied {len(text)} characters to clipboard",
            "text_length": len(text)
        }
    except ImportError:
        return {
            "success": False,
            "message": "pyperclip not available - clipboard operations not supported",
            "error": "missing_dependency"
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Failed to copy to clipboard: {str(e)}",
            "error": str(e)
        }


def paste_from_clipboard() -> dict:
    """
    Paste text from system clipboard

    Returns:
        dict: Result with clipboard text content
    """
    try:
        import pyperclip
        clipboard_text = pyperclip.paste()

        return {
            "success": True,
            "text": clipboard_text,
            "text_length": len(clipboard_text),
            "message": f"Retrieved {len(clipboard_text)} characters from clipboard"
        }
    except ImportError:
        return {
            "success": False,
            "text": "",
            "message": "pyperclip not available - clipboard operations not supported",
            "error": "missing_dependency"
        }
    except Exception as e:
        return {
            "success": False,
            "text": "",
            "message": f"Failed to read from clipboard: {str(e)}",
            "error": str(e)
        }


def clear_clipboard() -> dict:
    """
    Clear system clipboard content

    Returns:
        dict: Result with success status
    """
    try:
        import pyperclip
        pyperclip.copy("")  # Clear clipboard by setting empty string

        return {
            "success": True,
            "message": "Clipboard cleared successfully"
        }
    except ImportError:
        return {
            "success": False,
            "message": "pyperclip not available - clipboard operations not supported",
            "error": "missing_dependency"
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Failed to clear clipboard: {str(e)}",
            "error": str(e)
        }


# Direct usage examples (for testing)
if __name__ == "__main__":
    # Test clipboard operations
    print("Testing clipboard operations...")

    # Test copy
    copy_result = copy_to_clipboard("Hello, Desktop Agent!")
    print(f"Copy result: {copy_result}")

    # Test paste
    paste_result = paste_from_clipboard()
    print(f"Paste result: {paste_result}")

    # Test clear
    clear_result = clear_clipboard()
    print(f"Clear result: {clear_result}")

    # Verify clear worked
    verify_result = paste_from_clipboard()
    print(f"Verify clear: {verify_result}")
