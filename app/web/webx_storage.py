"""
WebX Storage Manager - Phase 7
Advanced cookie and storage management for WebX contexts
"""

import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone


logger = logging.getLogger(__name__)


class CookieTransferError(Exception):
    """Raised when cookie transfer operations fail"""
    pass


class StorageSecurityError(Exception):
    """Raised when storage operations violate security policies"""
    pass


@dataclass
class CookieInfo:
    """Information about a browser cookie"""
    name: str
    value: str
    domain: str
    path: str = "/"
    secure: bool = True
    http_only: bool = True
    same_site: str = "Strict"  # "Strict", "Lax", "None"
    expires: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert cookie to dictionary"""
        cookie_dict = {
            "name": self.name,
            "value": self.value,
            "domain": self.domain,
            "path": self.path,
            "secure": self.secure,
            "httpOnly": self.http_only,
            "sameSite": self.same_site
        }

        if self.expires:
            cookie_dict["expires"] = self.expires.timestamp()

        return cookie_dict

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CookieInfo':
        """Create cookie from dictionary"""
        expires = None
        if "expires" in data and data["expires"]:
            expires = datetime.fromtimestamp(data["expires"], tz=timezone.utc)

        return cls(
            name=data["name"],
            value=data["value"],
            domain=data["domain"],
            path=data.get("path", "/"),
            secure=data.get("secure", True),
            http_only=data.get("httpOnly", True),
            same_site=data.get("sameSite", "Strict"),
            expires=expires
        )


@dataclass
class StorageData:
    """Browser storage data (localStorage, sessionStorage)"""
    storage_type: str  # "localStorage" or "sessionStorage"
    domain: str
    data: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert storage data to dictionary"""
        return {
            "storage_type": self.storage_type,
            "domain": self.domain,
            "data": self.data
        }


class WebXStorageManager:
    """Manages cookies and browser storage across WebX contexts"""

    def __init__(self, browser_context=None):
        """Initialize storage manager"""
        self.browser_context = browser_context
        self.cookie_operations_count = 0
        self.storage_operations_count = 0

        # Security policy for cookie operations
        self.security_policy = {
            "require_secure_cookies": True,
            "require_http_only": True,
            "default_same_site": "Strict",
            "allowed_domains": [],  # Empty = allow all
            "blocked_domains": ["ads.example.com", "tracking.example.com"],
            "max_cookie_value_length": 4096
        }

        logger.info("WebX Storage Manager initialized")

    def set_cookie(
        self,
        name: str,
        value: str,
        domain: str,
        path: str = "/",
        secure: bool = True,
        http_only: bool = True,
        same_site: str = "Strict",
        expires: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Set cookie with security validation

        Args:
            name: Cookie name
            value: Cookie value
            domain: Cookie domain
            path: Cookie path
            secure: Secure flag
            http_only: HttpOnly flag
            same_site: SameSite attribute
            expires: Expiration datetime

        Returns:
            Dict with operation result
        """
        try:
            # Validate security requirements
            security_result = self._validate_cookie_security(
                name, value, domain, secure, http_only, same_site
            )

            if not security_result["valid"]:
                raise CookieTransferError(
                    f"Cookie security validation failed: {security_result['error']}"
                )

            # Create cookie info
            cookie = CookieInfo(
                name=name,
                value=value,
                domain=domain,
                path=path,
                secure=secure,
                http_only=http_only,
                same_site=same_site,
                expires=expires
            )

            # Set cookie in browser context
            set_result = self._set_browser_cookie(cookie.to_dict())

            if set_result["success"]:
                self.cookie_operations_count += 1

                logger.info(f"Cookie set successfully: {name} for {domain}")

                return {
                    "success": True,
                    "cookie_name": name,
                    "cookie_domain": domain,
                    "security_validated": True
                }
            else:
                raise CookieTransferError(f"Failed to set cookie: {set_result.get('error', 'Unknown error')}")

        except Exception as e:
            logger.error(f"Cookie set operation failed: {e}")
            raise CookieTransferError(str(e))

    def get_cookies(
        self,
        domain: Optional[str] = None,
        name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get cookies filtered by domain and/or name

        Args:
            domain: Filter by domain (optional)
            name: Filter by specific cookie name (optional)

        Returns:
            Dict with cookies list
        """
        try:
            # Get all cookies from browser context
            all_cookies = self._get_browser_cookies()

            # Apply filters
            filtered_cookies = []

            for cookie_data in all_cookies:
                # Domain filter
                if domain and not self._domain_matches(cookie_data.get("domain", ""), domain):
                    continue

                # Name filter
                if name and cookie_data.get("name") != name:
                    continue

                filtered_cookies.append(cookie_data)

            self.cookie_operations_count += 1

            logger.info(f"Retrieved {len(filtered_cookies)} cookies (domain: {domain}, name: {name})")

            return {
                "success": True,
                "cookies": filtered_cookies,
                "total_count": len(filtered_cookies)
            }

        except Exception as e:
            logger.error(f"Cookie get operation failed: {e}")
            return {"success": False, "error": str(e), "cookies": []}

    def transfer_cookies(
        self,
        from_domain: str,
        to_domain: str,
        cookie_names: Optional[List[str]] = None,
        context_switch: bool = False
    ) -> Dict[str, Any]:
        """
        Transfer cookies between domains or contexts

        Args:
            from_domain: Source domain
            to_domain: Target domain
            cookie_names: Specific cookies to transfer (optional)
            context_switch: Whether this is a context switch operation

        Returns:
            Dict with transfer results
        """
        try:
            # Get source cookies
            source_cookies = self.get_cookies(domain=from_domain)

            if not source_cookies["success"]:
                raise CookieTransferError(f"Failed to get source cookies from {from_domain}")

            cookies_to_transfer = source_cookies["cookies"]

            # Filter by specific cookie names if provided
            if cookie_names:
                cookies_to_transfer = [
                    cookie for cookie in cookies_to_transfer
                    if cookie.get("name") in cookie_names
                ]

            # Transfer each cookie
            transferred_count = 0
            transfer_errors = []

            for cookie_data in cookies_to_transfer:
                try:
                    # Update cookie domain
                    cookie_data["domain"] = to_domain

                    # Set cookie in target domain
                    self._set_browser_cookie(cookie_data)
                    transferred_count += 1

                except Exception as e:
                    transfer_errors.append(f"Cookie {cookie_data.get('name', 'unknown')}: {str(e)}")

            success = transferred_count > 0

            if success:
                logger.info(f"Transferred {transferred_count} cookies from {from_domain} to {to_domain}")

            return {
                "success": success,
                "transferred_count": transferred_count,
                "total_cookies": len(cookies_to_transfer),
                "errors": transfer_errors,
                "from_domain": from_domain,
                "to_domain": to_domain
            }

        except Exception as e:
            logger.error(f"Cookie transfer failed: {e}")
            raise CookieTransferError(str(e))

    def set_local_storage(
        self,
        domain: str,
        key: str,
        value: str
    ) -> Dict[str, Any]:
        """Set localStorage item for domain"""
        try:
            storage_data = {
                "domain": domain,
                "key": key,
                "value": value,
                "storage_type": "localStorage"
            }

            result = self._set_browser_storage(storage_data)

            if result["success"]:
                self.storage_operations_count += 1
                logger.info(f"localStorage set: {key} for {domain}")

            return result

        except Exception as e:
            logger.error(f"localStorage set failed: {e}")
            return {"success": False, "error": str(e)}

    def get_local_storage(
        self,
        domain: str,
        key: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get localStorage items for domain"""
        try:
            storage_data = self._get_browser_storage(domain, "localStorage")

            if key:
                # Return specific key
                value = storage_data.get(key)
                return {
                    "success": value is not None,
                    "key": key,
                    "value": value,
                    "domain": domain
                }
            else:
                # Return all localStorage for domain
                return {
                    "success": True,
                    "storage_data": storage_data,
                    "domain": domain,
                    "keys_count": len(storage_data)
                }

        except Exception as e:
            logger.error(f"localStorage get failed: {e}")
            return {"success": False, "error": str(e)}

    def clear_storage(
        self,
        domain: str,
        storage_types: List[str] = None
    ) -> Dict[str, Any]:
        """Clear storage for domain"""
        if storage_types is None:
            storage_types = ["cookies", "localStorage", "sessionStorage"]

        try:
            cleared_items = {
                "cookies": 0,
                "localStorage": 0,
                "sessionStorage": 0
            }

            for storage_type in storage_types:
                if storage_type == "cookies":
                    # Clear cookies for domain
                    cookies = self.get_cookies(domain=domain)
                    for cookie in cookies.get("cookies", []):
                        self._delete_browser_cookie(cookie["name"], domain)
                        cleared_items["cookies"] += 1

                elif storage_type in ["localStorage", "sessionStorage"]:
                    # Clear browser storage
                    self._clear_browser_storage(domain, storage_type)
                    cleared_items[storage_type] = 1  # Mark as cleared

            total_cleared = sum(cleared_items.values())

            logger.info(f"Cleared storage for {domain}: {cleared_items}")

            return {
                "success": True,
                "domain": domain,
                "cleared_items": cleared_items,
                "total_cleared": total_cleared
            }

        except Exception as e:
            logger.error(f"Storage clear failed: {e}")
            return {"success": False, "error": str(e)}

    def _validate_cookie_security(
        self,
        name: str,
        value: str,
        domain: str,
        secure: bool,
        http_only: bool,
        same_site: str
    ) -> Dict[str, Any]:
        """Validate cookie against security policy"""

        # Check blocked domains
        if domain in self.security_policy["blocked_domains"]:
            return {"valid": False, "error": f"Domain {domain} is blocked"}

        # Check allowed domains (if specified)
        allowed_domains = self.security_policy["allowed_domains"]
        if allowed_domains and not any(domain.endswith(allowed) for allowed in allowed_domains):
            return {"valid": False, "error": f"Domain {domain} not in allowed list"}

        # Security requirements
        if self.security_policy["require_secure_cookies"] and not secure:
            return {"valid": False, "error": "Secure flag required but not set"}

        if self.security_policy["require_http_only"] and not http_only:
            return {"valid": False, "error": "HttpOnly flag required but not set"}

        # Value length check
        max_length = self.security_policy["max_cookie_value_length"]
        if len(value) > max_length:
            return {"valid": False, "error": f"Cookie value exceeds maximum length {max_length}"}

        return {"valid": True}

    def _domain_matches(self, cookie_domain: str, target_domain: str) -> bool:
        """Check if cookie domain matches target domain"""
        if cookie_domain == target_domain:
            return True

        # Handle subdomain matching
        if cookie_domain.startswith('.') and target_domain.endswith(cookie_domain[1:]):
            return True

        return False

    def _set_browser_cookie(self, cookie_data: Dict[str, Any]) -> Dict[str, Any]:
        """Set cookie in browser context (mock implementation)"""
        # Mock implementation - in real usage would interact with browser
        return {"success": True}

    def _get_browser_cookies(self) -> List[Dict[str, Any]]:
        """Get cookies from browser context (mock implementation)"""
        # Mock implementation - in real usage would query browser
        if hasattr(self, '_mock_cookies'):
            return self._mock_cookies

        return []

    def _delete_browser_cookie(self, name: str, domain: str) -> Dict[str, Any]:
        """Delete cookie from browser context (mock implementation)"""
        # Mock implementation
        return {"success": True}

    def _set_browser_storage(self, storage_data: Dict[str, Any]) -> Dict[str, Any]:
        """Set browser storage item (mock implementation)"""
        # Mock implementation
        return {"success": True}

    def _get_browser_storage(self, domain: str, storage_type: str) -> Dict[str, Any]:
        """Get browser storage items (mock implementation)"""
        # Mock implementation
        return {}

    def _clear_browser_storage(self, domain: str, storage_type: str) -> Dict[str, Any]:
        """Clear browser storage (mock implementation)"""
        # Mock implementation
        return {"success": True}

    def get_storage_metrics(self) -> Dict[str, Any]:
        """Get storage operation metrics"""
        return {
            "cookie_operations": self.cookie_operations_count,
            "storage_operations": self.storage_operations_count,
            "security_policy": self.security_policy
        }


# Global storage manager instance
_storage_manager: Optional[WebXStorageManager] = None


def get_storage_manager() -> WebXStorageManager:
    """Get global WebX storage manager instance"""
    global _storage_manager
    if _storage_manager is None:
        _storage_manager = WebXStorageManager()
    return _storage_manager


def webx_set_cookie(name: str, value: str, domain: str, **kwargs) -> Dict[str, Any]:
    """
    Convenience function for cookie setting

    Usage:
        webx_set_cookie("session", "abc123", "example.com", secure=True)
        webx_set_cookie("token", "xyz789", "app.com", http_only=True)
    """
    storage_manager = get_storage_manager()
    return storage_manager.set_cookie(name, value, domain, **kwargs)


def webx_get_cookies(domain: Optional[str] = None, **kwargs) -> Dict[str, Any]:
    """
    Convenience function for cookie retrieval

    Usage:
        webx_get_cookies(domain="example.com")
        webx_get_cookies(name="session_token")
    """
    storage_manager = get_storage_manager()
    return storage_manager.get_cookies(domain, **kwargs)
