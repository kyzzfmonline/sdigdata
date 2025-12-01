"""Public elections API routes (no authentication required)."""

from typing import Annotated
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.core.responses import success_response
from app.services import elections as election_service
from app.services import election_analytics as analytics_service
from app.services import voting as voting_service
from app.services import voter_verification as verification_service

router = APIRouter(prefix="/public/elections", tags=["Public Elections"])


# ============================================
# PYDANTIC MODELS
# ============================================


class PublicVoteRequest(BaseModel):
    """Public vote request model."""

    position_id: UUID | None = None
    candidate_id: UUID | None = None
    poll_option_id: UUID | None = None


class PublicVotesRequest(BaseModel):
    """Cast multiple public votes request model."""

    votes: list[PublicVoteRequest]
    voter_token: str  # Required for verified voting


class PublicVerifyRequest(BaseModel):
    """Public voter verification request model."""

    national_id: str | None = None
    phone: str | None = None
    otp: str | None = None


class PublicOTPRequest(BaseModel):
    """Request OTP for public voting."""

    phone: str = Field(..., min_length=10, max_length=20)


# ============================================
# PUBLIC ELECTION ENDPOINTS
# ============================================


@router.get("/{election_id}")
async def get_public_election(
    election_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
):
    """
    Get public election information.

    Returns election details, positions, candidates, and poll options
    for elections that allow public voting.
    """
    election = await election_service.get_election_by_id(conn, election_id)

    if not election:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Election not found",
        )

    # Check if election is active
    if election["status"] not in ("active", "scheduled"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Election is {election['status']}",
        )

    # Get positions and candidates
    positions = await election_service.list_positions(conn, election_id)
    for position in positions:
        candidates = await election_service.list_candidates(conn, UUID(position["id"]))
        # Remove sensitive fields from public view
        position["candidates"] = [
            {
                "id": c["id"],
                "name": c["name"],
                "photo_url": c["photo_url"],
                "party": c["party"],
                "bio": c["bio"],
                "manifesto": c["manifesto"],
            }
            for c in candidates
        ]

    # Get poll options
    poll_options = await election_service.list_poll_options(conn, election_id)

    # Build public response
    public_data = {
        "id": str(election["id"]),
        "title": election["title"],
        "description": election["description"],
        "election_type": election["election_type"],
        "voting_method": election["voting_method"],
        "verification_level": election["verification_level"],
        "require_national_id": election["require_national_id"],
        "require_phone_otp": election["require_phone_otp"],
        "status": election["status"],
        "start_date": election["start_date"].isoformat(),
        "end_date": election["end_date"].isoformat(),
        "branding": election["branding"],
        "positions": positions,
        "poll_options": poll_options,
    }

    # Include vote count if allowed
    if election["show_voter_count"]:
        public_data["total_votes"] = await voting_service.get_unique_voter_count(
            conn, election_id
        )

    # Include results if visibility allows
    if election["results_visibility"] == "real_time" or election["status"] == "closed":
        results = await analytics_service.calculate_results(conn, election_id)
        public_data["results"] = results

    return success_response(data=public_data)


@router.post("/{election_id}/request-otp")
async def request_public_otp(
    election_id: UUID,
    request: PublicOTPRequest,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
):
    """Request an OTP for public voting verification."""
    election = await election_service.get_election_by_id(conn, election_id)

    if not election:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Election not found",
        )

    if election["status"] != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Election is not active",
        )

    if not election["require_phone_otp"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This election does not require phone verification",
        )

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


@router.post("/{election_id}/verify")
async def verify_public_voter(
    election_id: UUID,
    request: PublicVerifyRequest,
    req: Request,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
):
    """
    Verify voter eligibility for public voting.

    Returns a voter_token on success that must be used when casting votes.
    """
    election = await election_service.get_election_by_id(conn, election_id)

    if not election:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Election not found",
        )

    if election["status"] != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Election is not active",
        )

    # Anonymous elections don't need verification
    if election["verification_level"] == "anonymous":
        voter_token = voting_service.generate_voter_hash(election_id=election_id)
        return success_response(
            data={"voter_token": voter_token, "verified": True},
            message="Anonymous voting enabled",
        )

    # Verified elections require credentials
    success, message, voter_token = await verification_service.verify_voter_eligibility(
        conn=conn,
        election_id=election_id,
        national_id=request.national_id,
        phone=request.phone,
        otp=request.otp,
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
            ip_address=ip_address,
            user_agent=user_agent,
        )

    # Log action
    await election_service.log_election_action(
        conn,
        election_id,
        "public_voter_verified",
        None,  # No user ID for public voters
        {"verification_method": "phone_otp" if request.otp else "national_id"},
        ip_address=req.client.host if req.client else None,
    )

    return success_response(
        data={"voter_token": voter_token, "verified": True},
        message=message,
    )


@router.post("/{election_id}/vote")
async def cast_public_vote(
    election_id: UUID,
    request: PublicVotesRequest,
    req: Request,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
):
    """
    Cast votes in a public election.

    Requires a valid voter_token from the /verify endpoint.
    """
    election = await election_service.get_election_by_id(conn, election_id)

    if not election:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Election not found",
        )

    if election["status"] != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Election is not active",
        )

    voter_hash = request.voter_token

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

    # Generate receipt
    receipt = await voting_service.generate_vote_receipt(conn, election_id, voter_hash)

    # Log action
    await election_service.log_election_action(
        conn,
        election_id,
        "public_vote_cast",
        None,
        {"votes_count": len(results)},
        ip_address=req.client.host if req.client else None,
    )

    return success_response(
        data={"votes_cast": len(results), "receipt": receipt},
        message="Vote(s) cast successfully",
    )


@router.get("/{election_id}/results")
async def get_public_results(
    election_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
):
    """
    Get public election results.

    Results are only available based on the election's visibility settings.
    """
    election = await election_service.get_election_by_id(conn, election_id)

    if not election:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Election not found",
        )

    # Check results visibility
    if election["results_visibility"] == "after_close" and election["status"] != "closed":
        return success_response(
            data={
                "election_id": str(election_id),
                "status": election["status"],
                "results_hidden": True,
                "message": "Results will be available after the election closes",
            }
        )

    results = await analytics_service.calculate_results(conn, election_id)

    return success_response(data=results)


@router.get("/{election_id}/check-vote/{voter_token}")
async def check_public_vote_status(
    election_id: UUID,
    voter_token: str,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
):
    """Check if a voter has already voted using their voter token."""
    has_voted = await voting_service.has_voted(conn, election_id, voter_token)

    receipt = None
    if has_voted:
        receipt = await voting_service.generate_vote_receipt(conn, election_id, voter_token)

    return success_response(
        data={
            "has_voted": has_voted,
            "receipt": receipt,
        }
    )
