"""Collation service for election result aggregation.

Handles collation officers, result aggregation, and real-time collation tracking.
"""

import json
from datetime import datetime
from typing import Any
from uuid import UUID

import asyncpg


# ============================================
# COLLATION OFFICERS
# ============================================


async def create_collation_officer(
    conn: asyncpg.Connection,
    *,
    user_id: UUID,
    organization_id: UUID,
    officer_type: str,  # 'presiding', 'returning', 'deputy_returning', 'collation_clerk'
    level: str,  # 'polling_station', 'electoral_area', 'constituency', 'regional', 'national'
    id_number: str | None = None,
    phone: str | None = None,
    emergency_contact: str | None = None,
    training_completed: bool = False,
    training_date: datetime | None = None,
    oath_taken: bool = False,
    oath_date: datetime | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Register a user as a collation officer."""
    # Check if officer already exists for this user
    existing = await conn.fetchrow(
        "SELECT id FROM collation_officers WHERE user_id = $1",
        user_id,
    )

    if existing:
        # Update existing officer
        row = await conn.fetchrow(
            """
            UPDATE collation_officers SET
                officer_type = $2,
                level = $3,
                id_number = COALESCE($4, id_number),
                phone = COALESCE($5, phone),
                emergency_contact = COALESCE($6, emergency_contact),
                training_completed = COALESCE($7, training_completed),
                training_date = COALESCE($8, training_date),
                oath_taken = COALESCE($9, oath_taken),
                oath_date = COALESCE($10, oath_date),
                metadata = COALESCE($11, metadata),
                updated_at = NOW()
            WHERE user_id = $1
            RETURNING *
            """,
            user_id,
            officer_type,
            level,
            id_number,
            phone,
            emergency_contact,
            training_completed,
            training_date,
            oath_taken,
            oath_date,
            json.dumps(metadata) if metadata else None,
        )
    else:
        # Insert new officer
        row = await conn.fetchrow(
            """
            INSERT INTO collation_officers (
                user_id, organization_id, officer_type, level, id_number, phone,
                emergency_contact, training_completed, training_date,
                oath_taken, oath_date, metadata
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
            RETURNING *
            """,
            user_id,
            organization_id,
            officer_type,
            level,
            id_number,
            phone,
            emergency_contact,
            training_completed,
            training_date,
            oath_taken,
            oath_date,
            json.dumps(metadata) if metadata else None,
        )
    return dict(row) if row else {}


async def get_collation_officer(
    conn: asyncpg.Connection,
    officer_id: UUID | None = None,
    user_id: UUID | None = None,
) -> dict[str, Any] | None:
    """Get a collation officer by ID or user ID."""
    if officer_id:
        row = await conn.fetchrow(
            """
            SELECT co.*, u.username, u.email
            FROM collation_officers co
            JOIN users u ON co.user_id = u.id
            WHERE co.id = $1
            """,
            officer_id,
        )
    elif user_id:
        row = await conn.fetchrow(
            """
            SELECT co.*, u.username, u.email
            FROM collation_officers co
            JOIN users u ON co.user_id = u.id
            WHERE co.user_id = $1
            """,
            user_id,
        )
    else:
        return None

    return dict(row) if row else None


async def list_collation_officers(
    conn: asyncpg.Connection,
    *,
    officer_type: str | None = None,
    level: str | None = None,
    status: str | None = None,
    organization_id: UUID | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """List collation officers."""
    query = """
        SELECT co.*, u.username, u.email
        FROM collation_officers co
        JOIN users u ON co.user_id = u.id
        WHERE 1=1
    """
    params: list[Any] = []
    param_count = 0

    if officer_type:
        param_count += 1
        query += f" AND co.officer_type = ${param_count}"
        params.append(officer_type)

    if level:
        param_count += 1
        query += f" AND co.level = ${param_count}"
        params.append(level)

    if status:
        param_count += 1
        query += f" AND co.status = ${param_count}"
        params.append(status)

    if organization_id:
        param_count += 1
        query += f" AND co.organization_id = ${param_count}"
        params.append(organization_id)

    query += f" ORDER BY co.created_at DESC LIMIT ${param_count + 1} OFFSET ${param_count + 2}"
    params.extend([limit, offset])

    rows = await conn.fetch(query, *params)
    return [dict(row) for row in rows]


# ============================================
# OFFICER ASSIGNMENTS
# ============================================


async def assign_officer(
    conn: asyncpg.Connection,
    *,
    officer_id: UUID,
    election_id: UUID,
    polling_station_id: UUID | None = None,
    collation_center_id: UUID | None = None,
    role: str,  # 'presiding_officer', 'returning_officer', 'collation_clerk'
    assigned_by: UUID,
) -> dict[str, Any]:
    """Assign an officer to a polling station or collation center."""
    row = await conn.fetchrow(
        """
        INSERT INTO officer_assignments (
            officer_id, election_id, polling_station_id,
            collation_center_id, role, assigned_by
        )
        VALUES ($1, $2, $3, $4, $5, $6)
        ON CONFLICT (officer_id, election_id, polling_station_id)
        WHERE polling_station_id IS NOT NULL
        DO UPDATE SET role = $5, assigned_by = $6, updated_at = NOW()
        RETURNING *
        """,
        officer_id,
        election_id,
        polling_station_id,
        collation_center_id,
        role,
        assigned_by,
    )
    return dict(row) if row else {}


async def get_officer_assignments(
    conn: asyncpg.Connection,
    election_id: UUID,
    *,
    officer_id: UUID | None = None,
    polling_station_id: UUID | None = None,
    collation_center_id: UUID | None = None,
) -> list[dict[str, Any]]:
    """Get officer assignments for an election."""
    query = """
        SELECT
            oa.*,
            co.officer_type,
            u.username as officer_name,
            ps.name as polling_station_name,
            ps.code as polling_station_code,
            cc.name as collation_center_name
        FROM officer_assignments oa
        JOIN collation_officers co ON oa.officer_id = co.id
        JOIN users u ON co.user_id = u.id
        LEFT JOIN polling_stations ps ON oa.polling_station_id = ps.id
        LEFT JOIN collation_centers cc ON oa.collation_center_id = cc.id
        WHERE oa.election_id = $1
    """
    params: list[Any] = [election_id]
    param_count = 1

    if officer_id:
        param_count += 1
        query += f" AND oa.officer_id = ${param_count}"
        params.append(officer_id)

    if polling_station_id:
        param_count += 1
        query += f" AND oa.polling_station_id = ${param_count}"
        params.append(polling_station_id)

    if collation_center_id:
        param_count += 1
        query += f" AND oa.collation_center_id = ${param_count}"
        params.append(collation_center_id)

    query += " ORDER BY oa.created_at"
    rows = await conn.fetch(query, *params)
    return [dict(row) for row in rows]


async def remove_assignment(
    conn: asyncpg.Connection,
    assignment_id: UUID,
) -> bool:
    """Remove an officer assignment."""
    result = await conn.execute(
        "DELETE FROM officer_assignments WHERE id = $1",
        assignment_id,
    )
    return result == "DELETE 1"


# ============================================
# COLLATION CENTERS
# ============================================


async def create_collation_center(
    conn: asyncpg.Connection,
    *,
    organization_id: UUID,
    name: str,
    level: str,  # 'electoral_area', 'constituency', 'regional', 'national'
    electoral_area_id: UUID | None = None,
    constituency_id: UUID | None = None,
    region_id: UUID | None = None,
    address: str | None = None,
    gps_lat: float | None = None,
    gps_lng: float | None = None,
    contact_phone: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a collation center."""
    row = await conn.fetchrow(
        """
        INSERT INTO collation_centers (
            organization_id, name, level, electoral_area_id, constituency_id,
            region_id, address, gps_lat, gps_lng, contact_phone, metadata
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
        RETURNING *
        """,
        organization_id,
        name,
        level,
        electoral_area_id,
        constituency_id,
        region_id,
        address,
        gps_lat,
        gps_lng,
        contact_phone,
        json.dumps(metadata) if metadata else None,
    )
    return dict(row) if row else {}


async def list_collation_centers(
    conn: asyncpg.Connection,
    *,
    level: str | None = None,
    region_id: UUID | None = None,
    constituency_id: UUID | None = None,
    organization_id: UUID | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """List collation centers."""
    query = """
        SELECT
            cc.*,
            ea.name as electoral_area_name,
            c.name as constituency_name,
            r.name as region_name
        FROM collation_centers cc
        LEFT JOIN electoral_areas ea ON cc.electoral_area_id = ea.id
        LEFT JOIN constituencies c ON cc.constituency_id = c.id OR ea.constituency_id = c.id
        LEFT JOIN regions r ON cc.region_id = r.id OR c.region_id = r.id
        WHERE 1=1
    """
    params: list[Any] = []
    param_count = 0

    if level:
        param_count += 1
        query += f" AND cc.level = ${param_count}"
        params.append(level)

    if region_id:
        param_count += 1
        query += f" AND (cc.region_id = ${param_count} OR c.region_id = ${param_count})"
        params.append(region_id)

    if constituency_id:
        param_count += 1
        query += f" AND (cc.constituency_id = ${param_count} OR ea.constituency_id = ${param_count})"
        params.append(constituency_id)

    if organization_id:
        param_count += 1
        query += f" AND cc.organization_id = ${param_count}"
        params.append(organization_id)

    query += f" ORDER BY cc.name LIMIT ${param_count + 1} OFFSET ${param_count + 2}"
    params.extend([limit, offset])

    rows = await conn.fetch(query, *params)
    return [dict(row) for row in rows]


# ============================================
# RESULT AGGREGATION
# ============================================


async def aggregate_results(
    conn: asyncpg.Connection,
    election_id: UUID,
    *,
    level: str,  # 'electoral_area', 'constituency', 'regional', 'national'
    area_id: UUID | None = None,  # ID of the area to aggregate for
) -> dict[str, Any]:
    """
    Aggregate results from approved result sheets.

    For electoral_area: aggregates all polling stations in that area
    For constituency: aggregates all electoral areas
    For regional: aggregates all constituencies
    For national: aggregates all regions
    """
    # Build the aggregation query based on level
    if level == "electoral_area" and area_id:
        query = """
            SELECT
                rse.position_id,
                rse.candidate_id,
                rse.poll_option_id,
                SUM(rse.votes) as total_votes,
                COUNT(DISTINCT rs.polling_station_id) as stations_counted
            FROM result_sheet_entries rse
            JOIN result_sheets rs ON rse.result_sheet_id = rs.id
            JOIN polling_stations ps ON rs.polling_station_id = ps.id
            WHERE rs.election_id = $1
              AND rs.status IN ('approved', 'certified')
              AND rs.sheet_type = 'polling_station'
              AND ps.electoral_area_id = $2
            GROUP BY rse.position_id, rse.candidate_id, rse.poll_option_id
        """
        params = [election_id, area_id]

    elif level == "constituency" and area_id:
        query = """
            SELECT
                rse.position_id,
                rse.candidate_id,
                rse.poll_option_id,
                SUM(rse.votes) as total_votes,
                COUNT(DISTINCT rs.polling_station_id) as stations_counted
            FROM result_sheet_entries rse
            JOIN result_sheets rs ON rse.result_sheet_id = rs.id
            JOIN polling_stations ps ON rs.polling_station_id = ps.id
            JOIN electoral_areas ea ON ps.electoral_area_id = ea.id
            WHERE rs.election_id = $1
              AND rs.status IN ('approved', 'certified')
              AND rs.sheet_type = 'polling_station'
              AND ea.constituency_id = $2
            GROUP BY rse.position_id, rse.candidate_id, rse.poll_option_id
        """
        params = [election_id, area_id]

    elif level == "regional" and area_id:
        query = """
            SELECT
                rse.position_id,
                rse.candidate_id,
                rse.poll_option_id,
                SUM(rse.votes) as total_votes,
                COUNT(DISTINCT rs.polling_station_id) as stations_counted
            FROM result_sheet_entries rse
            JOIN result_sheets rs ON rse.result_sheet_id = rs.id
            JOIN polling_stations ps ON rs.polling_station_id = ps.id
            JOIN electoral_areas ea ON ps.electoral_area_id = ea.id
            JOIN constituencies c ON ea.constituency_id = c.id
            WHERE rs.election_id = $1
              AND rs.status IN ('approved', 'certified')
              AND rs.sheet_type = 'polling_station'
              AND c.region_id = $2
            GROUP BY rse.position_id, rse.candidate_id, rse.poll_option_id
        """
        params = [election_id, area_id]

    else:  # national
        query = """
            SELECT
                rse.position_id,
                rse.candidate_id,
                rse.poll_option_id,
                SUM(rse.votes) as total_votes,
                COUNT(DISTINCT rs.polling_station_id) as stations_counted
            FROM result_sheet_entries rse
            JOIN result_sheets rs ON rse.result_sheet_id = rs.id
            WHERE rs.election_id = $1
              AND rs.status IN ('approved', 'certified')
              AND rs.sheet_type = 'polling_station'
            GROUP BY rse.position_id, rse.candidate_id, rse.poll_option_id
        """
        params = [election_id]

    rows = await conn.fetch(query, *params)

    # Get candidate/position details
    results_by_position: dict[str, list[dict[str, Any]]] = {}
    total_stations = 0

    for row in rows:
        total_stations = max(total_stations, row["stations_counted"])

        pos_id = str(row["position_id"]) if row["position_id"] else "poll"
        if pos_id not in results_by_position:
            results_by_position[pos_id] = []

        results_by_position[pos_id].append({
            "candidate_id": str(row["candidate_id"]) if row["candidate_id"] else None,
            "poll_option_id": str(row["poll_option_id"]) if row["poll_option_id"] else None,
            "votes": row["total_votes"],
        })

    # Sort each position by votes
    for pos_id in results_by_position:
        results_by_position[pos_id].sort(key=lambda x: x["votes"], reverse=True)

    return {
        "election_id": str(election_id),
        "level": level,
        "area_id": str(area_id) if area_id else None,
        "stations_counted": total_stations,
        "results_by_position": results_by_position,
        "aggregated_at": datetime.utcnow().isoformat(),
    }


async def save_collation_result(
    conn: asyncpg.Connection,
    *,
    election_id: UUID,
    level: str,
    electoral_area_id: UUID | None = None,
    constituency_id: UUID | None = None,
    region_id: UUID | None = None,
    results_data: dict[str, Any],
    collated_by: UUID,
) -> dict[str, Any]:
    """Save aggregated collation results."""
    row = await conn.fetchrow(
        """
        INSERT INTO collation_results (
            election_id, level, electoral_area_id, constituency_id,
            region_id, results_data, collated_by
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        ON CONFLICT (election_id, level, electoral_area_id, constituency_id, region_id)
        DO UPDATE SET
            results_data = $6,
            collated_by = $7,
            updated_at = NOW()
        RETURNING *
        """,
        election_id,
        level,
        electoral_area_id,
        constituency_id,
        region_id,
        json.dumps(results_data),
        collated_by,
    )
    return dict(row) if row else {}


async def get_collation_results(
    conn: asyncpg.Connection,
    election_id: UUID,
    *,
    level: str | None = None,
) -> list[dict[str, Any]]:
    """Get saved collation results."""
    query = """
        SELECT
            cr.*,
            ea.name as electoral_area_name,
            c.name as constituency_name,
            r.name as region_name,
            u.username as collated_by_username
        FROM collation_results cr
        LEFT JOIN electoral_areas ea ON cr.electoral_area_id = ea.id
        LEFT JOIN constituencies c ON cr.constituency_id = c.id
        LEFT JOIN regions r ON cr.region_id = r.id
        LEFT JOIN users u ON cr.collated_by = u.id
        WHERE cr.election_id = $1
    """
    params: list[Any] = [election_id]

    if level:
        query += " AND cr.level = $2"
        params.append(level)

    query += " ORDER BY cr.level, cr.updated_at DESC"
    rows = await conn.fetch(query, *params)
    return [dict(row) for row in rows]


# ============================================
# REAL-TIME COLLATION DASHBOARD
# ============================================


async def get_collation_dashboard(
    conn: asyncpg.Connection,
    election_id: UUID,
) -> dict[str, Any]:
    """Get comprehensive collation dashboard data."""
    # Get election info
    election = await conn.fetchrow(
        "SELECT id, title, status FROM elections WHERE id = $1",
        election_id,
    )

    if not election:
        return {}

    # Get total polling stations for this election
    total_stations = await conn.fetchval(
        """
        SELECT COUNT(*) FROM election_polling_stations
        WHERE election_id = $1
        """,
        election_id,
    )

    # Get result sheet status breakdown
    status_breakdown = await conn.fetch(
        """
        SELECT status, COUNT(*) as count
        FROM result_sheets
        WHERE election_id = $1 AND sheet_type = 'polling_station'
        GROUP BY status
        """,
        election_id,
    )
    status_counts = {row["status"]: row["count"] for row in status_breakdown}

    # Get regional breakdown
    regional_breakdown = await conn.fetch(
        """
        SELECT
            r.id as region_id,
            r.name as region_name,
            COUNT(DISTINCT ps.id) as total_stations,
            COUNT(DISTINCT CASE WHEN rs.status IN ('approved', 'certified') THEN rs.id END) as completed_stations,
            SUM(CASE WHEN rs.status IN ('approved', 'certified') THEN rse.votes_in_figures ELSE 0 END) as total_votes
        FROM regions r
        LEFT JOIN constituencies c ON c.region_id = r.id
        LEFT JOIN electoral_areas ea ON ea.constituency_id = c.id
        LEFT JOIN polling_stations ps ON ps.electoral_area_id = ea.id
        LEFT JOIN election_polling_stations eps ON eps.polling_station_id = ps.id AND eps.election_id = $1
        LEFT JOIN result_sheets rs ON rs.polling_station_id = ps.id AND rs.election_id = $1
        LEFT JOIN result_sheet_entries rse ON rse.result_sheet_id = rs.id
        WHERE eps.election_id = $1 OR eps.election_id IS NULL
        GROUP BY r.id, r.name
        HAVING COUNT(DISTINCT ps.id) > 0
        ORDER BY r.name
        """,
        election_id,
    )

    # Get top candidates (quick preview)
    top_candidates = await conn.fetch(
        """
        SELECT
            rse.candidate_name,
            rse.party,
            SUM(rse.votes_in_figures) as total_votes
        FROM result_sheet_entries rse
        JOIN result_sheets rs ON rse.result_sheet_id = rs.id
        WHERE rs.election_id = $1
          AND rs.status IN ('approved', 'certified')
          AND rse.candidate_name IS NOT NULL
        GROUP BY rse.candidate_name, rse.party
        ORDER BY total_votes DESC
        LIMIT 10
        """,
        election_id,
    )

    # Calculate totals
    certified = status_counts.get("certified", 0)
    approved = status_counts.get("approved", 0)
    verified = status_counts.get("verified", 0)
    submitted = status_counts.get("submitted", 0)
    drafts = status_counts.get("draft", 0)

    completed = certified + approved
    in_progress = verified + submitted + drafts
    pending = (total_stations or 0) - (completed + in_progress)

    return {
        "election": dict(election),
        "summary": {
            "total_stations": total_stations or 0,
            "completed": completed,
            "in_progress": in_progress,
            "pending": max(0, pending),
            "completion_percentage": round(
                (completed / total_stations * 100) if total_stations else 0, 2
            ),
        },
        "status_breakdown": {
            "draft": drafts,
            "submitted": submitted,
            "verified": verified,
            "approved": approved,
            "certified": certified,
        },
        "regional_breakdown": [dict(row) for row in regional_breakdown],
        "top_candidates": [dict(row) for row in top_candidates],
        "last_updated": datetime.utcnow().isoformat(),
    }


async def get_live_feed(
    conn: asyncpg.Connection,
    election_id: UUID,
    *,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Get live feed of recent collation activities."""
    rows = await conn.fetch(
        """
        SELECT
            cwl.id,
            cwl.action,
            cwl.created_at,
            cwl.reason,
            cwl.from_status,
            cwl.to_status,
            u.username as performed_by,
            rs.sheet_type,
            ps.name as polling_station_name,
            ps.code as polling_station_code,
            ea.name as electoral_area_name,
            c.name as constituency_name,
            r.name as region_name
        FROM collation_workflow_log cwl
        LEFT JOIN result_sheets rs ON cwl.result_sheet_id = rs.id
        LEFT JOIN polling_stations ps ON rs.polling_station_id = ps.id
        LEFT JOIN electoral_areas ea ON ps.electoral_area_id = ea.id
        LEFT JOIN constituencies c ON ea.constituency_id = c.id
        LEFT JOIN regions r ON c.region_id = r.id
        LEFT JOIN users u ON cwl.performed_by = u.id
        WHERE cwl.election_id = $1
        ORDER BY cwl.created_at DESC
        LIMIT $2
        """,
        election_id,
        limit,
    )
    return [dict(row) for row in rows]


# ============================================
# INCIDENTS AND DISCREPANCIES
# ============================================


async def report_incident(
    conn: asyncpg.Connection,
    *,
    election_id: UUID,
    polling_station_id: UUID | None = None,
    electoral_area_id: UUID | None = None,
    constituency_id: UUID | None = None,
    region_id: UUID | None = None,
    result_sheet_id: UUID | None = None,
    incident_type: str,  # 'violence', 'equipment_failure', 'irregularity', 'protest', 'other'
    category: str,  # 'technical', 'civil', 'procedural', 'security', 'other'
    severity: str,  # 'low', 'medium', 'high', 'critical'
    title: str,
    description: str,
    reported_by: UUID,
    report_gps_lat: float | None = None,
    report_gps_lng: float | None = None,
) -> dict[str, Any]:
    """Report a collation incident."""
    row = await conn.fetchrow(
        """
        INSERT INTO collation_incidents (
            election_id, polling_station_id, electoral_area_id, constituency_id,
            region_id, result_sheet_id, incident_type, category, severity,
            title, description, reported_by, report_gps_lat, report_gps_lng
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
        RETURNING *
        """,
        election_id,
        polling_station_id,
        electoral_area_id,
        constituency_id,
        region_id,
        result_sheet_id,
        incident_type,
        category,
        severity,
        title,
        description,
        reported_by,
        report_gps_lat,
        report_gps_lng,
    )
    return dict(row) if row else {}


async def list_incidents(
    conn: asyncpg.Connection,
    election_id: UUID,
    *,
    status: str | None = None,
    severity: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """List incidents for an election."""
    query = """
        SELECT
            ci.*,
            ps.name as polling_station_name,
            ea.name as electoral_area_name,
            c.name as constituency_name,
            r.name as region_name,
            u.username as reported_by_username,
            ru.username as resolved_by_username
        FROM collation_incidents ci
        LEFT JOIN polling_stations ps ON ci.polling_station_id = ps.id
        LEFT JOIN electoral_areas ea ON ci.electoral_area_id = ea.id
        LEFT JOIN constituencies c ON ci.constituency_id = c.id
        LEFT JOIN regions r ON ci.region_id = r.id
        LEFT JOIN users u ON ci.reported_by = u.id
        LEFT JOIN users ru ON ci.resolved_by = ru.id
        WHERE ci.election_id = $1
    """
    params: list[Any] = [election_id]
    param_count = 1

    if status:
        param_count += 1
        query += f" AND ci.status = ${param_count}"
        params.append(status)

    if severity:
        param_count += 1
        query += f" AND ci.severity = ${param_count}"
        params.append(severity)

    query += f" ORDER BY ci.reported_at DESC LIMIT ${param_count + 1}"
    params.append(limit)

    rows = await conn.fetch(query, *params)
    return [dict(row) for row in rows]


async def resolve_incident(
    conn: asyncpg.Connection,
    incident_id: UUID,
    resolved_by: UUID,
    resolution_notes: str,
) -> dict[str, Any] | None:
    """Resolve an incident."""
    row = await conn.fetchrow(
        """
        UPDATE collation_incidents
        SET
            status = 'resolved',
            resolved_by = $2,
            resolved_at = NOW(),
            resolution = $3
        WHERE id = $1
        RETURNING *
        """,
        incident_id,
        resolved_by,
        resolution_notes,
    )
    return dict(row) if row else None


async def get_discrepancies(
    conn: asyncpg.Connection,
    election_id: UUID,
    *,
    status: str | None = None,
) -> list[dict[str, Any]]:
    """Get discrepancies detected in result sheets."""
    query = """
        SELECT
            cd.*,
            rs.sheet_type,
            ps.name as polling_station_name,
            u.username as resolved_by_username
        FROM collation_discrepancies cd
        JOIN result_sheets rs ON cd.result_sheet_id = rs.id
        LEFT JOIN polling_stations ps ON rs.polling_station_id = ps.id
        LEFT JOIN users u ON cd.resolved_by = u.id
        WHERE rs.election_id = $1
    """
    params: list[Any] = [election_id]

    if status:
        query += " AND cd.status = $2"
        params.append(status)

    query += " ORDER BY cd.detected_at DESC"
    rows = await conn.fetch(query, *params)
    return [dict(row) for row in rows]


async def resolve_discrepancy(
    conn: asyncpg.Connection,
    discrepancy_id: UUID,
    resolved_by: UUID,
    resolution_notes: str,
) -> dict[str, Any] | None:
    """Resolve a discrepancy."""
    row = await conn.fetchrow(
        """
        UPDATE collation_discrepancies
        SET
            status = 'resolved',
            resolved_by = $2,
            resolved_at = NOW(),
            resolution_notes = $3
        WHERE id = $1
        RETURNING *
        """,
        discrepancy_id,
        resolved_by,
        resolution_notes,
    )
    return dict(row) if row else None
