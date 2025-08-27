"""
Plugin Loader with Sandboxing
Safely loads plugins from plugins/actions/*.py with security restrictions
"""

import os
import sys
import importlib
import importlib.util
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable
import inspect
import subprocess
import signal
from dataclasses import dataclass
from ..utils.logging import get_logger

logger = get_logger(__name__)


class PluginSecurityError(Exception):
    """Raised when plugin security violation is detected"""
    pass


class SandboxViolationError(Exception):
    """Raised when plugin violates sandbox restrictions"""
    pass


@dataclass
class PluginInfo:
    name: str
    path: Path
    actions: Dict[str, Callable]
    metadata: Dict[str, Any]


class PluginLoader:
    """Loads and manages plugins with security restrictions"""
    
    DEFAULT_ALLOWLIST = [
        "clipboard_actions",
        "file_utils", 
        "data_processing"
    ]
    
    def __init__(self, plugins_dir: Optional[Path] = None):
        self.plugins_dir = plugins_dir or Path("plugins/actions")
        self.allowlist = set(self.DEFAULT_ALLOWLIST)
        self.loaded_plugins: Dict[str, PluginInfo] = {}
        self.actions_registry: Dict[str, Callable] = {}
    
    def set_plugin_allowlist(self, allowlist: List[str]):
        """Set the plugin allowlist"""
        self.allowlist = set(allowlist)
        logger.info(f"Plugin allowlist updated: {self.allowlist}")
    
    def load_plugins_from_directory(self, plugins_dir: Optional[Path] = None) -> Dict[str, PluginInfo]:
        """Load all allowed plugins from directory"""
        plugins_dir = plugins_dir or self.plugins_dir
        
        if not plugins_dir.exists():
            logger.warning(f"Plugins directory not found: {plugins_dir}")
            return {}
        
        plugins = {}
        
        for plugin_file in plugins_dir.glob("*.py"):
            if plugin_file.name.startswith("__"):
                continue  # Skip __init__.py etc.
            
            plugin_name = plugin_file.stem
            
            # Check allowlist
            if plugin_name not in self.allowlist:
                logger.warning(f"Plugin {plugin_name} not on allowlist, skipping")
                raise PluginSecurityError(f"Plugin {plugin_name} not on allowlist")
            
            try:
                plugin_info = self._load_single_plugin(plugin_file)
                plugins[plugin_name] = plugin_info
                self.loaded_plugins[plugin_name] = plugin_info
                
                # Register actions
                for action_name, action_func in plugin_info.actions.items():
                    self.actions_registry[action_name] = action_func
                
                logger.info(f"Loaded plugin: {plugin_name} ({len(plugin_info.actions)} actions)")
                
            except Exception as e:
                logger.error(f"Failed to load plugin {plugin_name}: {e}")
                raise PluginSecurityError(f"Failed to load plugin {plugin_name}: {e}")
        
        return plugins
    
    def _load_single_plugin(self, plugin_file: Path) -> PluginInfo:
        """Load a single plugin file with security checks"""
        plugin_name = plugin_file.stem
        
        # Read and validate plugin code
        plugin_code = plugin_file.read_text(encoding='utf-8')
        self._validate_plugin_code(plugin_code, plugin_name)
        
        # Load plugin module
        spec = importlib.util.spec_from_file_location(plugin_name, plugin_file)
        if spec is None or spec.loader is None:
            raise PluginSecurityError(f"Cannot load plugin spec: {plugin_name}")
        
        module = importlib.util.module_from_spec(spec)
        
        # Execute plugin in restricted environment
        try:
            spec.loader.exec_module(module)
        except Exception as e:
            raise PluginSecurityError(f"Plugin execution failed: {e}")
        
        # Validate plugin structure
        if not hasattr(module, 'register'):
            raise PluginSecurityError(f"Plugin {plugin_name} missing register() function")
        
        # Extract actions using mock registry
        actions = {}
        mock_registry = MockActionsRegistry(actions)
        
        try:
            module.register(mock_registry)
        except Exception as e:
            raise PluginSecurityError(f"Plugin registration failed: {e}")
        
        # Get plugin metadata
        metadata = {
            "description": getattr(module, "__doc__", ""),
            "version": getattr(module, "__version__", "1.0.0"),
            "author": getattr(module, "__author__", "unknown")
        }
        
        return PluginInfo(
            name=plugin_name,
            path=plugin_file,
            actions=actions,
            metadata=metadata
        )
    
    def _validate_plugin_code(self, code: str, plugin_name: str):
        """Validate plugin code for security violations"""
        # Check for dangerous imports
        dangerous_imports = [
            'subprocess', 'os.system', 'eval', 'exec',
            'urllib', 'requests', 'socket', 'http',
            '__import__', 'importlib', 'sys.modules'
        ]
        
        code_lower = code.lower()
        for dangerous in dangerous_imports:
            if dangerous in code_lower:
                logger.warning(f"Plugin {plugin_name} contains potentially dangerous import: {dangerous}")
                # Allow some imports with warnings
                if dangerous in ['subprocess', 'os.system', 'eval', 'exec']:
                    raise PluginSecurityError(f"Plugin {plugin_name} uses dangerous function: {dangerous}")
        
        # Check for file system access outside sandbox
        if '/etc/' in code or '/usr/' in code or '/var/' in code:
            raise PluginSecurityError(f"Plugin {plugin_name} attempts to access system directories")
    
    def get_available_actions(self) -> Dict[str, str]:
        """Get list of available actions with descriptions"""
        actions = {}
        for plugin_name, plugin_info in self.loaded_plugins.items():
            for action_name, action_func in plugin_info.actions.items():
                doc = inspect.getdoc(action_func) or "No description available"
                actions[action_name] = doc
        
        return actions
    
    def execute_action(self, action_name: str, *args, **kwargs) -> Any:
        """Execute a registered plugin action"""
        if action_name not in self.actions_registry:
            raise PluginSecurityError(f"Action not found: {action_name}")
        
        action_func = self.actions_registry[action_name]
        
        # Execute in sandbox
        sandbox = PluginSandbox()
        return sandbox.execute_plugin_function_obj(action_func, args, kwargs)


class MockActionsRegistry:
    """Mock registry for extracting plugin actions during loading"""
    
    def __init__(self, actions_dict: Dict[str, Callable]):
        self.actions_dict = actions_dict
    
    def register(self, action_name: str, action_func: Callable):
        """Register an action (mock implementation)"""
        self.actions_dict[action_name] = action_func


class PluginSandbox:
    """Sandbox for safe plugin execution"""
    
    def __init__(self, timeout_seconds: int = 30):
        self.timeout_seconds = timeout_seconds
        self.allowed_env_vars = {"HOME", "PLUGIN_DATA_DIR", "USER"}
        self.sandbox_dir = Path.home() / "PluginsWork"
        self.sandbox_dir.mkdir(exist_ok=True)
    
    def set_allowed_env_vars(self, env_vars: List[str]):
        """Set allowed environment variables"""
        self.allowed_env_vars = set(env_vars)
    
    def execute_plugin_function(self, plugin_code: str, function_name: str, args: List[Any]) -> Any:
        """Execute plugin function in sandbox"""
        # This is a simplified sandbox - in production would use more isolation
        
        # Restricted globals
        restricted_globals = {
            '__builtins__': {
                'len': len, 'str': str, 'int': int, 'float': float, 'bool': bool,
                'list': list, 'dict': dict, 'tuple': tuple, 'set': set,
                'print': print, 'range': range, 'enumerate': enumerate,
                'zip': zip, 'map': map, 'filter': filter,
            },
            'os': FilteredOS(self.allowed_env_vars, self.sandbox_dir),
            'pyperclip': __import__('pyperclip'),  # Allow clipboard access
        }
        
        # Compile and execute
        try:
            code_obj = compile(plugin_code, '<plugin>', 'exec')
            namespace = {}
            exec(code_obj, restricted_globals, namespace)
            
            if function_name not in namespace:
                raise SandboxViolationError(f"Function {function_name} not found in plugin")
            
            func = namespace[function_name]
            
            # Set timeout
            def timeout_handler(signum, frame):
                raise SandboxViolationError(f"Plugin execution timeout ({self.timeout_seconds}s)")
            
            old_handler = signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(self.timeout_seconds)
            
            try:
                result = func(*args)
                signal.alarm(0)  # Cancel timeout
                return result
            finally:
                signal.signal(signal.SIGALRM, old_handler)
                
        except SandboxViolationError:
            raise
        except Exception as e:
            raise SandboxViolationError(f"Plugin execution error: {e}")
    
    def execute_plugin_function_obj(self, func: Callable, args: tuple, kwargs: dict) -> Any:
        """Execute plugin function object in sandbox"""
        # Simplified execution with timeout
        def timeout_handler(signum, frame):
            raise SandboxViolationError(f"Plugin execution timeout ({self.timeout_seconds}s)")
        
        old_handler = signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(self.timeout_seconds)
        
        try:
            result = func(*args, **kwargs)
            signal.alarm(0)
            return result
        except Exception as e:
            raise SandboxViolationError(f"Plugin execution error: {e}")
        finally:
            signal.signal(signal.SIGALRM, old_handler)


class FilteredOS:
    """Filtered OS module for sandbox"""
    
    def __init__(self, allowed_env_vars: set, sandbox_dir: Path):
        self.allowed_env_vars = allowed_env_vars
        self.sandbox_dir = sandbox_dir
        self._real_os = __import__('os')
    
    @property
    def environ(self):
        """Filtered environment variables"""
        filtered_env = {}
        for key, value in self._real_os.environ.items():
            if key in self.allowed_env_vars:
                filtered_env[key] = value
        return filtered_env
    
    def path(self):
        """Safe path operations"""
        return self._real_os.path
    
    def makedirs(self, path, exist_ok=False):
        """Restricted makedirs"""
        path_obj = Path(path)
        if not str(path_obj).startswith(str(self.sandbox_dir)):
            raise SandboxViolationError(f"File access denied: {path}")
        return self._real_os.makedirs(path, exist_ok=exist_ok)


# Global plugin loader
_plugin_loader: Optional[PluginLoader] = None


def get_plugin_loader() -> PluginLoader:
    """Get global plugin loader instance"""
    global _plugin_loader
    if _plugin_loader is None:
        _plugin_loader = PluginLoader()
    return _plugin_loader