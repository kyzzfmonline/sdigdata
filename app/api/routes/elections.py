"""Elections API routes."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.responses import success_response
from app.services import elections as election_service
from app.services.permissions import require_permission

router = APIRouter(prefix="/elections", tags=["Elections"])


# ============================================
# PYDANTIC MODELS
# ============================================


class ElectionCreate(BaseModel):
    """Create election request model."""

    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    election_type: str = Field(..., pattern="^(election|poll|survey|referendum)$")
    voting_method: str = Field(..., pattern="^(single_choice|multi_choice|ranked_choice)$")
    verification_level: str = Field(
        default="anonymous", pattern="^(anonymous|registered|verified)$"
    )
    require_national_id: bool = False
    require_phone_otp: bool = False
    results_visibility: str = Field(default="after_close", pattern="^(real_time|after_close)$")
    show_voter_count: bool = True
    start_date: datetime
    end_date: datetime
    linked_form_id: UUID | None = None
    settings: dict | None = None
    branding: dict | None = None


class ElectionUpdate(BaseModel):
    """Update election request model."""

    title: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    election_type: str | None = Field(None, pattern="^(election|poll|survey|referendum)$")
    voting_method: str | None = Field(
        None, pattern="^(single_choice|multi_choice|ranked_choice)$"
    )
    verification_level: str | None = Field(
        None, pattern="^(anonymous|registered|verified)$"
    )
    require_national_id: bool | None = None
    require_phone_otp: bool | None = None
    results_visibility: str | None = Field(None, pattern="^(real_time|after_close)$")
    show_voter_count: bool | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    linked_form_id: UUID | None = None
    settings: dict | None = None
    branding: dict | None = None


class PositionCreate(BaseModel):
    """Create position request model."""

    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    max_selections: int = Field(default=1, ge=1)
    display_order: int | None = None


class PositionUpdate(BaseModel):
    """Update position request model."""

    title: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    max_selections: int | None = Field(None, ge=1)
    display_order: int | None = None


class CandidateCreate(BaseModel):
    """Create candidate request model."""

    name: str = Field(..., min_length=1, max_length=255)
    photo_url: str | None = None
    party: str | None = None
    bio: str | None = None
    manifesto: str | None = None
    policies: dict | None = None
    experience: dict | None = None
    endorsements: list | None = None
    display_order: int | None = None


class CandidateUpdate(BaseModel):
    """Update candidate request model."""

    name: str | None = Field(None, min_length=1, max_length=255)
    photo_url: str | None = None
    party: str | None = None
    bio: str | None = None
    manifesto: str | None = None
    policies: dict | None = None
    experience: dict | None = None
    endorsements: list | None = None
    display_order: int | None = None


class PollOptionCreate(BaseModel):
    """Create poll option request model."""

    option_text: str = Field(..., min_length=1, max_length=500)
    description: str | None = None
    display_order: int | None = None


class PollOptionUpdate(BaseModel):
    """Update poll option request model."""

    option_text: str | None = Field(None, min_length=1, max_length=500)
    description: str | None = None
    display_order: int | None = None


# ============================================
# ELECTION CRUD ENDPOINTS
# ============================================


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_election(
    request: ElectionCreate,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """
    Create a new election.

    Requires `elections.create` permission.
    """
    await require_permission(conn, UUID(current_user["id"]), "elections", "create")

    election = await election_service.create_election(
        conn=conn,
        organization_id=UUID(current_user["organization_id"]),
        title=request.title,
        election_type=request.election_type,
        voting_method=request.voting_method,
        start_date=request.start_date,
        end_date=request.end_date,
        created_by=UUID(current_user["id"]),
        description=request.description,
        verification_level=request.verification_level,
        require_national_id=request.require_national_id,
        require_phone_otp=request.require_phone_otp,
        results_visibility=request.results_visibility,
        show_voter_count=request.show_voter_count,
        linked_form_id=request.linked_form_id,
        settings=request.settings,
        branding=request.branding,
    )

    if not election:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to create election",
        )

    # Log action
    await election_service.log_election_action(
        conn,
        UUID(election["id"]),
        "election_created",
        UUID(current_user["id"]),
        {"title": request.title, "type": request.election_type},
    )

    return success_response(data=election, message="Election created successfully")


@router.get("")
async def list_elections(
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    status_filter: str | None = Query(None, alias="status"),
    election_type: str | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """
    List elections for the current user's organization.

    Requires `elections.read` permission.
    """
    await require_permission(conn, UUID(current_user["id"]), "elections", "read")

    elections = await election_service.list_elections(
        conn=conn,
        organization_id=UUID(current_user["organization_id"]),
        status=status_filter,
        election_type=election_type,
        limit=limit,
        offset=offset,
    )

    return success_response(data=elections, message=f"Found {len(elections)} elections")


@router.get("/{election_id}")
async def get_election(
    election_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """
    Get election details by ID.

    Requires `elections.read` permission.
    """
    await require_permission(conn, UUID(current_user["id"]), "elections", "read")

    election = await election_service.get_election_by_id(conn, election_id)

    if not election:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Election not found",
        )

    # Get positions and candidates/options
    positions = await election_service.list_positions(conn, election_id)
    for position in positions:
        position["candidates"] = await election_service.list_candidates(
            conn, UUID(position["id"])
        )

    poll_options = await election_service.list_poll_options(conn, election_id)

    election["positions"] = positions
    election["poll_options"] = poll_options

    return success_response(data=election)


@router.put("/{election_id}")
async def update_election(
    election_id: UUID,
    request: ElectionUpdate,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """
    Update an election.

    Requires `elections.update` permission.
    Can only update draft or scheduled elections.
    """
    await require_permission(conn, UUID(current_user["id"]), "elections", "update")

    existing = await election_service.get_election_by_id(conn, election_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Election not found",
        )

    if existing["status"] not in ("draft", "scheduled"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only update draft or scheduled elections",
        )

    update_data = request.model_dump(exclude_unset=True)
    election = await election_service.update_election(conn, election_id, **update_data)

    if not election:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to update election",
        )

    # Log action
    await election_service.log_election_action(
        conn,
        election_id,
        "election_updated",
        UUID(current_user["id"]),
        {"fields_updated": list(update_data.keys())},
    )

    return success_response(data=election, message="Election updated successfully")


@router.delete("/{election_id}")
async def delete_election(
    election_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """
    Delete an election (soft delete).

    Requires `elections.delete` permission.
    """
    await require_permission(conn, UUID(current_user["id"]), "elections", "delete")

    existing = await election_service.get_election_by_id(conn, election_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Election not found",
        )

    success = await election_service.delete_election(conn, election_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to delete election",
        )

    # Log action
    await election_service.log_election_action(
        conn,
        election_id,
        "election_deleted",
        UUID(current_user["id"]),
    )

    return success_response(message="Election deleted successfully")


# ============================================
# ELECTION LIFECYCLE ENDPOINTS
# ============================================


@router.post("/{election_id}/publish")
async def publish_election(
    election_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """
    Publish an election (draft -> scheduled/active).

    Requires `elections.publish` permission.
    """
    await require_permission(conn, UUID(current_user["id"]), "elections", "publish")

    election = await election_service.publish_election(conn, election_id)

    if not election:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to publish election. Ensure it is in draft status.",
        )

    await election_service.log_election_action(
        conn,
        election_id,
        "election_published",
        UUID(current_user["id"]),
        {"new_status": election["status"]},
    )

    return success_response(data=election, message=f"Election {election['status']}")


@router.post("/{election_id}/pause")
async def pause_election(
    election_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """
    Pause an active election.

    Requires `elections.manage` permission.
    """
    await require_permission(conn, UUID(current_user["id"]), "elections", "manage")

    election = await election_service.pause_election(conn, election_id)

    if not election:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to pause election. Ensure it is active.",
        )

    await election_service.log_election_action(
        conn,
        election_id,
        "election_paused",
        UUID(current_user["id"]),
    )

    return success_response(data=election, message="Election paused")


@router.post("/{election_id}/resume")
async def resume_election(
    election_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """
    Resume a paused election.

    Requires `elections.manage` permission.
    """
    await require_permission(conn, UUID(current_user["id"]), "elections", "manage")

    election = await election_service.resume_election(conn, election_id)

    if not election:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to resume election. Ensure it is paused.",
        )

    await election_service.log_election_action(
        conn,
        election_id,
        "election_resumed",
        UUID(current_user["id"]),
    )

    return success_response(data=election, message="Election resumed")


@router.post("/{election_id}/close")
async def close_election(
    election_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """
    Close an election.

    Requires `elections.manage` permission.
    """
    await require_permission(conn, UUID(current_user["id"]), "elections", "manage")

    election = await election_service.close_election(conn, election_id)

    if not election:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to close election.",
        )

    await election_service.log_election_action(
        conn,
        election_id,
        "election_closed",
        UUID(current_user["id"]),
    )

    return success_response(data=election, message="Election closed")


@router.post("/{election_id}/cancel")
async def cancel_election(
    election_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """
    Cancel an election.

    Requires `elections.manage` permission.
    """
    await require_permission(conn, UUID(current_user["id"]), "elections", "manage")

    election = await election_service.cancel_election(conn, election_id)

    if not election:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to cancel election.",
        )

    await election_service.log_election_action(
        conn,
        election_id,
        "election_cancelled",
        UUID(current_user["id"]),
    )

    return success_response(data=election, message="Election cancelled")


# ============================================
# POSITION ENDPOINTS
# ============================================


@router.post("/{election_id}/positions", status_code=status.HTTP_201_CREATED)
async def add_position(
    election_id: UUID,
    request: PositionCreate,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Add a position to an election."""
    await require_permission(conn, UUID(current_user["id"]), "elections", "update")

    position = await election_service.add_position(
        conn=conn,
        election_id=election_id,
        title=request.title,
        description=request.description,
        max_selections=request.max_selections,
        display_order=request.display_order,
    )

    if not position:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to add position",
        )

    return success_response(data=position, message="Position added successfully")


@router.get("/{election_id}/positions")
async def list_positions(
    election_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """List all positions for an election."""
    await require_permission(conn, UUID(current_user["id"]), "elections", "read")

    positions = await election_service.list_positions(conn, election_id)

    # Include candidates for each position
    for position in positions:
        position["candidates"] = await election_service.list_candidates(
            conn, UUID(position["id"])
        )

    return success_response(data=positions)


@router.put("/{election_id}/positions/{position_id}")
async def update_position(
    election_id: UUID,
    position_id: UUID,
    request: PositionUpdate,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Update a position."""
    await require_permission(conn, UUID(current_user["id"]), "elections", "update")

    position = await election_service.update_position(
        conn=conn,
        position_id=position_id,
        title=request.title,
        description=request.description,
        max_selections=request.max_selections,
        display_order=request.display_order,
    )

    if not position:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Position not found",
        )

    return success_response(data=position, message="Position updated successfully")


@router.delete("/{election_id}/positions/{position_id}")
async def delete_position(
    election_id: UUID,
    position_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Delete a position and all its candidates."""
    await require_permission(conn, UUID(current_user["id"]), "elections", "update")

    success = await election_service.delete_position(conn, position_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Position not found",
        )

    return success_response(message="Position deleted successfully")


# ============================================
# CANDIDATE ENDPOINTS
# ============================================


@router.post(
    "/{election_id}/positions/{position_id}/candidates",
    status_code=status.HTTP_201_CREATED,
)
async def add_candidate(
    election_id: UUID,
    position_id: UUID,
    request: CandidateCreate,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Add a candidate to a position."""
    await require_permission(conn, UUID(current_user["id"]), "elections", "update")

    candidate = await election_service.add_candidate(
        conn=conn,
        position_id=position_id,
        name=request.name,
        photo_url=request.photo_url,
        party=request.party,
        bio=request.bio,
        manifesto=request.manifesto,
        policies=request.policies,
        experience=request.experience,
        endorsements=request.endorsements,
        display_order=request.display_order,
    )

    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to add candidate",
        )

    return success_response(data=candidate, message="Candidate added successfully")


@router.get("/{election_id}/positions/{position_id}/candidates")
async def list_candidates(
    election_id: UUID,
    position_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """List all candidates for a position."""
    await require_permission(conn, UUID(current_user["id"]), "elections", "read")

    candidates = await election_service.list_candidates(conn, position_id)

    return success_response(data=candidates)


@router.put("/{election_id}/candidates/{candidate_id}")
async def update_candidate(
    election_id: UUID,
    candidate_id: UUID,
    request: CandidateUpdate,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Update a candidate."""
    await require_permission(conn, UUID(current_user["id"]), "elections", "update")

    update_data = request.model_dump(exclude_unset=True)
    candidate = await election_service.update_candidate(conn, candidate_id, **update_data)

    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found",
        )

    return success_response(data=candidate, message="Candidate updated successfully")


@router.delete("/{election_id}/candidates/{candidate_id}")
async def delete_candidate(
    election_id: UUID,
    candidate_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Delete a candidate."""
    await require_permission(conn, UUID(current_user["id"]), "elections", "update")

    success = await election_service.delete_candidate(conn, candidate_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found",
        )

    return success_response(message="Candidate deleted successfully")


@router.get("/{election_id}/candidates/compare")
async def compare_candidates(
    election_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    candidate_ids: str = Query(..., description="Comma-separated candidate UUIDs"),
):
    """Compare multiple candidates."""
    await require_permission(conn, UUID(current_user["id"]), "elections", "read")

    ids = [UUID(cid.strip()) for cid in candidate_ids.split(",")]
    candidates = await election_service.compare_candidates(conn, ids)

    return success_response(data=candidates)


# ============================================
# POLL OPTION ENDPOINTS
# ============================================


@router.post("/{election_id}/options", status_code=status.HTTP_201_CREATED)
async def add_poll_option(
    election_id: UUID,
    request: PollOptionCreate,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Add a poll option to an election."""
    await require_permission(conn, UUID(current_user["id"]), "elections", "update")

    option = await election_service.add_poll_option(
        conn=conn,
        election_id=election_id,
        option_text=request.option_text,
        description=request.description,
        display_order=request.display_order,
    )

    if not option:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to add poll option",
        )

    return success_response(data=option, message="Poll option added successfully")


@router.get("/{election_id}/options")
async def list_poll_options(
    election_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """List all poll options for an election."""
    await require_permission(conn, UUID(current_user["id"]), "elections", "read")

    options = await election_service.list_poll_options(conn, election_id)

    return success_response(data=options)


@router.put("/{election_id}/options/{option_id}")
async def update_poll_option(
    election_id: UUID,
    option_id: UUID,
    request: PollOptionUpdate,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Update a poll option."""
    await require_permission(conn, UUID(current_user["id"]), "elections", "update")

    option = await election_service.update_poll_option(
        conn=conn,
        option_id=option_id,
        option_text=request.option_text,
        description=request.description,
        display_order=request.display_order,
    )

    if not option:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Poll option not found",
        )

    return success_response(data=option, message="Poll option updated successfully")


@router.delete("/{election_id}/options/{option_id}")
async def delete_poll_option(
    election_id: UUID,
    option_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Delete a poll option."""
    await require_permission(conn, UUID(current_user["id"]), "elections", "update")

    success = await election_service.delete_poll_option(conn, option_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Poll option not found",
        )

    return success_response(message="Poll option deleted successfully")


# ============================================
# AUDIT LOG ENDPOINT
# ============================================


@router.get("/{election_id}/audit-log")
async def get_audit_log(
    election_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """Get audit log for an election."""
    await require_permission(conn, UUID(current_user["id"]), "elections", "manage")

    logs = await election_service.get_election_audit_log(
        conn, election_id, limit=limit, offset=offset
    )

    return success_response(data=logs)
