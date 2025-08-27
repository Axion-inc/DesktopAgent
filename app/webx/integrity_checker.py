"""
WebX Integrity and Permission Checking System
Enforces security policies for WebX extensions and native messaging
"""

import json
import hashlib
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum

from ..utils.logging import get_logger
from ..security.policy_engine import get_policy_engine

logger = get_logger(__name__)


class PermissionLevel(Enum):
    NONE = "none"
    READ_ONLY = "read_only"
    STANDARD = "standard"
    ELEVATED = "elevated"
    SYSTEM = "system"


class IntegrityStatus(Enum):
    VALID = "valid"
    INVALID = "invalid"
    UNKNOWN = "unknown"
    EXPIRED = "expired"


@dataclass
class WebXPermission:
    name: str
    level: PermissionLevel
    description: str
    required_capabilities: Set[str] = field(default_factory=set)
    auto_grant: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "level": self.level.value,
            "description": self.description,
            "required_capabilities": list(self.required_capabilities),
            "auto_grant": self.auto_grant
        }


@dataclass
class IntegrityCheckResult:
    status: IntegrityStatus
    component: str
    expected_hash: Optional[str] = None
    actual_hash: Optional[str] = None
    last_checked: Optional[datetime] = None
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "component": self.component,
            "expected_hash": self.expected_hash,
            "actual_hash": self.actual_hash,
            "last_checked": self.last_checked.isoformat() if self.last_checked else None,
            "errors": self.errors,
            "warnings": self.warnings
        }


class WebXIntegrityChecker:
    """Manages WebX component integrity verification and permission enforcement"""
    
    def __init__(self):
        self.permissions_registry = self._initialize_permissions()
        self.component_hashes: Dict[str, str] = {}
        self.granted_permissions: Dict[str, Set[str]] = {}  # client_id -> permissions
        self.integrity_cache: Dict[str, IntegrityCheckResult] = {}
        self.cache_ttl = timedelta(minutes=15)  # Cache integrity results for 15 minutes
        
    def _initialize_permissions(self) -> Dict[str, WebXPermission]:
        """Initialize the WebX permissions registry"""
        return {
            # Basic WebX permissions
            "webx.dom.read": WebXPermission(
                name="webx.dom.read",
                level=PermissionLevel.READ_ONLY,
                description="Read DOM structure and content",
                required_capabilities={"ui_interaction"},
                auto_grant=True
            ),
            "webx.dom.modify": WebXPermission(
                name="webx.dom.modify",
                level=PermissionLevel.STANDARD,
                description="Modify DOM elements and content",
                required_capabilities={"ui_interaction"},
                auto_grant=False
            ),
            "webx.form.fill": WebXPermission(
                name="webx.form.fill",
                level=PermissionLevel.STANDARD,
                description="Fill form fields automatically",
                required_capabilities={"ui_interaction"},
                auto_grant=True
            ),
            "webx.form.submit": WebXPermission(
                name="webx.form.submit",
                level=PermissionLevel.ELEVATED,
                description="Submit forms on behalf of user",
                required_capabilities={"ui_interaction"},
                auto_grant=False
            ),
            "webx.navigation": WebXPermission(
                name="webx.navigation",
                level=PermissionLevel.STANDARD,
                description="Navigate between pages and URLs",
                required_capabilities={"network_access"},
                auto_grant=True
            ),
            "webx.download": WebXPermission(
                name="webx.download",
                level=PermissionLevel.STANDARD,
                description="Download files from web pages",
                required_capabilities={"network_access", "file_write"},
                auto_grant=False
            ),
            "webx.upload": WebXPermission(
                name="webx.upload",
                level=PermissionLevel.ELEVATED,
                description="Upload files through web forms",
                required_capabilities={"file_read", "network_access"},
                auto_grant=False
            ),
            "webx.storage.read": WebXPermission(
                name="webx.storage.read",
                level=PermissionLevel.STANDARD,
                description="Read browser storage (localStorage, cookies)",
                required_capabilities={"system_info"},
                auto_grant=False
            ),
            "webx.storage.write": WebXPermission(
                name="webx.storage.write",
                level=PermissionLevel.ELEVATED,
                description="Write to browser storage",
                required_capabilities={"system_info"},
                auto_grant=False
            ),
            "webx.native.messaging": WebXPermission(
                name="webx.native.messaging",
                level=PermissionLevel.SYSTEM,
                description="Communicate with native Desktop Agent",
                required_capabilities={"process_control"},
                auto_grant=True
            ),
            "webx.screenshot": WebXPermission(
                name="webx.screenshot",
                level=PermissionLevel.STANDARD,
                description="Capture screenshots of web pages",
                required_capabilities={"screen_capture"},
                auto_grant=True
            ),
            "webx.cookies.access": WebXPermission(
                name="webx.cookies.access",
                level=PermissionLevel.ELEVATED,
                description="Access and modify browser cookies",
                required_capabilities={"network_access"},
                auto_grant=False
            ),
            "webx.history.read": WebXPermission(
                name="webx.history.read",
                level=PermissionLevel.STANDARD,
                description="Read browser history",
                required_capabilities={"system_info"},
                auto_grant=False
            ),
            "webx.tabs.control": WebXPermission(
                name="webx.tabs.control",
                level=PermissionLevel.ELEVATED,
                description="Create, close, and control browser tabs",
                required_capabilities={"ui_interaction"},
                auto_grant=False
            ),
            "webx.extension.management": WebXPermission(
                name="webx.extension.management",
                level=PermissionLevel.SYSTEM,
                description="Manage browser extensions",
                required_capabilities={"process_control"},
                auto_grant=False
            )
        }
    
    def register_component_hash(self, component_name: str, expected_hash: str):
        """Register expected hash for a WebX component"""
        self.component_hashes[component_name] = expected_hash
        logger.info(f"Registered component hash: {component_name}")
    
    def verify_component_integrity(self, component_path: Path, component_name: str = None) -> IntegrityCheckResult:
        """Verify integrity of a WebX component"""
        if component_name is None:
            component_name = component_path.name
            
        # Check cache first
        cache_key = f"{component_name}:{component_path}"
        if cache_key in self.integrity_cache:
            cached = self.integrity_cache[cache_key]
            if cached.last_checked and datetime.now() - cached.last_checked < self.cache_ttl:
                return cached
        
        result = IntegrityCheckResult(
            status=IntegrityStatus.UNKNOWN,
            component=component_name,
            last_checked=datetime.now()
        )
        
        try:
            if not component_path.exists():
                result.status = IntegrityStatus.INVALID
                result.errors.append(f"Component file not found: {component_path}")
                return result
            
            # Calculate actual hash
            with open(component_path, 'rb') as f:
                content = f.read()
                result.actual_hash = hashlib.sha256(content).hexdigest()
            
            # Check against expected hash if available
            if component_name in self.component_hashes:
                result.expected_hash = self.component_hashes[component_name]
                
                if result.actual_hash == result.expected_hash:
                    result.status = IntegrityStatus.VALID
                    logger.debug(f"Component integrity verified: {component_name}")
                else:
                    result.status = IntegrityStatus.INVALID
                    result.errors.append(f"Hash mismatch: expected {result.expected_hash}, got {result.actual_hash}")
                    logger.warning(f"Component integrity failed: {component_name}")
            else:
                result.status = IntegrityStatus.UNKNOWN
                result.warnings.append(f"No expected hash registered for {component_name}")
                logger.debug(f"No expected hash for component: {component_name}")
            
            # Cache result
            self.integrity_cache[cache_key] = result
            
        except Exception as e:
            result.status = IntegrityStatus.INVALID
            result.errors.append(f"Integrity check error: {str(e)}")
            logger.error(f"Failed to verify integrity of {component_name}: {e}")
        
        return result
    
    def check_permission(
        self, 
        client_id: str, 
        permission_name: str, 
        capabilities: Set[str] = None
    ) -> Tuple[bool, List[str]]:
        """Check if a client has a specific WebX permission"""
        
        errors = []
        
        # Check if permission exists
        if permission_name not in self.permissions_registry:
            errors.append(f"Unknown permission: {permission_name}")
            return False, errors
        
        permission = self.permissions_registry[permission_name]
        
        # Check if permission is already granted
        client_permissions = self.granted_permissions.get(client_id, set())
        if permission_name in client_permissions:
            return True, []
        
        # Check capability requirements
        if capabilities is None:
            capabilities = set()
            
        missing_capabilities = permission.required_capabilities - capabilities
        if missing_capabilities:
            errors.append(f"Missing required capabilities: {', '.join(missing_capabilities)}")
        
        # Check if auto-grant is enabled
        if permission.auto_grant and not missing_capabilities:
            self.grant_permission(client_id, permission_name)
            return True, []
        
        return False, errors
    
    def grant_permission(self, client_id: str, permission_name: str) -> bool:
        """Grant a permission to a client"""
        try:
            if permission_name not in self.permissions_registry:
                logger.warning(f"Attempted to grant unknown permission: {permission_name}")
                return False
            
            if client_id not in self.granted_permissions:
                self.granted_permissions[client_id] = set()
            
            self.granted_permissions[client_id].add(permission_name)
            logger.info(f"Granted permission {permission_name} to client {client_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to grant permission {permission_name} to {client_id}: {e}")
            return False
    
    def revoke_permission(self, client_id: str, permission_name: str) -> bool:
        """Revoke a permission from a client"""
        try:
            client_permissions = self.granted_permissions.get(client_id, set())
            if permission_name in client_permissions:
                client_permissions.remove(permission_name)
                logger.info(f"Revoked permission {permission_name} from client {client_id}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Failed to revoke permission {permission_name} from {client_id}: {e}")
            return False
    
    def revoke_all_permissions(self, client_id: str):
        """Revoke all permissions from a client"""
        try:
            if client_id in self.granted_permissions:
                del self.granted_permissions[client_id]
                logger.info(f"Revoked all permissions from client {client_id}")
                
        except Exception as e:
            logger.error(f"Failed to revoke all permissions from {client_id}: {e}")
    
    def get_client_permissions(self, client_id: str) -> List[Dict[str, Any]]:
        """Get all permissions granted to a client"""
        client_permissions = self.granted_permissions.get(client_id, set())
        
        result = []
        for perm_name in client_permissions:
            if perm_name in self.permissions_registry:
                perm = self.permissions_registry[perm_name]
                result.append({
                    **perm.to_dict(),
                    "granted_at": "unknown"  # Would track this in production
                })
        
        return result
    
    def validate_webx_request(
        self, 
        client_id: str, 
        request: Dict[str, Any],
        capabilities: Set[str] = None
    ) -> Tuple[bool, List[str], List[str]]:
        """Validate a WebX request from an extension"""
        
        errors = []
        warnings = []
        
        # Extract method and parameters
        method = request.get("method", "")
        params = request.get("params", {})
        
        # Determine required permissions based on method
        required_permissions = self._get_required_permissions_for_method(method)
        
        # Check each required permission
        for permission in required_permissions:
            allowed, perm_errors = self.check_permission(client_id, permission, capabilities)
            if not allowed:
                errors.extend([f"Permission {permission}: {err}" for err in perm_errors])
        
        # Additional security checks
        if method == "execute_script":
            script = params.get("script", "")
            if self._is_dangerous_script(script):
                errors.append("Script contains potentially dangerous operations")
        
        if method == "navigate":
            url = params.get("url", "")
            if self._is_blocked_url(url):
                errors.append(f"Navigation to blocked URL: {url}")
        
        # Rate limiting check (simplified)
        if not self._check_rate_limit(client_id):
            errors.append("Rate limit exceeded")
        
        is_allowed = len(errors) == 0
        
        if not is_allowed:
            logger.warning(f"WebX request blocked for client {client_id}: {method}")
        
        return is_allowed, errors, warnings
    
    def _get_required_permissions_for_method(self, method: str) -> List[str]:
        """Map WebX methods to required permissions"""
        method_permissions = {
            "get_dom_structure": ["webx.dom.read"],
            "modify_element": ["webx.dom.modify"],
            "fill_form_field": ["webx.form.fill"],
            "submit_form": ["webx.form.submit"],
            "navigate": ["webx.navigation"],
            "download_file": ["webx.download"],
            "upload_file": ["webx.upload"],
            "get_local_storage": ["webx.storage.read"],
            "set_local_storage": ["webx.storage.write"],
            "take_screenshot": ["webx.screenshot"],
            "get_cookies": ["webx.cookies.access"],
            "set_cookies": ["webx.cookies.access"],
            "get_history": ["webx.history.read"],
            "create_tab": ["webx.tabs.control"],
            "close_tab": ["webx.tabs.control"],
            "execute_script": ["webx.dom.modify"],
            "native_message": ["webx.native.messaging"]
        }
        
        return method_permissions.get(method, [])
    
    def _is_dangerous_script(self, script: str) -> bool:
        """Check if a script contains dangerous operations"""
        dangerous_patterns = [
            "eval(",
            "Function(",
            "document.write(",
            "innerHTML =",
            "outerHTML =",
            "location.href =",
            "window.open(",
            "XMLHttpRequest",
            "fetch(",
            "localStorage.clear(",
            "sessionStorage.clear("
        ]
        
        script_lower = script.lower()
        return any(pattern.lower() in script_lower for pattern in dangerous_patterns)
    
    def _is_blocked_url(self, url: str) -> bool:
        """Check if a URL is blocked by security policy"""
        blocked_domains = [
            "file://",
            "javascript:",
            "data:",
            "vbscript:",
            "chrome://",
            "chrome-extension://",
            "moz-extension://"
        ]
        
        url_lower = url.lower()
        return any(blocked.lower() in url_lower for blocked in blocked_domains)
    
    def _check_rate_limit(self, client_id: str) -> bool:
        """Simple rate limiting check (would be more sophisticated in production)"""
        # Placeholder: allow all requests for now
        # In production, this would track request counts per time window
        return True
    
    def perform_integrity_audit(self) -> Dict[str, Any]:
        """Perform a comprehensive integrity audit of all WebX components"""
        
        webx_dir = Path("webx-extension")
        audit_results = {
            "audit_time": datetime.now().isoformat(),
            "components_checked": 0,
            "components_valid": 0,
            "components_invalid": 0,
            "components_unknown": 0,
            "results": []
        }
        
        # Define critical WebX components to check
        critical_components = [
            "manifest.json",
            "background.js",
            "content.js",
            "sdk/webx-plugin-sdk.js",
            "plugins/form-helper-plugin.js"
        ]
        
        for component in critical_components:
            component_path = webx_dir / component
            result = self.verify_component_integrity(component_path, component)
            
            audit_results["components_checked"] += 1
            if result.status == IntegrityStatus.VALID:
                audit_results["components_valid"] += 1
            elif result.status == IntegrityStatus.INVALID:
                audit_results["components_invalid"] += 1
            else:
                audit_results["components_unknown"] += 1
            
            audit_results["results"].append(result.to_dict())
        
        logger.info(f"WebX integrity audit completed: {audit_results['components_checked']} components checked")
        return audit_results
    
    def get_security_metrics(self) -> Dict[str, Any]:
        """Get security metrics for dashboard"""
        
        total_clients = len(self.granted_permissions)
        total_permissions_granted = sum(len(perms) for perms in self.granted_permissions.values())
        
        # Count permissions by level
        permission_levels = {}
        for client_perms in self.granted_permissions.values():
            for perm_name in client_perms:
                if perm_name in self.permissions_registry:
                    level = self.permissions_registry[perm_name].level.value
                    permission_levels[level] = permission_levels.get(level, 0) + 1
        
        return {
            "webx_clients_active": total_clients,
            "webx_permissions_granted": total_permissions_granted,
            "webx_permission_levels": permission_levels,
            "webx_integrity_cache_size": len(self.integrity_cache),
            "webx_registered_components": len(self.component_hashes)
        }


# Global integrity checker instance
_integrity_checker: Optional[WebXIntegrityChecker] = None


def get_integrity_checker() -> WebXIntegrityChecker:
    """Get the global WebX integrity checker instance"""
    global _integrity_checker
    if _integrity_checker is None:
        _integrity_checker = WebXIntegrityChecker()
        
        # Register default component hashes (would be loaded from config in production)
        _initialize_default_hashes(_integrity_checker)
    
    return _integrity_checker


def _initialize_default_hashes(checker: WebXIntegrityChecker):
    """Initialize default component hashes"""
    # These would typically be loaded from a secure configuration file
    default_hashes = {
        "background.js": "placeholder_hash_background_js",
        "content.js": "placeholder_hash_content_js",  
        "webx-plugin-sdk.js": "placeholder_hash_sdk_js",
        "form-helper-plugin.js": "placeholder_hash_form_helper_js"
    }
    
    for component, hash_value in default_hashes.items():
        checker.register_component_hash(component, hash_value)