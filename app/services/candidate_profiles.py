"""Candidate profile service functions."""

import json
from datetime import date
from typing import Any
from uuid import UUID

import asyncpg


def _parse_profile_row(row: asyncpg.Record | None) -> dict[str, Any] | None:
    """Parse a profile row into a dict with proper JSON parsing."""
    if not row:
        return None

    result = dict(row)

    # Convert UUID fields to strings
    uuid_fields = ("id", "organization_id", "party_id")
    for field in uuid_fields:
        if result.get(field) is not None:
            result[field] = str(result[field])

    # Parse JSONB fields
    for field in ("policies", "experience", "endorsements", "education", "social_links"):
        if result.get(field):
            if isinstance(result[field], str):
                result[field] = json.loads(result[field])

    return result


def _parse_assignment_row(row: asyncpg.Record | None) -> dict[str, Any] | None:
    """Parse an assignment row into a dict."""
    if not row:
        return None

    result = dict(row)

    uuid_fields = ("id", "candidate_profile_id", "position_id", "election_id")
    for field in uuid_fields:
        if result.get(field) is not None:
            result[field] = str(result[field])

    return result


# ============================================
# CANDIDATE PROFILE CRUD
# ============================================


async def create_candidate_profile(
    conn: asyncpg.Connection,
    organization_id: UUID,
    name: str,
    photo_url: str | None = None,
    email: str | None = None,
    phone: str | None = None,
    date_of_birth: str | None = None,
    party_id: UUID | None = None,
    party: str | None = None,
    bio: str | None = None,
    manifesto: str | None = None,
    policies: dict | None = None,
    experience: dict | None = None,
    endorsements: list | None = None,
    education: list | None = None,
    social_links: dict | None = None,
) -> dict[str, Any] | None:
    """Create a new candidate profile."""
    dob = None
    if date_of_birth:
        try:
            dob = date.fromisoformat(date_of_birth)
        except ValueError:
            pass

    result = await conn.fetchrow(
        """
        INSERT INTO candidate_profiles (
            organization_id, name, photo_url, email, phone, date_of_birth,
            party_id, party, bio, manifesto, policies, experience, endorsements,
            education, social_links
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
        ON CONFLICT DO NOTHING
        RETURNING *
        """,
        str(organization_id),
        name,
        photo_url,
        email,
        phone,
        dob,
        str(party_id) if party_id else None,
        party,
        bio,
        manifesto,
        json.dumps(policies or {}),
        json.dumps(experience or {}),
        json.dumps(endorsements or []),
        json.dumps(education or []),
        json.dumps(social_links or {}),
    )
    return _parse_profile_row(result)


async def get_candidate_profile(
    conn: asyncpg.Connection,
    profile_id: UUID,
    organization_id: UUID | None = None,
) -> dict[str, Any] | None:
    """Get a candidate profile by ID."""
    query = """
        SELECT * FROM candidate_profiles
        WHERE id = $1 AND deleted = FALSE
    """
    params: list[Any] = [str(profile_id)]

    if organization_id:
        query += " AND organization_id = $2"
        params.append(str(organization_id))

    result = await conn.fetchrow(query, *params)
    return _parse_profile_row(result)


async def list_candidate_profiles(
    conn: asyncpg.Connection,
    organization_id: UUID,
    party: str | None = None,
    status: str | None = None,
    search: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    """List candidate profiles with filtering."""
    query = """
        SELECT * FROM candidate_profiles
        WHERE organization_id = $1 AND deleted = FALSE
    """
    count_query = """
        SELECT COUNT(*) FROM candidate_profiles
        WHERE organization_id = $1 AND deleted = FALSE
    """
    params: list[Any] = [str(organization_id)]
    param_num = 2

    if party:
        query += f" AND party = ${param_num}"
        count_query += f" AND party = ${param_num}"
        params.append(party)
        param_num += 1

    if status:
        query += f" AND status = ${param_num}"
        count_query += f" AND status = ${param_num}"
        params.append(status)
        param_num += 1

    if search:
        search_term = f"%{search}%"
        query += f" AND (name ILIKE ${param_num} OR party ILIKE ${param_num})"
        count_query += f" AND (name ILIKE ${param_num} OR party ILIKE ${param_num})"
        params.append(search_term)
        param_num += 1

    # Get total count
    total = await conn.fetchval(count_query, *params)

    # Add ordering and pagination
    query += " ORDER BY name ASC"
    query += f" LIMIT ${param_num} OFFSET ${param_num + 1}"
    params.extend([limit, offset])

    rows = await conn.fetch(query, *params)
    return [_parse_profile_row(row) for row in rows], total or 0


async def update_candidate_profile(
    conn: asyncpg.Connection,
    profile_id: UUID,
    organization_id: UUID,
    **kwargs,
) -> dict[str, Any] | None:
    """Update a candidate profile."""
    # Build dynamic update query
    updates = []
    params: list[Any] = []
    param_num = 1

    field_mapping = {
        "name": "name",
        "photo_url": "photo_url",
        "email": "email",
        "phone": "phone",
        "date_of_birth": "date_of_birth",
        "party_id": "party_id",
        "party": "party",
        "bio": "bio",
        "manifesto": "manifesto",
        "policies": "policies",
        "experience": "experience",
        "endorsements": "endorsements",
        "education": "education",
        "social_links": "social_links",
        "status": "status",
    }

    for key, column in field_mapping.items():
        if key in kwargs and kwargs[key] is not None:
            value = kwargs[key]

            # Handle special types
            if key == "date_of_birth":
                try:
                    value = date.fromisoformat(value)
                except ValueError:
                    continue
            elif key == "party_id":
                value = str(value)
            elif key in ("policies", "experience", "social_links"):
                value = json.dumps(value)
            elif key in ("endorsements", "education"):
                value = json.dumps(value)

            updates.append(f"{column} = ${param_num}")
            params.append(value)
            param_num += 1

    if not updates:
        return await get_candidate_profile(conn, profile_id, organization_id)

    updates.append("updated_at = CURRENT_TIMESTAMP")
    params.extend([str(profile_id), str(organization_id)])

    query = f"""
        UPDATE candidate_profiles
        SET {", ".join(updates)}
        WHERE id = ${param_num} AND organization_id = ${param_num + 1} AND deleted = FALSE
        RETURNING *
    """

    result = await conn.fetchrow(query, *params)
    return _parse_profile_row(result)


async def delete_candidate_profile(
    conn: asyncpg.Connection,
    profile_id: UUID,
    organization_id: UUID,
) -> bool:
    """Soft delete a candidate profile."""
    result = await conn.execute(
        """
        UPDATE candidate_profiles
        SET deleted = TRUE, deleted_at = CURRENT_TIMESTAMP, status = 'inactive'
        WHERE id = $1 AND organization_id = $2 AND deleted = FALSE
        """,
        str(profile_id),
        str(organization_id),
    )
    return int(result.split()[-1]) > 0


# ============================================
# ELECTION CANDIDATE ASSIGNMENT
# ============================================


async def assign_candidate_to_position(
    conn: asyncpg.Connection,
    candidate_profile_id: UUID,
    position_id: UUID,
    organization_id: UUID,
    display_name: str | None = None,
    campaign_photo_url: str | None = None,
    campaign_slogan: str | None = None,
    campaign_manifesto: str | None = None,
    ballot_number: int | None = None,
) -> dict[str, Any] | None:
    """Assign a candidate to an election position."""
    # Verify the position belongs to an election in the org
    # and get the election_id
    position_check = await conn.fetchrow(
        """
        SELECT ep.id, ep.election_id
        FROM election_positions ep
        JOIN elections e ON ep.election_id = e.id
        WHERE ep.id = $1 AND e.organization_id = $2 AND e.deleted = FALSE
        """,
        str(position_id),
        str(organization_id),
    )

    if not position_check:
        return None

    election_id = position_check["election_id"]

    # Verify the candidate profile exists in the org
    profile_check = await conn.fetchval(
        """
        SELECT 1 FROM candidate_profiles
        WHERE id = $1 AND organization_id = $2 AND deleted = FALSE
        """,
        str(candidate_profile_id),
        str(organization_id),
    )

    if not profile_check:
        return None

    result = await conn.fetchrow(
        """
        INSERT INTO election_candidates (
            candidate_profile_id, position_id, election_id,
            display_name, campaign_photo_url, campaign_slogan,
            campaign_manifesto, ballot_number
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        ON CONFLICT DO NOTHING
        RETURNING *
        """,
        str(candidate_profile_id),
        str(position_id),
        str(election_id),
        display_name,
        campaign_photo_url,
        campaign_slogan,
        campaign_manifesto,
        ballot_number,
    )
    return _parse_assignment_row(result)


async def remove_candidate_from_position(
    conn: asyncpg.Connection,
    assignment_id: UUID,
    organization_id: UUID,
) -> bool:
    """Remove a candidate from an election position."""
    # Only allow if election hasn't started
    result = await conn.execute(
        """
        DELETE FROM election_candidates ec
        USING elections e
        WHERE ec.id = $1
          AND ec.election_id = e.id
          AND e.organization_id = $2
          AND e.status IN ('draft', 'scheduled')
        """,
        str(assignment_id),
        str(organization_id),
    )
    return int(result.split()[-1]) > 0


async def update_candidacy_status(
    conn: asyncpg.Connection,
    assignment_id: UUID,
    organization_id: UUID,
    status: str,
) -> dict[str, Any] | None:
    """Update candidacy status."""
    result = await conn.fetchrow(
        """
        UPDATE election_candidates ec
        SET status = $1, updated_at = CURRENT_TIMESTAMP
        FROM elections e
        WHERE ec.id = $2
          AND ec.election_id = e.id
          AND e.organization_id = $3
        RETURNING ec.*
        """,
        status,
        str(assignment_id),
        str(organization_id),
    )
    return _parse_assignment_row(result)


async def get_election_candidates(
    conn: asyncpg.Connection,
    election_id: UUID,
    position_id: UUID | None = None,
) -> list[dict[str, Any]]:
    """Get all candidates for an election with profile info."""
    query = """
        SELECT
            ec.*,
            cp.name as profile_name,
            cp.photo_url as profile_photo,
            cp.party,
            cp.bio,
            cp.manifesto as profile_manifesto,
            cp.total_elections,
            cp.total_wins,
            cp.total_votes_received,
            cp.highest_vote_percentage
        FROM election_candidates ec
        JOIN candidate_profiles cp ON ec.candidate_profile_id = cp.id
        WHERE ec.election_id = $1
    """
    params: list[Any] = [str(election_id)]

    if position_id:
        query += " AND ec.position_id = $2"
        params.append(str(position_id))

    query += " ORDER BY ec.ballot_number NULLS LAST, ec.display_order"

    rows = await conn.fetch(query, *params)
    results = []
    for row in rows:
        data = _parse_assignment_row(row)
        if data:
            # Add profile info
            data["profile_name"] = row["profile_name"]
            data["profile_photo"] = row["profile_photo"]
            data["party"] = row["party"]
            data["bio"] = row["bio"]
            data["profile_manifesto"] = row["profile_manifesto"]
            data["total_elections"] = row["total_elections"]
            data["total_wins"] = row["total_wins"]
            data["total_votes_received"] = row["total_votes_received"]
            data["highest_vote_percentage"] = float(row["highest_vote_percentage"] or 0)
            # Use display_name if set, otherwise profile_name
            data["display_name"] = data.get("display_name") or row["profile_name"]
            results.append(data)
    return results


# ============================================
# CANDIDATE HISTORY & STATS
# ============================================


async def get_candidate_election_history(
    conn: asyncpg.Connection,
    profile_id: UUID,
) -> list[dict[str, Any]]:
    """Get election history for a candidate."""
    rows = await conn.fetch(
        """
        SELECT
            ec.id as assignment_id,
            e.id as election_id,
            e.title as election_title,
            e.election_type,
            e.start_date as election_date,
            e.status as election_status,
            ep.title as position_title,
            ec.votes_received,
            ec.vote_percentage,
            ec.ranking,
            ec.is_winner,
            ec.status as candidacy_status
        FROM election_candidates ec
        JOIN elections e ON ec.election_id = e.id
        JOIN election_positions ep ON ec.position_id = ep.id
        WHERE ec.candidate_profile_id = $1
        ORDER BY e.start_date DESC
        """,
        str(profile_id),
    )

    results = []
    for row in rows:
        results.append({
            "assignment_id": str(row["assignment_id"]),
            "election_id": str(row["election_id"]),
            "election_title": row["election_title"],
            "election_type": row["election_type"],
            "election_date": row["election_date"].isoformat() if row["election_date"] else None,
            "election_status": row["election_status"],
            "position_title": row["position_title"],
            "votes_received": row["votes_received"],
            "vote_percentage": float(row["vote_percentage"] or 0),
            "ranking": row["ranking"],
            "is_winner": row["is_winner"],
            "candidacy_status": row["candidacy_status"],
        })
    return results


async def get_candidate_stats(
    conn: asyncpg.Connection,
    profile_id: UUID,
    organization_id: UUID,
) -> dict[str, Any] | None:
    """Get detailed statistics for a candidate."""
    profile = await get_candidate_profile(conn, profile_id, organization_id)
    if not profile:
        return None

    # Get detailed breakdown
    breakdown = await conn.fetch(
        """
        SELECT
            e.election_type,
            COUNT(*) as elections,
            COUNT(*) FILTER (WHERE ec.is_winner = TRUE) as wins,
            SUM(ec.votes_received) as total_votes,
            AVG(ec.vote_percentage) as avg_percentage
        FROM election_candidates ec
        JOIN elections e ON ec.election_id = e.id
        WHERE ec.candidate_profile_id = $1
        GROUP BY e.election_type
        """,
        str(profile_id),
    )

    stats_by_type = {}
    for row in breakdown:
        stats_by_type[row["election_type"]] = {
            "elections": row["elections"],
            "wins": row["wins"],
            "total_votes": row["total_votes"] or 0,
            "avg_percentage": float(row["avg_percentage"] or 0),
        }

    return {
        "profile": profile,
        "summary": {
            "total_elections": profile.get("total_elections", 0),
            "total_wins": profile.get("total_wins", 0),
            "total_votes_received": profile.get("total_votes_received", 0),
            "highest_vote_percentage": float(profile.get("highest_vote_percentage", 0)),
            "win_rate": (
                round(profile.get("total_wins", 0) / profile.get("total_elections", 1) * 100, 1)
                if profile.get("total_elections", 0) > 0
                else 0
            ),
        },
        "by_election_type": stats_by_type,
    }


async def get_candidates_leaderboard(
    conn: asyncpg.Connection,
    organization_id: UUID,
    sort_by: str = "total_wins",
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Get leaderboard of candidates."""
    sort_columns = {
        "total_wins": "total_wins DESC, total_votes_received DESC",
        "total_votes": "total_votes_received DESC, total_wins DESC",
        "win_rate": "CASE WHEN total_elections > 0 THEN total_wins::float / total_elections ELSE 0 END DESC",
        "elections_count": "total_elections DESC, total_wins DESC",
    }

    order_by = sort_columns.get(sort_by, sort_columns["total_wins"])

    rows = await conn.fetch(
        f"""
        SELECT
            id, name, photo_url, party,
            total_elections, total_wins, total_votes_received,
            highest_vote_percentage,
            CASE WHEN total_elections > 0
                 THEN ROUND(total_wins::numeric / total_elections * 100, 1)
                 ELSE 0
            END as win_rate
        FROM candidate_profiles
        WHERE organization_id = $1 AND deleted = FALSE AND total_elections > 0
        ORDER BY {order_by}
        LIMIT $2
        """,
        str(organization_id),
        limit,
    )

    results = []
    for i, row in enumerate(rows, 1):
        results.append({
            "rank": i,
            "id": str(row["id"]),
            "name": row["name"],
            "photo_url": row["photo_url"],
            "party": row["party"],
            "total_elections": row["total_elections"],
            "total_wins": row["total_wins"],
            "total_votes_received": row["total_votes_received"],
            "highest_vote_percentage": float(row["highest_vote_percentage"] or 0),
            "win_rate": float(row["win_rate"] or 0),
        })
    return results


async def update_election_results(
    conn: asyncpg.Connection,
    election_id: UUID,
) -> bool:
    """Update candidate stats after an election closes."""
    try:
        await conn.execute(
            "SELECT update_candidate_stats($1)",
            str(election_id),
        )
        return True
    except Exception:
        return False
