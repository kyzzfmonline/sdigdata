"""RBAC (Role-Based Access Control) service for role and permission management."""

from typing import Any
from uuid import UUID

import asyncpg


# ============================================================================
# ROLES
# ============================================================================


async def list_roles(conn: asyncpg.Connection) -> list[dict[str, Any]]:
    """List all roles with permission counts."""
    results = await conn.fetch("""
        SELECT
            r.id,
            r.name,
            r.description,
            r.created_at,
            COUNT(DISTINCT rp.permission_id) as permission_count,
            COUNT(DISTINCT ur.user_id) as user_count
        FROM roles r
        LEFT JOIN role_permissions rp ON r.id = rp.role_id
        LEFT JOIN user_roles ur ON r.id = ur.role_id
        GROUP BY r.id, r.name, r.description, r.created_at
        ORDER BY r.name
    """)
    return [dict(row) for row in results]


async def get_role_by_id(
    conn: asyncpg.Connection, role_id: UUID
) -> dict[str, Any] | None:
    """Get role details with permissions."""
    role = await conn.fetchrow("""
        SELECT id, name, description, created_at
        FROM roles
        WHERE id = $1
    """, str(role_id))

    if not role:
        return None

    # Get permissions for this role
    permissions = await conn.fetch("""
        SELECT p.id, p.name, p.resource, p.action, p.description
        FROM role_permissions rp
        JOIN permissions p ON rp.permission_id = p.id
        WHERE rp.role_id = $1
        ORDER BY p.resource, p.action
    """, str(role_id))

    role_dict = dict(role)
    role_dict["permissions"] = [dict(p) for p in permissions]

    return role_dict


async def create_role(
    conn: asyncpg.Connection,
    name: str,
    description: str | None = None,
) -> dict[str, Any] | None:
    """Create a new role."""
    result = await conn.fetchrow("""
        INSERT INTO roles (name, description)
        VALUES ($1, $2)
        RETURNING id, name, description, created_at
    """, name, description)

    return dict(result) if result else None


async def update_role(
    conn: asyncpg.Connection,
    role_id: UUID,
    name: str | None = None,
    description: str | None = None,
) -> dict[str, Any] | None:
    """Update a role."""
    updates: list[str] = []
    params: list[Any] = []

    if name is not None:
        updates.append(f"name = ${len(params) + 1}")
        params.append(name)

    if description is not None:
        updates.append(f"description = ${len(params) + 1}")
        params.append(description)

    if not updates:
        return await get_role_by_id(conn, role_id)

    params.append(str(role_id))

    query = f"""
        UPDATE roles
        SET {", ".join(updates)}
        WHERE id = ${len(params)}
        RETURNING id, name, description, created_at
    """

    result = await conn.fetchrow(query, *params)
    return dict(result) if result else None


async def delete_role(conn: asyncpg.Connection, role_id: UUID) -> bool:
    """Delete a role."""
    result = await conn.execute(
        "DELETE FROM roles WHERE id = $1",
        str(role_id),
    )
    return int(result.split()[-1]) > 0


# ============================================================================
# PERMISSIONS
# ============================================================================


async def list_permissions(
    conn: asyncpg.Connection,
    resource: str | None = None,
) -> list[dict[str, Any]]:
    """List all permissions, optionally filtered by resource."""
    query = """
        SELECT id, name, resource, action, description
        FROM permissions
    """
    params: list[str] = []

    if resource:
        query += " WHERE resource = $1"
        params.append(resource)

    query += " ORDER BY resource, action"

    results = await conn.fetch(query, *params)
    return [dict(row) for row in results]


async def create_permission(
    conn: asyncpg.Connection,
    name: str,
    resource: str,
    action: str,
    description: str | None = None,
) -> dict[str, Any] | None:
    """Create a new permission."""
    result = await conn.fetchrow("""
        INSERT INTO permissions (name, resource, action, description)
        VALUES ($1, $2, $3, $4)
        RETURNING id, name, resource, action, description
    """, name, resource, action, description)

    return dict(result) if result else None


async def delete_permission(conn: asyncpg.Connection, permission_id: UUID) -> bool:
    """Delete a permission."""
    result = await conn.execute(
        "DELETE FROM permissions WHERE id = $1",
        str(permission_id),
    )
    return int(result.split()[-1]) > 0


# ============================================================================
# ROLE PERMISSIONS
# ============================================================================


async def assign_permissions_to_role(
    conn: asyncpg.Connection,
    role_id: UUID,
    permission_ids: list[UUID],
) -> int:
    """Assign multiple permissions to a role."""
    count = 0
    for perm_id in permission_ids:
        result = await conn.execute("""
            INSERT INTO role_permissions (role_id, permission_id)
            VALUES ($1, $2)
            ON CONFLICT DO NOTHING
        """, str(role_id), str(perm_id))

        if "INSERT" in result:
            count += 1

    return count


async def revoke_permissions_from_role(
    conn: asyncpg.Connection,
    role_id: UUID,
    permission_ids: list[UUID],
) -> int:
    """Revoke multiple permissions from a role."""
    # Build query for multiple permission IDs
    placeholders = ",".join(f"${i+2}" for i in range(len(permission_ids)))
    query = f"""
        DELETE FROM role_permissions
        WHERE role_id = $1 AND permission_id IN ({placeholders})
    """

    params = [str(role_id)] + [str(pid) for pid in permission_ids]
    result = await conn.execute(query, *params)

    return int(result.split()[-1])


async def get_role_permissions(
    conn: asyncpg.Connection, role_id: UUID
) -> list[dict[str, Any]]:
    """Get all permissions for a role."""
    results = await conn.fetch("""
        SELECT p.id, p.name, p.resource, p.action, p.description
        FROM role_permissions rp
        JOIN permissions p ON rp.permission_id = p.id
        WHERE rp.role_id = $1
        ORDER BY p.resource, p.action
    """, str(role_id))

    return [dict(row) for row in results]


# ============================================================================
# USER ROLES
# ============================================================================


async def assign_role_to_user(
    conn: asyncpg.Connection,
    user_id: UUID,
    role_id: UUID,
) -> bool:
    """Assign a role to a user."""
    result = await conn.execute("""
        INSERT INTO user_roles (user_id, role_id)
        VALUES ($1, $2)
        ON CONFLICT DO NOTHING
    """, str(user_id), str(role_id))

    return "INSERT" in result


async def revoke_role_from_user(
    conn: asyncpg.Connection,
    user_id: UUID,
    role_id: UUID,
) -> bool:
    """Revoke a role from a user."""
    result = await conn.execute("""
        DELETE FROM user_roles
        WHERE user_id = $1 AND role_id = $2
    """, str(user_id), str(role_id))

    return int(result.split()[-1]) > 0


async def get_user_roles(
    conn: asyncpg.Connection, user_id: UUID
) -> list[dict[str, Any]]:
    """Get all roles assigned to a user."""
    results = await conn.fetch("""
        SELECT r.id, r.name, r.description, ur.assigned_at
        FROM user_roles ur
        JOIN roles r ON ur.role_id = r.id
        WHERE ur.user_id = $1
        ORDER BY r.name
    """, str(user_id))

    return [dict(row) for row in results]


async def get_user_permissions(
    conn: asyncpg.Connection, user_id: UUID
) -> list[dict[str, Any]]:
    """Get all permissions for a user (aggregated from all their roles)."""
    results = await conn.fetch("""
        SELECT DISTINCT p.id, p.name, p.resource, p.action, p.description
        FROM user_roles ur
        JOIN role_permissions rp ON ur.role_id = rp.role_id
        JOIN permissions p ON rp.permission_id = p.id
        WHERE ur.user_id = $1
        ORDER BY p.resource, p.action
    """, str(user_id))

    return [dict(row) for row in results]


async def get_role_users(
    conn: asyncpg.Connection, role_id: UUID
) -> list[dict[str, Any]]:
    """Get all users assigned to a role."""
    results = await conn.fetch("""
        SELECT u.id, u.username, u.email, ur.assigned_at
        FROM user_roles ur
        JOIN users u ON ur.user_id = u.id
        WHERE ur.role_id = $1 AND u.deleted = FALSE
        ORDER BY u.username
    """, str(role_id))

    return [dict(row) for row in results]
