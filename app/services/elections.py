"""Elections service functions."""

import json
from datetime import datetime
from typing import Any
from uuid import UUID

import asyncpg


# ============================================
# ELECTION CRUD OPERATIONS
# ============================================


async def create_election(
    conn: asyncpg.Connection,
    organization_id: UUID,
    title: str,
    election_type: str,
    voting_method: str,
    start_date: datetime,
    end_date: datetime,
    created_by: UUID,
    description: str | None = None,
    verification_level: str = "anonymous",
    require_national_id: bool = False,
    require_phone_otp: bool = False,
    results_visibility: str = "after_close",
    show_voter_count: bool = True,
    linked_form_id: UUID | None = None,
    settings: dict | None = None,
    branding: dict | None = None,
) -> dict | None:
    """Create a new election."""
    result = await conn.fetchrow(
        """
        INSERT INTO elections (
            organization_id, title, description, election_type, voting_method,
            verification_level, require_national_id, require_phone_otp,
            results_visibility, show_voter_count, start_date, end_date,
            linked_form_id, settings, branding, created_by
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16)
        RETURNING *
        """,
        str(organization_id),
        title,
        description,
        election_type,
        voting_method,
        verification_level,
        require_national_id,
        require_phone_otp,
        results_visibility,
        show_voter_count,
        start_date,
        end_date,
        str(linked_form_id) if linked_form_id else None,
        json.dumps(settings or {}),
        json.dumps(branding or {}),
        str(created_by),
    )
    return _parse_election_row(result) if result else None


async def get_election_by_id(
    conn: asyncpg.Connection, election_id: UUID
) -> dict | None:
    """Get election by ID."""
    result = await conn.fetchrow(
        """
        SELECT e.*, o.name as organization_name
        FROM elections e
        JOIN organizations o ON e.organization_id = o.id
        WHERE e.id = $1 AND e.deleted = FALSE
        """,
        str(election_id),
    )
    return _parse_election_row(result) if result else None


async def list_elections(
    conn: asyncpg.Connection,
    organization_id: UUID | None = None,
    status: str | None = None,
    election_type: str | None = None,
    include_deleted: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    """List elections with optional filters."""
    query = """
        SELECT e.*, o.name as organization_name
        FROM elections e
        JOIN organizations o ON e.organization_id = o.id
        WHERE 1=1
    """
    params: list[Any] = []

    if not include_deleted:
        query += " AND e.deleted = FALSE"

    if organization_id:
        params.append(str(organization_id))
        query += f" AND e.organization_id = ${len(params)}"

    if status:
        params.append(status)
        query += f" AND e.status = ${len(params)}"

    if election_type:
        params.append(election_type)
        query += f" AND e.election_type = ${len(params)}"

    query += " ORDER BY e.created_at DESC"

    params.append(limit)
    query += f" LIMIT ${len(params)}"

    params.append(offset)
    query += f" OFFSET ${len(params)}"

    results = await conn.fetch(query, *params)
    return [_parse_election_row(row) for row in results]


async def update_election(
    conn: asyncpg.Connection,
    election_id: UUID,
    **kwargs: Any,
) -> dict | None:
    """Update election details."""
    allowed_fields = {
        "title",
        "description",
        "election_type",
        "voting_method",
        "verification_level",
        "require_national_id",
        "require_phone_otp",
        "results_visibility",
        "show_voter_count",
        "start_date",
        "end_date",
        "linked_form_id",
        "settings",
        "branding",
        "status",
    }

    updates: list[str] = []
    params: list[Any] = []

    for field, value in kwargs.items():
        if field in allowed_fields and value is not None:
            params.append(
                json.dumps(value)
                if field in ("settings", "branding")
                else (str(value) if isinstance(value, UUID) else value)
            )
            updates.append(f"{field} = ${len(params)}")

    if not updates:
        return await get_election_by_id(conn, election_id)

    updates.append("updated_at = CURRENT_TIMESTAMP")
    params.append(str(election_id))

    query = f"""
        UPDATE elections
        SET {", ".join(updates)}
        WHERE id = ${len(params)} AND deleted = FALSE
        RETURNING *
    """

    result = await conn.fetchrow(query, *params)
    return _parse_election_row(result) if result else None


async def delete_election(conn: asyncpg.Connection, election_id: UUID) -> bool:
    """Soft delete an election."""
    result = await conn.execute(
        """
        UPDATE elections
        SET deleted = TRUE, deleted_at = CURRENT_TIMESTAMP
        WHERE id = $1 AND deleted = FALSE
        """,
        str(election_id),
    )
    return int(result.split()[-1]) > 0


# ============================================
# ELECTION LIFECYCLE MANAGEMENT
# ============================================


async def publish_election(
    conn: asyncpg.Connection, election_id: UUID
) -> dict | None:
    """Publish an election (draft -> scheduled or active based on dates)."""
    election = await get_election_by_id(conn, election_id)
    if not election or election["status"] != "draft":
        return None

    now = datetime.now(election["start_date"].tzinfo)
    new_status = "active" if now >= election["start_date"] else "scheduled"

    result = await conn.fetchrow(
        """
        UPDATE elections
        SET status = $1, updated_at = CURRENT_TIMESTAMP
        WHERE id = $2 AND status = 'draft' AND deleted = FALSE
        RETURNING *
        """,
        new_status,
        str(election_id),
    )
    return _parse_election_row(result) if result else None


async def pause_election(
    conn: asyncpg.Connection, election_id: UUID
) -> dict | None:
    """Pause an active election."""
    result = await conn.fetchrow(
        """
        UPDATE elections
        SET status = 'paused', updated_at = CURRENT_TIMESTAMP
        WHERE id = $1 AND status = 'active' AND deleted = FALSE
        RETURNING *
        """,
        str(election_id),
    )
    return _parse_election_row(result) if result else None


async def resume_election(
    conn: asyncpg.Connection, election_id: UUID
) -> dict | None:
    """Resume a paused election."""
    result = await conn.fetchrow(
        """
        UPDATE elections
        SET status = 'active', updated_at = CURRENT_TIMESTAMP
        WHERE id = $1 AND status = 'paused' AND deleted = FALSE
        RETURNING *
        """,
        str(election_id),
    )
    return _parse_election_row(result) if result else None


async def close_election(
    conn: asyncpg.Connection, election_id: UUID
) -> dict | None:
    """Close an election."""
    result = await conn.fetchrow(
        """
        UPDATE elections
        SET status = 'closed', updated_at = CURRENT_TIMESTAMP
        WHERE id = $1 AND status IN ('active', 'paused') AND deleted = FALSE
        RETURNING *
        """,
        str(election_id),
    )
    return _parse_election_row(result) if result else None


async def cancel_election(
    conn: asyncpg.Connection, election_id: UUID
) -> dict | None:
    """Cancel an election."""
    result = await conn.fetchrow(
        """
        UPDATE elections
        SET status = 'cancelled', updated_at = CURRENT_TIMESTAMP
        WHERE id = $1 AND status NOT IN ('closed', 'cancelled') AND deleted = FALSE
        RETURNING *
        """,
        str(election_id),
    )
    return _parse_election_row(result) if result else None


async def check_and_update_election_status(conn: asyncpg.Connection) -> int:
    """Check and update election statuses based on dates. Returns count of updated."""
    # Activate scheduled elections that have started
    activated = await conn.execute(
        """
        UPDATE elections
        SET status = 'active', updated_at = CURRENT_TIMESTAMP
        WHERE status = 'scheduled'
        AND start_date <= CURRENT_TIMESTAMP
        AND end_date > CURRENT_TIMESTAMP
        AND deleted = FALSE
        """
    )

    # Close active elections that have ended
    closed = await conn.execute(
        """
        UPDATE elections
        SET status = 'closed', updated_at = CURRENT_TIMESTAMP
        WHERE status IN ('active', 'paused')
        AND end_date <= CURRENT_TIMESTAMP
        AND deleted = FALSE
        """
    )

    return int(activated.split()[-1]) + int(closed.split()[-1])


# ============================================
# POSITION OPERATIONS
# ============================================


async def add_position(
    conn: asyncpg.Connection,
    election_id: UUID,
    title: str,
    description: str | None = None,
    max_selections: int = 1,
    display_order: int | None = None,
) -> dict | None:
    """Add a position to an election."""
    if display_order is None:
        max_order = await conn.fetchval(
            "SELECT COALESCE(MAX(display_order), -1) FROM election_positions WHERE election_id = $1",
            str(election_id),
        )
        display_order = max_order + 1

    result = await conn.fetchrow(
        """
        INSERT INTO election_positions (election_id, title, description, max_selections, display_order)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING *
        """,
        str(election_id),
        title,
        description,
        max_selections,
        display_order,
    )
    return _parse_position_row(result)


async def get_position_by_id(
    conn: asyncpg.Connection, position_id: UUID
) -> dict | None:
    """Get position by ID."""
    result = await conn.fetchrow(
        "SELECT * FROM election_positions WHERE id = $1",
        str(position_id),
    )
    return _parse_position_row(result)


async def list_positions(
    conn: asyncpg.Connection, election_id: UUID
) -> list[dict]:
    """List all positions for an election."""
    results = await conn.fetch(
        """
        SELECT * FROM election_positions
        WHERE election_id = $1
        ORDER BY display_order ASC
        """,
        str(election_id),
    )
    return [_parse_position_row(row) for row in results]


async def update_position(
    conn: asyncpg.Connection,
    position_id: UUID,
    title: str | None = None,
    description: str | None = None,
    max_selections: int | None = None,
    display_order: int | None = None,
) -> dict | None:
    """Update a position."""
    updates: list[str] = []
    params: list[Any] = []

    if title is not None:
        params.append(title)
        updates.append(f"title = ${len(params)}")

    if description is not None:
        params.append(description)
        updates.append(f"description = ${len(params)}")

    if max_selections is not None:
        params.append(max_selections)
        updates.append(f"max_selections = ${len(params)}")

    if display_order is not None:
        params.append(display_order)
        updates.append(f"display_order = ${len(params)}")

    if not updates:
        return await get_position_by_id(conn, position_id)

    params.append(str(position_id))
    query = f"""
        UPDATE election_positions
        SET {", ".join(updates)}
        WHERE id = ${len(params)}
        RETURNING *
    """

    result = await conn.fetchrow(query, *params)
    return _parse_position_row(result)


async def delete_position(conn: asyncpg.Connection, position_id: UUID) -> bool:
    """Delete a position and its candidates."""
    result = await conn.execute(
        "DELETE FROM election_positions WHERE id = $1",
        str(position_id),
    )
    return int(result.split()[-1]) > 0


# ============================================
# CANDIDATE OPERATIONS
# ============================================


async def add_candidate(
    conn: asyncpg.Connection,
    position_id: UUID,
    name: str,
    photo_url: str | None = None,
    party: str | None = None,
    bio: str | None = None,
    manifesto: str | None = None,
    policies: dict | None = None,
    experience: dict | None = None,
    endorsements: list | None = None,
    display_order: int | None = None,
) -> dict | None:
    """Add a candidate to a position."""
    if display_order is None:
        max_order = await conn.fetchval(
            "SELECT COALESCE(MAX(display_order), -1) FROM candidates WHERE position_id = $1",
            str(position_id),
        )
        display_order = max_order + 1

    result = await conn.fetchrow(
        """
        INSERT INTO candidates (
            position_id, name, photo_url, party, bio, manifesto,
            policies, experience, endorsements, display_order
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        RETURNING *
        """,
        str(position_id),
        name,
        photo_url,
        party,
        bio,
        manifesto,
        json.dumps(policies or {}),
        json.dumps(experience or {}),
        json.dumps(endorsements or []),
        display_order,
    )
    return _parse_candidate_row(result) if result else None


async def get_candidate_by_id(
    conn: asyncpg.Connection, candidate_id: UUID
) -> dict | None:
    """Get candidate by ID."""
    result = await conn.fetchrow(
        "SELECT * FROM candidates WHERE id = $1",
        str(candidate_id),
    )
    return _parse_candidate_row(result) if result else None


async def list_candidates(
    conn: asyncpg.Connection, position_id: UUID
) -> list[dict]:
    """List all candidates for a position."""
    results = await conn.fetch(
        """
        SELECT * FROM candidates
        WHERE position_id = $1
        ORDER BY display_order ASC
        """,
        str(position_id),
    )
    return [_parse_candidate_row(row) for row in results]


async def list_all_candidates_for_election(
    conn: asyncpg.Connection, election_id: UUID
) -> list[dict]:
    """List all candidates for an election across all positions."""
    results = await conn.fetch(
        """
        SELECT c.*, p.title as position_title, p.election_id
        FROM candidates c
        JOIN election_positions p ON c.position_id = p.id
        WHERE p.election_id = $1
        ORDER BY p.display_order ASC, c.display_order ASC
        """,
        str(election_id),
    )
    return [_parse_candidate_row(row) for row in results]


async def update_candidate(
    conn: asyncpg.Connection,
    candidate_id: UUID,
    **kwargs: Any,
) -> dict | None:
    """Update a candidate."""
    allowed_fields = {
        "name",
        "photo_url",
        "party",
        "bio",
        "manifesto",
        "policies",
        "experience",
        "endorsements",
        "display_order",
    }

    updates: list[str] = []
    params: list[Any] = []

    for field, value in kwargs.items():
        if field in allowed_fields and value is not None:
            if field in ("policies", "experience", "endorsements"):
                params.append(json.dumps(value))
            else:
                params.append(value)
            updates.append(f"{field} = ${len(params)}")

    if not updates:
        return await get_candidate_by_id(conn, candidate_id)

    updates.append("updated_at = CURRENT_TIMESTAMP")
    params.append(str(candidate_id))

    query = f"""
        UPDATE candidates
        SET {", ".join(updates)}
        WHERE id = ${len(params)}
        RETURNING *
    """

    result = await conn.fetchrow(query, *params)
    return _parse_candidate_row(result) if result else None


async def delete_candidate(conn: asyncpg.Connection, candidate_id: UUID) -> bool:
    """Delete a candidate."""
    result = await conn.execute(
        "DELETE FROM candidates WHERE id = $1",
        str(candidate_id),
    )
    return int(result.split()[-1]) > 0


async def compare_candidates(
    conn: asyncpg.Connection, candidate_ids: list[UUID]
) -> list[dict]:
    """Get candidates for comparison."""
    placeholders = ", ".join(f"${i+1}" for i in range(len(candidate_ids)))
    results = await conn.fetch(
        f"""
        SELECT c.*, p.title as position_title, p.election_id
        FROM candidates c
        JOIN election_positions p ON c.position_id = p.id
        WHERE c.id IN ({placeholders})
        ORDER BY c.display_order ASC
        """,
        *[str(cid) for cid in candidate_ids],
    )
    return [_parse_candidate_row(row) for row in results]


# ============================================
# POLL OPTION OPERATIONS
# ============================================


async def add_poll_option(
    conn: asyncpg.Connection,
    election_id: UUID,
    option_text: str,
    description: str | None = None,
    display_order: int | None = None,
) -> dict | None:
    """Add a poll option."""
    if display_order is None:
        max_order = await conn.fetchval(
            "SELECT COALESCE(MAX(display_order), -1) FROM poll_options WHERE election_id = $1",
            str(election_id),
        )
        display_order = max_order + 1

    result = await conn.fetchrow(
        """
        INSERT INTO poll_options (election_id, option_text, description, display_order)
        VALUES ($1, $2, $3, $4)
        RETURNING *
        """,
        str(election_id),
        option_text,
        description,
        display_order,
    )
    return _parse_poll_option_row(result)


async def get_poll_option_by_id(
    conn: asyncpg.Connection, option_id: UUID
) -> dict | None:
    """Get poll option by ID."""
    result = await conn.fetchrow(
        "SELECT * FROM poll_options WHERE id = $1",
        str(option_id),
    )
    return _parse_poll_option_row(result)


async def list_poll_options(
    conn: asyncpg.Connection, election_id: UUID
) -> list[dict]:
    """List all poll options for an election."""
    results = await conn.fetch(
        """
        SELECT * FROM poll_options
        WHERE election_id = $1
        ORDER BY display_order ASC
        """,
        str(election_id),
    )
    return [_parse_poll_option_row(row) for row in results]


async def update_poll_option(
    conn: asyncpg.Connection,
    option_id: UUID,
    option_text: str | None = None,
    description: str | None = None,
    display_order: int | None = None,
) -> dict | None:
    """Update a poll option."""
    updates: list[str] = []
    params: list[Any] = []

    if option_text is not None:
        params.append(option_text)
        updates.append(f"option_text = ${len(params)}")

    if description is not None:
        params.append(description)
        updates.append(f"description = ${len(params)}")

    if display_order is not None:
        params.append(display_order)
        updates.append(f"display_order = ${len(params)}")

    if not updates:
        return await get_poll_option_by_id(conn, option_id)

    params.append(str(option_id))
    query = f"""
        UPDATE poll_options
        SET {", ".join(updates)}
        WHERE id = ${len(params)}
        RETURNING *
    """

    result = await conn.fetchrow(query, *params)
    return _parse_poll_option_row(result)


async def delete_poll_option(conn: asyncpg.Connection, option_id: UUID) -> bool:
    """Delete a poll option."""
    result = await conn.execute(
        "DELETE FROM poll_options WHERE id = $1",
        str(option_id),
    )
    return int(result.split()[-1]) > 0


# ============================================
# AUDIT LOGGING
# ============================================


async def log_election_action(
    conn: asyncpg.Connection,
    election_id: UUID,
    action: str,
    actor_id: UUID | None = None,
    details: dict | None = None,
    ip_address: str | None = None,
) -> dict | None:
    """Log an election action for audit trail."""
    result = await conn.fetchrow(
        """
        INSERT INTO election_audit_log (election_id, action, actor_id, details, ip_address)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING *
        """,
        str(election_id),
        action,
        str(actor_id) if actor_id else None,
        json.dumps(details) if details else None,
        ip_address,
    )
    return _parse_audit_row(result)


async def get_election_audit_log(
    conn: asyncpg.Connection,
    election_id: UUID,
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    """Get audit log for an election."""
    results = await conn.fetch(
        """
        SELECT al.*, u.username as actor_name
        FROM election_audit_log al
        LEFT JOIN users u ON al.actor_id = u.id
        WHERE al.election_id = $1
        ORDER BY al.created_at DESC
        LIMIT $2 OFFSET $3
        """,
        str(election_id),
        limit,
        offset,
    )
    return [_parse_audit_row(row) for row in results]


# ============================================
# HELPER FUNCTIONS
# ============================================


def _parse_election_row(row: asyncpg.Record | None) -> dict | None:
    """Parse an election row into a dict with proper JSON parsing."""
    if not row:
        return None

    result = dict(row)

    # Convert UUID fields to strings for JSON serialization
    uuid_fields = ("id", "organization_id", "created_by", "linked_form_id")
    for field in uuid_fields:
        if result.get(field) is not None:
            result[field] = str(result[field])

    # Parse JSONB fields
    for field in ("settings", "branding"):
        if result.get(field):
            if isinstance(result[field], str):
                result[field] = json.loads(result[field])

    return result


def _parse_candidate_row(row: asyncpg.Record | None) -> dict | None:
    """Parse a candidate row into a dict with proper JSON parsing."""
    if not row:
        return None

    result = dict(row)

    # Convert UUID fields to strings for JSON serialization
    uuid_fields = ("id", "position_id", "election_id")
    for field in uuid_fields:
        if result.get(field) is not None:
            result[field] = str(result[field])

    # Parse JSONB fields
    for field in ("policies", "experience", "endorsements"):
        if result.get(field):
            if isinstance(result[field], str):
                result[field] = json.loads(result[field])

    return result


def _parse_audit_row(row: asyncpg.Record | None) -> dict | None:
    """Parse an audit log row into a dict with proper JSON parsing."""
    if not row:
        return None

    result = dict(row)

    # Convert UUID fields to strings for JSON serialization
    uuid_fields = ("id", "election_id", "actor_id")
    for field in uuid_fields:
        if result.get(field) is not None:
            result[field] = str(result[field])

    if result.get("details"):
        if isinstance(result["details"], str):
            result["details"] = json.loads(result["details"])

    # Convert IP to string
    if result.get("ip_address"):
        result["ip_address"] = str(result["ip_address"])

    return result


def _parse_position_row(row: asyncpg.Record | None) -> dict | None:
    """Parse a position row into a dict with UUID conversion."""
    if not row:
        return None

    result = dict(row)

    # Convert UUID fields to strings for JSON serialization
    uuid_fields = ("id", "election_id")
    for field in uuid_fields:
        if result.get(field) is not None:
            result[field] = str(result[field])

    return result


def _parse_poll_option_row(row: asyncpg.Record | None) -> dict | None:
    """Parse a poll option row into a dict with UUID conversion."""
    if not row:
        return None

    result = dict(row)

    # Convert UUID fields to strings for JSON serialization
    uuid_fields = ("id", "election_id")
    for field in uuid_fields:
        if result.get(field) is not None:
            result[field] = str(result[field])

    return result
