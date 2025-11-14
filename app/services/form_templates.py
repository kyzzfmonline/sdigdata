"""Form templates service."""

import json
from typing import Any
from uuid import UUID

import asyncpg


async def create_template(
    conn: asyncpg.Connection,
    name: str,
    category: str,
    form_schema: dict[str, Any],
    created_by: UUID,
    description: str | None = None,
    thumbnail_url: str | None = None,
    is_public: bool = False,
    organization_id: UUID | None = None,
    tags: list[str] | None = None,
) -> dict[str, Any] | None:
    """Create a new form template."""
    result = await conn.fetchrow(
        """
        INSERT INTO form_templates (
            name, description, category, form_schema, thumbnail_url,
            is_public, organization_id, created_by, tags
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        RETURNING id, name, description, category, form_schema, thumbnail_url,
                  is_public, organization_id, created_by, created_at, updated_at,
                  usage_count, tags
        """,
        name,
        description,
        category,
        json.dumps(form_schema),
        thumbnail_url,
        is_public,
        str(organization_id) if organization_id else None,
        str(created_by),
        tags or [],
    )
    if result:
        result_dict = dict(result)
        result_dict["form_schema"] = (
            json.loads(result_dict["form_schema"])
            if isinstance(result_dict["form_schema"], str)
            else result_dict["form_schema"]
        )
        return result_dict
    return None


async def get_template_by_id(
    conn: asyncpg.Connection, template_id: UUID
) -> dict[str, Any] | None:
    """Get a template by ID."""
    result = await conn.fetchrow(
        """
        SELECT id, name, description, category, form_schema, thumbnail_url,
               is_public, organization_id, created_by, created_at, updated_at,
               usage_count, tags
        FROM form_templates
        WHERE id = $1
        """,
        str(template_id),
    )
    if result:
        result_dict = dict(result)
        result_dict["form_schema"] = (
            json.loads(result_dict["form_schema"])
            if isinstance(result_dict["form_schema"], str)
            else result_dict["form_schema"]
        )
        return result_dict
    return None


async def list_templates(
    conn: asyncpg.Connection,
    category: str | None = None,
    search: str | None = None,
    is_public: bool | None = None,
    organization_id: UUID | None = None,
    sort: str = "created_at",
    order: str = "desc",
    page: int = 1,
    limit: int = 20,
) -> tuple[list[dict[str, Any]], int]:
    """List form templates with filters and pagination."""
    # Build WHERE clause
    where_clauses: list[str] = []
    params: list[Any] = []

    if category:
        where_clauses.append(f"category = ${len(params) + 1}")
        params.append(category)

    if search:
        where_clauses.append(
            f"(name ILIKE ${len(params) + 1} OR description ILIKE ${len(params) + 1})"
        )
        params.append(f"%{search}%")

    if is_public is not None:
        where_clauses.append(f"is_public = ${len(params) + 1}")
        params.append(is_public)

    if organization_id:
        where_clauses.append(
            f"(organization_id = ${len(params) + 1} OR is_public = TRUE)"
        )
        params.append(str(organization_id))

    where_clause = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    # Count total
    count_query = f"SELECT COUNT(*) FROM form_templates {where_clause}"
    total = await conn.fetchval(count_query, *params)

    # Get templates
    offset = (page - 1) * limit
    sort_column = sort if sort in ["created_at", "usage_count", "name"] else "created_at"
    sort_order = "DESC" if order.lower() == "desc" else "ASC"

    query = f"""
        SELECT id, name, description, category, thumbnail_url,
               is_public, usage_count, tags, created_at,
               (SELECT jsonb_array_length(form_schema->'fields')) as field_count
        FROM form_templates
        {where_clause}
        ORDER BY {sort_column} {sort_order}
        LIMIT ${len(params) + 1} OFFSET ${len(params) + 2}
    """
    params.extend([limit, offset])

    results = await conn.fetch(query, *params)
    templates = [dict(row) for row in results]

    return templates, total or 0


async def update_template(
    conn: asyncpg.Connection,
    template_id: UUID,
    name: str | None = None,
    description: str | None = None,
    form_schema: dict[str, Any] | None = None,
    thumbnail_url: str | None = None,
    is_public: bool | None = None,
    tags: list[str] | None = None,
) -> dict[str, Any] | None:
    """Update a template."""
    updates: list[str] = []
    params: list[Any] = []

    if name is not None:
        updates.append(f"name = ${len(params) + 1}")
        params.append(name)

    if description is not None:
        updates.append(f"description = ${len(params) + 1}")
        params.append(description)

    if form_schema is not None:
        updates.append(f"form_schema = ${len(params) + 1}")
        params.append(json.dumps(form_schema))

    if thumbnail_url is not None:
        updates.append(f"thumbnail_url = ${len(params) + 1}")
        params.append(thumbnail_url)

    if is_public is not None:
        updates.append(f"is_public = ${len(params) + 1}")
        params.append(is_public)

    if tags is not None:
        updates.append(f"tags = ${len(params) + 1}")
        params.append(tags)

    if not updates:
        return await get_template_by_id(conn, template_id)

    updates.append("updated_at = CURRENT_TIMESTAMP")
    params.append(str(template_id))

    query = f"""
        UPDATE form_templates
        SET {", ".join(updates)}
        WHERE id = ${len(params)}
        RETURNING id, name, description, category, form_schema, thumbnail_url,
                  is_public, organization_id, created_by, created_at, updated_at,
                  usage_count, tags
    """

    result = await conn.fetchrow(query, *params)
    if result:
        result_dict = dict(result)
        result_dict["form_schema"] = (
            json.loads(result_dict["form_schema"])
            if isinstance(result_dict["form_schema"], str)
            else result_dict["form_schema"]
        )
        return result_dict
    return None


async def delete_template(conn: asyncpg.Connection, template_id: UUID) -> bool:
    """Delete a template."""
    result = await conn.execute(
        "DELETE FROM form_templates WHERE id = $1",
        str(template_id),
    )
    return int(result.split()[-1]) > 0


async def increment_template_usage(
    conn: asyncpg.Connection, template_id: UUID
) -> None:
    """Increment the usage count for a template."""
    await conn.execute(
        """
        UPDATE form_templates
        SET usage_count = usage_count + 1
        WHERE id = $1
        """,
        str(template_id),
    )


async def get_popular_templates(
    conn: asyncpg.Connection, limit: int = 10
) -> list[dict[str, Any]]:
    """Get most popular templates by usage count."""
    results = await conn.fetch(
        """
        SELECT id, name, description, category, thumbnail_url,
               is_public, usage_count, tags, created_at
        FROM form_templates
        WHERE is_public = TRUE
        ORDER BY usage_count DESC, created_at DESC
        LIMIT $1
        """,
        limit,
    )
    return [dict(row) for row in results]
