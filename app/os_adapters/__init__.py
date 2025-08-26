import platform

def get_os_adapter():
    """Get the appropriate OS adapter for the current platform"""
    system = platform.system()
    
    if system == "Darwin":
        from .macos import MacOSAdapter
        return MacOSAdapter()
    elif system == "Windows":
        from .windows import WindowsAdapter
        return WindowsAdapter()
    else:
        # Fallback to MacOS adapter for testing
        from .macos import MacOSAdapter
        return MacOSAdapter()

__all__ = [
    "base",
    "macos", 
    "windows",
    "get_os_adapter",
]

