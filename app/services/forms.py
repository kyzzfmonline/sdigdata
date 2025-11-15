"""Form service functions."""
# type: ignore

import json
from uuid import UUID

import asyncpg


async def create_form(
    conn: asyncpg.Connection,
    title: str,
    organization_id: UUID,
    schema: dict,
    created_by: UUID,
    status: str = "draft",
    description: str | None = None,
) -> dict | None:
    """Create a new form."""
    result = await conn.fetchrow(
        """
        INSERT INTO forms (title, organization_id, schema, status, version, created_by, description)
        VALUES ($1, $2, $3, $4, 1, $5, $6)
        RETURNING id, title, organization_id, schema, status, version, created_by, created_at, description
        """,
        title,
        str(organization_id),
        json.dumps(schema),
        status,
        str(created_by),
        description,
    )
    # Parse JSON schema back to dict
    if result:
        result_dict = dict(result)
        result_dict["schema"] = (
            json.loads(result_dict["schema"])
            if isinstance(result_dict["schema"], str)
            else result_dict["schema"]
        )
        return result_dict
    return None


async def get_form_by_id(conn: asyncpg.Connection, form_id: UUID) -> dict | None:
    """Get form by ID."""
    result = await conn.fetchrow(
        """
        SELECT id, title, organization_id, schema, status, version, created_by, created_at, description
        FROM forms
        WHERE id = $1 AND deleted = FALSE
        """,
        str(form_id),
    )
    if result:
        result_dict = dict(result)
        result_dict["schema"] = (
            json.loads(result_dict["schema"])
            if isinstance(result_dict["schema"], str)
            else result_dict["schema"]
        )
        return result_dict
    return None


async def list_forms(
    conn: asyncpg.Connection,
    organization_id: UUID | None = None,
    status: str | None = None,
) -> list[dict]:
    """List forms with optional filters."""
    query = """
        SELECT id, title, organization_id, schema, status, version, created_by, created_at, description
        FROM forms
        WHERE deleted = FALSE
    """
    params: list[str] = []

    if organization_id:
        query += f" AND organization_id = ${len(params) + 1}"
        params.append(str(organization_id))

    if status:
        query += f" AND status = ${len(params) + 1}"
        params.append(status)

    query += " ORDER BY created_at DESC"

    results = await conn.fetch(query, *params)
    output = []
    for result in results:
        result_dict = dict(result)
        result_dict["schema"] = (
            json.loads(result_dict["schema"])
            if isinstance(result_dict["schema"], str)
            else result_dict["schema"]
        )
        output.append(result_dict)
    return output


async def update_form_status(
    conn: asyncpg.Connection, form_id: UUID, status: str
) -> dict | None:
    """Update form status."""
    result = await conn.fetchrow(
        """
        UPDATE forms
        SET status = $1
        WHERE id = $2
        RETURNING id, title, organization_id, schema, status, version, created_by, created_at, description
        """,
        status,
        str(form_id),
    )
    if result:
        result_dict = dict(result)
        result_dict["schema"] = (
            json.loads(result_dict["schema"])
            if isinstance(result_dict["schema"], str)
            else result_dict["schema"]
        )
        return result_dict
    return None


async def assign_form_to_agent(
    conn: asyncpg.Connection, form_id: UUID, agent_id: UUID
) -> dict | None:
    """Assign a form to an agent."""
    result = await conn.fetchrow(
        """
        INSERT INTO form_assignments (form_id, agent_id)
        VALUES ($1, $2)
        ON CONFLICT (form_id, agent_id) DO NOTHING
        RETURNING id, form_id, agent_id, assigned_at
        """,
        str(form_id),
        str(agent_id),
    )
    if not result:
        # Already assigned, fetch existing
        result = await conn.fetchrow(
            """
            SELECT id, form_id, agent_id, assigned_at
            FROM form_assignments
            WHERE form_id = $1 AND agent_id = $2
            """,
            str(form_id),
            str(agent_id),
        )
    return dict(result) if result else None


async def get_assigned_agents(conn: asyncpg.Connection, form_id: UUID) -> list[dict]:
    """Get all agents assigned to a form."""
    results = await conn.fetch(
        """
        SELECT u.id, u.username, u.role, fa.assigned_at
        FROM form_assignments fa
        JOIN users u ON fa.agent_id = u.id
        WHERE fa.form_id = $1
        ORDER BY fa.assigned_at DESC
        """,
        str(form_id),
    )
    return [dict(row) for row in results]


async def get_agent_assigned_forms(
    conn: asyncpg.Connection, agent_id: UUID
) -> list[dict]:
    """Get all forms assigned to an agent."""
    results = await conn.fetch(
        """
        SELECT f.id, f.title, f.organization_id, f.schema, f.status, f.version, fa.assigned_at, f.description
        FROM form_assignments fa
        JOIN forms f ON fa.form_id = f.id
        WHERE fa.agent_id = $1
        ORDER BY fa.assigned_at DESC
        """,
        str(agent_id),
    )
    output = []
    for result in results:
        result_dict = dict(result)
        result_dict["schema"] = (
            json.loads(result_dict["schema"])
            if isinstance(result_dict["schema"], str)
            else result_dict["schema"]
        )
        output.append(result_dict)
    return output


async def assign_form_to_agents(
    conn: asyncpg.Connection,
    form_id: UUID,
    agent_ids: list[UUID],
    assigned_by: UUID,
    due_date: str | None = None,
    target_responses: int | None = None,
) -> list[dict]:
    """Assign a form to multiple agents."""
    assignments = []
    for agent_id in agent_ids:
        result = await conn.fetchrow(
            """
            INSERT INTO form_assignments (form_id, agent_id, assigned_by, due_date, target_responses, status)
            VALUES ($1, $2, $3, $4, $5, 'active')
            ON CONFLICT (form_id, agent_id) DO UPDATE
            SET due_date = EXCLUDED.due_date,
                target_responses = EXCLUDED.target_responses,
                assigned_by = EXCLUDED.assigned_by,
                status = 'active'
            RETURNING id, form_id, agent_id, assigned_by, assigned_at, due_date, target_responses, status
            """,
            str(form_id),
            str(agent_id),
            str(assigned_by),
            due_date,
            target_responses,
        )
        if result:
            assignments.append(dict(result))
    return assignments


async def get_form_assignments(conn: asyncpg.Connection, form_id: UUID) -> list[dict]:
    """Get all assignments for a form."""
    results = await conn.fetch(
        """
        SELECT
            fa.id,
            fa.form_id,
            fa.agent_id,
            u.username as agent_name,
            fa.assigned_by,
            fa.assigned_at,
            fa.due_date,
            fa.target_responses,
            fa.completed_responses,
            fa.status
        FROM form_assignments fa
        JOIN users u ON fa.agent_id = u.id
        WHERE fa.form_id = $1
        ORDER BY fa.assigned_at DESC
        """,
        str(form_id),
    )
    return [dict(row) for row in results]


async def update_form(
    conn: asyncpg.Connection,
    form_id: UUID,
    title: str | None = None,
    schema: dict | None = None,
    status: str | None = None,
    description: str | None = None,
) -> dict | None:
    """Update form details."""
    updates: list[str] = []
    params: list[str] = []

    if title is not None:
        updates.append(f"title = ${len(params) + 1}")
        params.append(title)

    if schema is not None:
        updates.append(f"schema = ${len(params) + 1}")
        params.append(json.dumps(schema))

    if status is not None:
        updates.append(f"status = ${len(params) + 1}")
        params.append(status)
        if status == "active":
            updates.append("published_at = CURRENT_TIMESTAMP")

    if description is not None:
        updates.append(f"description = ${len(params) + 1}")
        params.append(description)

    if not updates:
        return await get_form_by_id(conn, form_id)

    updates.append("updated_at = CURRENT_TIMESTAMP")
    params.append(str(form_id))

    query = f"""
        UPDATE forms
        SET {", ".join(updates)}
        WHERE id = ${len(params)}
        RETURNING id, title, organization_id, schema, status, version, created_by, created_at, updated_at, published_at, description
    """

    result = await conn.fetchrow(query, *params)
    if result:
        result_dict = dict(result)
        result_dict["schema"] = (
            json.loads(result_dict["schema"])
            if isinstance(result_dict["schema"], str)
            else result_dict["schema"]
        )
        return result_dict
    return None


async def delete_form(conn: asyncpg.Connection, form_id: UUID) -> bool:
    """Soft delete a form."""
    result = await conn.execute(
        """
        UPDATE forms
        SET deleted = TRUE, deleted_at = CURRENT_TIMESTAMP
        WHERE id = $1
        """,
        str(form_id),
    )
    return int(result.split()[-1]) > 0


# Form Lifecycle Management Functions

async def publish_form(conn: asyncpg.Connection, form_id: UUID) -> dict | None:
    """Publish a form (draft → active)."""
    result = await conn.fetchrow(
        """
        UPDATE forms
        SET status = 'active', published_at = CURRENT_TIMESTAMP
        WHERE id = $1 AND status = 'draft'  AND deleted = FALSE
        RETURNING id, title, organization_id, schema, status, version, created_by, created_at, published_at, is_public
        """,
        str(form_id),
    )
    if result:
        result_dict = dict(result)
        result_dict["schema"] = (
            json.loads(result_dict["schema"])
            if isinstance(result_dict["schema"], str)
            else result_dict["schema"]
        )
        return result_dict
    return None


async def archive_form(
    conn: asyncpg.Connection, form_id: UUID, reason: str | None = None
) -> dict | None:
    """Archive a form (active → archived or draft → archived)."""
    result = await conn.fetchrow(
        """
        UPDATE forms
        SET status = 'archived', archived_at = CURRENT_TIMESTAMP
        WHERE id = $1 AND status IN ('draft', 'active') AND deleted = FALSE
        RETURNING id, title, organization_id, schema, status, version, created_by, created_at, archived_at
        """,
        str(form_id),
    )
    if result:
        result_dict = dict(result)
        result_dict["schema"] = (
            json.loads(result_dict["schema"])
            if isinstance(result_dict["schema"], str)
            else result_dict["schema"]
        )
        result_dict["archive_reason"] = reason
        return result_dict
    return None


async def reactivate_form(conn: asyncpg.Connection, form_id: UUID) -> dict | None:
    """Reactivate an archived form (archived → active)."""
    result = await conn.fetchrow(
        """
        UPDATE forms
        SET status = 'active', archived_at = NULL, published_at = CURRENT_TIMESTAMP
        WHERE id = $1 AND status = 'archived' AND deleted = FALSE
        RETURNING id, title, organization_id, schema, status, version, created_by, created_at, published_at
        """,
        str(form_id),
    )
    if result:
        result_dict = dict(result)
        result_dict["schema"] = (
            json.loads(result_dict["schema"])
            if isinstance(result_dict["schema"], str)
            else result_dict["schema"]
        )
        return result_dict
    return None


async def decommission_form(
    conn: asyncpg.Connection, form_id: UUID, user_id: UUID, reason: str
) -> dict | None:
    """Decommission a form (archived → decommissioned). This is a final state."""
    result = await conn.fetchrow(
        """
        UPDATE forms
        SET status = 'decommissioned',
            decommissioned_at = CURRENT_TIMESTAMP,
            decommissioned_by = $2,
            decommission_reason = $3
        WHERE id = $1 AND status = 'archived' AND deleted = FALSE
        RETURNING id, title, organization_id, schema, status, version, created_by, created_at,
                  archived_at, decommissioned_at, decommissioned_by, decommission_reason
        """,
        str(form_id),
        str(user_id),
        reason,
    )
    if result:
        result_dict = dict(result)
        result_dict["schema"] = (
            json.loads(result_dict["schema"])
            if isinstance(result_dict["schema"], str)
            else result_dict["schema"]
        )
        return result_dict
    return None


async def can_submit_response(conn: asyncpg.Connection, form_id: UUID) -> bool:
    """Check if a form can accept responses (must be active and public)."""
    result = await conn.fetchval(
        """
        SELECT COUNT(*) FROM forms
        WHERE id = $1 AND status = 'active' AND is_public = TRUE AND deleted = FALSE
        """,
        str(form_id),
    )
    return result > 0


async def get_form_public_url(form_id: UUID, base_url: str = "") -> str:
    """Generate public URL for a form."""
    return f"{base_url}/forms/{form_id}/public"
