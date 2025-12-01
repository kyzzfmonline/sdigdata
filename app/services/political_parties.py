"""Political parties service functions."""

import json
from datetime import date
from typing import Any
from uuid import UUID

import asyncpg


def _parse_party_row(row: asyncpg.Record | None) -> dict[str, Any] | None:
    """Parse a party row into a dict."""
    if not row:
        return None

    result = dict(row)

    # Convert UUID fields to strings
    uuid_fields = ("id", "organization_id")
    for field in uuid_fields:
        if result.get(field) is not None:
            result[field] = str(result[field])

    # Parse JSONB fields
    if result.get("social_links"):
        if isinstance(result["social_links"], str):
            result["social_links"] = json.loads(result["social_links"])

    return result


# ============================================
# PARTY CRUD
# ============================================


async def create_party(
    conn: asyncpg.Connection,
    organization_id: UUID,
    name: str,
    abbreviation: str | None = None,
    slogan: str | None = None,
    description: str | None = None,
    logo_url: str | None = None,
    color_primary: str | None = None,
    color_secondary: str | None = None,
    headquarters_address: str | None = None,
    website: str | None = None,
    email: str | None = None,
    phone: str | None = None,
    social_links: dict | None = None,
    leader_name: str | None = None,
    founded_date: str | None = None,
    registration_number: str | None = None,
) -> dict[str, Any] | None:
    """Create a new political party."""
    founded = None
    if founded_date:
        try:
            founded = date.fromisoformat(founded_date)
        except ValueError:
            pass

    result = await conn.fetchrow(
        """
        INSERT INTO political_parties (
            organization_id, name, abbreviation, slogan, description,
            logo_url, color_primary, color_secondary,
            headquarters_address, website, email, phone, social_links,
            leader_name, founded_date, registration_number
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16)
        ON CONFLICT DO NOTHING
        RETURNING *
        """,
        str(organization_id),
        name,
        abbreviation,
        slogan,
        description,
        logo_url,
        color_primary,
        color_secondary,
        headquarters_address,
        website,
        email,
        phone,
        json.dumps(social_links or {}),
        leader_name,
        founded,
        registration_number,
    )
    return _parse_party_row(result)


async def get_party(
    conn: asyncpg.Connection,
    party_id: UUID,
    organization_id: UUID | None = None,
) -> dict[str, Any] | None:
    """Get a political party by ID."""
    query = """
        SELECT * FROM political_parties
        WHERE id = $1 AND deleted = FALSE
    """
    params: list[Any] = [str(party_id)]

    if organization_id:
        query += " AND organization_id = $2"
        params.append(str(organization_id))

    result = await conn.fetchrow(query, *params)
    return _parse_party_row(result)


async def list_parties(
    conn: asyncpg.Connection,
    organization_id: UUID,
    status: str | None = None,
    search: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    """List political parties with filtering."""
    query = """
        SELECT * FROM political_parties
        WHERE organization_id = $1 AND deleted = FALSE
    """
    count_query = """
        SELECT COUNT(*) FROM political_parties
        WHERE organization_id = $1 AND deleted = FALSE
    """
    params: list[Any] = [str(organization_id)]
    param_num = 2

    if status:
        query += f" AND status = ${param_num}"
        count_query += f" AND status = ${param_num}"
        params.append(status)
        param_num += 1

    if search:
        search_term = f"%{search}%"
        query += f" AND (name ILIKE ${param_num} OR abbreviation ILIKE ${param_num})"
        count_query += f" AND (name ILIKE ${param_num} OR abbreviation ILIKE ${param_num})"
        params.append(search_term)
        param_num += 1

    # Get total count
    total = await conn.fetchval(count_query, *params)

    # Add ordering and pagination
    query += " ORDER BY name ASC"
    query += f" LIMIT ${param_num} OFFSET ${param_num + 1}"
    params.extend([limit, offset])

    rows = await conn.fetch(query, *params)
    return [_parse_party_row(row) for row in rows], total or 0


async def update_party(
    conn: asyncpg.Connection,
    party_id: UUID,
    organization_id: UUID,
    **kwargs,
) -> dict[str, Any] | None:
    """Update a political party."""
    updates = []
    params: list[Any] = []
    param_num = 1

    field_mapping = {
        "name": "name",
        "abbreviation": "abbreviation",
        "slogan": "slogan",
        "description": "description",
        "logo_url": "logo_url",
        "color_primary": "color_primary",
        "color_secondary": "color_secondary",
        "headquarters_address": "headquarters_address",
        "website": "website",
        "email": "email",
        "phone": "phone",
        "social_links": "social_links",
        "leader_name": "leader_name",
        "founded_date": "founded_date",
        "registration_number": "registration_number",
        "status": "status",
    }

    for key, column in field_mapping.items():
        if key in kwargs and kwargs[key] is not None:
            value = kwargs[key]

            # Handle special types
            if key == "founded_date":
                try:
                    value = date.fromisoformat(value)
                except ValueError:
                    continue
            elif key == "social_links":
                value = json.dumps(value)

            updates.append(f"{column} = ${param_num}")
            params.append(value)
            param_num += 1

    if not updates:
        return await get_party(conn, party_id, organization_id)

    updates.append("updated_at = CURRENT_TIMESTAMP")
    params.extend([str(party_id), str(organization_id)])

    query = f"""
        UPDATE political_parties
        SET {", ".join(updates)}
        WHERE id = ${param_num} AND organization_id = ${param_num + 1} AND deleted = FALSE
        RETURNING *
    """

    result = await conn.fetchrow(query, *params)
    return _parse_party_row(result)


async def delete_party(
    conn: asyncpg.Connection,
    party_id: UUID,
    organization_id: UUID,
) -> bool:
    """Soft delete a political party."""
    result = await conn.execute(
        """
        UPDATE political_parties
        SET deleted = TRUE, deleted_at = CURRENT_TIMESTAMP, status = 'dissolved'
        WHERE id = $1 AND organization_id = $2 AND deleted = FALSE
        """,
        str(party_id),
        str(organization_id),
    )
    return int(result.split()[-1]) > 0


# ============================================
# PARTY STATS & ANALYTICS
# ============================================


async def get_party_candidates(
    conn: asyncpg.Connection,
    party_id: UUID,
    organization_id: UUID,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    """Get all candidates belonging to a party."""
    query = """
        SELECT cp.*, pp.name as party_name, pp.abbreviation as party_abbreviation
        FROM candidate_profiles cp
        JOIN political_parties pp ON cp.party_id = pp.id
        WHERE cp.party_id = $1 AND pp.organization_id = $2 AND cp.deleted = FALSE
    """
    count_query = """
        SELECT COUNT(*) FROM candidate_profiles cp
        JOIN political_parties pp ON cp.party_id = pp.id
        WHERE cp.party_id = $1 AND pp.organization_id = $2 AND cp.deleted = FALSE
    """
    params: list[Any] = [str(party_id), str(organization_id)]
    param_num = 3

    if status:
        query += f" AND cp.status = ${param_num}"
        count_query += f" AND cp.status = ${param_num}"
        params.append(status)
        param_num += 1

    total = await conn.fetchval(count_query, *params)

    query += " ORDER BY cp.name ASC"
    query += f" LIMIT ${param_num} OFFSET ${param_num + 1}"
    params.extend([limit, offset])

    rows = await conn.fetch(query, *params)

    results = []
    for row in rows:
        data = dict(row)
        # Convert UUIDs
        for field in ("id", "organization_id", "party_id"):
            if data.get(field):
                data[field] = str(data[field])
        # Parse JSONB
        for field in ("policies", "experience", "endorsements", "education", "social_links"):
            if data.get(field) and isinstance(data[field], str):
                data[field] = json.loads(data[field])
        results.append(data)

    return results, total or 0


async def get_party_election_history(
    conn: asyncpg.Connection,
    party_id: UUID,
) -> list[dict[str, Any]]:
    """Get election history for a party."""
    rows = await conn.fetch(
        """
        SELECT * FROM party_election_stats
        WHERE party_id = $1
        ORDER BY election_date DESC
        """,
        str(party_id),
    )

    results = []
    for row in rows:
        results.append({
            "party_id": str(row["party_id"]),
            "party_name": row["party_name"],
            "abbreviation": row["abbreviation"],
            "election_id": str(row["election_id"]),
            "election_title": row["election_title"],
            "election_type": row["election_type"],
            "election_date": row["election_date"].isoformat() if row["election_date"] else None,
            "candidates_fielded": row["candidates_fielded"],
            "seats_won": row["seats_won"],
            "total_votes": row["total_votes"],
            "avg_vote_percentage": float(row["avg_vote_percentage"] or 0),
        })
    return results


async def get_party_stats(
    conn: asyncpg.Connection,
    party_id: UUID,
    organization_id: UUID,
) -> dict[str, Any] | None:
    """Get detailed statistics for a party."""
    party = await get_party(conn, party_id, organization_id)
    if not party:
        return None

    # Get candidate breakdown
    candidate_stats = await conn.fetchrow(
        """
        SELECT
            COUNT(*) as total_candidates,
            COUNT(*) FILTER (WHERE status = 'active') as active_candidates,
            SUM(total_elections) as total_candidate_participations,
            SUM(total_wins) as total_candidate_wins,
            SUM(total_votes_received) as total_votes_received
        FROM candidate_profiles
        WHERE party_id = $1 AND deleted = FALSE
        """,
        str(party_id),
    )

    # Get election type breakdown
    election_breakdown = await conn.fetch(
        """
        SELECT
            election_type,
            COUNT(DISTINCT election_id) as elections,
            SUM(candidates_fielded) as total_candidates,
            SUM(seats_won) as total_wins,
            SUM(total_votes) as total_votes
        FROM party_election_stats
        WHERE party_id = $1
        GROUP BY election_type
        """,
        str(party_id),
    )

    by_type = {}
    for row in election_breakdown:
        by_type[row["election_type"]] = {
            "elections": row["elections"],
            "candidates": row["total_candidates"],
            "wins": row["total_wins"],
            "votes": row["total_votes"],
        }

    return {
        "party": party,
        "candidates": {
            "total": candidate_stats["total_candidates"] if candidate_stats else 0,
            "active": candidate_stats["active_candidates"] if candidate_stats else 0,
        },
        "elections": {
            "total_participations": candidate_stats["total_candidate_participations"] if candidate_stats else 0,
            "total_wins": candidate_stats["total_candidate_wins"] if candidate_stats else 0,
            "total_votes_received": candidate_stats["total_votes_received"] if candidate_stats else 0,
        },
        "by_election_type": by_type,
    }


async def get_parties_leaderboard(
    conn: asyncpg.Connection,
    organization_id: UUID,
    sort_by: str = "total_wins",
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Get leaderboard of parties."""
    sort_columns = {
        "total_wins": "total_wins DESC, total_elections_participated DESC",
        "total_candidates": "total_candidates DESC, total_wins DESC",
        "elections": "total_elections_participated DESC, total_wins DESC",
    }

    order_by = sort_columns.get(sort_by, sort_columns["total_wins"])

    rows = await conn.fetch(
        f"""
        SELECT
            id, name, abbreviation, logo_url, color_primary,
            total_candidates, total_elections_participated, total_wins
        FROM political_parties
        WHERE organization_id = $1 AND deleted = FALSE AND total_elections_participated > 0
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
            "abbreviation": row["abbreviation"],
            "logo_url": row["logo_url"],
            "color_primary": row["color_primary"],
            "total_candidates": row["total_candidates"],
            "total_elections_participated": row["total_elections_participated"],
            "total_wins": row["total_wins"],
        })
    return results


async def update_all_party_stats(conn: asyncpg.Connection) -> bool:
    """Update statistics for all parties."""
    try:
        await conn.execute("SELECT update_party_stats()")
        return True
    except Exception:
        return False
