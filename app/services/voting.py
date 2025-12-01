"""Voting service functions."""

import hashlib
import json
from datetime import datetime
from typing import Any
from uuid import UUID

import asyncpg


# ============================================
# VOTER REGISTRATION & VERIFICATION
# ============================================


def hash_identifier(identifier: str) -> str:
    """Create SHA-256 hash of an identifier for privacy."""
    return hashlib.sha256(identifier.encode()).hexdigest()


async def register_voter(
    conn: asyncpg.Connection,
    election_id: UUID,
    national_id: str | None = None,
    phone: str | None = None,
    user_id: UUID | None = None,
    region: str | None = None,
    age_group: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> dict | None:
    """Register a voter for an election."""
    national_id_hash = hash_identifier(national_id) if national_id else None
    phone_hash = hash_identifier(phone) if phone else None

    result = await conn.fetchrow(
        """
        INSERT INTO voters (
            election_id, national_id_hash, phone_hash, user_id,
            region, age_group, ip_address, user_agent
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        ON CONFLICT DO NOTHING
        RETURNING *
        """,
        str(election_id),
        national_id_hash,
        phone_hash,
        str(user_id) if user_id else None,
        region,
        age_group,
        ip_address,
        user_agent,
    )
    return _parse_voter_row(result) if result else None


async def get_voter(
    conn: asyncpg.Connection,
    election_id: UUID,
    national_id: str | None = None,
    phone: str | None = None,
    user_id: UUID | None = None,
) -> dict | None:
    """Get voter by identifier."""
    if national_id:
        id_hash = hash_identifier(national_id)
        result = await conn.fetchrow(
            """
            SELECT * FROM voters
            WHERE election_id = $1 AND national_id_hash = $2
            """,
            str(election_id),
            id_hash,
        )
    elif phone:
        id_hash = hash_identifier(phone)
        result = await conn.fetchrow(
            """
            SELECT * FROM voters
            WHERE election_id = $1 AND phone_hash = $2
            """,
            str(election_id),
            id_hash,
        )
    elif user_id:
        result = await conn.fetchrow(
            """
            SELECT * FROM voters
            WHERE election_id = $1 AND user_id = $2
            """,
            str(election_id),
            str(user_id),
        )
    else:
        return None

    return _parse_voter_row(result) if result else None


async def verify_voter(
    conn: asyncpg.Connection,
    voter_id: UUID,
    verification_method: str,
) -> dict | None:
    """Mark a voter as verified."""
    result = await conn.fetchrow(
        """
        UPDATE voters
        SET verified_at = CURRENT_TIMESTAMP, verification_method = $1
        WHERE id = $2
        RETURNING *
        """,
        verification_method,
        str(voter_id),
    )
    return _parse_voter_row(result) if result else None


async def has_voted(
    conn: asyncpg.Connection,
    election_id: UUID,
    voter_hash: str,
) -> bool:
    """Check if a voter has already voted."""
    result = await conn.fetchval(
        """
        SELECT has_voted FROM voters
        WHERE election_id = $1 AND (
            national_id_hash = $2 OR phone_hash = $2 OR id::text = $2
        )
        """,
        str(election_id),
        voter_hash,
    )
    return result is True


async def mark_voted(
    conn: asyncpg.Connection,
    voter_id: UUID,
) -> bool:
    """Mark a voter as having voted."""
    result = await conn.execute(
        """
        UPDATE voters
        SET has_voted = TRUE, voted_at = CURRENT_TIMESTAMP
        WHERE id = $1 AND has_voted = FALSE
        """,
        str(voter_id),
    )
    return int(result.split()[-1]) > 0


# ============================================
# VOTE CASTING
# ============================================


async def check_can_vote(
    conn: asyncpg.Connection,
    election_id: UUID,
    voter_hash: str,
) -> tuple[bool, str]:
    """Check if a voter can vote. Returns (can_vote, reason)."""
    # Check election exists and is active
    election = await conn.fetchrow(
        """
        SELECT status, start_date, end_date, verification_level
        FROM elections
        WHERE id = $1 AND deleted = FALSE
        """,
        str(election_id),
    )

    if not election:
        return False, "Election not found"

    if election["status"] != "active":
        return False, f"Election is {election['status']}, not accepting votes"

    now = datetime.now(election["start_date"].tzinfo)
    if now < election["start_date"]:
        return False, "Election has not started yet"

    if now > election["end_date"]:
        return False, "Election has ended"

    # Check if voter has already voted (for non-anonymous elections)
    if election["verification_level"] != "anonymous":
        voted = await has_voted(conn, election_id, voter_hash)
        if voted:
            return False, "You have already voted in this election"

    return True, "OK"


async def cast_vote(
    conn: asyncpg.Connection,
    election_id: UUID,
    voter_hash: str,
    position_id: UUID | None = None,
    candidate_id: UUID | None = None,
    poll_option_id: UUID | None = None,
    region: str | None = None,
    age_group: str | None = None,
    rank: int | None = None,
) -> dict | None:
    """Cast a single vote."""
    result = await conn.fetchrow(
        """
        INSERT INTO votes (
            election_id, position_id, candidate_id, poll_option_id,
            voter_hash, region, age_group, rank
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        ON CONFLICT DO NOTHING
        RETURNING *
        """,
        str(election_id),
        str(position_id) if position_id else None,
        str(candidate_id) if candidate_id else None,
        str(poll_option_id) if poll_option_id else None,
        voter_hash,
        region,
        age_group,
        rank,
    )
    return _parse_vote_row(result)


async def cast_votes_batch(
    conn: asyncpg.Connection,
    election_id: UUID,
    voter_hash: str,
    votes: list[dict],
    region: str | None = None,
    age_group: str | None = None,
) -> list[dict]:
    """Cast multiple votes in a batch (for multi-position elections)."""
    results = []

    for vote in votes:
        result = await cast_vote(
            conn=conn,
            election_id=election_id,
            voter_hash=voter_hash,
            position_id=vote.get("position_id"),
            candidate_id=vote.get("candidate_id"),
            poll_option_id=vote.get("poll_option_id"),
            region=region,
            age_group=age_group,
            rank=vote.get("rank"),
        )
        if result:
            results.append(result)

    return results


async def cast_ranked_votes(
    conn: asyncpg.Connection,
    election_id: UUID,
    voter_hash: str,
    position_id: UUID,
    rankings: list[dict],  # [{"candidate_id": uuid, "rank": 1}, ...]
    region: str | None = None,
    age_group: str | None = None,
) -> list[dict]:
    """Cast ranked-choice votes for a position."""
    results = []

    for ranking in rankings:
        result = await cast_vote(
            conn=conn,
            election_id=election_id,
            voter_hash=voter_hash,
            position_id=position_id,
            candidate_id=ranking["candidate_id"],
            region=region,
            age_group=age_group,
            rank=ranking["rank"],
        )
        if result:
            results.append(result)

    return results


async def get_votes_for_election(
    conn: asyncpg.Connection,
    election_id: UUID,
    position_id: UUID | None = None,
) -> list[dict]:
    """Get all votes for an election (for counting)."""
    query = """
        SELECT v.*, c.name as candidate_name, p.option_text
        FROM votes v
        LEFT JOIN candidates c ON v.candidate_id = c.id
        LEFT JOIN poll_options p ON v.poll_option_id = p.id
        WHERE v.election_id = $1
    """
    params: list[Any] = [str(election_id)]

    if position_id:
        query += " AND v.position_id = $2"
        params.append(str(position_id))

    query += " ORDER BY v.voted_at ASC"

    results = await conn.fetch(query, *params)
    return [_parse_vote_row(row) for row in results]


async def get_vote_count(
    conn: asyncpg.Connection,
    election_id: UUID,
    position_id: UUID | None = None,
    candidate_id: UUID | None = None,
    poll_option_id: UUID | None = None,
) -> int:
    """Get vote count with optional filters."""
    query = "SELECT COUNT(*) FROM votes WHERE election_id = $1"
    params: list[Any] = [str(election_id)]

    if position_id:
        params.append(str(position_id))
        query += f" AND position_id = ${len(params)}"

    if candidate_id:
        params.append(str(candidate_id))
        query += f" AND candidate_id = ${len(params)}"

    if poll_option_id:
        params.append(str(poll_option_id))
        query += f" AND poll_option_id = ${len(params)}"

    result = await conn.fetchval(query, *params)
    return result or 0


async def get_unique_voter_count(
    conn: asyncpg.Connection,
    election_id: UUID,
) -> int:
    """Get count of unique voters."""
    result = await conn.fetchval(
        """
        SELECT COUNT(DISTINCT voter_hash)
        FROM votes
        WHERE election_id = $1
        """,
        str(election_id),
    )
    return result or 0


# ============================================
# VOTE RECEIPT
# ============================================


async def generate_vote_receipt(
    conn: asyncpg.Connection,
    election_id: UUID,
    voter_hash: str,
) -> dict | None:
    """Generate a vote receipt for a voter."""
    votes = await conn.fetch(
        """
        SELECT v.id, v.voted_at, v.position_id,
               ep.title as position_title,
               c.name as candidate_name, c.party,
               po.option_text
        FROM votes v
        LEFT JOIN election_positions ep ON v.position_id = ep.id
        LEFT JOIN candidates c ON v.candidate_id = c.id
        LEFT JOIN poll_options po ON v.poll_option_id = po.id
        WHERE v.election_id = $1 AND v.voter_hash = $2
        ORDER BY v.voted_at ASC
        """,
        str(election_id),
        voter_hash,
    )

    if not votes:
        return None

    election = await conn.fetchrow(
        """
        SELECT id, title, election_type
        FROM elections
        WHERE id = $1
        """,
        str(election_id),
    )

    return {
        "election_id": str(election["id"]),
        "election_title": election["title"],
        "election_type": election["election_type"],
        "voter_hash": voter_hash[:16] + "...",  # Partial hash for reference
        "votes_cast": len(votes),
        "voted_at": votes[0]["voted_at"].isoformat() if votes else None,
        "confirmation_code": hash_identifier(f"{election_id}-{voter_hash}")[:12].upper(),
    }


# ============================================
# VOTE VALIDATION
# ============================================


async def validate_vote_selections(
    conn: asyncpg.Connection,
    election_id: UUID,
    votes: list[dict],
) -> tuple[bool, list[str]]:
    """Validate vote selections against election rules."""
    errors: list[str] = []

    election = await conn.fetchrow(
        """
        SELECT voting_method, election_type
        FROM elections
        WHERE id = $1 AND deleted = FALSE
        """,
        str(election_id),
    )

    if not election:
        return False, ["Election not found"]

    voting_method = election["voting_method"]
    election_type = election["election_type"]

    # For candidate-based elections
    if election_type in ("election", "referendum"):
        # Get all positions
        positions = await conn.fetch(
            """
            SELECT id, max_selections
            FROM election_positions
            WHERE election_id = $1
            """,
            str(election_id),
        )
        position_limits = {str(p["id"]): p["max_selections"] for p in positions}

        # Group votes by position
        votes_per_position: dict[str, list] = {}
        for vote in votes:
            pos_id = str(vote.get("position_id", ""))
            if pos_id not in votes_per_position:
                votes_per_position[pos_id] = []
            votes_per_position[pos_id].append(vote)

        # Validate each position
        for pos_id, pos_votes in votes_per_position.items():
            if pos_id not in position_limits:
                errors.append(f"Invalid position: {pos_id}")
                continue

            max_sel = position_limits[pos_id]

            if voting_method == "single_choice" and len(pos_votes) > 1:
                errors.append(f"Single choice only: position {pos_id}")

            if len(pos_votes) > max_sel:
                errors.append(
                    f"Too many selections for position {pos_id}: max {max_sel}"
                )

            # Validate candidates exist
            for vote in pos_votes:
                candidate_id = vote.get("candidate_id")
                if candidate_id:
                    exists = await conn.fetchval(
                        """
                        SELECT 1 FROM candidates
                        WHERE id = $1 AND position_id = $2
                        """,
                        str(candidate_id),
                        pos_id,
                    )
                    if not exists:
                        errors.append(f"Invalid candidate: {candidate_id}")

    # For poll-based elections
    elif election_type in ("poll", "survey"):
        for vote in votes:
            option_id = vote.get("poll_option_id")
            if option_id:
                exists = await conn.fetchval(
                    """
                    SELECT 1 FROM poll_options
                    WHERE id = $1 AND election_id = $2
                    """,
                    str(option_id),
                    str(election_id),
                )
                if not exists:
                    errors.append(f"Invalid poll option: {option_id}")

    return len(errors) == 0, errors


# ============================================
# HELPER FUNCTIONS
# ============================================


def _parse_voter_row(row: asyncpg.Record | None) -> dict | None:
    """Parse a voter row into a dict."""
    if not row:
        return None

    result = dict(row)

    # Convert UUID fields to strings for JSON serialization
    uuid_fields = ("id", "election_id", "user_id")
    for field in uuid_fields:
        if result.get(field) is not None:
            result[field] = str(result[field])

    # Convert IP to string
    if result.get("ip_address"):
        result["ip_address"] = str(result["ip_address"])

    return result


def _parse_vote_row(row: asyncpg.Record | None) -> dict | None:
    """Parse a vote row into a dict."""
    if not row:
        return None

    result = dict(row)

    # Convert UUID fields to strings for JSON serialization
    uuid_fields = ("id", "election_id", "position_id", "candidate_id", "poll_option_id")
    for field in uuid_fields:
        if result.get(field) is not None:
            result[field] = str(result[field])

    return result


def generate_voter_hash(
    election_id: UUID,
    national_id: str | None = None,
    phone: str | None = None,
    user_id: UUID | None = None,
) -> str:
    """Generate a consistent voter hash for duplicate prevention."""
    identifier = None
    if national_id:
        identifier = f"national_id:{national_id}"
    elif phone:
        identifier = f"phone:{phone}"
    elif user_id:
        identifier = f"user_id:{user_id}"
    else:
        # For anonymous voting, use a random unique identifier
        import uuid

        identifier = f"anonymous:{uuid.uuid4()}"

    return hash_identifier(f"{election_id}:{identifier}")
