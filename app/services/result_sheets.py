"""Result sheets service for election collation.

Handles creation, submission, verification, and approval of result sheets
at polling station and collation center levels.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

import asyncpg


# ============================================
# RESULT SHEET CRUD
# ============================================


async def create_result_sheet(
    conn: asyncpg.Connection,
    *,
    election_id: UUID,
    position_id: UUID,
    polling_station_id: UUID,
    sheet_type: str = "primary",  # 'primary', 'duplicate', etc.
    created_by: UUID,
) -> dict[str, Any]:
    """Create a new result sheet."""
    row = await conn.fetchrow(
        """
        INSERT INTO result_sheets (
            election_id, position_id, polling_station_id,
            sheet_type, status, entered_by, entered_at
        )
        VALUES ($1, $2, $3, $4, 'draft', $5, NOW())
        RETURNING *
        """,
        election_id,
        position_id,
        polling_station_id,
        sheet_type,
        created_by,
    )
    return _parse_row(row) if row else {}


def _parse_row(row: asyncpg.Record | None) -> dict[str, Any]:
    """Parse a database row to dict with proper string conversions."""
    if not row:
        return {}
    result = dict(row)
    # Convert UUID fields to strings
    for key in list(result.keys()):
        if hasattr(result[key], 'hex'):  # UUID-like object
            result[key] = str(result[key])
    return result


async def get_result_sheet(
    conn: asyncpg.Connection,
    sheet_id: UUID,
) -> dict[str, Any] | None:
    """Get a result sheet by ID with full details."""
    row = await conn.fetchrow(
        """
        SELECT
            rs.*,
            ps.name as polling_station_name,
            ps.code as polling_station_code,
            ep.title as position_title,
            e.title as election_title,
            u.username as entered_by_username,
            ea.name as electoral_area_name,
            c.name as constituency_name,
            r.name as region_name
        FROM result_sheets rs
        LEFT JOIN polling_stations ps ON rs.polling_station_id = ps.id
        LEFT JOIN election_positions ep ON rs.position_id = ep.id
        LEFT JOIN elections e ON rs.election_id = e.id
        LEFT JOIN users u ON rs.entered_by = u.id
        LEFT JOIN electoral_areas ea ON ps.electoral_area_id = ea.id
        LEFT JOIN constituencies c ON ea.constituency_id = c.id
        LEFT JOIN regions r ON c.region_id = r.id
        WHERE rs.id = $1
        """,
        sheet_id,
    )
    return _parse_row(row) if row else None


async def get_result_sheet_by_station(
    conn: asyncpg.Connection,
    election_id: UUID,
    position_id: UUID,
    polling_station_id: UUID,
) -> dict[str, Any] | None:
    """Get result sheet for a specific polling station in an election."""
    row = await conn.fetchrow(
        """
        SELECT * FROM result_sheets
        WHERE election_id = $1 AND position_id = $2 AND polling_station_id = $3
        """,
        election_id,
        position_id,
        polling_station_id,
    )
    return _parse_row(row) if row else None


async def list_result_sheets(
    conn: asyncpg.Connection,
    election_id: UUID,
    *,
    position_id: UUID | None = None,
    sheet_type: str | None = None,
    status: str | None = None,
    constituency_id: UUID | None = None,
    region_id: UUID | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """List result sheets with filtering."""
    query = """
        SELECT
            rs.*,
            ps.name as polling_station_name,
            ps.code as polling_station_code,
            ps.registered_voters as station_registered_voters,
            ep.title as position_title,
            ea.name as electoral_area_name,
            c.name as constituency_name,
            r.name as region_name,
            u.username as entered_by_username
        FROM result_sheets rs
        LEFT JOIN polling_stations ps ON rs.polling_station_id = ps.id
        LEFT JOIN election_positions ep ON rs.position_id = ep.id
        LEFT JOIN electoral_areas ea ON ps.electoral_area_id = ea.id
        LEFT JOIN constituencies c ON ea.constituency_id = c.id
        LEFT JOIN regions r ON c.region_id = r.id
        LEFT JOIN users u ON rs.entered_by = u.id
        WHERE rs.election_id = $1
    """
    params: list[Any] = [election_id]
    param_count = 1

    if position_id:
        param_count += 1
        query += f" AND rs.position_id = ${param_count}"
        params.append(position_id)

    if sheet_type:
        param_count += 1
        query += f" AND rs.sheet_type = ${param_count}"
        params.append(sheet_type)

    if status:
        param_count += 1
        query += f" AND rs.status = ${param_count}"
        params.append(status)

    if constituency_id:
        param_count += 1
        query += f" AND c.id = ${param_count}"
        params.append(constituency_id)

    if region_id:
        param_count += 1
        query += f" AND r.id = ${param_count}"
        params.append(region_id)

    query += f" ORDER BY rs.created_at DESC LIMIT ${param_count + 1} OFFSET ${param_count + 2}"
    params.extend([limit, offset])

    rows = await conn.fetch(query, *params)
    return [_parse_row(row) for row in rows]


async def update_result_sheet(
    conn: asyncpg.Connection,
    sheet_id: UUID,
    **updates: Any,
) -> dict[str, Any] | None:
    """Update result sheet fields."""
    allowed_fields = {
        "registered_voters",
        "ballots_issued",
        "ballots_cast",
        "valid_votes",
        "rejected_ballots",
        "spoilt_ballots",
        "unused_ballots",
        "notes",
        "metadata",
    }

    filtered_updates = {k: v for k, v in updates.items() if k in allowed_fields}
    if not filtered_updates:
        return await get_result_sheet(conn, sheet_id)

    set_clauses = []
    params: list[Any] = []
    for i, (key, value) in enumerate(filtered_updates.items(), start=1):
        set_clauses.append(f"{key} = ${i}")
        params.append(value)

    params.append(sheet_id)
    query = f"""
        UPDATE result_sheets
        SET {', '.join(set_clauses)}, updated_at = NOW()
        WHERE id = ${len(params)}
        RETURNING *
    """

    row = await conn.fetchrow(query, *params)
    return _parse_row(row) if row else None


# ============================================
# RESULT SHEET ENTRIES (VOTE COUNTS)
# ============================================


async def add_result_entry(
    conn: asyncpg.Connection,
    *,
    result_sheet_id: UUID,
    candidate_id: UUID | None = None,
    candidate_name: str = "Unknown Candidate",
    party: str | None = None,
    votes: int,
    votes_in_words: str | None = None,
    ballot_order: int | None = None,
) -> dict[str, Any]:
    """Add a vote count entry to a result sheet."""
    row = await conn.fetchrow(
        """
        INSERT INTO result_sheet_entries (
            result_sheet_id, candidate_id, candidate_name, party,
            votes_in_figures, votes_in_words, ballot_order
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        RETURNING *
        """,
        result_sheet_id,
        candidate_id,
        candidate_name,
        party,
        votes,
        votes_in_words,
        ballot_order,
    )
    return _parse_row(row) if row else {}


async def get_result_entries(
    conn: asyncpg.Connection,
    result_sheet_id: UUID,
) -> list[dict[str, Any]]:
    """Get all vote entries for a result sheet."""
    rows = await conn.fetch(
        """
        SELECT
            rse.*,
            c.name as db_candidate_name,
            c.party as db_candidate_party
        FROM result_sheet_entries rse
        LEFT JOIN candidates c ON rse.candidate_id = c.id
        WHERE rse.result_sheet_id = $1
        ORDER BY rse.ballot_order NULLS LAST, rse.votes_in_figures DESC
        """,
        result_sheet_id,
    )
    return [_parse_row(row) for row in rows]


async def bulk_update_entries(
    conn: asyncpg.Connection,
    result_sheet_id: UUID,
    entries: list[dict[str, Any]],
) -> int:
    """Bulk update result sheet entries."""
    count = 0
    for entry in entries:
        await add_result_entry(
            conn,
            result_sheet_id=result_sheet_id,
            candidate_id=entry.get("candidate_id"),
            candidate_name=entry.get("candidate_name", "Unknown Candidate"),
            party=entry.get("party"),
            votes=entry["votes"],
            votes_in_words=entry.get("votes_in_words"),
            ballot_order=entry.get("ballot_order"),
        )
        count += 1
    return count


# ============================================
# RESULT SHEET ATTACHMENTS
# ============================================


async def add_attachment(
    conn: asyncpg.Connection,
    *,
    result_sheet_id: UUID,
    attachment_type: str,  # 'pink_sheet', 'photo', 'signature', 'other'
    file_url: str,
    file_name: str | None = None,
    uploaded_by: UUID,
    description: str | None = None,
) -> dict[str, Any]:
    """Add an attachment to a result sheet."""
    row = await conn.fetchrow(
        """
        INSERT INTO result_sheet_attachments (
            result_sheet_id, file_type, file_url, file_name, uploaded_by, description
        )
        VALUES ($1, $2, $3, $4, $5, $6)
        RETURNING *
        """,
        result_sheet_id,
        attachment_type,
        file_url,
        file_name,
        uploaded_by,
        description,
    )
    return _parse_row(row) if row else {}


async def get_attachments(
    conn: asyncpg.Connection,
    result_sheet_id: UUID,
) -> list[dict[str, Any]]:
    """Get all attachments for a result sheet."""
    rows = await conn.fetch(
        """
        SELECT
            rsa.*,
            u.username as uploaded_by_username
        FROM result_sheet_attachments rsa
        LEFT JOIN users u ON rsa.uploaded_by = u.id
        WHERE rsa.result_sheet_id = $1
        ORDER BY rsa.uploaded_at DESC
        """,
        result_sheet_id,
    )
    return [_parse_row(row) for row in rows]


async def delete_attachment(
    conn: asyncpg.Connection,
    attachment_id: UUID,
) -> bool:
    """Delete an attachment."""
    result = await conn.execute(
        "DELETE FROM result_sheet_attachments WHERE id = $1",
        attachment_id,
    )
    return result == "DELETE 1"


# ============================================
# WORKFLOW OPERATIONS
# ============================================


async def submit_result_sheet(
    conn: asyncpg.Connection,
    sheet_id: UUID,
    submitted_by: UUID,
) -> dict[str, Any] | None:
    """Submit a result sheet for verification."""
    # Get current sheet
    sheet = await get_result_sheet(conn, sheet_id)
    if not sheet:
        return None

    if sheet["status"] != "draft":
        raise ValueError(f"Cannot submit sheet with status: {sheet['status']}")

    # Validate entries exist
    entries = await get_result_entries(conn, sheet_id)
    if not entries:
        raise ValueError("Cannot submit sheet without vote entries")

    # Calculate totals
    total_valid = sum(e["votes_in_figures"] for e in entries)

    # Update status
    row = await conn.fetchrow(
        """
        UPDATE result_sheets
        SET
            status = 'submitted',
            submitted_at = NOW(),
            submitted_by = $2,
            valid_votes = $3,
            updated_at = NOW()
        WHERE id = $1
        RETURNING *
        """,
        sheet_id,
        submitted_by,
        total_valid,
    )

    if row:
        # Log workflow action
        await log_workflow_action(
            conn,
            result_sheet_id=sheet_id,
            action="submitted",
            performed_by=submitted_by,
            from_status="draft",
            to_status="submitted",
            notes="Result sheet submitted for verification",
        )

    return _parse_row(row) if row else None


async def verify_result_sheet(
    conn: asyncpg.Connection,
    sheet_id: UUID,
    verified_by: UUID,
    *,
    notes: str | None = None,
) -> dict[str, Any] | None:
    """Mark a result sheet as verified."""
    sheet = await get_result_sheet(conn, sheet_id)
    if not sheet:
        return None

    if sheet["status"] != "submitted":
        raise ValueError(f"Cannot verify sheet with status: {sheet['status']}")

    row = await conn.fetchrow(
        """
        UPDATE result_sheets
        SET
            status = 'verified',
            verified_at = NOW(),
            verified_by = $2,
            verification_notes = $3,
            updated_at = NOW()
        WHERE id = $1
        RETURNING *
        """,
        sheet_id,
        verified_by,
        notes,
    )

    if row:
        await log_workflow_action(
            conn,
            result_sheet_id=sheet_id,
            action="verified",
            performed_by=verified_by,
            from_status="submitted",
            to_status="verified",
            notes=notes,
        )

    return _parse_row(row) if row else None


async def approve_result_sheet(
    conn: asyncpg.Connection,
    sheet_id: UUID,
    approved_by: UUID,
    *,
    notes: str | None = None,
) -> dict[str, Any] | None:
    """Approve a verified result sheet."""
    sheet = await get_result_sheet(conn, sheet_id)
    if not sheet:
        return None

    if sheet["status"] != "verified":
        raise ValueError(f"Cannot approve sheet with status: {sheet['status']}")

    row = await conn.fetchrow(
        """
        UPDATE result_sheets
        SET
            status = 'approved',
            approved_at = NOW(),
            approved_by = $2,
            updated_at = NOW()
        WHERE id = $1
        RETURNING *
        """,
        sheet_id,
        approved_by,
    )

    if row:
        await log_workflow_action(
            conn,
            result_sheet_id=sheet_id,
            action="approved",
            performed_by=approved_by,
            from_status="verified",
            to_status="approved",
            notes=notes,
        )

    return _parse_row(row) if row else None


async def certify_result_sheet(
    conn: asyncpg.Connection,
    sheet_id: UUID,
    certified_by: UUID,
    *,
    notes: str | None = None,
) -> dict[str, Any] | None:
    """Certify an approved result sheet (final status)."""
    sheet = await get_result_sheet(conn, sheet_id)
    if not sheet:
        return None

    if sheet["status"] != "approved":
        raise ValueError(f"Cannot certify sheet with status: {sheet['status']}")

    row = await conn.fetchrow(
        """
        UPDATE result_sheets
        SET
            status = 'certified',
            updated_at = NOW()
        WHERE id = $1
        RETURNING *
        """,
        sheet_id,
    )

    if row:
        await log_workflow_action(
            conn,
            result_sheet_id=sheet_id,
            action="certified",
            performed_by=certified_by,
            from_status="approved",
            to_status="certified",
            notes=notes,
        )

    return _parse_row(row) if row else None


async def reject_result_sheet(
    conn: asyncpg.Connection,
    sheet_id: UUID,
    rejected_by: UUID,
    reason: str,
) -> dict[str, Any] | None:
    """Reject a result sheet back to draft status."""
    sheet = await get_result_sheet(conn, sheet_id)
    if not sheet:
        return None

    row = await conn.fetchrow(
        """
        UPDATE result_sheets
        SET
            status = 'draft',
            submitted_at = NULL,
            submitted_by = NULL,
            verified_at = NULL,
            verified_by = NULL,
            verification_notes = NULL,
            approved_at = NULL,
            approved_by = NULL,
            rejected_by = $2,
            rejected_at = NOW(),
            rejection_reason = $3,
            updated_at = NOW()
        WHERE id = $1
        RETURNING *
        """,
        sheet_id,
        rejected_by,
        reason,
    )

    if row:
        await log_workflow_action(
            conn,
            result_sheet_id=sheet_id,
            action="rejected",
            performed_by=rejected_by,
            from_status=sheet["status"],  # Previous status
            to_status="draft",
            notes=reason,
        )

    return _parse_row(row) if row else None


async def log_workflow_action(
    conn: asyncpg.Connection,
    *,
    result_sheet_id: UUID,
    action: str,
    performed_by: UUID,
    to_status: str,
    from_status: str | None = None,
    notes: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Log a workflow action for audit trail."""
    import json

    # Get election_id from result sheet (required by table)
    sheet = await conn.fetchrow(
        "SELECT election_id FROM result_sheets WHERE id = $1",
        result_sheet_id,
    )
    if not sheet:
        return {}

    row = await conn.fetchrow(
        """
        INSERT INTO collation_workflow_log (
            result_sheet_id, election_id, action, from_status, to_status,
            performed_by, reason, metadata
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        RETURNING *
        """,
        result_sheet_id,
        sheet["election_id"],
        action,
        from_status,
        to_status,
        performed_by,
        notes,
        json.dumps(metadata) if metadata else None,
    )
    return _parse_row(row) if row else {}


async def get_workflow_history(
    conn: asyncpg.Connection,
    result_sheet_id: UUID,
) -> list[dict[str, Any]]:
    """Get workflow history for a result sheet."""
    rows = await conn.fetch(
        """
        SELECT
            cwl.*,
            u.username as performed_by_username
        FROM collation_workflow_log cwl
        LEFT JOIN users u ON cwl.performed_by = u.id
        WHERE cwl.result_sheet_id = $1
        ORDER BY cwl.created_at DESC
        """,
        result_sheet_id,
    )
    return [_parse_row(row) for row in rows]


# ============================================
# STATISTICS
# ============================================


async def get_sheet_summary(
    conn: asyncpg.Connection,
    sheet_id: UUID,
) -> dict[str, Any]:
    """Get complete summary of a result sheet."""
    sheet = await get_result_sheet(conn, sheet_id)
    if not sheet:
        return {}

    entries = await get_result_entries(conn, sheet_id)
    attachments = await get_attachments(conn, sheet_id)
    workflow = await get_workflow_history(conn, sheet_id)

    # Group entries by position
    positions: dict[str, list[dict[str, Any]]] = {}
    for entry in entries:
        pos_title = entry.get("position_title") or "Poll"
        if pos_title not in positions:
            positions[pos_title] = []
        positions[pos_title].append(entry)

    return {
        **sheet,
        "entries_by_position": positions,
        "total_entries": len(entries),
        "attachments": attachments,
        "workflow_history": workflow,
    }


async def get_submission_progress(
    conn: asyncpg.Connection,
    election_id: UUID,
    *,
    region_id: UUID | None = None,
    constituency_id: UUID | None = None,
) -> dict[str, Any]:
    """Get result sheet submission progress for an election."""
    # Get sheets by status
    status_query = """
        SELECT
            rs.status,
            COUNT(*) as count
        FROM result_sheets rs
        LEFT JOIN polling_stations ps ON rs.polling_station_id = ps.id
        LEFT JOIN electoral_areas ea ON ps.electoral_area_id = ea.id
        LEFT JOIN constituencies c ON ea.constituency_id = c.id
        WHERE rs.election_id = $1
    """
    status_params: list[Any] = [election_id]

    if region_id:
        status_query += " AND c.region_id = $2"
        status_params.append(region_id)
    elif constituency_id:
        status_query += " AND c.id = $2"
        status_params.append(constituency_id)

    status_query += " GROUP BY rs.status"

    status_rows = await conn.fetch(status_query, *status_params)
    status_counts = {row["status"]: row["count"] for row in status_rows}

    submitted = sum(
        status_counts.get(s, 0)
        for s in ["submitted", "verified", "approved", "certified"]
    )

    total = sum(status_counts.values())

    return {
        "total_stations": total,
        "sheets_created": total,
        "drafts": status_counts.get("draft", 0),
        "submitted": status_counts.get("submitted", 0),
        "verified": status_counts.get("verified", 0),
        "approved": status_counts.get("approved", 0),
        "certified": status_counts.get("certified", 0),
        "completion_rate": round((submitted / total * 100) if total else 0, 2),
    }
