"""Permission groups service for managing reusable permission sets."""

from typing import Any
from uuid import UUID

import asyncpg


# ============================================================================
# PERMISSION GROUP MANAGEMENT
# ============================================================================


async def create_permission_group(
    conn: asyncpg.Connection,
    name: str,
    description: str | None = None,
    permission_ids: list[UUID] | None = None,
    organization_id: UUID | None = None,
    is_system: bool = False,
) -> dict[str, Any]:
    """Create a new permission group.

    Args:
        conn: Database connection
        name: Group name
        description: Group description
        permission_ids: List of permission IDs to add to group
        organization_id: Organization ID (None = system-wide)
        is_system: Whether this is a system-managed group

    Returns:
        Created permission group with permissions
    """
    # Create group
    group = await conn.fetchrow(
        """
        INSERT INTO permission_groups (name, description, organization_id, is_system)
        VALUES ($1, $2, $3, $4)
        RETURNING id, name, description, organization_id, is_system, created_at, updated_at
        """,
        name,
        description,
        str(organization_id) if organization_id else None,
        is_system,
    )

    group_dict = dict(group) if group else {}

    # Add permissions if provided
    if permission_ids:
        await add_permissions_to_group(conn, UUID(group_dict["id"]), permission_ids)

    # Get full group with permissions
    return await get_permission_group_by_id(conn, UUID(group_dict["id"])) or group_dict


async def get_permission_group_by_id(
    conn: asyncpg.Connection, group_id: UUID
) -> dict[str, Any] | None:
    """Get permission group by ID with all permissions.

    Args:
        conn: Database connection
        group_id: Group ID

    Returns:
        Permission group with permissions list
    """
    # Get group
    group = await conn.fetchrow(
        """
        SELECT id, name, description, organization_id, is_system, created_at, updated_at
        FROM permission_groups
        WHERE id = $1
        """,
        str(group_id),
    )

    if not group:
        return None

    # Get permissions
    permissions = await conn.fetch(
        """
        SELECT p.id, p.name, p.resource, p.action, p.description
        FROM permission_group_permissions pgp
        JOIN permissions p ON pgp.permission_id = p.id
        WHERE pgp.group_id = $1
        ORDER BY p.resource, p.action
        """,
        str(group_id),
    )

    group_dict = dict(group)
    group_dict["permissions"] = [dict(p) for p in permissions]
    group_dict["permission_count"] = len(permissions)

    return group_dict


async def list_permission_groups(
    conn: asyncpg.Connection,
    organization_id: UUID | None = None,
    include_system: bool = True,
) -> list[dict[str, Any]]:
    """List all permission groups.

    Args:
        conn: Database connection
        organization_id: Filter by organization (None = all)
        include_system: Include system groups

    Returns:
        List of permission groups with permission counts
    """
    conditions = []
    params: list[Any] = []

    if organization_id:
        conditions.append("organization_id = $1")
        params.append(str(organization_id))

    if not include_system:
        conditions.append("is_system = FALSE")

    where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

    results = await conn.fetch(
        f"""
        SELECT
            pg.id, pg.name, pg.description, pg.organization_id, pg.is_system,
            pg.created_at, pg.updated_at,
            COUNT(pgp.permission_id) as permission_count
        FROM permission_groups pg
        LEFT JOIN permission_group_permissions pgp ON pg.id = pgp.group_id
        {where_clause}
        GROUP BY pg.id, pg.name, pg.description, pg.organization_id, pg.is_system, pg.created_at, pg.updated_at
        ORDER BY pg.name
        """,
        *params,
    )

    return [dict(row) for row in results]


async def update_permission_group(
    conn: asyncpg.Connection,
    group_id: UUID,
    name: str | None = None,
    description: str | None = None,
) -> dict[str, Any] | None:
    """Update permission group metadata.

    Args:
        conn: Database connection
        group_id: Group ID
        name: New name
        description: New description

    Returns:
        Updated permission group
    """
    updates = []
    params = []

    if name is not None:
        updates.append(f"name = ${len(params) + 1}")
        params.append(name)

    if description is not None:
        updates.append(f"description = ${len(params) + 1}")
        params.append(description)

    if not updates:
        return await get_permission_group_by_id(conn, group_id)

    updates.append("updated_at = CURRENT_TIMESTAMP")
    params.append(str(group_id))

    query = f"""
        UPDATE permission_groups
        SET {", ".join(updates)}
        WHERE id = ${len(params)}
        RETURNING id, name, description, organization_id, is_system, created_at, updated_at
    """

    result = await conn.fetchrow(query, *params)
    return dict(result) if result else None


async def delete_permission_group(conn: asyncpg.Connection, group_id: UUID) -> bool:
    """Delete a permission group.

    Args:
        conn: Database connection
        group_id: Group ID

    Returns:
        True if deleted, False if not found or system group
    """
    # Check if system group
    group = await conn.fetchrow(
        "SELECT is_system FROM permission_groups WHERE id = $1",
        str(group_id),
    )

    if not group:
        return False

    if group["is_system"]:
        # Cannot delete system groups
        return False

    result = await conn.execute(
        "DELETE FROM permission_groups WHERE id = $1",
        str(group_id),
    )

    return int(result.split()[-1]) > 0


# ============================================================================
# GROUP PERMISSIONS MANAGEMENT
# ============================================================================


async def add_permissions_to_group(
    conn: asyncpg.Connection, group_id: UUID, permission_ids: list[UUID]
) -> int:
    """Add permissions to a group.

    Args:
        conn: Database connection
        group_id: Group ID
        permission_ids: List of permission IDs

    Returns:
        Number of permissions added
    """
    count = 0
    for perm_id in permission_ids:
        result = await conn.execute(
            """
            INSERT INTO permission_group_permissions (group_id, permission_id)
            VALUES ($1, $2)
            ON CONFLICT DO NOTHING
            """,
            str(group_id),
            str(perm_id),
        )
        if "INSERT" in result:
            count += 1

    return count


async def remove_permissions_from_group(
    conn: asyncpg.Connection, group_id: UUID, permission_ids: list[UUID]
) -> int:
    """Remove permissions from a group.

    Args:
        conn: Database connection
        group_id: Group ID
        permission_ids: List of permission IDs

    Returns:
        Number of permissions removed
    """
    placeholders = ",".join(f"${i+2}" for i in range(len(permission_ids)))
    query = f"""
        DELETE FROM permission_group_permissions
        WHERE group_id = $1 AND permission_id IN ({placeholders})
    """

    params = [str(group_id)] + [str(pid) for pid in permission_ids]
    result = await conn.execute(query, *params)

    return int(result.split()[-1])


async def assign_group_to_role(
    conn: asyncpg.Connection, role_id: UUID, group_id: UUID
) -> int:
    """Assign all permissions from a group to a role.

    Args:
        conn: Database connection
        role_id: Role ID
        group_id: Permission group ID

    Returns:
        Number of permissions added to role
    """
    # Get all permissions from group
    permissions = await conn.fetch(
        """
        SELECT permission_id
        FROM permission_group_permissions
        WHERE group_id = $1
        """,
        str(group_id),
    )

    if not permissions:
        return 0

    # Add all permissions to role
    count = 0
    for perm in permissions:
        result = await conn.execute(
            """
            INSERT INTO role_permissions (role_id, permission_id)
            VALUES ($1, $2)
            ON CONFLICT DO NOTHING
            """,
            str(role_id),
            perm["permission_id"],
        )
        if "INSERT" in result:
            count += 1

    return count


# ============================================================================
# SYSTEM PERMISSION GROUPS (PRESETS)
# ============================================================================


async def create_system_permission_groups(conn: asyncpg.Connection) -> int:
    """Create default system permission groups.

    Args:
        conn: Database connection

    Returns:
        Number of groups created
    """
    # Define system groups
    groups = [
        {
            "name": "Forms Full Access",
            "description": "Complete access to form management",
            "permissions": ["forms:create", "forms:read", "forms:update", "forms:delete", "forms:publish", "forms:assign"],
        },
        {
            "name": "Responses Full Access",
            "description": "Complete access to response management",
            "permissions": ["responses:create", "responses:read", "responses:update", "responses:delete", "responses:export"],
        },
        {
            "name": "Read Only",
            "description": "View-only access to all resources",
            "permissions": ["forms:read", "responses:read", "organizations:read", "users:read"],
        },
        {
            "name": "Data Collector",
            "description": "Submit and view responses",
            "permissions": ["forms:read", "responses:create", "responses:read"],
        },
        {
            "name": "Analytics Access",
            "description": "View analytics and reports",
            "permissions": ["analytics:view", "analytics:export", "responses:read", "forms:read"],
        },
    ]

    created_count = 0

    for group_def in groups:
        # Check if group exists
        existing = await conn.fetchval(
            """
            SELECT id FROM permission_groups
            WHERE name = $1 AND is_system = TRUE
            """,
            group_def["name"],
        )

        if existing:
            continue

        # Get permission IDs
        permission_names = group_def["permissions"]
        perm_ids = []

        for perm_name in permission_names:
            perm_id = await conn.fetchval(
                "SELECT id FROM permissions WHERE name = $1",
                perm_name,
            )
            if perm_id:
                perm_ids.append(UUID(perm_id))

        # Create group
        await create_permission_group(
            conn,
            name=group_def["name"],
            description=group_def["description"],
            permission_ids=perm_ids,
            is_system=True,
        )
        created_count += 1

    return created_count
