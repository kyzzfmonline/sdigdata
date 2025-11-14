"""Permission checking service for role-based access control."""

from uuid import UUID

import asyncpg


class PermissionChecker:
    """Service for checking user permissions."""

    def __init__(self, conn: asyncpg.Connection):
        self.conn = conn

    async def has_permission(self, user_id: UUID, resource: str, action: str) -> bool:
        """Check if user has permission for a specific resource and action."""
        result = await self.conn.fetchval(
            """
            SELECT EXISTS(
                SELECT 1
                FROM user_roles ur
                JOIN role_permissions rp ON ur.role_id = rp.role_id
                JOIN permissions p ON rp.permission_id = p.id
                WHERE ur.user_id = $1
                AND ur.is_active = TRUE
                AND (ur.expires_at IS NULL OR ur.expires_at > CURRENT_TIMESTAMP)
                AND p.resource = $2
                AND p.action = $3
            )
            """,
            user_id,
            resource,
            action,
        )
        return result or False

    async def has_any_permission(self, user_id: UUID, permissions: list[tuple]) -> bool:
        """Check if user has any of the specified permissions."""
        if not permissions:
            return False

        # Build query for multiple permissions
        conditions = []
        params = [user_id]
        param_num = 2

        for resource, action in permissions:
            conditions.append(
                f"(p.resource = ${param_num} AND p.action = ${param_num + 1})"
            )
            params.extend([resource, action])
            param_num += 2

        query = f"""
            SELECT EXISTS(
                SELECT 1
                FROM user_roles ur
                JOIN role_permissions rp ON ur.role_id = rp.role_id
                JOIN permissions p ON rp.permission_id = p.id
                WHERE ur.user_id = $1
                AND ur.is_active = TRUE
                AND (ur.expires_at IS NULL OR ur.expires_at > CURRENT_TIMESTAMP)
                AND ({" OR ".join(conditions)})
            )
        """

        result = await self.conn.fetchval(query, *params)
        return result or False

    async def get_user_permissions(self, user_id: UUID) -> list[dict]:
        """Get all permissions for a user."""
        rows = await self.conn.fetch(
            """
            SELECT DISTINCT p.name, p.resource, p.action, p.description
            FROM user_roles ur
            JOIN role_permissions rp ON ur.role_id = rp.role_id
            JOIN permissions p ON rp.permission_id = p.id
            WHERE ur.user_id = $1
            AND ur.is_active = TRUE
            AND (ur.expires_at IS NULL OR ur.expires_at > CURRENT_TIMESTAMP)
            ORDER BY p.resource, p.action
            """,
            user_id,
        )
        return [dict(row) for row in rows]

    async def get_user_roles(self, user_id: UUID) -> list[dict]:
        """Get all active roles for a user."""
        rows = await self.conn.fetch(
            """
            SELECT r.id, r.name, r.description, r.level, ur.assigned_at, ur.expires_at, ur.is_active
            FROM user_roles ur
            JOIN roles r ON ur.role_id = r.id
            WHERE ur.user_id = $1
            AND ur.is_active = TRUE
            AND (ur.expires_at IS NULL OR ur.expires_at > CURRENT_TIMESTAMP)
            ORDER BY r.level DESC
            """,
            user_id,
        )
        return [dict(row) for row in rows]

    async def get_highest_role_level(self, user_id: UUID) -> int:
        """Get the highest role level for a user."""
        result = await self.conn.fetchval(
            """
            SELECT MAX(r.level)
            FROM user_roles ur
            JOIN roles r ON ur.role_id = r.id
            WHERE ur.user_id = $1
            AND ur.is_active = TRUE
            AND (ur.expires_at IS NULL OR ur.expires_at > CURRENT_TIMESTAMP)
            """,
            user_id,
        )
        return result or 0


async def check_permission(
    conn: asyncpg.Connection, user_id: UUID, resource: str, action: str
) -> bool:
    """Convenience function to check a single permission."""
    checker = PermissionChecker(conn)
    return await checker.has_permission(user_id, resource, action)


async def require_permission(
    conn: asyncpg.Connection, user_id: UUID, resource: str, action: str
) -> None:
    """Raise exception if user doesn't have permission."""
    if not await check_permission(conn, user_id, resource, action):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Insufficient permissions: {resource}.{action} required",
        )


# Import here to avoid circular imports
from fastapi import HTTPException, status  # noqa: E402
