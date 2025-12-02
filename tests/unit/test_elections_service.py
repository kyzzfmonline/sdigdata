"""Unit tests for elections service."""

import pytest
from uuid import UUID, uuid4
from datetime import datetime, timedelta, timezone

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


# ============================================
# ELECTION CRUD TESTS
# ============================================


@pytest.mark.asyncio
async def test_create_election(db_connection):
    """Test creating an election."""
    user = await create_test_user(db_connection)

    election = await elections_service.create_election(
        db_connection,
        organization_id=user["organization_id"],
        title="Presidential Election 2024",
        election_type="election",
        voting_method="single_choice",
        start_date=datetime.now(timezone.utc),
        end_date=datetime.now(timezone.utc) + timedelta(days=7),
        created_by=user["id"],
        description="National presidential election",
    )

    assert election is not None
    assert election["title"] == "Presidential Election 2024"
    assert election["election_type"] == "election"
    assert election["voting_method"] == "single_choice"
    assert election["status"] == "draft"


@pytest.mark.asyncio
async def test_get_election_by_id(db_connection):
    """Test getting an election by ID."""
    user = await create_test_user(db_connection)

    created = await elections_service.create_election(
        db_connection,
        organization_id=user["organization_id"],
        title="Test Election",
        election_type="poll",
        voting_method="single_choice",
        start_date=datetime.now(timezone.utc),
        end_date=datetime.now(timezone.utc) + timedelta(days=1),
        created_by=user["id"],
    )

    election = await elections_service.get_election_by_id(
        db_connection, _to_uuid(created["id"])
    )

    assert election is not None
    assert election["title"] == "Test Election"
    assert election["election_type"] == "poll"


@pytest.mark.asyncio
async def test_list_elections(db_connection):
    """Test listing elections."""
    user = await create_test_user(db_connection)

    await elections_service.create_election(
        db_connection,
        organization_id=user["organization_id"],
        title="Election A",
        election_type="election",
        voting_method="single_choice",
        start_date=datetime.now(timezone.utc),
        end_date=datetime.now(timezone.utc) + timedelta(days=1),
        created_by=user["id"],
    )
    await elections_service.create_election(
        db_connection,
        organization_id=user["organization_id"],
        title="Poll B",
        election_type="poll",
        voting_method="multi_choice",
        start_date=datetime.now(timezone.utc),
        end_date=datetime.now(timezone.utc) + timedelta(days=1),
        created_by=user["id"],
    )

    # List all elections for the org
    elections = await elections_service.list_elections(
        db_connection, organization_id=user["organization_id"]
    )
    assert len(elections) >= 2

    # Filter by election type
    polls = await elections_service.list_elections(
        db_connection,
        organization_id=user["organization_id"],
        election_type="poll",
    )
    assert all(e["election_type"] == "poll" for e in polls)


@pytest.mark.asyncio
async def test_update_election(db_connection):
    """Test updating an election."""
    user = await create_test_user(db_connection)

    election = await elections_service.create_election(
        db_connection,
        organization_id=user["organization_id"],
        title="Original Title",
        election_type="election",
        voting_method="single_choice",
        start_date=datetime.now(timezone.utc),
        end_date=datetime.now(timezone.utc) + timedelta(days=1),
        created_by=user["id"],
    )

    updated = await elections_service.update_election(
        db_connection,
        _to_uuid(election["id"]),
        title="Updated Title",
        description="New description",
    )

    assert updated is not None
    assert updated["title"] == "Updated Title"
    assert updated["description"] == "New description"


@pytest.mark.asyncio
async def test_delete_election(db_connection):
    """Test soft deleting an election."""
    user = await create_test_user(db_connection)

    election = await elections_service.create_election(
        db_connection,
        organization_id=user["organization_id"],
        title="To Be Deleted",
        election_type="election",
        voting_method="single_choice",
        start_date=datetime.now(timezone.utc),
        end_date=datetime.now(timezone.utc) + timedelta(days=1),
        created_by=user["id"],
    )

    result = await elections_service.delete_election(
        db_connection, _to_uuid(election["id"])
    )
    assert result is True

    # Verify it's no longer found
    deleted = await elections_service.get_election_by_id(
        db_connection, _to_uuid(election["id"])
    )
    assert deleted is None


# ============================================
# ELECTION LIFECYCLE TESTS
# ============================================


@pytest.mark.asyncio
async def test_publish_election_scheduled(db_connection):
    """Test publishing an election that becomes scheduled."""
    user = await create_test_user(db_connection)

    # Create election starting in the future
    election = await elections_service.create_election(
        db_connection,
        organization_id=user["organization_id"],
        title="Future Election",
        election_type="election",
        voting_method="single_choice",
        start_date=datetime.now(timezone.utc) + timedelta(days=7),
        end_date=datetime.now(timezone.utc) + timedelta(days=14),
        created_by=user["id"],
    )

    published = await elections_service.publish_election(
        db_connection, _to_uuid(election["id"])
    )

    assert published is not None
    assert published["status"] == "scheduled"


@pytest.mark.asyncio
async def test_publish_election_active(db_connection):
    """Test publishing an election that becomes active immediately."""
    user = await create_test_user(db_connection)

    # Create election that should be active now
    election = await elections_service.create_election(
        db_connection,
        organization_id=user["organization_id"],
        title="Active Election",
        election_type="election",
        voting_method="single_choice",
        start_date=datetime.now(timezone.utc) - timedelta(hours=1),
        end_date=datetime.now(timezone.utc) + timedelta(days=7),
        created_by=user["id"],
    )

    published = await elections_service.publish_election(
        db_connection, _to_uuid(election["id"])
    )

    assert published is not None
    assert published["status"] == "active"


@pytest.mark.asyncio
async def test_pause_and_resume_election(db_connection):
    """Test pausing and resuming an election."""
    user = await create_test_user(db_connection)

    election = await elections_service.create_election(
        db_connection,
        organization_id=user["organization_id"],
        title="Pauseable Election",
        election_type="election",
        voting_method="single_choice",
        start_date=datetime.now(timezone.utc) - timedelta(hours=1),
        end_date=datetime.now(timezone.utc) + timedelta(days=7),
        created_by=user["id"],
    )

    # Publish it first
    await elections_service.publish_election(
        db_connection, _to_uuid(election["id"])
    )

    # Pause
    paused = await elections_service.pause_election(
        db_connection, _to_uuid(election["id"])
    )
    assert paused is not None
    assert paused["status"] == "paused"

    # Resume
    resumed = await elections_service.resume_election(
        db_connection, _to_uuid(election["id"])
    )
    assert resumed is not None
    assert resumed["status"] == "active"


@pytest.mark.asyncio
async def test_close_election(db_connection):
    """Test closing an election."""
    user = await create_test_user(db_connection)

    election = await elections_service.create_election(
        db_connection,
        organization_id=user["organization_id"],
        title="Closeable Election",
        election_type="election",
        voting_method="single_choice",
        start_date=datetime.now(timezone.utc) - timedelta(hours=1),
        end_date=datetime.now(timezone.utc) + timedelta(days=7),
        created_by=user["id"],
    )

    # Publish it first
    await elections_service.publish_election(
        db_connection, _to_uuid(election["id"])
    )

    # Close
    closed = await elections_service.close_election(
        db_connection, _to_uuid(election["id"])
    )
    assert closed is not None
    assert closed["status"] == "closed"


@pytest.mark.asyncio
async def test_cancel_election(db_connection):
    """Test cancelling an election."""
    user = await create_test_user(db_connection)

    election = await elections_service.create_election(
        db_connection,
        organization_id=user["organization_id"],
        title="Cancellable Election",
        election_type="election",
        voting_method="single_choice",
        start_date=datetime.now(timezone.utc) + timedelta(days=7),
        end_date=datetime.now(timezone.utc) + timedelta(days=14),
        created_by=user["id"],
    )

    cancelled = await elections_service.cancel_election(
        db_connection, _to_uuid(election["id"])
    )
    assert cancelled is not None
    assert cancelled["status"] == "cancelled"


# ============================================
# POSITION TESTS
# ============================================


@pytest.mark.asyncio
async def test_add_position(db_connection):
    """Test adding a position to an election."""
    user = await create_test_user(db_connection)

    election = await elections_service.create_election(
        db_connection,
        organization_id=user["organization_id"],
        title="Election with Positions",
        election_type="election",
        voting_method="single_choice",
        start_date=datetime.now(timezone.utc),
        end_date=datetime.now(timezone.utc) + timedelta(days=7),
        created_by=user["id"],
    )

    position = await elections_service.add_position(
        db_connection,
        election_id=_to_uuid(election["id"]),
        title="President",
        description="Vote for your preferred president",
        max_selections=1,
    )

    assert position is not None
    assert position["title"] == "President"
    assert position["max_selections"] == 1


@pytest.mark.asyncio
async def test_list_positions(db_connection):
    """Test listing positions for an election."""
    user = await create_test_user(db_connection)

    election = await elections_service.create_election(
        db_connection,
        organization_id=user["organization_id"],
        title="Multi-Position Election",
        election_type="election",
        voting_method="single_choice",
        start_date=datetime.now(timezone.utc),
        end_date=datetime.now(timezone.utc) + timedelta(days=7),
        created_by=user["id"],
    )

    await elections_service.add_position(
        db_connection,
        election_id=_to_uuid(election["id"]),
        title="President",
    )
    await elections_service.add_position(
        db_connection,
        election_id=_to_uuid(election["id"]),
        title="Vice President",
    )

    positions = await elections_service.list_positions(
        db_connection, _to_uuid(election["id"])
    )
    assert len(positions) == 2


@pytest.mark.asyncio
async def test_update_position(db_connection):
    """Test updating a position."""
    user = await create_test_user(db_connection)

    election = await elections_service.create_election(
        db_connection,
        organization_id=user["organization_id"],
        title="Election for Update Test",
        election_type="election",
        voting_method="single_choice",
        start_date=datetime.now(timezone.utc),
        end_date=datetime.now(timezone.utc) + timedelta(days=7),
        created_by=user["id"],
    )

    position = await elections_service.add_position(
        db_connection,
        election_id=_to_uuid(election["id"]),
        title="Original Position",
    )

    updated = await elections_service.update_position(
        db_connection,
        position_id=_to_uuid(position["id"]),
        title="Updated Position",
        max_selections=3,
    )

    assert updated is not None
    assert updated["title"] == "Updated Position"
    assert updated["max_selections"] == 3


@pytest.mark.asyncio
async def test_delete_position(db_connection):
    """Test deleting a position."""
    user = await create_test_user(db_connection)

    election = await elections_service.create_election(
        db_connection,
        organization_id=user["organization_id"],
        title="Election for Delete Test",
        election_type="election",
        voting_method="single_choice",
        start_date=datetime.now(timezone.utc),
        end_date=datetime.now(timezone.utc) + timedelta(days=7),
        created_by=user["id"],
    )

    position = await elections_service.add_position(
        db_connection,
        election_id=_to_uuid(election["id"]),
        title="To Be Deleted",
    )

    result = await elections_service.delete_position(
        db_connection, _to_uuid(position["id"])
    )
    assert result is True


# ============================================
# CANDIDATE TESTS
# ============================================


@pytest.mark.asyncio
async def test_add_candidate(db_connection):
    """Test adding a candidate to a position."""
    user = await create_test_user(db_connection)

    election = await elections_service.create_election(
        db_connection,
        organization_id=user["organization_id"],
        title="Election with Candidates",
        election_type="election",
        voting_method="single_choice",
        start_date=datetime.now(timezone.utc),
        end_date=datetime.now(timezone.utc) + timedelta(days=7),
        created_by=user["id"],
    )

    position = await elections_service.add_position(
        db_connection,
        election_id=_to_uuid(election["id"]),
        title="President",
    )

    candidate = await elections_service.add_candidate(
        db_connection,
        position_id=_to_uuid(position["id"]),
        name="John Doe",
        party="Independent",
        bio="A candidate for the people",
    )

    assert candidate is not None
    assert candidate["name"] == "John Doe"
    assert candidate["party"] == "Independent"


@pytest.mark.asyncio
async def test_list_candidates(db_connection):
    """Test listing candidates for a position."""
    user = await create_test_user(db_connection)

    election = await elections_service.create_election(
        db_connection,
        organization_id=user["organization_id"],
        title="Election for Candidate List",
        election_type="election",
        voting_method="single_choice",
        start_date=datetime.now(timezone.utc),
        end_date=datetime.now(timezone.utc) + timedelta(days=7),
        created_by=user["id"],
    )

    position = await elections_service.add_position(
        db_connection,
        election_id=_to_uuid(election["id"]),
        title="President",
    )

    await elections_service.add_candidate(
        db_connection,
        position_id=_to_uuid(position["id"]),
        name="Candidate A",
        party="Party A",
    )
    await elections_service.add_candidate(
        db_connection,
        position_id=_to_uuid(position["id"]),
        name="Candidate B",
        party="Party B",
    )

    candidates = await elections_service.list_candidates(
        db_connection, _to_uuid(position["id"])
    )
    assert len(candidates) == 2


@pytest.mark.asyncio
async def test_list_all_candidates_for_election(db_connection):
    """Test listing all candidates across all positions for an election."""
    user = await create_test_user(db_connection)

    election = await elections_service.create_election(
        db_connection,
        organization_id=user["organization_id"],
        title="Multi-Position Election for All Candidates",
        election_type="election",
        voting_method="single_choice",
        start_date=datetime.now(timezone.utc),
        end_date=datetime.now(timezone.utc) + timedelta(days=7),
        created_by=user["id"],
    )

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

    await elections_service.add_candidate(
        db_connection,
        position_id=_to_uuid(pos1["id"]),
        name="Presidential Candidate",
    )
    await elections_service.add_candidate(
        db_connection,
        position_id=_to_uuid(pos2["id"]),
        name="VP Candidate 1",
    )
    await elections_service.add_candidate(
        db_connection,
        position_id=_to_uuid(pos2["id"]),
        name="VP Candidate 2",
    )

    all_candidates = await elections_service.list_all_candidates_for_election(
        db_connection, _to_uuid(election["id"])
    )
    assert len(all_candidates) == 3


@pytest.mark.asyncio
async def test_update_candidate(db_connection):
    """Test updating a candidate."""
    user = await create_test_user(db_connection)

    election = await elections_service.create_election(
        db_connection,
        organization_id=user["organization_id"],
        title="Election for Candidate Update",
        election_type="election",
        voting_method="single_choice",
        start_date=datetime.now(timezone.utc),
        end_date=datetime.now(timezone.utc) + timedelta(days=7),
        created_by=user["id"],
    )

    position = await elections_service.add_position(
        db_connection,
        election_id=_to_uuid(election["id"]),
        title="President",
    )

    candidate = await elections_service.add_candidate(
        db_connection,
        position_id=_to_uuid(position["id"]),
        name="Original Name",
        party="Original Party",
    )

    updated = await elections_service.update_candidate(
        db_connection,
        candidate_id=_to_uuid(candidate["id"]),
        name="Updated Name",
        bio="Updated bio information",
    )

    assert updated is not None
    assert updated["name"] == "Updated Name"
    assert updated["bio"] == "Updated bio information"
    assert updated["party"] == "Original Party"  # Unchanged


@pytest.mark.asyncio
async def test_delete_candidate(db_connection):
    """Test deleting a candidate."""
    user = await create_test_user(db_connection)

    election = await elections_service.create_election(
        db_connection,
        organization_id=user["organization_id"],
        title="Election for Candidate Delete",
        election_type="election",
        voting_method="single_choice",
        start_date=datetime.now(timezone.utc),
        end_date=datetime.now(timezone.utc) + timedelta(days=7),
        created_by=user["id"],
    )

    position = await elections_service.add_position(
        db_connection,
        election_id=_to_uuid(election["id"]),
        title="President",
    )

    candidate = await elections_service.add_candidate(
        db_connection,
        position_id=_to_uuid(position["id"]),
        name="To Be Deleted",
    )

    result = await elections_service.delete_candidate(
        db_connection, _to_uuid(candidate["id"])
    )
    assert result is True


# ============================================
# POLL OPTION TESTS
# ============================================


@pytest.mark.asyncio
async def test_add_poll_option(db_connection):
    """Test adding a poll option."""
    user = await create_test_user(db_connection)

    election = await elections_service.create_election(
        db_connection,
        organization_id=user["organization_id"],
        title="Poll with Options",
        election_type="poll",
        voting_method="single_choice",
        start_date=datetime.now(timezone.utc),
        end_date=datetime.now(timezone.utc) + timedelta(days=7),
        created_by=user["id"],
    )

    option = await elections_service.add_poll_option(
        db_connection,
        election_id=_to_uuid(election["id"]),
        option_text="Yes",
        description="Vote yes to approve",
    )

    assert option is not None
    assert option["option_text"] == "Yes"
    assert option["description"] == "Vote yes to approve"


@pytest.mark.asyncio
async def test_list_poll_options(db_connection):
    """Test listing poll options."""
    user = await create_test_user(db_connection)

    election = await elections_service.create_election(
        db_connection,
        organization_id=user["organization_id"],
        title="Poll for Options List",
        election_type="poll",
        voting_method="single_choice",
        start_date=datetime.now(timezone.utc),
        end_date=datetime.now(timezone.utc) + timedelta(days=7),
        created_by=user["id"],
    )

    await elections_service.add_poll_option(
        db_connection,
        election_id=_to_uuid(election["id"]),
        option_text="Yes",
    )
    await elections_service.add_poll_option(
        db_connection,
        election_id=_to_uuid(election["id"]),
        option_text="No",
    )
    await elections_service.add_poll_option(
        db_connection,
        election_id=_to_uuid(election["id"]),
        option_text="Abstain",
    )

    options = await elections_service.list_poll_options(
        db_connection, _to_uuid(election["id"])
    )
    assert len(options) == 3


@pytest.mark.asyncio
async def test_update_poll_option(db_connection):
    """Test updating a poll option."""
    user = await create_test_user(db_connection)

    election = await elections_service.create_election(
        db_connection,
        organization_id=user["organization_id"],
        title="Poll for Option Update",
        election_type="poll",
        voting_method="single_choice",
        start_date=datetime.now(timezone.utc),
        end_date=datetime.now(timezone.utc) + timedelta(days=7),
        created_by=user["id"],
    )

    option = await elections_service.add_poll_option(
        db_connection,
        election_id=_to_uuid(election["id"]),
        option_text="Original Text",
    )

    updated = await elections_service.update_poll_option(
        db_connection,
        option_id=_to_uuid(option["id"]),
        option_text="Updated Text",
        description="New description",
    )

    assert updated is not None
    assert updated["option_text"] == "Updated Text"
    assert updated["description"] == "New description"


@pytest.mark.asyncio
async def test_delete_poll_option(db_connection):
    """Test deleting a poll option."""
    user = await create_test_user(db_connection)

    election = await elections_service.create_election(
        db_connection,
        organization_id=user["organization_id"],
        title="Poll for Option Delete",
        election_type="poll",
        voting_method="single_choice",
        start_date=datetime.now(timezone.utc),
        end_date=datetime.now(timezone.utc) + timedelta(days=7),
        created_by=user["id"],
    )

    option = await elections_service.add_poll_option(
        db_connection,
        election_id=_to_uuid(election["id"]),
        option_text="To Be Deleted",
    )

    result = await elections_service.delete_poll_option(
        db_connection, _to_uuid(option["id"])
    )
    assert result is True


# ============================================
# AUDIT LOG TESTS
# ============================================


@pytest.mark.asyncio
async def test_log_election_action(db_connection):
    """Test logging an election action."""
    user = await create_test_user(db_connection)

    election = await elections_service.create_election(
        db_connection,
        organization_id=user["organization_id"],
        title="Election for Audit",
        election_type="election",
        voting_method="single_choice",
        start_date=datetime.now(timezone.utc),
        end_date=datetime.now(timezone.utc) + timedelta(days=7),
        created_by=user["id"],
    )

    log_entry = await elections_service.log_election_action(
        db_connection,
        election_id=_to_uuid(election["id"]),
        action="published",
        actor_id=user["id"],
        details={"reason": "Ready for voting"},
        ip_address="192.168.1.1",
    )

    assert log_entry is not None
    assert log_entry["action"] == "published"
    assert log_entry["details"]["reason"] == "Ready for voting"


@pytest.mark.asyncio
async def test_get_election_audit_log(db_connection):
    """Test getting the audit log for an election."""
    user = await create_test_user(db_connection)

    election = await elections_service.create_election(
        db_connection,
        organization_id=user["organization_id"],
        title="Election for Audit Log",
        election_type="election",
        voting_method="single_choice",
        start_date=datetime.now(timezone.utc),
        end_date=datetime.now(timezone.utc) + timedelta(days=7),
        created_by=user["id"],
    )

    await elections_service.log_election_action(
        db_connection,
        election_id=_to_uuid(election["id"]),
        action="created",
        actor_id=user["id"],
    )
    await elections_service.log_election_action(
        db_connection,
        election_id=_to_uuid(election["id"]),
        action="published",
        actor_id=user["id"],
    )

    logs = await elections_service.get_election_audit_log(
        db_connection, _to_uuid(election["id"])
    )
    assert len(logs) >= 2
