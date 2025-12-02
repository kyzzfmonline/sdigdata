"""Unit tests for voting service."""

import pytest
from uuid import UUID, uuid4
from datetime import datetime, timedelta, timezone

from app.services import voting as voting_service
from app.services import elections as elections_service
from app.services.organizations import create_organization
from app.services.users import create_user
from app.core.security import hash_password


def _to_uuid(val) -> UUID:
    """Convert a value to UUID, handling asyncpg UUID objects."""
    if isinstance(val, UUID):
        return val
    if isinstance(val, str):
        return UUID(val)
    return UUID(str(val))


async def create_test_user(db_connection):
    """Helper to create a test user with unique username."""
    org = await create_organization(
        db_connection,
        name=f"Test Org {uuid4().hex[:8]}",
        logo_url=None,
        primary_color=None,
    )

    password_hash = hash_password("testpass123")
    user = await create_user(
        db_connection,
        username=f"testuser_{uuid4().hex[:8]}",
        password_hash=password_hash,
        role="admin",
        organization_id=org["id"],
    )

    return {
        "id": _to_uuid(user["id"]),
        "organization_id": _to_uuid(org["id"]),
    }


async def create_active_election(db_connection, user):
    """Helper to create an active election."""
    election = await elections_service.create_election(
        db_connection,
        organization_id=user["organization_id"],
        title=f"Active Election {uuid4().hex[:8]}",
        election_type="election",
        voting_method="single_choice",
        start_date=datetime.now(timezone.utc) - timedelta(hours=1),
        end_date=datetime.now(timezone.utc) + timedelta(days=7),
        created_by=user["id"],
    )
    # Publish it to make it active
    await elections_service.publish_election(
        db_connection, _to_uuid(election["id"])
    )
    return election


async def create_poll(db_connection, user):
    """Helper to create an active poll."""
    poll = await elections_service.create_election(
        db_connection,
        organization_id=user["organization_id"],
        title=f"Active Poll {uuid4().hex[:8]}",
        election_type="poll",
        voting_method="single_choice",
        start_date=datetime.now(timezone.utc) - timedelta(hours=1),
        end_date=datetime.now(timezone.utc) + timedelta(days=7),
        created_by=user["id"],
    )
    # Publish it to make it active
    await elections_service.publish_election(
        db_connection, _to_uuid(poll["id"])
    )
    return poll


# ============================================
# VOTER REGISTRATION TESTS
# ============================================


@pytest.mark.asyncio
async def test_register_voter_with_national_id(db_connection):
    """Test registering a voter with national ID."""
    user = await create_test_user(db_connection)
    election = await create_active_election(db_connection, user)

    voter = await voting_service.register_voter(
        db_connection,
        election_id=_to_uuid(election["id"]),
        national_id="GHA-1234567890",
        region="Greater Accra",
        age_group="25-34",
    )

    assert voter is not None
    assert voter["election_id"] == election["id"]
    assert voter["national_id_hash"] is not None
    assert voter["region"] == "Greater Accra"
    assert voter["has_voted"] is False


@pytest.mark.asyncio
async def test_register_voter_with_phone(db_connection):
    """Test registering a voter with phone number."""
    user = await create_test_user(db_connection)
    election = await create_active_election(db_connection, user)

    voter = await voting_service.register_voter(
        db_connection,
        election_id=_to_uuid(election["id"]),
        phone="+233201234567",
    )

    assert voter is not None
    assert voter["phone_hash"] is not None


@pytest.mark.asyncio
async def test_get_voter(db_connection):
    """Test getting a registered voter."""
    user = await create_test_user(db_connection)
    election = await create_active_election(db_connection, user)

    national_id = f"GHA-{uuid4().hex[:10]}"
    await voting_service.register_voter(
        db_connection,
        election_id=_to_uuid(election["id"]),
        national_id=national_id,
    )

    voter = await voting_service.get_voter(
        db_connection,
        election_id=_to_uuid(election["id"]),
        national_id=national_id,
    )

    assert voter is not None


@pytest.mark.asyncio
async def test_verify_voter(db_connection):
    """Test verifying a voter."""
    user = await create_test_user(db_connection)
    election = await create_active_election(db_connection, user)

    voter = await voting_service.register_voter(
        db_connection,
        election_id=_to_uuid(election["id"]),
        national_id=f"GHA-{uuid4().hex[:10]}",
    )

    verified = await voting_service.verify_voter(
        db_connection,
        voter_id=_to_uuid(voter["id"]),
        verification_method="national_id",
    )

    assert verified is not None
    assert verified["verified_at"] is not None
    assert verified["verification_method"] == "national_id"


@pytest.mark.asyncio
async def test_mark_voted(db_connection):
    """Test marking a voter as having voted."""
    user = await create_test_user(db_connection)
    election = await create_active_election(db_connection, user)

    voter = await voting_service.register_voter(
        db_connection,
        election_id=_to_uuid(election["id"]),
        national_id=f"GHA-{uuid4().hex[:10]}",
    )

    result = await voting_service.mark_voted(
        db_connection, _to_uuid(voter["id"])
    )
    assert result is True

    # Try to mark again - should fail
    result = await voting_service.mark_voted(
        db_connection, _to_uuid(voter["id"])
    )
    assert result is False


# ============================================
# VOTE CASTING TESTS
# ============================================


@pytest.mark.asyncio
async def test_cast_vote_for_candidate(db_connection):
    """Test casting a vote for a candidate."""
    user = await create_test_user(db_connection)
    election = await create_active_election(db_connection, user)

    position = await elections_service.add_position(
        db_connection,
        election_id=_to_uuid(election["id"]),
        title="President",
        max_selections=1,
    )

    candidate = await elections_service.add_candidate(
        db_connection,
        position_id=_to_uuid(position["id"]),
        name="John Doe",
        party="Independent",
    )

    voter_hash = voting_service.generate_voter_hash(
        _to_uuid(election["id"]),
        national_id=f"GHA-{uuid4().hex[:10]}",
    )

    vote = await voting_service.cast_vote(
        db_connection,
        election_id=_to_uuid(election["id"]),
        voter_hash=voter_hash,
        position_id=_to_uuid(position["id"]),
        candidate_id=_to_uuid(candidate["id"]),
    )

    assert vote is not None
    assert vote["election_id"] == election["id"]
    assert vote["candidate_id"] == candidate["id"]


@pytest.mark.asyncio
async def test_cast_vote_for_poll_option(db_connection):
    """Test casting a vote for a poll option."""
    user = await create_test_user(db_connection)
    poll = await create_poll(db_connection, user)

    option = await elections_service.add_poll_option(
        db_connection,
        election_id=_to_uuid(poll["id"]),
        option_text="Yes",
    )

    voter_hash = voting_service.generate_voter_hash(
        _to_uuid(poll["id"]),
        phone="+233201234567",
    )

    vote = await voting_service.cast_vote(
        db_connection,
        election_id=_to_uuid(poll["id"]),
        voter_hash=voter_hash,
        poll_option_id=_to_uuid(option["id"]),
    )

    assert vote is not None
    assert vote["poll_option_id"] == option["id"]


@pytest.mark.asyncio
async def test_cast_votes_batch(db_connection):
    """Test casting multiple votes in a batch."""
    user = await create_test_user(db_connection)
    election = await create_active_election(db_connection, user)

    pos1 = await elections_service.add_position(
        db_connection,
        election_id=_to_uuid(election["id"]),
        title="President",
    )
    pos2 = await elections_service.add_position(
        db_connection,
        election_id=_to_uuid(election["id"]),
        title="Vice President",
    )

    cand1 = await elections_service.add_candidate(
        db_connection,
        position_id=_to_uuid(pos1["id"]),
        name="Presidential Candidate",
    )
    cand2 = await elections_service.add_candidate(
        db_connection,
        position_id=_to_uuid(pos2["id"]),
        name="VP Candidate",
    )

    voter_hash = voting_service.generate_voter_hash(
        _to_uuid(election["id"]),
        national_id=f"GHA-{uuid4().hex[:10]}",
    )

    votes = [
        {"position_id": _to_uuid(pos1["id"]), "candidate_id": _to_uuid(cand1["id"])},
        {"position_id": _to_uuid(pos2["id"]), "candidate_id": _to_uuid(cand2["id"])},
    ]

    results = await voting_service.cast_votes_batch(
        db_connection,
        election_id=_to_uuid(election["id"]),
        voter_hash=voter_hash,
        votes=votes,
    )

    assert len(results) == 2


@pytest.mark.asyncio
async def test_cast_ranked_votes(db_connection):
    """Test casting ranked-choice votes."""
    user = await create_test_user(db_connection)

    # Create a ranked-choice election
    election = await elections_service.create_election(
        db_connection,
        organization_id=user["organization_id"],
        title="Ranked Choice Election",
        election_type="election",
        voting_method="ranked_choice",
        start_date=datetime.now(timezone.utc) - timedelta(hours=1),
        end_date=datetime.now(timezone.utc) + timedelta(days=7),
        created_by=user["id"],
    )
    await elections_service.publish_election(db_connection, _to_uuid(election["id"]))

    position = await elections_service.add_position(
        db_connection,
        election_id=_to_uuid(election["id"]),
        title="Board Member",
        max_selections=3,
    )

    cand1 = await elections_service.add_candidate(
        db_connection,
        position_id=_to_uuid(position["id"]),
        name="Candidate A",
    )
    cand2 = await elections_service.add_candidate(
        db_connection,
        position_id=_to_uuid(position["id"]),
        name="Candidate B",
    )
    cand3 = await elections_service.add_candidate(
        db_connection,
        position_id=_to_uuid(position["id"]),
        name="Candidate C",
    )

    voter_hash = voting_service.generate_voter_hash(
        _to_uuid(election["id"]),
        national_id=f"GHA-{uuid4().hex[:10]}",
    )

    rankings = [
        {"candidate_id": _to_uuid(cand1["id"]), "rank": 1},
        {"candidate_id": _to_uuid(cand2["id"]), "rank": 2},
        {"candidate_id": _to_uuid(cand3["id"]), "rank": 3},
    ]

    results = await voting_service.cast_ranked_votes(
        db_connection,
        election_id=_to_uuid(election["id"]),
        voter_hash=voter_hash,
        position_id=_to_uuid(position["id"]),
        rankings=rankings,
    )

    assert len(results) == 3


# ============================================
# VOTE COUNTING TESTS
# ============================================


@pytest.mark.asyncio
async def test_get_vote_count(db_connection):
    """Test getting vote count."""
    user = await create_test_user(db_connection)
    election = await create_active_election(db_connection, user)

    position = await elections_service.add_position(
        db_connection,
        election_id=_to_uuid(election["id"]),
        title="President",
    )

    candidate = await elections_service.add_candidate(
        db_connection,
        position_id=_to_uuid(position["id"]),
        name="Candidate",
    )

    # Cast multiple votes
    for i in range(5):
        voter_hash = voting_service.generate_voter_hash(
            _to_uuid(election["id"]),
            national_id=f"GHA-{uuid4().hex[:10]}",
        )
        await voting_service.cast_vote(
            db_connection,
            election_id=_to_uuid(election["id"]),
            voter_hash=voter_hash,
            position_id=_to_uuid(position["id"]),
            candidate_id=_to_uuid(candidate["id"]),
        )

    count = await voting_service.get_vote_count(
        db_connection,
        election_id=_to_uuid(election["id"]),
        candidate_id=_to_uuid(candidate["id"]),
    )

    assert count == 5


@pytest.mark.asyncio
async def test_get_unique_voter_count(db_connection):
    """Test getting unique voter count."""
    user = await create_test_user(db_connection)
    election = await create_active_election(db_connection, user)

    pos1 = await elections_service.add_position(
        db_connection,
        election_id=_to_uuid(election["id"]),
        title="President",
    )
    pos2 = await elections_service.add_position(
        db_connection,
        election_id=_to_uuid(election["id"]),
        title="Vice President",
    )

    cand1 = await elections_service.add_candidate(
        db_connection,
        position_id=_to_uuid(pos1["id"]),
        name="Pres Candidate",
    )
    cand2 = await elections_service.add_candidate(
        db_connection,
        position_id=_to_uuid(pos2["id"]),
        name="VP Candidate",
    )

    # One voter casts 2 votes (one per position)
    voter_hash = voting_service.generate_voter_hash(
        _to_uuid(election["id"]),
        national_id=f"GHA-{uuid4().hex[:10]}",
    )
    await voting_service.cast_vote(
        db_connection,
        election_id=_to_uuid(election["id"]),
        voter_hash=voter_hash,
        position_id=_to_uuid(pos1["id"]),
        candidate_id=_to_uuid(cand1["id"]),
    )
    await voting_service.cast_vote(
        db_connection,
        election_id=_to_uuid(election["id"]),
        voter_hash=voter_hash,
        position_id=_to_uuid(pos2["id"]),
        candidate_id=_to_uuid(cand2["id"]),
    )

    unique_count = await voting_service.get_unique_voter_count(
        db_connection, _to_uuid(election["id"])
    )

    # Should be 1 unique voter even though 2 votes were cast
    assert unique_count == 1


# ============================================
# CHECK CAN VOTE TESTS
# ============================================


@pytest.mark.asyncio
async def test_check_can_vote_active_election(db_connection):
    """Test that voting is allowed in an active election."""
    user = await create_test_user(db_connection)
    election = await create_active_election(db_connection, user)

    voter_hash = voting_service.generate_voter_hash(
        _to_uuid(election["id"]),
        national_id=f"GHA-{uuid4().hex[:10]}",
    )

    can_vote, reason = await voting_service.check_can_vote(
        db_connection,
        election_id=_to_uuid(election["id"]),
        voter_hash=voter_hash,
    )

    assert can_vote is True
    assert reason == "OK"


@pytest.mark.asyncio
async def test_check_can_vote_draft_election(db_connection):
    """Test that voting is not allowed in a draft election."""
    user = await create_test_user(db_connection)

    # Create but don't publish
    election = await elections_service.create_election(
        db_connection,
        organization_id=user["organization_id"],
        title="Draft Election",
        election_type="election",
        voting_method="single_choice",
        start_date=datetime.now(timezone.utc) - timedelta(hours=1),
        end_date=datetime.now(timezone.utc) + timedelta(days=7),
        created_by=user["id"],
    )

    voter_hash = voting_service.generate_voter_hash(
        _to_uuid(election["id"]),
        national_id=f"GHA-{uuid4().hex[:10]}",
    )

    can_vote, reason = await voting_service.check_can_vote(
        db_connection,
        election_id=_to_uuid(election["id"]),
        voter_hash=voter_hash,
    )

    assert can_vote is False
    assert "draft" in reason.lower()


# ============================================
# VOTE RECEIPT TESTS
# ============================================


@pytest.mark.asyncio
async def test_generate_vote_receipt(db_connection):
    """Test generating a vote receipt."""
    user = await create_test_user(db_connection)
    election = await create_active_election(db_connection, user)

    position = await elections_service.add_position(
        db_connection,
        election_id=_to_uuid(election["id"]),
        title="President",
    )

    candidate = await elections_service.add_candidate(
        db_connection,
        position_id=_to_uuid(position["id"]),
        name="Candidate",
    )

    voter_hash = voting_service.generate_voter_hash(
        _to_uuid(election["id"]),
        national_id=f"GHA-{uuid4().hex[:10]}",
    )

    await voting_service.cast_vote(
        db_connection,
        election_id=_to_uuid(election["id"]),
        voter_hash=voter_hash,
        position_id=_to_uuid(position["id"]),
        candidate_id=_to_uuid(candidate["id"]),
    )

    receipt = await voting_service.generate_vote_receipt(
        db_connection,
        election_id=_to_uuid(election["id"]),
        voter_hash=voter_hash,
    )

    assert receipt is not None
    assert receipt["votes_cast"] == 1
    assert receipt["confirmation_code"] is not None


# ============================================
# VOTE VALIDATION TESTS
# ============================================


@pytest.mark.asyncio
async def test_validate_vote_selections_valid(db_connection):
    """Test validating valid vote selections."""
    user = await create_test_user(db_connection)
    election = await create_active_election(db_connection, user)

    position = await elections_service.add_position(
        db_connection,
        election_id=_to_uuid(election["id"]),
        title="President",
        max_selections=1,
    )

    candidate = await elections_service.add_candidate(
        db_connection,
        position_id=_to_uuid(position["id"]),
        name="Candidate",
    )

    votes = [
        {"position_id": position["id"], "candidate_id": candidate["id"]},
    ]

    is_valid, errors = await voting_service.validate_vote_selections(
        db_connection,
        election_id=_to_uuid(election["id"]),
        votes=votes,
    )

    assert is_valid is True
    assert len(errors) == 0


@pytest.mark.asyncio
async def test_validate_vote_selections_invalid_candidate(db_connection):
    """Test validating vote with invalid candidate."""
    user = await create_test_user(db_connection)
    election = await create_active_election(db_connection, user)

    position = await elections_service.add_position(
        db_connection,
        election_id=_to_uuid(election["id"]),
        title="President",
    )

    votes = [
        {"position_id": position["id"], "candidate_id": str(uuid4())},
    ]

    is_valid, errors = await voting_service.validate_vote_selections(
        db_connection,
        election_id=_to_uuid(election["id"]),
        votes=votes,
    )

    assert is_valid is False
    assert len(errors) > 0


# ============================================
# HELPER FUNCTION TESTS
# ============================================


def test_hash_identifier():
    """Test that identifier hashing is consistent."""
    identifier = "GHA-1234567890"

    hash1 = voting_service.hash_identifier(identifier)
    hash2 = voting_service.hash_identifier(identifier)

    assert hash1 == hash2
    assert len(hash1) == 64  # SHA-256 produces 64 hex characters


def test_generate_voter_hash():
    """Test voter hash generation."""
    election_id = uuid4()

    # Same input should produce same hash
    hash1 = voting_service.generate_voter_hash(election_id, national_id="GHA-123")
    hash2 = voting_service.generate_voter_hash(election_id, national_id="GHA-123")
    assert hash1 == hash2

    # Different input should produce different hash
    hash3 = voting_service.generate_voter_hash(election_id, national_id="GHA-456")
    assert hash1 != hash3
