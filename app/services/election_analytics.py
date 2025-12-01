"""Election analytics service functions."""

import json
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

import asyncpg


# ============================================
# RESULTS CALCULATION
# ============================================


async def calculate_results(
    conn: asyncpg.Connection,
    election_id: UUID,
    position_id: UUID | None = None,
) -> dict:
    """Calculate current election results."""
    election = await conn.fetchrow(
        """
        SELECT id, title, election_type, voting_method, status,
               results_visibility, show_voter_count
        FROM elections
        WHERE id = $1 AND deleted = FALSE
        """,
        str(election_id),
    )

    if not election:
        return {"error": "Election not found"}

    election_type = election["election_type"]
    voting_method = election["voting_method"]

    # Get total votes
    total_votes = await conn.fetchval(
        """
        SELECT COUNT(DISTINCT voter_hash)
        FROM votes
        WHERE election_id = $1
        """,
        str(election_id),
    )

    results: dict[str, Any] = {
        "election_id": str(election_id),
        "election_title": election["title"],
        "election_type": election_type,
        "voting_method": voting_method,
        "status": election["status"],
        "total_voters": total_votes,
    }

    if election_type in ("election", "referendum"):
        # Get results by position
        positions = await _calculate_position_results(
            conn, election_id, voting_method, position_id
        )
        results["positions"] = positions
    else:
        # Get poll/survey results
        options = await _calculate_poll_results(conn, election_id)
        results["options"] = options

    return results


async def _calculate_position_results(
    conn: asyncpg.Connection,
    election_id: UUID,
    voting_method: str,
    position_id: UUID | None = None,
) -> list[dict]:
    """Calculate results for election positions."""
    query = """
        SELECT p.id, p.title, p.max_selections
        FROM election_positions p
        WHERE p.election_id = $1
    """
    params: list[Any] = [str(election_id)]

    if position_id:
        query += " AND p.id = $2"
        params.append(str(position_id))

    query += " ORDER BY p.display_order ASC"

    positions = await conn.fetch(query, *params)
    results = []

    for position in positions:
        pos_id = str(position["id"])

        if voting_method == "ranked_choice":
            candidates = await _calculate_ranked_choice_results(conn, election_id, pos_id)
        else:
            candidates = await _calculate_simple_results(conn, election_id, pos_id)

        # Get total votes for this position
        total_position_votes = await conn.fetchval(
            """
            SELECT COUNT(DISTINCT voter_hash)
            FROM votes
            WHERE election_id = $1 AND position_id = $2
            """,
            str(election_id),
            pos_id,
        )

        results.append({
            "position_id": pos_id,
            "title": position["title"],
            "max_selections": position["max_selections"],
            "total_votes": total_position_votes,
            "candidates": candidates,
        })

    return results


async def _calculate_simple_results(
    conn: asyncpg.Connection,
    election_id: UUID,
    position_id: str,
) -> list[dict]:
    """Calculate simple (single/multi choice) results."""
    results = await conn.fetch(
        """
        SELECT
            c.id as candidate_id,
            c.name,
            c.party,
            c.photo_url,
            COUNT(v.id) as vote_count
        FROM candidates c
        LEFT JOIN votes v ON c.id = v.candidate_id
            AND v.election_id = $1
            AND v.position_id = $2
        WHERE c.position_id = $2
        GROUP BY c.id, c.name, c.party, c.photo_url
        ORDER BY vote_count DESC, c.display_order ASC
        """,
        str(election_id),
        position_id,
    )

    total_votes = sum(r["vote_count"] for r in results)
    candidates = []

    for i, row in enumerate(results):
        percentage = (row["vote_count"] / total_votes * 100) if total_votes > 0 else 0
        candidates.append({
            "candidate_id": str(row["candidate_id"]),
            "name": row["name"],
            "party": row["party"],
            "photo_url": row["photo_url"],
            "votes": row["vote_count"],
            "percentage": round(percentage, 2),
            "rank": i + 1,
        })

    return candidates


async def _calculate_ranked_choice_results(
    conn: asyncpg.Connection,
    election_id: UUID,
    position_id: str,
) -> list[dict]:
    """Calculate ranked-choice (instant runoff) results."""
    # Get all votes with rankings
    votes = await conn.fetch(
        """
        SELECT voter_hash, candidate_id, rank
        FROM votes
        WHERE election_id = $1 AND position_id = $2
        ORDER BY voter_hash, rank ASC
        """,
        str(election_id),
        position_id,
    )

    # Get candidates
    candidates = await conn.fetch(
        """
        SELECT id, name, party, photo_url
        FROM candidates
        WHERE position_id = $1
        ORDER BY display_order ASC
        """,
        position_id,
    )

    candidate_map = {str(c["id"]): dict(c) for c in candidates}

    # Group votes by voter
    ballots: dict[str, list] = {}
    for vote in votes:
        voter = vote["voter_hash"]
        if voter not in ballots:
            ballots[voter] = []
        ballots[voter].append(str(vote["candidate_id"]))

    # Run instant-runoff tabulation
    active_candidates = set(candidate_map.keys())
    rounds = []
    eliminated = []

    while len(active_candidates) > 1:
        # Count first-choice votes
        vote_counts: dict[str, int] = {c: 0 for c in active_candidates}

        for ballot in ballots.values():
            # Find first active candidate on ballot
            for candidate_id in ballot:
                if candidate_id in active_candidates:
                    vote_counts[candidate_id] += 1
                    break

        total = sum(vote_counts.values())

        round_results = {
            "round": len(rounds) + 1,
            "candidates": [],
        }

        for cid, count in sorted(vote_counts.items(), key=lambda x: -x[1]):
            percentage = (count / total * 100) if total > 0 else 0
            round_results["candidates"].append({
                "candidate_id": cid,
                "name": candidate_map[cid]["name"],
                "votes": count,
                "percentage": round(percentage, 2),
            })

            # Check for majority winner
            if percentage > 50:
                rounds.append(round_results)
                # We have a winner
                final_results = []
                for i, candidate in enumerate(round_results["candidates"]):
                    final_results.append({
                        "candidate_id": candidate["candidate_id"],
                        "name": candidate_map[candidate["candidate_id"]]["name"],
                        "party": candidate_map[candidate["candidate_id"]]["party"],
                        "photo_url": candidate_map[candidate["candidate_id"]]["photo_url"],
                        "votes": candidate["votes"],
                        "percentage": candidate["percentage"],
                        "rank": i + 1,
                        "rounds": rounds,
                    })
                return final_results

        rounds.append(round_results)

        # Eliminate candidate with fewest votes
        min_votes = min(vote_counts.values())
        for cid, count in vote_counts.items():
            if count == min_votes:
                active_candidates.remove(cid)
                eliminated.append(cid)
                break

    # Final results (remaining candidate wins)
    final_results = []
    remaining = list(active_candidates)[0] if active_candidates else None

    for i, cid in enumerate([remaining] + eliminated[::-1] if remaining else eliminated[::-1]):
        if cid:
            final_results.append({
                "candidate_id": cid,
                "name": candidate_map[cid]["name"],
                "party": candidate_map[cid]["party"],
                "photo_url": candidate_map[cid]["photo_url"],
                "votes": 0,  # Would need recalculation
                "percentage": 0,
                "rank": i + 1,
                "rounds": rounds,
            })

    return final_results


async def _calculate_poll_results(
    conn: asyncpg.Connection,
    election_id: UUID,
) -> list[dict]:
    """Calculate poll/survey results."""
    results = await conn.fetch(
        """
        SELECT
            po.id as option_id,
            po.option_text,
            po.description,
            COUNT(v.id) as vote_count
        FROM poll_options po
        LEFT JOIN votes v ON po.id = v.poll_option_id
            AND v.election_id = $1
        WHERE po.election_id = $1
        GROUP BY po.id, po.option_text, po.description
        ORDER BY vote_count DESC, po.display_order ASC
        """,
        str(election_id),
    )

    total_votes = sum(r["vote_count"] for r in results)
    options = []

    for i, row in enumerate(results):
        percentage = (row["vote_count"] / total_votes * 100) if total_votes > 0 else 0
        options.append({
            "option_id": str(row["option_id"]),
            "option_text": row["option_text"],
            "description": row["description"],
            "votes": row["vote_count"],
            "percentage": round(percentage, 2),
            "rank": i + 1,
        })

    return options


# ============================================
# LIVE RESULTS
# ============================================


async def get_live_results(
    conn: asyncpg.Connection,
    election_id: UUID,
) -> dict | None:
    """Get live results (check visibility settings first)."""
    election = await conn.fetchrow(
        """
        SELECT results_visibility, status
        FROM elections
        WHERE id = $1 AND deleted = FALSE
        """,
        str(election_id),
    )

    if not election:
        return None

    # Check if results should be visible
    if election["results_visibility"] == "after_close" and election["status"] != "closed":
        return {
            "election_id": str(election_id),
            "status": election["status"],
            "results_hidden": True,
            "message": "Results will be available after the election closes",
        }

    return await calculate_results(conn, election_id)


# ============================================
# DEMOGRAPHIC ANALYTICS
# ============================================


async def get_demographic_breakdown(
    conn: asyncpg.Connection,
    election_id: UUID,
) -> dict:
    """Get voting breakdown by demographics."""
    # By region
    regional = await conn.fetch(
        """
        SELECT region, COUNT(*) as vote_count
        FROM votes
        WHERE election_id = $1 AND region IS NOT NULL
        GROUP BY region
        ORDER BY vote_count DESC
        """,
        str(election_id),
    )

    # By age group
    age_groups = await conn.fetch(
        """
        SELECT age_group, COUNT(*) as vote_count
        FROM votes
        WHERE election_id = $1 AND age_group IS NOT NULL
        GROUP BY age_group
        ORDER BY age_group ASC
        """,
        str(election_id),
    )

    # Votes by hour
    hourly = await conn.fetch(
        """
        SELECT
            DATE_TRUNC('hour', voted_at) as hour,
            COUNT(*) as vote_count
        FROM votes
        WHERE election_id = $1
        GROUP BY DATE_TRUNC('hour', voted_at)
        ORDER BY hour ASC
        """,
        str(election_id),
    )

    return {
        "election_id": str(election_id),
        "by_region": [
            {"region": r["region"], "votes": r["vote_count"]}
            for r in regional
        ],
        "by_age_group": [
            {"age_group": a["age_group"], "votes": a["vote_count"]}
            for a in age_groups
        ],
        "by_hour": [
            {"hour": h["hour"].isoformat(), "votes": h["vote_count"]}
            for h in hourly
        ],
    }


async def get_regional_results(
    conn: asyncpg.Connection,
    election_id: UUID,
    position_id: UUID | None = None,
) -> dict:
    """Get results broken down by region."""
    query = """
        SELECT
            v.region,
            c.id as candidate_id,
            c.name as candidate_name,
            COUNT(*) as vote_count
        FROM votes v
        JOIN candidates c ON v.candidate_id = c.id
        WHERE v.election_id = $1 AND v.region IS NOT NULL
    """
    params: list[Any] = [str(election_id)]

    if position_id:
        query += " AND v.position_id = $2"
        params.append(str(position_id))

    query += """
        GROUP BY v.region, c.id, c.name
        ORDER BY v.region, vote_count DESC
    """

    results = await conn.fetch(query, *params)

    # Group by region
    by_region: dict[str, list] = {}
    for row in results:
        region = row["region"]
        if region not in by_region:
            by_region[region] = []
        by_region[region].append({
            "candidate_id": str(row["candidate_id"]),
            "candidate_name": row["candidate_name"],
            "votes": row["vote_count"],
        })

    return {
        "election_id": str(election_id),
        "regions": [
            {"region": region, "candidates": candidates}
            for region, candidates in by_region.items()
        ],
    }


# ============================================
# VOTING TRENDS
# ============================================


async def get_voting_trends(
    conn: asyncpg.Connection,
    election_id: UUID,
    granularity: str = "hour",  # hour, day, minute
) -> dict:
    """Get voting trends over time."""
    trunc_map = {
        "minute": "minute",
        "hour": "hour",
        "day": "day",
    }
    trunc = trunc_map.get(granularity, "hour")

    # Overall trend
    overall = await conn.fetch(
        f"""
        SELECT
            DATE_TRUNC('{trunc}', voted_at) as period,
            COUNT(*) as votes,
            COUNT(DISTINCT voter_hash) as unique_voters
        FROM votes
        WHERE election_id = $1
        GROUP BY DATE_TRUNC('{trunc}', voted_at)
        ORDER BY period ASC
        """,
        str(election_id),
    )

    # Cumulative
    cumulative = []
    running_total = 0
    for row in overall:
        running_total += row["votes"]
        cumulative.append({
            "period": row["period"].isoformat(),
            "votes": row["votes"],
            "unique_voters": row["unique_voters"],
            "cumulative_votes": running_total,
        })

    return {
        "election_id": str(election_id),
        "granularity": granularity,
        "trend": cumulative,
    }


# ============================================
# TURNOUT STATISTICS
# ============================================


async def get_turnout_stats(
    conn: asyncpg.Connection,
    election_id: UUID,
) -> dict:
    """Get voter turnout statistics."""
    # Get registered voters count
    registered = await conn.fetchval(
        """
        SELECT COUNT(*) FROM voters
        WHERE election_id = $1
        """,
        str(election_id),
    )

    # Get actual voters count
    voted = await conn.fetchval(
        """
        SELECT COUNT(*) FROM voters
        WHERE election_id = $1 AND has_voted = TRUE
        """,
        str(election_id),
    )

    # Get unique voters from votes table
    unique_voters = await conn.fetchval(
        """
        SELECT COUNT(DISTINCT voter_hash)
        FROM votes
        WHERE election_id = $1
        """,
        str(election_id),
    )

    # Turnout by region
    regional_turnout = await conn.fetch(
        """
        SELECT
            region,
            COUNT(*) FILTER (WHERE has_voted = TRUE) as voted,
            COUNT(*) as registered
        FROM voters
        WHERE election_id = $1 AND region IS NOT NULL
        GROUP BY region
        ORDER BY region
        """,
        str(election_id),
    )

    turnout_rate = (voted / registered * 100) if registered > 0 else 0

    return {
        "election_id": str(election_id),
        "registered_voters": registered,
        "votes_cast": voted,
        "unique_voters": unique_voters,
        "turnout_rate": round(turnout_rate, 2),
        "by_region": [
            {
                "region": r["region"],
                "registered": r["registered"],
                "voted": r["voted"],
                "turnout_rate": round(
                    (r["voted"] / r["registered"] * 100) if r["registered"] > 0 else 0, 2
                ),
            }
            for r in regional_turnout
        ],
    }


# ============================================
# PREDICTIONS
# ============================================


async def calculate_predictions(
    conn: asyncpg.Connection,
    election_id: UUID,
) -> dict:
    """Calculate predictions based on current voting patterns."""
    election = await conn.fetchrow(
        """
        SELECT status, start_date, end_date
        FROM elections
        WHERE id = $1 AND deleted = FALSE
        """,
        str(election_id),
    )

    if not election or election["status"] != "active":
        return {"error": "Election must be active for predictions"}

    # Calculate time progress
    now = datetime.now(election["start_date"].tzinfo)
    total_duration = (election["end_date"] - election["start_date"]).total_seconds()
    elapsed = (now - election["start_date"]).total_seconds()
    time_progress = min(elapsed / total_duration, 1.0) if total_duration > 0 else 0

    # Get current results
    results = await calculate_results(conn, election_id)

    # Get voting velocity (votes per hour in last hour)
    velocity = await conn.fetchval(
        """
        SELECT COUNT(*) / GREATEST(EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - MIN(voted_at))) / 3600, 1)
        FROM votes
        WHERE election_id = $1 AND voted_at >= CURRENT_TIMESTAMP - INTERVAL '1 hour'
        """,
        str(election_id),
    )

    # Estimate final turnout
    current_votes = results.get("total_voters", 0)
    remaining_hours = max((election["end_date"] - now).total_seconds() / 3600, 0)
    projected_additional = int(velocity * remaining_hours) if velocity else 0
    projected_total = current_votes + projected_additional

    predictions = {
        "election_id": str(election_id),
        "time_progress": round(time_progress * 100, 1),
        "current_votes": current_votes,
        "voting_velocity": round(velocity, 1) if velocity else 0,
        "projected_total_votes": projected_total,
        "remaining_hours": round(remaining_hours, 1),
        "confidence": "low" if time_progress < 0.3 else ("medium" if time_progress < 0.7 else "high"),
    }

    # Project winners (if positions exist)
    if "positions" in results:
        projected_winners = []
        for position in results["positions"]:
            if position["candidates"]:
                leader = position["candidates"][0]
                projected_winners.append({
                    "position_id": position["position_id"],
                    "position_title": position["title"],
                    "projected_winner": leader["name"],
                    "current_lead": leader["percentage"],
                })
        predictions["projected_winners"] = projected_winners

    return predictions


# ============================================
# CANDIDATE COMPARISON
# ============================================


async def compare_candidates_analytics(
    conn: asyncpg.Connection,
    election_id: UUID,
    candidate_ids: list[UUID],
) -> dict:
    """Compare candidates with detailed analytics."""
    # Get candidate details
    placeholders = ", ".join(f"${i+2}" for i in range(len(candidate_ids)))
    candidates = await conn.fetch(
        f"""
        SELECT c.*, p.title as position_title
        FROM candidates c
        JOIN election_positions p ON c.position_id = p.id
        WHERE p.election_id = $1 AND c.id IN ({placeholders})
        """,
        str(election_id),
        *[str(cid) for cid in candidate_ids],
    )

    comparisons = []
    for candidate in candidates:
        # Get vote stats for this candidate
        vote_stats = await conn.fetchrow(
            """
            SELECT
                COUNT(*) as total_votes,
                COUNT(DISTINCT region) as regions_present
            FROM votes
            WHERE election_id = $1 AND candidate_id = $2
            """,
            str(election_id),
            str(candidate["id"]),
        )

        # Get regional breakdown
        regional = await conn.fetch(
            """
            SELECT region, COUNT(*) as votes
            FROM votes
            WHERE election_id = $1 AND candidate_id = $2 AND region IS NOT NULL
            GROUP BY region
            ORDER BY votes DESC
            LIMIT 5
            """,
            str(election_id),
            str(candidate["id"]),
        )

        comparisons.append({
            "candidate_id": str(candidate["id"]),
            "name": candidate["name"],
            "party": candidate["party"],
            "position": candidate["position_title"],
            "bio": candidate["bio"],
            "policies": candidate["policies"] if isinstance(candidate["policies"], dict) else json.loads(candidate["policies"] or "{}"),
            "experience": candidate["experience"] if isinstance(candidate["experience"], dict) else json.loads(candidate["experience"] or "{}"),
            "endorsements": candidate["endorsements"] if isinstance(candidate["endorsements"], list) else json.loads(candidate["endorsements"] or "[]"),
            "vote_stats": {
                "total_votes": vote_stats["total_votes"] if vote_stats else 0,
                "regions_present": vote_stats["regions_present"] if vote_stats else 0,
            },
            "top_regions": [
                {"region": r["region"], "votes": r["votes"]}
                for r in regional
            ],
        })

    return {
        "election_id": str(election_id),
        "candidates": comparisons,
    }


# ============================================
# DASHBOARD STATS
# ============================================


async def get_elections_dashboard(
    conn: asyncpg.Connection,
    organization_id: UUID | None = None,
) -> dict:
    """Get dashboard overview of all elections."""
    base_query = """
        SELECT
            status,
            COUNT(*) as count
        FROM elections
        WHERE deleted = FALSE
    """
    params: list[Any] = []

    if organization_id:
        params.append(str(organization_id))
        base_query += f" AND organization_id = ${len(params)}"

    base_query += " GROUP BY status"

    status_counts = await conn.fetch(base_query, *params)

    # Get active elections
    active_query = """
        SELECT e.id, e.title, e.election_type, e.start_date, e.end_date,
               COUNT(DISTINCT v.voter_hash) as votes
        FROM elections e
        LEFT JOIN votes v ON e.id = v.election_id
        WHERE e.status = 'active' AND e.deleted = FALSE
    """
    if organization_id:
        active_query += f" AND e.organization_id = $1"

    active_query += """
        GROUP BY e.id, e.title, e.election_type, e.start_date, e.end_date
        ORDER BY e.end_date ASC
        LIMIT 5
    """

    active_elections = await conn.fetch(
        active_query,
        *([str(organization_id)] if organization_id else []),
    )

    # Get upcoming elections
    upcoming_query = """
        SELECT id, title, election_type, start_date
        FROM elections
        WHERE status = 'scheduled' AND deleted = FALSE
    """
    if organization_id:
        upcoming_query += f" AND organization_id = $1"

    upcoming_query += """
        ORDER BY start_date ASC
        LIMIT 5
    """

    upcoming = await conn.fetch(
        upcoming_query,
        *([str(organization_id)] if organization_id else []),
    )

    # Get recent closed elections
    closed_query = """
        SELECT e.id, e.title, e.end_date,
               COUNT(DISTINCT v.voter_hash) as total_votes
        FROM elections e
        LEFT JOIN votes v ON e.id = v.election_id
        WHERE e.status = 'closed' AND e.deleted = FALSE
    """
    if organization_id:
        closed_query += f" AND e.organization_id = $1"

    closed_query += """
        GROUP BY e.id, e.title, e.end_date
        ORDER BY e.end_date DESC
        LIMIT 5
    """

    recent_closed = await conn.fetch(
        closed_query,
        *([str(organization_id)] if organization_id else []),
    )

    return {
        "status_summary": {s["status"]: s["count"] for s in status_counts},
        "active_elections": [
            {
                "id": str(e["id"]),
                "title": e["title"],
                "type": e["election_type"],
                "end_date": e["end_date"].isoformat(),
                "votes": e["votes"],
            }
            for e in active_elections
        ],
        "upcoming_elections": [
            {
                "id": str(e["id"]),
                "title": e["title"],
                "type": e["election_type"],
                "start_date": e["start_date"].isoformat(),
            }
            for e in upcoming
        ],
        "recent_closed": [
            {
                "id": str(e["id"]),
                "title": e["title"],
                "end_date": e["end_date"].isoformat(),
                "total_votes": e["total_votes"],
            }
            for e in recent_closed
        ],
    }


# ============================================
# RESULTS FINALIZATION
# ============================================


async def finalize_results(
    conn: asyncpg.Connection,
    election_id: UUID,
    user_id: UUID,
) -> dict | None:
    """Finalize and cache election results."""
    election = await conn.fetchrow(
        """
        SELECT status, election_type
        FROM elections
        WHERE id = $1 AND deleted = FALSE
        """,
        str(election_id),
    )

    if not election or election["status"] != "closed":
        return None

    # Calculate final results
    results = await calculate_results(conn, election_id)

    # Store results in election_results table
    if election["election_type"] in ("election", "referendum"):
        for position in results.get("positions", []):
            for candidate in position.get("candidates", []):
                await conn.execute(
                    """
                    INSERT INTO election_results (
                        election_id, position_id, candidate_id,
                        vote_count, percentage, is_final, finalized_at, finalized_by
                    )
                    VALUES ($1, $2, $3, $4, $5, TRUE, CURRENT_TIMESTAMP, $6)
                    ON CONFLICT (election_id, position_id, candidate_id)
                    DO UPDATE SET
                        vote_count = EXCLUDED.vote_count,
                        percentage = EXCLUDED.percentage,
                        is_final = TRUE,
                        finalized_at = CURRENT_TIMESTAMP,
                        finalized_by = EXCLUDED.finalized_by
                    """,
                    str(election_id),
                    position["position_id"],
                    candidate["candidate_id"],
                    candidate["votes"],
                    candidate["percentage"],
                    str(user_id),
                )
    else:
        for option in results.get("options", []):
            await conn.execute(
                """
                INSERT INTO election_results (
                    election_id, poll_option_id,
                    vote_count, percentage, is_final, finalized_at, finalized_by
                )
                VALUES ($1, $2, $3, $4, TRUE, CURRENT_TIMESTAMP, $5)
                ON CONFLICT (election_id, poll_option_id)
                DO UPDATE SET
                    vote_count = EXCLUDED.vote_count,
                    percentage = EXCLUDED.percentage,
                    is_final = TRUE,
                    finalized_at = CURRENT_TIMESTAMP,
                    finalized_by = EXCLUDED.finalized_by
                """,
                str(election_id),
                option["option_id"],
                option["votes"],
                option["percentage"],
                str(user_id),
            )

    results["finalized"] = True
    results["finalized_by"] = str(user_id)

    return results


async def get_finalized_results(
    conn: asyncpg.Connection,
    election_id: UUID,
) -> dict | None:
    """Get finalized results from cache."""
    results = await conn.fetch(
        """
        SELECT er.*, c.name as candidate_name, c.party,
               p.title as position_title, po.option_text
        FROM election_results er
        LEFT JOIN candidates c ON er.candidate_id = c.id
        LEFT JOIN election_positions p ON er.position_id = p.id
        LEFT JOIN poll_options po ON er.poll_option_id = po.id
        WHERE er.election_id = $1 AND er.is_final = TRUE
        ORDER BY er.vote_count DESC
        """,
        str(election_id),
    )

    if not results:
        return None

    election = await conn.fetchrow(
        """
        SELECT title, election_type
        FROM elections
        WHERE id = $1
        """,
        str(election_id),
    )

    return {
        "election_id": str(election_id),
        "election_title": election["title"],
        "finalized": True,
        "results": [
            {
                "candidate_name": r["candidate_name"],
                "party": r["party"],
                "option_text": r["option_text"],
                "position_title": r["position_title"],
                "votes": r["vote_count"],
                "percentage": float(r["percentage"]) if r["percentage"] else 0,
            }
            for r in results
        ],
    }
