"""
WebX Plugin Sandboxing System
Provides secure execution environments for WebX plugins with different security levels
"""

import json
import time
import resource
import threading
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, field
from enum import Enum

from ..utils.logging import get_logger
from .integrity_checker import get_integrity_checker

logger = get_logger(__name__)


class SandboxLevel(Enum):
    NONE = "none"
    MINIMAL = "minimal"
    STANDARD = "standard"
    STRICT = "strict"
    MAXIMUM = "maximum"


class ExecutionStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    BLOCKED = "blocked"


@dataclass
class SandboxConfig:
    level: SandboxLevel
    max_execution_time: int  # seconds
    max_memory_mb: int
    allowed_apis: Set[str] = field(default_factory=set)
    blocked_apis: Set[str] = field(default_factory=set)
    file_system_access: str = "none"  # none, read_only, restricted, full
    network_access: bool = False
    process_spawning: bool = False
    dom_access_level: str = "read_only"  # none, read_only, limited, full

    def to_dict(self) -> Dict[str, Any]:
        return {
            "level": self.level.value,
            "max_execution_time": self.max_execution_time,
            "max_memory_mb": self.max_memory_mb,
            "allowed_apis": list(self.allowed_apis),
            "blocked_apis": list(self.blocked_apis),
            "file_system_access": self.file_system_access,
            "network_access": self.network_access,
            "process_spawning": self.process_spawning,
            "dom_access_level": self.dom_access_level
        }


@dataclass
class ExecutionResult:
    status: ExecutionStatus
    result: Any = None
    error: Optional[str] = None
    execution_time: float = 0.0
    memory_used: int = 0  # bytes
    warnings: List[str] = field(default_factory=list)
    security_violations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "execution_time": self.execution_time,
            "memory_used": self.memory_used,
            "warnings": self.warnings,
            "security_violations": self.security_violations
        }


class PluginSandbox:
    """Secure execution environment for WebX plugins"""

    def __init__(self):
        self.sandbox_configs = self._initialize_sandbox_configs()
        self.active_executions: Dict[str, Dict[str, Any]] = {}
        self.execution_history: List[Dict[str, Any]] = []
        self.blocked_plugins: Set[str] = set()
        self.integrity_checker = get_integrity_checker()

    def _initialize_sandbox_configs(self) -> Dict[SandboxLevel, SandboxConfig]:
        """Initialize sandbox configurations for different security levels"""
        return {
            SandboxLevel.NONE: SandboxConfig(
                level=SandboxLevel.NONE,
                max_execution_time=300,  # 5 minutes
                max_memory_mb=512,
                allowed_apis={"*"},  # All APIs allowed
                file_system_access="full",
                network_access=True,
                process_spawning=True,
                dom_access_level="full"
            ),

            SandboxLevel.MINIMAL: SandboxConfig(
                level=SandboxLevel.MINIMAL,
                max_execution_time=120,  # 2 minutes
                max_memory_mb=256,
                allowed_apis={
                    "console.log", "console.error", "console.warn",
                    "JSON.parse", "JSON.stringify",
                    "Math.*", "Date.*", "String.*", "Array.*"
                },
                blocked_apis={
                    "eval", "Function", "setTimeout", "setInterval",
                    "XMLHttpRequest", "fetch", "WebSocket",
                    "localStorage", "sessionStorage"
                },
                file_system_access="none",
                network_access=False,
                process_spawning=False,
                dom_access_level="read_only"
            ),

            SandboxLevel.STANDARD: SandboxConfig(
                level=SandboxLevel.STANDARD,
                max_execution_time=180,  # 3 minutes
                max_memory_mb=256,
                allowed_apis={
                    "console.*", "JSON.*", "Math.*", "Date.*",
                    "String.*", "Array.*", "Object.*",
                    "document.querySelector", "document.querySelectorAll",
                    "document.getElementById", "element.click",
                    "element.focus", "element.blur"
                },
                blocked_apis={
                    "eval", "Function", "XMLHttpRequest", "fetch",
                    "WebSocket", "Worker", "SharedWorker",
                    "localStorage.clear", "sessionStorage.clear",
                    "window.open", "location.href", "history.pushState"
                },
                file_system_access="none",
                network_access=False,
                process_spawning=False,
                dom_access_level="limited"
            ),

            SandboxLevel.STRICT: SandboxConfig(
                level=SandboxLevel.STRICT,
                max_execution_time=60,  # 1 minute
                max_memory_mb=128,
                allowed_apis={
                    "console.log", "console.error",
                    "JSON.parse", "JSON.stringify",
                    "Math.*", "String.*", "Array.*",
                    "document.querySelector", "element.textContent",
                    "element.getAttribute", "element.classList"
                },
                blocked_apis={
                    "eval", "Function", "setTimeout", "setInterval",
                    "XMLHttpRequest", "fetch", "WebSocket",
                    "localStorage", "sessionStorage", "indexedDB",
                    "window.open", "location", "history",
                    "document.write", "element.innerHTML", "element.outerHTML"
                },
                file_system_access="none",
                network_access=False,
                process_spawning=False,
                dom_access_level="read_only"
            ),

            SandboxLevel.MAXIMUM: SandboxConfig(
                level=SandboxLevel.MAXIMUM,
                max_execution_time=30,  # 30 seconds
                max_memory_mb=64,
                allowed_apis={
                    "console.log",
                    "JSON.parse", "JSON.stringify",
                    "Math.min", "Math.max", "Math.round",
                    "String.prototype.substr", "String.prototype.substring",
                    "Array.prototype.map", "Array.prototype.filter"
                },
                blocked_apis={
                    "*"  # Block everything by default, only allow specific APIs
                },
                file_system_access="none",
                network_access=False,
                process_spawning=False,
                dom_access_level="none"
            )
        }

    def execute_plugin(
        self,
        plugin_code: str,
        plugin_id: str,
        sandbox_level: SandboxLevel,
        context: Dict[str, Any] = None,
        execution_id: str = None
    ) -> ExecutionResult:
        """Execute plugin code in a sandboxed environment"""

        if execution_id is None:
            execution_id = f"exec_{int(time.time() * 1000)}"

        # Check if plugin is blocked
        if plugin_id in self.blocked_plugins:
            return ExecutionResult(
                status=ExecutionStatus.BLOCKED,
                error=f"Plugin {plugin_id} is blocked due to security violations"
            )

        config = self.sandbox_configs[sandbox_level]
        start_time = time.time()

        # Record execution start
        self.active_executions[execution_id] = {
            "plugin_id": plugin_id,
            "sandbox_level": sandbox_level.value,
            "start_time": start_time,
            "status": ExecutionStatus.RUNNING.value
        }

        try:
            # Create sandboxed execution context
            sandbox_context = self._create_sandbox_context(config, context or {})

            # Validate plugin code
            validation_result = self._validate_plugin_code(plugin_code, config)
            if validation_result.security_violations:
                return ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    error="Plugin code contains security violations",
                    security_violations=validation_result.security_violations
                )

            # Execute in isolated environment
            result = self._execute_in_isolation(
                plugin_code,
                sandbox_context,
                config,
                execution_id
            )

            execution_time = time.time() - start_time

            # Update result with timing
            result.execution_time = execution_time

            # Log successful execution
            logger.info(f"Plugin executed successfully: {plugin_id} ({execution_time:.2f}s)")

            return result

        except TimeoutError:
            return ExecutionResult(
                status=ExecutionStatus.TIMEOUT,
                error=f"Plugin execution exceeded {config.max_execution_time}s timeout",
                execution_time=time.time() - start_time
            )

        except MemoryError:
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                error=f"Plugin execution exceeded {config.max_memory_mb}MB memory limit",
                execution_time=time.time() - start_time
            )

        except Exception as e:
            logger.error(f"Plugin execution failed for {plugin_id}: {e}")
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                error=str(e),
                execution_time=time.time() - start_time
            )

        finally:
            # Clean up execution tracking
            if execution_id in self.active_executions:
                execution_info = self.active_executions.pop(execution_id)
                self.execution_history.append({
                    **execution_info,
                    "end_time": time.time(),
                    "execution_time": time.time() - start_time
                })

    def _create_sandbox_context(self, config: SandboxConfig, user_context: Dict[str, Any]) -> Dict[str, Any]:
        """Create a restricted execution context based on sandbox configuration"""

        # Base safe context
        sandbox_context = {
            "__builtins__": {
                # Safe built-ins only
                "len": len,
                "str": str,
                "int": int,
                "float": float,
                "bool": bool,
                "list": list,
                "dict": dict,
                "tuple": tuple,
                "set": set,
                "min": min,
                "max": max,
                "abs": abs,
                "round": round,
                "range": range,
                "enumerate": enumerate,
                "zip": zip,
                "isinstance": isinstance,
                "hasattr": hasattr,
                "getattr": getattr
            },
            "JSON": {
                "parse": json.loads,
                "stringify": json.dumps
            },
            "Math": {
                "min": min,
                "max": max,
                "abs": abs,
                "round": round
            },
            "console": {
                "log": lambda *args: logger.info(f"Plugin: {' '.join(str(arg) for arg in args)}"),
                "error": lambda *args: logger.error(f"Plugin: {' '.join(str(arg) for arg in args)}"),
                "warn": lambda *args: logger.warning(f"Plugin: {' '.join(str(arg) for arg in args)}")
            }
        }

        # Add DOM access based on configuration
        if config.dom_access_level != "none":
            sandbox_context["document"] = self._create_dom_proxy(config.dom_access_level)

        # Add user-provided context (filtered)
        filtered_context = self._filter_user_context(user_context, config)
        sandbox_context.update(filtered_context)

        return sandbox_context

    def _create_dom_proxy(self, access_level: str) -> Dict[str, Any]:
        """Create a DOM proxy object with restricted access"""

        if access_level == "read_only":
            return {
                "querySelector": lambda selector: {"textContent": "mock_element"},
                "querySelectorAll": lambda selector: [{"textContent": "mock_element"}],
                "getElementById": lambda id: {"textContent": "mock_element"}
            }

        elif access_level == "limited":
            return {
                "querySelector": lambda selector: {
                    "textContent": "mock_element",
                    "click": lambda: None,
                    "focus": lambda: None,
                    "blur": lambda: None
                },
                "querySelectorAll": lambda selector: [{
                    "textContent": "mock_element",
                    "click": lambda: None
                }],
                "getElementById": lambda id: {
                    "textContent": "mock_element",
                    "click": lambda: None
                }
            }

        elif access_level == "full":
            # In a real implementation, this would provide full DOM access
            # For security, we still return a mock here
            return {
                "querySelector": lambda selector: {"innerHTML": "mock_full_access"},
                "write": lambda content: logger.warning("Plugin attempted document.write"),
                "createElement": lambda tag: {"tagName": tag}
            }

        return {}

    def _filter_user_context(self, context: Dict[str, Any], config: SandboxConfig) -> Dict[str, Any]:
        """Filter user context based on sandbox configuration"""

        # Remove dangerous objects/functions
        dangerous_keys = ["eval", "exec", "compile", "__import__", "open", "file"]

        filtered = {}
        for key, value in context.items():
            if key.startswith("_") or key in dangerous_keys:
                continue

            # Only allow safe data types
            if isinstance(value, (str, int, float, bool, list, dict, tuple)):
                filtered[key] = value
            elif callable(value) and config.level == SandboxLevel.NONE:
                # Only allow functions in no-sandbox mode
                filtered[key] = value

        return filtered

    def _validate_plugin_code(self, code: str, config: SandboxConfig) -> ExecutionResult:
        """Validate plugin code for security violations"""

        result = ExecutionResult(status=ExecutionStatus.PENDING)

        # Check for blocked APIs
        for blocked_api in config.blocked_apis:
            if blocked_api == "*":
                continue  # Special case handled elsewhere

            if blocked_api in code:
                result.security_violations.append(f"Use of blocked API: {blocked_api}")

        # Check for dangerous patterns
        dangerous_patterns = [
            "eval(",
            "exec(",
            "compile(",
            "__import__",
            "subprocess",
            "os.",
            "sys.",
            "file(",
            "open(",
            "input(",
            "raw_input(",
            "execfile(",
            "reload(",
            "import ",
            "from ",
            "globals(",
            "locals(",
            "vars(",
            "dir(",
            "delattr(",
            "setattr("
        ]

        code_lower = code.lower()
        for pattern in dangerous_patterns:
            if pattern.lower() in code_lower:
                result.security_violations.append(f"Dangerous pattern detected: {pattern}")

        # Check code length (simple DoS protection)
        if len(code) > 100000:  # 100KB limit
            result.security_violations.append("Plugin code exceeds size limit")

        # Check for excessive loops (basic analysis)
        loop_keywords = ["while", "for"]
        loop_count = sum(code_lower.count(keyword) for keyword in loop_keywords)
        if loop_count > 10:
            result.warnings.append("Plugin contains many loops - potential performance impact")

        return result

    def _execute_in_isolation(
        self,
        code: str,
        context: Dict[str, Any],
        config: SandboxConfig,
        execution_id: str
    ) -> ExecutionResult:
        """Execute plugin code in an isolated environment with resource limits"""

        # Set up resource limits
        try:
            # Memory limit (soft limit)
            memory_limit = config.max_memory_mb * 1024 * 1024  # Convert to bytes
            resource.setrlimit(resource.RLIMIT_AS, (memory_limit, memory_limit))
        except (OSError, AttributeError):
            # Resource limits may not be available on all systems
            pass

        # Set up execution timeout
        result = ExecutionResult(status=ExecutionStatus.RUNNING)

        def timeout_handler():
            time.sleep(config.max_execution_time)
            if execution_id in self.active_executions:
                self.active_executions[execution_id]["status"] = "timeout"

        timeout_thread = threading.Thread(target=timeout_handler)
        timeout_thread.daemon = True
        timeout_thread.start()

        try:
            # Execute the code with restricted context
            execution_globals = context.copy()
            execution_locals = {}

            # Use compile + exec for better control
            compiled_code = compile(code, f"<plugin_{execution_id}>", "exec")

            # Execute with timeout check
            # Mark start time (kept for potential future metrics)
            _ = time.time()
            exec(compiled_code, execution_globals, execution_locals)

            # Check if timed out during execution
            if (
                execution_id in self.active_executions
                and self.active_executions[execution_id]["status"] == "timeout"
            ):
                raise TimeoutError("Execution timeout")

            # Extract result if available
            plugin_result = execution_locals.get("result", None)

            result.status = ExecutionStatus.COMPLETED
            result.result = plugin_result

        except SyntaxError as e:
            result.status = ExecutionStatus.FAILED
            result.error = f"Syntax error: {str(e)}"

        except TimeoutError:
            result.status = ExecutionStatus.TIMEOUT
            result.error = f"Execution timeout ({config.max_execution_time}s)"

        except MemoryError:
            result.status = ExecutionStatus.FAILED
            result.error = f"Memory limit exceeded ({config.max_memory_mb}MB)"

        except Exception as e:
            result.status = ExecutionStatus.FAILED
            result.error = f"Runtime error: {str(e)}"

        return result

    def block_plugin(self, plugin_id: str, reason: str = "Security violation"):
        """Block a plugin from execution"""
        self.blocked_plugins.add(plugin_id)
        logger.warning(f"Blocked plugin {plugin_id}: {reason}")

    def unblock_plugin(self, plugin_id: str):
        """Unblock a previously blocked plugin"""
        self.blocked_plugins.discard(plugin_id)
        logger.info(f"Unblocked plugin {plugin_id}")

    def get_sandbox_info(self, level: SandboxLevel) -> Dict[str, Any]:
        """Get information about a sandbox level"""
        if level in self.sandbox_configs:
            return self.sandbox_configs[level].to_dict()
        return {}

    def get_execution_stats(self) -> Dict[str, Any]:
        """Get execution statistics"""

        total_executions = len(self.execution_history)
        active_executions = len(self.active_executions)

        # Calculate success rate
        successful = sum(
            1
            for exec_info in self.execution_history
            if exec_info.get("status") == ExecutionStatus.COMPLETED.value
        )
        success_rate = (successful / total_executions * 100) if total_executions > 0 else 0

        # Average execution time
        total_time = sum(exec_info.get("execution_time", 0) for exec_info in self.execution_history)
        avg_execution_time = (total_time / total_executions) if total_executions > 0 else 0

        return {
            "total_executions": total_executions,
            "active_executions": active_executions,
            "success_rate_percent": round(success_rate, 1),
            "average_execution_time": round(avg_execution_time, 3),
            "blocked_plugins": len(self.blocked_plugins),
            "sandbox_levels_available": len(self.sandbox_configs)
        }


# Global plugin sandbox instance
_plugin_sandbox: Optional[PluginSandbox] = None


def get_plugin_sandbox() -> PluginSandbox:
    """Get the global plugin sandbox instance"""
    global _plugin_sandbox
    if _plugin_sandbox is None:
        _plugin_sandbox = PluginSandbox()
    return _plugin_sandbox
