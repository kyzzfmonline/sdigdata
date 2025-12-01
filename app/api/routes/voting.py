"""Voting API routes."""

from typing import Annotated
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.responses import success_response
from app.services import elections as election_service
from app.services import voting as voting_service
from app.services import voter_verification as verification_service
from app.services.permissions import require_permission

router = APIRouter(prefix="/elections", tags=["Voting"])


# ============================================
# PYDANTIC MODELS
# ============================================


class VoteRequest(BaseModel):
    """Single vote request model."""

    position_id: UUID | None = None
    candidate_id: UUID | None = None
    poll_option_id: UUID | None = None
    rank: int | None = Field(None, ge=1)


class CastVotesRequest(BaseModel):
    """Cast multiple votes request model."""

    votes: list[VoteRequest]
    voter_token: str | None = None  # For verified voting


class RankedVoteRequest(BaseModel):
    """Ranked-choice vote request model."""

    position_id: UUID
    rankings: list[dict]  # [{"candidate_id": uuid, "rank": 1}, ...]


class VerifyVoterRequest(BaseModel):
    """Verify voter request model."""

    national_id: str | None = None
    phone: str | None = None
    otp: str | None = None


class RequestOTPRequest(BaseModel):
    """Request OTP request model."""

    phone: str = Field(..., min_length=10, max_length=20)


# ============================================
# VOTER VERIFICATION ENDPOINTS
# ============================================


@router.post("/{election_id}/verify")
async def verify_voter(
    election_id: UUID,
    request: VerifyVoterRequest,
    req: Request,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """
    Verify voter eligibility for an election.

    Returns a voter_token on success that must be used when casting votes.
    """
    await require_permission(conn, UUID(current_user["id"]), "voting", "vote")

    success, message, voter_token = await verification_service.verify_voter_eligibility(
        conn=conn,
        election_id=election_id,
        national_id=request.national_id,
        phone=request.phone,
        otp=request.otp,
        user_id=UUID(current_user["id"]),
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message,
        )

    # Register the verified voter
    if voter_token:
        ip_address = req.client.host if req.client else None
        user_agent = req.headers.get("user-agent")

        await verification_service.register_verified_voter(
            conn=conn,
            election_id=election_id,
            voter_token=voter_token,
            national_id=request.national_id,
            phone=request.phone,
            user_id=UUID(current_user["id"]),
            ip_address=ip_address,
            user_agent=user_agent,
        )

    # Log action
    await election_service.log_election_action(
        conn,
        election_id,
        "voter_verified",
        UUID(current_user["id"]),
        {"verification_method": "phone_otp" if request.otp else "national_id" if request.national_id else "user_account"},
    )

    return success_response(
        data={"voter_token": voter_token, "verified": True},
        message=message,
    )


@router.post("/{election_id}/request-otp")
async def request_otp(
    election_id: UUID,
    request: RequestOTPRequest,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Request an OTP for phone verification."""
    await require_permission(conn, UUID(current_user["id"]), "voting", "vote")

    success, message = await verification_service.request_phone_verification(
        conn=conn,
        election_id=election_id,
        phone=request.phone,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message,
        )

    return success_response(message=message)


# ============================================
# VOTING ENDPOINTS
# ============================================


@router.post("/{election_id}/vote")
async def cast_vote(
    election_id: UUID,
    request: CastVotesRequest,
    req: Request,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """
    Cast votes in an election.

    For anonymous elections, no voter_token is required.
    For verified elections, the voter_token from /verify must be provided.
    """
    await require_permission(conn, UUID(current_user["id"]), "voting", "vote")

    # Get election details
    election = await election_service.get_election_by_id(conn, election_id)
    if not election:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Election not found",
        )

    # Determine voter hash
    if election["verification_level"] == "anonymous":
        voter_hash = voting_service.generate_voter_hash(
            election_id=election_id,
            user_id=UUID(current_user["id"]),
        )
    elif request.voter_token:
        voter_hash = request.voter_token
    else:
        # For registered/verified, generate from user ID
        voter_hash = voting_service.generate_voter_hash(
            election_id=election_id,
            user_id=UUID(current_user["id"]),
        )

    # Check if can vote
    can_vote, reason = await voting_service.check_can_vote(conn, election_id, voter_hash)
    if not can_vote:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=reason,
        )

    # Validate vote selections
    votes_data = [v.model_dump() for v in request.votes]
    valid, errors = await voting_service.validate_vote_selections(
        conn, election_id, votes_data
    )
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "Invalid vote selections", "errors": errors},
        )

    # Cast votes
    results = await voting_service.cast_votes_batch(
        conn=conn,
        election_id=election_id,
        voter_hash=voter_hash,
        votes=votes_data,
    )

    if not results:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to cast votes. You may have already voted.",
        )

    # Mark voter as voted (for non-anonymous)
    if election["verification_level"] != "anonymous":
        voter = await voting_service.get_voter(
            conn, election_id, user_id=UUID(current_user["id"])
        )
        if voter:
            await voting_service.mark_voted(conn, UUID(voter["id"]))

    # Generate receipt
    receipt = await voting_service.generate_vote_receipt(conn, election_id, voter_hash)

    # Log action
    await election_service.log_election_action(
        conn,
        election_id,
        "vote_cast",
        UUID(current_user["id"]),
        {"votes_count": len(results)},
    )

    return success_response(
        data={"votes_cast": len(results), "receipt": receipt},
        message="Vote(s) cast successfully",
    )


@router.post("/{election_id}/vote/ranked")
async def cast_ranked_vote(
    election_id: UUID,
    request: RankedVoteRequest,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Cast a ranked-choice vote for a position."""
    await require_permission(conn, UUID(current_user["id"]), "voting", "vote")

    # Get election details
    election = await election_service.get_election_by_id(conn, election_id)
    if not election:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Election not found",
        )

    if election["voting_method"] != "ranked_choice":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This election does not use ranked-choice voting",
        )

    # Generate voter hash
    voter_hash = voting_service.generate_voter_hash(
        election_id=election_id,
        user_id=UUID(current_user["id"]),
    )

    # Check if can vote
    can_vote, reason = await voting_service.check_can_vote(conn, election_id, voter_hash)
    if not can_vote:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=reason,
        )

    # Cast ranked votes
    results = await voting_service.cast_ranked_votes(
        conn=conn,
        election_id=election_id,
        voter_hash=voter_hash,
        position_id=request.position_id,
        rankings=request.rankings,
    )

    if not results:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to cast votes. You may have already voted.",
        )

    # Generate receipt
    receipt = await voting_service.generate_vote_receipt(conn, election_id, voter_hash)

    return success_response(
        data={"votes_cast": len(results), "receipt": receipt},
        message="Ranked vote(s) cast successfully",
    )


@router.get("/{election_id}/vote-status")
async def get_vote_status(
    election_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Check if the current user has voted in an election."""
    await require_permission(conn, UUID(current_user["id"]), "voting", "vote")

    # Generate voter hash based on user ID
    voter_hash = voting_service.generate_voter_hash(
        election_id=election_id,
        user_id=UUID(current_user["id"]),
    )

    has_voted = await voting_service.has_voted(conn, election_id, voter_hash)

    # Get receipt if voted
    receipt = None
    if has_voted:
        receipt = await voting_service.generate_vote_receipt(conn, election_id, voter_hash)

    return success_response(
        data={
            "has_voted": has_voted,
            "receipt": receipt,
        }
    )


@router.get("/{election_id}/vote-count")
async def get_vote_count(
    election_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Get the current vote count for an election."""
    await require_permission(conn, UUID(current_user["id"]), "elections", "read")

    election = await election_service.get_election_by_id(conn, election_id)
    if not election:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Election not found",
        )

    # Check if vote count should be shown
    if not election["show_voter_count"] and election["status"] != "closed":
        return success_response(
            data={"vote_count": None, "hidden": True},
            message="Vote count is hidden until election closes",
        )

    count = await voting_service.get_unique_voter_count(conn, election_id)

    return success_response(
        data={"vote_count": count, "hidden": False},
    )
