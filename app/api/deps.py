"""API dependencies for authentication and authorization."""

from typing import Annotated, List, Tuple
from uuid import UUID
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import asyncpg

from app.core.database import get_db
from app.core.security import decode_access_token
from app.services.users import get_user_by_id
from app.services.permissions import PermissionChecker, require_permission

security = HTTPBearer()


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
) -> dict:
    """
    Dependency to get the current authenticated user.

    Validates JWT token and returns user data.
    """
    token = credentials.credentials
    payload = decode_access_token(token)

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = await get_user_by_id(conn, UUID(user_id))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Remove password hash from response
    user.pop("password_hash", None)
    return user


def require_admin(current_user: Annotated[dict, Depends(get_current_user)]) -> dict:
    """
    Dependency to require admin role.

    Raises HTTP 403 if user is not an admin.
    """
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required"
        )
    return current_user


async def require_permission_dep(
    resource: str,
    action: str,
    current_user: Annotated[dict, Depends(get_current_user)],
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
) -> dict:
    """
    Dependency to require specific permission.

    Raises HTTP 403 if user doesn't have the required permission.
    """
    await require_permission(conn, UUID(current_user["id"]), resource, action)
    return current_user


async def require_any_permission_dep(
    permissions: List[Tuple[str, str]],
    current_user: Annotated[dict, Depends(get_current_user)],
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
) -> dict:
    """
    Dependency to require any of the specified permissions.

    Raises HTTP 403 if user doesn't have any of the required permissions.
    """
    checker = PermissionChecker(conn)
    if not await checker.has_any_permission(UUID(current_user["id"]), permissions):
        perm_list = [f"{r}.{a}" for r, a in permissions]
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Insufficient permissions: one of {perm_list} required",
        )
    return current_user


# Convenience functions for common permissions
async def require_users_admin(
    current_user: Annotated[dict, Depends(get_current_user)],
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
):
    return await require_permission_dep("users", "admin", current_user, conn)


async def require_users_read(
    current_user: Annotated[dict, Depends(get_current_user)],
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
):
    return await require_permission_dep("users", "read", current_user, conn)


async def require_forms_admin(
    current_user: Annotated[dict, Depends(get_current_user)],
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
):
    return await require_permission_dep("forms", "admin", current_user, conn)


async def require_responses_admin(
    current_user: Annotated[dict, Depends(get_current_user)],
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
):
    return await require_permission_dep("responses", "admin", current_user, conn)


async def require_system_admin(
    current_user: Annotated[dict, Depends(get_current_user)],
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
):
    return await require_permission_dep("system", "admin", current_user, conn)
