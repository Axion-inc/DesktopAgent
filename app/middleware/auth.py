"""
Authentication and Authorization middleware for FastAPI.

Provides RBAC integration with FastAPI endpoints and request context.
"""

from fastapi import HTTPException, Depends, Request
from fastapi.security import HTTPBasic, HTTPBasicCredentials, HTTPBearer
from typing import Optional, Dict, List
from functools import wraps
# import secrets

# Import RBAC components
try:
    from app.security.rbac import get_rbac_manager, RBACUser, Permission
except ImportError:
    # Fallback for development
    RBACUser = None
    Permission = None

security = HTTPBasic()
bearer_security = HTTPBearer(auto_error=False)

# Global user context (for request-scoped user tracking)
_current_user_context: Dict[str, RBACUser] = {}


class AuthenticationError(HTTPException):
    """Authentication failed."""
    def __init__(self, detail: str = "Authentication failed"):
        super().__init__(status_code=401, detail=detail)


class AuthorizationError(HTTPException):
    """Authorization failed (insufficient permissions)."""
    def __init__(self, detail: str = "Insufficient permissions"):
        super().__init__(status_code=403, detail=detail)


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPBasicCredentials] = Depends(security),
) -> Optional[RBACUser]:
    """Get the current authenticated user."""
    if not credentials:
        return None

    try:
        rbac = get_rbac_manager()
        user = rbac.authenticate_user(credentials.username, credentials.password)

        if not user:
            raise AuthenticationError("Invalid credentials")

        if not user.active:
            raise AuthenticationError("Account disabled")

        # Store in request-scoped context
        request_id = id(request)
        _current_user_context[request_id] = user

        # Log authentication for audit
        rbac.log_user_action(
            user_id=user.id,
            action="authenticate",
            resource="api",
            success=True,
            ip_address=request.client.host if request.client else "unknown"
        )

        return user

    except Exception as e:
        if isinstance(e, (AuthenticationError, AuthorizationError)):
            raise
        raise AuthenticationError("Authentication error")


def get_current_user_from_context() -> Optional[RBACUser]:
    """Get current user from global context (for use outside request cycle)."""
    # This is a simplified version - in production you'd want proper request context
    if _current_user_context:
        return list(_current_user_context.values())[-1]  # Get most recent
    return None


def require_permission(permission: str):
    """Decorator to require specific permission for endpoint access."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract request and user from args/kwargs
            request = None
            user = None

            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break

            if "current_user" in kwargs:
                user = kwargs["current_user"]
            elif "user" in kwargs:
                user = kwargs["user"]

            # Get user if not provided
            if not user and request:
                try:
                    user = await get_current_user(request)
                except Exception:
                    user = None

            if not user:
                raise AuthenticationError("Authentication required")

            # Check permission
            try:
                rbac = get_rbac_manager()
                if not rbac.check_user_permission(user.id, permission):
                    # Log authorization failure
                    rbac.log_user_action(
                        user_id=user.id,
                        action="permission_denied",
                        resource=permission,
                        success=False,
                        ip_address=request.client.host if request and request.client else "unknown"
                    )
                    raise AuthorizationError(f"Permission '{permission}' required")

                # Log successful authorization
                rbac.log_user_action(
                    user_id=user.id,
                    action="permission_granted",
                    resource=permission,
                    success=True,
                    ip_address=request.client.host if request and request.client else "unknown"
                )

            except Exception as e:
                if isinstance(e, AuthorizationError):
                    raise
                raise AuthorizationError("Authorization check failed")

            return await func(*args, **kwargs)
        return wrapper
    return decorator


def require_role(role: str):
    """Decorator to require specific role for endpoint access."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract user
            user = None
            request = None

            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break

            if "current_user" in kwargs:
                user = kwargs["current_user"]
            elif "user" in kwargs:
                user = kwargs["user"]

            if not user and request:
                try:
                    user = await get_current_user(request)
                except Exception:
                    user = None

            if not user:
                raise AuthenticationError("Authentication required")

            # Check role
            try:
                rbac = get_rbac_manager()
                user_roles = rbac.get_user_roles(user.id)
                role_names = [r.name for r in user_roles]

                if role not in role_names:
                    # Check role hierarchy (Admin can do everything)
                    if "Admin" not in role_names:
                        rbac.log_user_action(
                            user_id=user.id,
                            action="role_denied",
                            resource=role,
                            success=False,
                            ip_address=request.client.host if request and request.client else "unknown"
                        )
                        raise AuthorizationError(f"Role '{role}' required")

            except Exception as e:
                if isinstance(e, AuthorizationError):
                    raise
                raise AuthorizationError("Role check failed")

            return await func(*args, **kwargs)
        return wrapper
    return decorator


# Convenience permission decorators


def require_admin(func):
    """Require Admin role."""
    return require_role("Admin")(func)


def require_editor(func):
    """Require Editor role or higher."""
    def decorator(inner_func):
        @wraps(inner_func)
        async def wrapper(*args, **kwargs):
            user = None
            request = None

            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break

            if "current_user" in kwargs:
                user = kwargs["current_user"]

            if not user and request:
                try:
                    user = await get_current_user(request)
                except Exception:
                    user = None

            if not user:
                raise AuthenticationError("Authentication required")

            # Check if user has Editor or Admin role
            try:
                rbac = get_rbac_manager()
                user_roles = rbac.get_user_roles(user.id)
                role_names = [r.name for r in user_roles]

                if not any(role in role_names for role in ["Editor", "Admin"]):
                    raise AuthorizationError("Editor role or higher required")

            except Exception as e:
                if isinstance(e, AuthorizationError):
                    raise
                raise AuthorizationError("Role check failed")

            return await inner_func(*args, **kwargs)
        return wrapper
    return decorator(func)


def require_runner(func):
    """Require Runner role or higher."""
    def decorator(inner_func):
        @wraps(inner_func)
        async def wrapper(*args, **kwargs):
            user = None
            request = None

            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break

            if "current_user" in kwargs:
                user = kwargs["current_user"]

            if not user and request:
                try:
                    user = await get_current_user(request)
                except Exception:
                    user = None

            if not user:
                raise AuthenticationError("Authentication required")

            # Check if user has Runner, Editor, or Admin role
            try:
                rbac = get_rbac_manager()
                user_roles = rbac.get_user_roles(user.id)
                role_names = [r.name for r in user_roles]

                if not any(role in role_names for role in ["Runner", "Editor", "Admin"]):
                    raise AuthorizationError("Runner role or higher required")

            except Exception as e:
                if isinstance(e, AuthorizationError):
                    raise
                raise AuthorizationError("Role check failed")

            return await inner_func(*args, **kwargs)
        return wrapper
    return decorator(func)


async def cleanup_user_context(request: Request):
    """Cleanup user context after request."""
    request_id = id(request)
    _current_user_context.pop(request_id, None)


# RBAC-protected endpoint helpers


def create_protected_endpoint(
    app,
    path: str,
    methods: List[str],
    handler,
    required_permission: Optional[str] = None,
    required_role: Optional[str] = None,
):
    """Helper to create RBAC-protected endpoints."""

    if required_permission:
        handler = require_permission(required_permission)(handler)
    elif required_role:
        handler = require_role(required_role)(handler)

    # Add the endpoint to FastAPI
    for method in methods:
        if method.upper() == "GET":
            app.get(path)(handler)
        elif method.upper() == "POST":
            app.post(path)(handler)
        elif method.upper() == "PUT":
            app.put(path)(handler)
        elif method.upper() == "DELETE":
            app.delete(path)(handler)
