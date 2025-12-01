"""Candidate Profiles API routes for managing reusable candidates."""

from typing import Annotated
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.responses import success_response
from app.services import candidate_profiles as profile_service
from app.services.permissions import require_permission

router = APIRouter(prefix="/candidate-profiles", tags=["Candidate Profiles"])


# ============================================
# PYDANTIC MODELS
# ============================================


class CandidateProfileCreate(BaseModel):
    """Create a new candidate profile."""

    name: str = Field(..., min_length=2, max_length=255)
    photo_url: str | None = None
    email: str | None = None
    phone: str | None = None
    date_of_birth: str | None = None  # ISO date string
    party_id: UUID | None = None  # Reference to political_parties table
    party: str | None = None  # For independent candidates or backward compat
    bio: str | None = None
    manifesto: str | None = None
    policies: dict | None = None
    experience: dict | None = None
    endorsements: list | None = None
    education: list | None = None
    social_links: dict | None = None


class CandidateProfileUpdate(BaseModel):
    """Update an existing candidate profile."""

    name: str | None = Field(None, min_length=2, max_length=255)
    photo_url: str | None = None
    email: str | None = None
    phone: str | None = None
    date_of_birth: str | None = None
    party_id: UUID | None = None
    party: str | None = None
    bio: str | None = None
    manifesto: str | None = None
    policies: dict | None = None
    experience: dict | None = None
    endorsements: list | None = None
    education: list | None = None
    social_links: dict | None = None
    status: str | None = Field(None, pattern="^(active|inactive|suspended|deceased)$")


class AssignCandidateRequest(BaseModel):
    """Assign a candidate to an election position."""

    candidate_profile_id: UUID
    position_id: UUID
    display_name: str | None = None
    campaign_photo_url: str | None = None
    campaign_slogan: str | None = None
    campaign_manifesto: str | None = None
    ballot_number: int | None = None


# ============================================
# CANDIDATE PROFILE ENDPOINTS
# ============================================


@router.get("")
async def list_candidate_profiles(
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    party: str | None = None,
    cand_status: str | None = Query(None, alias="status", pattern="^(active|inactive|suspended|deceased)$"),
    search: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """
    List all candidate profiles for the organization.

    Can filter by party, status, or search by name.
    """
    await require_permission(conn, UUID(current_user["id"]), "elections", "read")

    profiles, total = await profile_service.list_candidate_profiles(
        conn=conn,
        organization_id=UUID(current_user["organization_id"]),
        party=party,
        status=cand_status,
        search=search,
        limit=limit,
        offset=offset,
    )

    return success_response(
        data={
            "profiles": profiles,
            "total": total,
            "limit": limit,
            "offset": offset,
        }
    )


@router.post("")
async def create_candidate_profile(
    request: CandidateProfileCreate,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """
    Create a new candidate profile.

    Candidate profiles can be reused across multiple elections.
    """
    await require_permission(conn, UUID(current_user["id"]), "elections", "create")

    profile = await profile_service.create_candidate_profile(
        conn=conn,
        organization_id=UUID(current_user["organization_id"]),
        name=request.name,
        photo_url=request.photo_url,
        email=request.email,
        phone=request.phone,
        date_of_birth=request.date_of_birth,
        party_id=request.party_id,
        party=request.party,
        bio=request.bio,
        manifesto=request.manifesto,
        policies=request.policies,
        experience=request.experience,
        endorsements=request.endorsements,
        education=request.education,
        social_links=request.social_links,
    )

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to create candidate profile. Name may already exist.",
        )

    return success_response(data=profile, message="Candidate profile created")


@router.get("/{profile_id}")
async def get_candidate_profile(
    profile_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """
    Get a candidate profile by ID with election history.
    """
    await require_permission(conn, UUID(current_user["id"]), "elections", "read")

    profile = await profile_service.get_candidate_profile(
        conn=conn,
        profile_id=profile_id,
        organization_id=UUID(current_user["organization_id"]),
    )

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate profile not found",
        )

    # Get election history
    history = await profile_service.get_candidate_election_history(
        conn=conn,
        profile_id=profile_id,
    )
    profile["election_history"] = history

    return success_response(data=profile)


@router.put("/{profile_id}")
async def update_candidate_profile(
    profile_id: UUID,
    request: CandidateProfileUpdate,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """
    Update a candidate profile.
    """
    await require_permission(conn, UUID(current_user["id"]), "elections", "update")

    profile = await profile_service.update_candidate_profile(
        conn=conn,
        profile_id=profile_id,
        organization_id=UUID(current_user["organization_id"]),
        **request.model_dump(exclude_unset=True),
    )

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate profile not found",
        )

    return success_response(data=profile, message="Candidate profile updated")


@router.delete("/{profile_id}")
async def delete_candidate_profile(
    profile_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """
    Soft delete a candidate profile.

    The profile will be marked as deleted but data is preserved for historical records.
    """
    await require_permission(conn, UUID(current_user["id"]), "elections", "delete")

    success = await profile_service.delete_candidate_profile(
        conn=conn,
        profile_id=profile_id,
        organization_id=UUID(current_user["organization_id"]),
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate profile not found",
        )

    return success_response(message="Candidate profile deleted")


# ============================================
# ELECTION CANDIDATE ASSIGNMENT ENDPOINTS
# ============================================


@router.post("/assign")
async def assign_candidate_to_election(
    request: AssignCandidateRequest,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """
    Assign a candidate profile to an election position.

    Allows specifying election-specific details like campaign slogan,
    campaign photo, and ballot number.
    """
    await require_permission(conn, UUID(current_user["id"]), "elections", "update")

    assignment = await profile_service.assign_candidate_to_position(
        conn=conn,
        candidate_profile_id=request.candidate_profile_id,
        position_id=request.position_id,
        organization_id=UUID(current_user["organization_id"]),
        display_name=request.display_name,
        campaign_photo_url=request.campaign_photo_url,
        campaign_slogan=request.campaign_slogan,
        campaign_manifesto=request.campaign_manifesto,
        ballot_number=request.ballot_number,
    )

    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to assign candidate. They may already be assigned to this election.",
        )

    return success_response(data=assignment, message="Candidate assigned to election")


@router.delete("/assign/{assignment_id}")
async def remove_candidate_from_election(
    assignment_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """
    Remove a candidate from an election position.

    Only allowed before the election has started.
    """
    await require_permission(conn, UUID(current_user["id"]), "elections", "update")

    success = await profile_service.remove_candidate_from_position(
        conn=conn,
        assignment_id=assignment_id,
        organization_id=UUID(current_user["organization_id"]),
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to remove candidate. The election may have already started.",
        )

    return success_response(message="Candidate removed from election")


@router.put("/assign/{assignment_id}/status")
async def update_candidacy_status(
    assignment_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    new_status: str = Query(..., pattern="^(nominated|confirmed|withdrawn|disqualified)$"),
):
    """
    Update the status of a candidate's participation in an election.

    Status options:
    - nominated: Initial status when assigned
    - confirmed: Officially confirmed to participate
    - withdrawn: Candidate withdrew from the race
    - disqualified: Removed by organizers
    """
    await require_permission(conn, UUID(current_user["id"]), "elections", "update")

    assignment = await profile_service.update_candidacy_status(
        conn=conn,
        assignment_id=assignment_id,
        organization_id=UUID(current_user["organization_id"]),
        status=new_status,
    )

    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate assignment not found",
        )

    return success_response(data=assignment, message=f"Candidate status updated to {new_status}")


# ============================================
# CANDIDATE STATS ENDPOINTS
# ============================================


@router.get("/{profile_id}/stats")
async def get_candidate_stats(
    profile_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """
    Get detailed statistics for a candidate across all elections.
    """
    await require_permission(conn, UUID(current_user["id"]), "elections", "read")

    stats = await profile_service.get_candidate_stats(
        conn=conn,
        profile_id=profile_id,
        organization_id=UUID(current_user["organization_id"]),
    )

    if not stats:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate profile not found",
        )

    return success_response(data=stats)


@router.get("/leaderboard")
async def get_candidates_leaderboard(
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    sort_by: str = Query("total_wins", pattern="^(total_wins|total_votes|win_rate|elections_count)$"),
    limit: int = Query(20, ge=1, le=100),
):
    """
    Get a leaderboard of candidates by various metrics.

    Sort options:
    - total_wins: Most elections won
    - total_votes: Most votes received overall
    - win_rate: Highest win percentage
    - elections_count: Most elections participated in
    """
    await require_permission(conn, UUID(current_user["id"]), "elections", "read")

    leaderboard = await profile_service.get_candidates_leaderboard(
        conn=conn,
        organization_id=UUID(current_user["organization_id"]),
        sort_by=sort_by,
        limit=limit,
    )

    return success_response(data=leaderboard)
