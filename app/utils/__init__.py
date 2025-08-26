# Utils package for Desktop Agent

# Direct import from the sibling utils.py module to avoid circular imports
import importlib.util
from pathlib import Path

# Load the utils.py module directly using its file path
_utils_module_path = Path(__file__).parent.parent / "utils.py"
_spec = importlib.util.spec_from_file_location("app_utils_module", _utils_module_path)
_utils_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_utils_module)


def take_screenshot(filename: str) -> str:
    """Take screenshot - wrapper for backward compatibility"""
    return _utils_module.take_screenshot(filename)


def get_logger():
    """Get logger - wrapper for backward compatibility"""
    return _utils_module.get_logger()


__all__ = ['take_screenshot', 'get_logger']
