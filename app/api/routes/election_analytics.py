"""Election analytics API routes."""

from typing import Annotated
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.responses import success_response
from app.services import elections as election_service
from app.services import election_analytics as analytics_service
from app.services.permissions import require_permission

router = APIRouter(prefix="/elections", tags=["Election Analytics"])


# ============================================
# RESULTS ENDPOINTS
# ============================================


@router.get("/{election_id}/results")
async def get_results(
    election_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    position_id: UUID | None = Query(None),
):
    """
    Get election results.

    Results visibility is determined by the election's `results_visibility` setting:
    - `real_time`: Results are always visible
    - `after_close`: Results are only visible after the election closes
    """
    await require_permission(conn, UUID(current_user["id"]), "election_analytics", "view")

    results = await analytics_service.get_live_results(conn, election_id)

    if not results:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Election not found",
        )

    return success_response(data=results)


@router.get("/{election_id}/results/final")
async def get_finalized_results(
    election_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Get finalized (cached) election results."""
    await require_permission(conn, UUID(current_user["id"]), "election_analytics", "view")

    results = await analytics_service.get_finalized_results(conn, election_id)

    if not results:
        # Fall back to calculated results
        results = await analytics_service.calculate_results(conn, election_id)

    return success_response(data=results)


@router.post("/{election_id}/results/finalize")
async def finalize_results(
    election_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """
    Finalize and cache election results.

    Requires `election_analytics.finalize` permission.
    Can only be done for closed elections.
    """
    await require_permission(conn, UUID(current_user["id"]), "election_analytics", "finalize")

    election = await election_service.get_election_by_id(conn, election_id)
    if not election:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Election not found",
        )

    if election["status"] != "closed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only finalize results for closed elections",
        )

    results = await analytics_service.finalize_results(
        conn, election_id, UUID(current_user["id"])
    )

    if not results:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to finalize results",
        )

    # Log action
    await election_service.log_election_action(
        conn,
        election_id,
        "results_finalized",
        UUID(current_user["id"]),
    )

    return success_response(data=results, message="Results finalized successfully")


# ============================================
# ANALYTICS ENDPOINTS
# ============================================


@router.get("/{election_id}/analytics")
async def get_election_analytics(
    election_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """
    Get comprehensive election analytics.

    Includes results, demographics, trends, and turnout data.
    """
    await require_permission(conn, UUID(current_user["id"]), "election_analytics", "view")

    election = await election_service.get_election_by_id(conn, election_id)
    if not election:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Election not found",
        )

    # Gather all analytics data
    results = await analytics_service.calculate_results(conn, election_id)
    demographics = await analytics_service.get_demographic_breakdown(conn, election_id)
    trends = await analytics_service.get_voting_trends(conn, election_id)
    turnout = await analytics_service.get_turnout_stats(conn, election_id)

    analytics = {
        "election": {
            "id": str(election_id),
            "title": election["title"],
            "type": election["election_type"],
            "status": election["status"],
            "voting_method": election["voting_method"],
        },
        "results": results,
        "demographics": demographics,
        "trends": trends,
        "turnout": turnout,
    }

    return success_response(data=analytics)


@router.get("/{election_id}/analytics/demographics")
async def get_demographic_breakdown(
    election_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Get voting breakdown by demographics (region, age group)."""
    await require_permission(conn, UUID(current_user["id"]), "election_analytics", "view")

    demographics = await analytics_service.get_demographic_breakdown(conn, election_id)

    return success_response(data=demographics)


@router.get("/{election_id}/analytics/regional")
async def get_regional_results(
    election_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    position_id: UUID | None = Query(None),
):
    """Get results broken down by region."""
    await require_permission(conn, UUID(current_user["id"]), "election_analytics", "view")

    regional = await analytics_service.get_regional_results(
        conn, election_id, position_id
    )

    return success_response(data=regional)


@router.get("/{election_id}/analytics/trends")
async def get_voting_trends(
    election_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    granularity: str = Query("hour", pattern="^(minute|hour|day)$"),
):
    """Get voting trends over time."""
    await require_permission(conn, UUID(current_user["id"]), "election_analytics", "view")

    trends = await analytics_service.get_voting_trends(
        conn, election_id, granularity=granularity
    )

    return success_response(data=trends)


@router.get("/{election_id}/analytics/turnout")
async def get_turnout_stats(
    election_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Get voter turnout statistics."""
    await require_permission(conn, UUID(current_user["id"]), "election_analytics", "view")

    turnout = await analytics_service.get_turnout_stats(conn, election_id)

    return success_response(data=turnout)


@router.get("/{election_id}/analytics/predictions")
async def get_predictions(
    election_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """
    Get predictions based on current voting patterns.

    Only available for active elections.
    """
    await require_permission(conn, UUID(current_user["id"]), "election_analytics", "view")

    predictions = await analytics_service.calculate_predictions(conn, election_id)

    if "error" in predictions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=predictions["error"],
        )

    return success_response(data=predictions)


@router.get("/{election_id}/analytics/comparison")
async def get_candidate_comparison(
    election_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    candidate_ids: str = Query(..., description="Comma-separated candidate UUIDs"),
):
    """
    Compare candidates with detailed analytics.

    Includes policies, experience, vote stats, and regional performance.
    """
    await require_permission(conn, UUID(current_user["id"]), "election_analytics", "view")

    ids = [UUID(cid.strip()) for cid in candidate_ids.split(",")]
    comparison = await analytics_service.compare_candidates_analytics(
        conn, election_id, ids
    )

    return success_response(data=comparison)


# ============================================
# DASHBOARD ENDPOINTS
# ============================================


@router.get("/dashboard")
async def get_elections_dashboard(
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Get overview dashboard of all elections."""
    await require_permission(conn, UUID(current_user["id"]), "election_analytics", "view")

    dashboard = await analytics_service.get_elections_dashboard(
        conn, UUID(current_user["organization_id"])
    )

    return success_response(data=dashboard)


@router.get("/dashboard/active")
async def get_active_elections_dashboard(
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Get dashboard for active elections only."""
    await require_permission(conn, UUID(current_user["id"]), "election_analytics", "view")

    elections = await election_service.list_elections(
        conn,
        organization_id=UUID(current_user["organization_id"]),
        status="active",
    )

    active_data = []
    for election in elections:
        results = await analytics_service.calculate_results(conn, UUID(election["id"]))
        turnout = await analytics_service.get_turnout_stats(conn, UUID(election["id"]))

        active_data.append({
            "election": {
                "id": str(election["id"]),
                "title": election["title"],
                "type": election["election_type"],
                "end_date": election["end_date"].isoformat(),
            },
            "total_votes": results.get("total_voters", 0),
            "turnout_rate": turnout.get("turnout_rate", 0),
        })

    return success_response(data=active_data)


# ============================================
# EXPORT ENDPOINTS
# ============================================


@router.get("/{election_id}/export")
async def export_election_data(
    election_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    format: str = Query("json", pattern="^(json|csv)$"),
):
    """
    Export election results and analytics.

    Requires `election_analytics.export` permission.
    """
    await require_permission(conn, UUID(current_user["id"]), "election_analytics", "export")

    election = await election_service.get_election_by_id(conn, election_id)
    if not election:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Election not found",
        )

    results = await analytics_service.calculate_results(conn, election_id)
    demographics = await analytics_service.get_demographic_breakdown(conn, election_id)
    turnout = await analytics_service.get_turnout_stats(conn, election_id)

    export_data = {
        "election": {
            "id": str(election_id),
            "title": election["title"],
            "type": election["election_type"],
            "status": election["status"],
            "start_date": election["start_date"].isoformat(),
            "end_date": election["end_date"].isoformat(),
        },
        "results": results,
        "demographics": demographics,
        "turnout": turnout,
        "exported_at": __import__("datetime").datetime.utcnow().isoformat(),
        "exported_by": current_user["username"],
    }

    if format == "csv":
        # Generate CSV for results
        import csv
        import io

        output = io.StringIO()
        writer = csv.writer(output)

        # Write election info
        writer.writerow(["Election", election["title"]])
        writer.writerow(["Type", election["election_type"]])
        writer.writerow(["Status", election["status"]])
        writer.writerow([])

        # Write results
        if "positions" in results:
            for position in results.get("positions", []):
                writer.writerow(["Position", position["title"]])
                writer.writerow(["Candidate", "Party", "Votes", "Percentage"])
                for candidate in position.get("candidates", []):
                    writer.writerow([
                        candidate.get("name", ""),
                        candidate.get("party", ""),
                        candidate.get("votes", 0),
                        f"{candidate.get('percentage', 0)}%",
                    ])
                writer.writerow([])
        elif "options" in results:
            writer.writerow(["Option", "Votes", "Percentage"])
            for option in results.get("options", []):
                writer.writerow([
                    option.get("option_text", ""),
                    option.get("votes", 0),
                    f"{option.get('percentage', 0)}%",
                ])

        # Write turnout
        writer.writerow([])
        writer.writerow(["Turnout Statistics"])
        writer.writerow(["Total Votes", turnout.get("votes_cast", 0)])
        writer.writerow(["Turnout Rate", f"{turnout.get('turnout_rate', 0)}%"])

        csv_content = output.getvalue()
        output.close()

        # Log export
        await election_service.log_election_action(
            conn,
            election_id,
            "results_exported",
            UUID(current_user["id"]),
            {"format": "csv"},
        )

        return StreamingResponse(
            iter([csv_content]),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=election_{election_id}_results.csv"
            },
        )

    # Log export
    await election_service.log_election_action(
        conn,
        election_id,
        "results_exported",
        UUID(current_user["id"]),
        {"format": "json"},
    )

    return success_response(data=export_data)
