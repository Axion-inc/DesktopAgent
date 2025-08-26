# Utils package for Desktop Agent

# Import functions from the sibling utils module
import importlib.util
from pathlib import Path

# Load the utils.py module directly to avoid circular imports
_utils_module_path = Path(__file__).parent.parent / "utils.py"
_spec = importlib.util.spec_from_file_location("app.utils_module", _utils_module_path)
_utils_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_utils_module)


def take_screenshot(filename: str) -> str:
    """Take screenshot - wrapper for backward compatibility"""
    return _utils_module.take_screenshot(filename)


def get_logger():
    """Get logger - wrapper for backward compatibility"""
    return _utils_module.get_logger()


__all__ = ['take_screenshot', 'get_logger']
