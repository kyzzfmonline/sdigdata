"""Political Parties API routes for managing parties/groups."""

from typing import Annotated
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.responses import success_response
from app.services import political_parties as party_service
from app.services.permissions import require_permission

router = APIRouter(prefix="/political-parties", tags=["Political Parties"])


# ============================================
# PYDANTIC MODELS
# ============================================


class PartyCreate(BaseModel):
    """Create a new political party."""

    name: str = Field(..., min_length=2, max_length=255)
    abbreviation: str | None = Field(None, max_length=20)
    slogan: str | None = Field(None, max_length=500)
    description: str | None = None
    logo_url: str | None = None
    color_primary: str | None = Field(None, pattern="^#[0-9A-Fa-f]{6}$")
    color_secondary: str | None = Field(None, pattern="^#[0-9A-Fa-f]{6}$")
    headquarters_address: str | None = None
    website: str | None = Field(None, max_length=500)
    email: str | None = None
    phone: str | None = None
    social_links: dict | None = None
    leader_name: str | None = None
    founded_date: str | None = None  # ISO date string
    registration_number: str | None = None


class PartyUpdate(BaseModel):
    """Update an existing political party."""

    name: str | None = Field(None, min_length=2, max_length=255)
    abbreviation: str | None = Field(None, max_length=20)
    slogan: str | None = Field(None, max_length=500)
    description: str | None = None
    logo_url: str | None = None
    color_primary: str | None = Field(None, pattern="^#[0-9A-Fa-f]{6}$")
    color_secondary: str | None = Field(None, pattern="^#[0-9A-Fa-f]{6}$")
    headquarters_address: str | None = None
    website: str | None = Field(None, max_length=500)
    email: str | None = None
    phone: str | None = None
    social_links: dict | None = None
    leader_name: str | None = None
    founded_date: str | None = None
    registration_number: str | None = None
    status: str | None = Field(None, pattern="^(active|inactive|suspended|dissolved)$")


# ============================================
# PARTY ENDPOINTS
# ============================================


@router.get("")
async def list_parties(
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    party_status: str | None = Query(None, alias="status", pattern="^(active|inactive|suspended|dissolved)$"),
    search: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """
    List all political parties for the organization.

    Can filter by status or search by name/abbreviation.
    """
    await require_permission(conn, UUID(current_user["id"]), "elections", "read")

    parties, total = await party_service.list_parties(
        conn=conn,
        organization_id=UUID(current_user["organization_id"]),
        status=party_status,
        search=search,
        limit=limit,
        offset=offset,
    )

    return success_response(
        data={
            "parties": parties,
            "total": total,
            "limit": limit,
            "offset": offset,
        }
    )


@router.post("")
async def create_party(
    request: PartyCreate,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """
    Create a new political party.

    Political parties can have candidates assigned to them across elections.
    """
    await require_permission(conn, UUID(current_user["id"]), "elections", "create")

    party = await party_service.create_party(
        conn=conn,
        organization_id=UUID(current_user["organization_id"]),
        **request.model_dump(),
    )

    if not party:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to create party. Name may already exist.",
        )

    return success_response(data=party, message="Political party created")


@router.get("/leaderboard")
async def get_parties_leaderboard(
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    sort_by: str = Query("total_wins", pattern="^(total_wins|total_candidates|elections)$"),
    limit: int = Query(20, ge=1, le=100),
):
    """
    Get a leaderboard of political parties by various metrics.

    Sort options:
    - total_wins: Most elections won
    - total_candidates: Most candidates
    - elections: Most elections participated in
    """
    await require_permission(conn, UUID(current_user["id"]), "elections", "read")

    leaderboard = await party_service.get_parties_leaderboard(
        conn=conn,
        organization_id=UUID(current_user["organization_id"]),
        sort_by=sort_by,
        limit=limit,
    )

    return success_response(data=leaderboard)


@router.get("/{party_id}")
async def get_party(
    party_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """
    Get a political party by ID with election history.
    """
    await require_permission(conn, UUID(current_user["id"]), "elections", "read")

    party = await party_service.get_party(
        conn=conn,
        party_id=party_id,
        organization_id=UUID(current_user["organization_id"]),
    )

    if not party:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Political party not found",
        )

    # Get election history
    history = await party_service.get_party_election_history(
        conn=conn,
        party_id=party_id,
    )
    party["election_history"] = history

    return success_response(data=party)


@router.put("/{party_id}")
async def update_party(
    party_id: UUID,
    request: PartyUpdate,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """
    Update a political party.
    """
    await require_permission(conn, UUID(current_user["id"]), "elections", "update")

    party = await party_service.update_party(
        conn=conn,
        party_id=party_id,
        organization_id=UUID(current_user["organization_id"]),
        **request.model_dump(exclude_unset=True),
    )

    if not party:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Political party not found",
        )

    return success_response(data=party, message="Political party updated")


@router.delete("/{party_id}")
async def delete_party(
    party_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """
    Soft delete a political party.

    The party will be marked as dissolved but data is preserved for historical records.
    Candidates belonging to this party will retain the association for historical purposes.
    """
    await require_permission(conn, UUID(current_user["id"]), "elections", "delete")

    success = await party_service.delete_party(
        conn=conn,
        party_id=party_id,
        organization_id=UUID(current_user["organization_id"]),
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Political party not found",
        )

    return success_response(message="Political party dissolved")


@router.get("/deleted/list")
async def list_deleted_parties(
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """
    List all soft-deleted (dissolved) political parties.

    These parties can be permanently deleted using the hard delete endpoint.
    """
    await require_permission(conn, UUID(current_user["id"]), "elections", "delete")

    parties, total = await party_service.list_deleted_parties(
        conn=conn,
        organization_id=UUID(current_user["organization_id"]),
        limit=limit,
        offset=offset,
    )

    return success_response(
        data={
            "parties": parties,
            "total": total,
            "limit": limit,
            "offset": offset,
        }
    )


@router.delete("/{party_id}/permanent")
async def hard_delete_party(
    party_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """
    Permanently delete a soft-deleted political party.

    WARNING: This action is irreversible and will remove all data associated
    with this party. Only parties that have already been soft-deleted (dissolved)
    can be permanently deleted.

    Use this when you need to re-create a party with the same name.
    """
    await require_permission(conn, UUID(current_user["id"]), "elections", "delete")

    success = await party_service.hard_delete_party(
        conn=conn,
        party_id=party_id,
        organization_id=UUID(current_user["organization_id"]),
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Political party not found or not in deleted state. Only dissolved parties can be permanently deleted.",
        )

    return success_response(message="Political party permanently deleted")


# ============================================
# PARTY STATS & CANDIDATES
# ============================================


@router.get("/{party_id}/candidates")
async def get_party_candidates(
    party_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    cand_status: str | None = Query(None, alias="status", pattern="^(active|inactive|suspended|deceased)$"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """
    Get all candidates belonging to a political party.
    """
    await require_permission(conn, UUID(current_user["id"]), "elections", "read")

    candidates, total = await party_service.get_party_candidates(
        conn=conn,
        party_id=party_id,
        organization_id=UUID(current_user["organization_id"]),
        status=cand_status,
        limit=limit,
        offset=offset,
    )

    return success_response(
        data={
            "candidates": candidates,
            "total": total,
            "limit": limit,
            "offset": offset,
        }
    )


@router.get("/{party_id}/stats")
async def get_party_stats(
    party_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """
    Get detailed statistics for a political party across all elections.
    """
    await require_permission(conn, UUID(current_user["id"]), "elections", "read")

    stats = await party_service.get_party_stats(
        conn=conn,
        party_id=party_id,
        organization_id=UUID(current_user["organization_id"]),
    )

    if not stats:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Political party not found",
        )

    return success_response(data=stats)


@router.get("/{party_id}/elections")
async def get_party_elections(
    party_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """
    Get election participation history for a political party.
    """
    await require_permission(conn, UUID(current_user["id"]), "elections", "read")

    # First verify party belongs to org
    party = await party_service.get_party(
        conn=conn,
        party_id=party_id,
        organization_id=UUID(current_user["organization_id"]),
    )

    if not party:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Political party not found",
        )

    history = await party_service.get_party_election_history(
        conn=conn,
        party_id=party_id,
    )

    return success_response(data=history)
