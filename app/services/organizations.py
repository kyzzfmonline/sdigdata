"""Organization service functions."""

from typing import Optional
from uuid import UUID
import asyncpg


async def create_organization(
    conn: asyncpg.Connection,
    name: str,
    logo_url: Optional[str] = None,
    primary_color: Optional[str] = None,
) -> dict:
    """Create a new organization."""
    result = await conn.fetchrow(
        """
        INSERT INTO organizations (name, logo_url, primary_color)
        VALUES ($1, $2, $3)
        RETURNING id, name, logo_url, primary_color, created_at
        """,
        name, logo_url, primary_color,
    )
    return dict(result) if result else None


async def get_organization_by_id(conn: asyncpg.Connection, org_id: UUID) -> Optional[dict]:
    """Get organization by ID."""
    result = await conn.fetchrow(
        """
        SELECT id, name, logo_url, primary_color, created_at
        FROM organizations
        WHERE id = $1
        """,
        str(org_id),
    )
    return dict(result) if result else None


async def get_first_organization(conn: asyncpg.Connection) -> Optional[dict]:
    """Get the first organization (useful for bootstrap)."""
    result = await conn.fetchrow(
        """
        SELECT id, name, logo_url, primary_color, created_at
        FROM organizations
        ORDER BY created_at ASC
        LIMIT 1
        """
    )
    return dict(result) if result else None


async def list_organizations(conn: asyncpg.Connection) -> list[dict]:
    """List all organizations."""
    results = await conn.fetch(
        """
        SELECT id, name, logo_url, primary_color, created_at
        FROM organizations
        ORDER BY created_at DESC
        """
    )
    return [dict(row) for row in results]


async def update_organization(
    conn: asyncpg.Connection,
    org_id: UUID,
    name: Optional[str] = None,
    logo_url: Optional[str] = None,
    primary_color: Optional[str] = None,
) -> Optional[dict]:
    """Update organization details."""
    updates = []
    params = []
    param_num = 1

    if name is not None:
        updates.append(f"name = ${param_num}")
        params.append(name)
        param_num += 1
    if logo_url is not None:
        updates.append(f"logo_url = ${param_num}")
        params.append(logo_url)
        param_num += 1
    if primary_color is not None:
        updates.append(f"primary_color = ${param_num}")
        params.append(primary_color)
        param_num += 1

    if not updates:
        return await get_organization_by_id(conn, org_id)

    params.append(str(org_id))

    query = f"""
        UPDATE organizations
        SET {', '.join(updates)}
        WHERE id = ${param_num}
        RETURNING id, name, logo_url, primary_color, created_at
    """

    result = await conn.fetchrow(query, *params)
    return dict(result) if result else None
