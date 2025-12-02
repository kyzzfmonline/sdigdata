"""Unit tests for result sheets service."""

import pytest
from uuid import UUID, uuid4

from app.services import result_sheets as sheets_service
from app.services import geographic as geo_service
from app.services import elections as election_service
from app.services.organizations import create_organization
from app.services.users import create_user
from app.core.security import hash_password


def _to_uuid(val) -> UUID:
    """Convert a value to UUID, handling asyncpg UUID objects."""
    if isinstance(val, UUID):
        return val
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


async def create_test_hierarchy(db_connection, org_id: UUID):
    """Helper to create a full geographic hierarchy."""
    unique_suffix = uuid4().hex[:6]

    region = await geo_service.create_region(
        db_connection, organization_id=org_id, name=f"Test Region {unique_suffix}", code=f"TR{unique_suffix}"
    )
    constituency = await geo_service.create_constituency(
        db_connection, organization_id=org_id, region_id=_to_uuid(region["id"]), name=f"Test Const {unique_suffix}", code=f"TC{unique_suffix}"
    )
    electoral_area = await geo_service.create_electoral_area(
        db_connection, organization_id=org_id, constituency_id=_to_uuid(constituency["id"]), name=f"Test EA {unique_suffix}", code=f"TEA{unique_suffix}"
    )
    polling_station = await geo_service.create_polling_station(
        db_connection,
        organization_id=org_id,
        electoral_area_id=_to_uuid(electoral_area["id"]),
        name=f"Test Station {unique_suffix}",
        code=f"TS{unique_suffix}",
        registered_voters=500,
    )
    return {
        "region": region,
        "constituency": constituency,
        "electoral_area": electoral_area,
        "polling_station": polling_station,
    }


async def create_test_position(db_connection, election_id: UUID):
    """Helper to create a test election position."""
    unique_suffix = uuid4().hex[:6]
    row = await db_connection.fetchrow(
        """
        INSERT INTO election_positions (election_id, title, description, max_selections, display_order)
        VALUES ($1, $2, $3, 1, 1)
        RETURNING *
        """,
        election_id,
        f"President {unique_suffix}",
        "Presidential election position",
    )
    result = dict(row)
    for key in list(result.keys()):
        if hasattr(result[key], 'hex'):
            result[key] = str(result[key])
    return result


async def create_test_election(db_connection, org_id, user_id):
    """Helper to create a test election with a position."""
    from datetime import datetime, timedelta

    election = await election_service.create_election(
        db_connection,
        title=f"Test Election {uuid4().hex[:8]}",
        election_type="election",
        voting_method="single_choice",
        start_date=datetime.now(),
        end_date=datetime.now() + timedelta(days=1),
        organization_id=org_id,
        created_by=user_id,
    )

    position = await create_test_position(db_connection, _to_uuid(election["id"]))

    return {
        "election": election,
        "position": position,
    }


async def create_sheet_with_entry(db_connection, user, hierarchy, election_data):
    """Helper to create a result sheet with an entry."""
    election = election_data["election"]
    position = election_data["position"]

    sheet = await sheets_service.create_result_sheet(
        db_connection,
        election_id=_to_uuid(election["id"]),
        position_id=_to_uuid(position["id"]),
        polling_station_id=_to_uuid(hierarchy["polling_station"]["id"]),
        sheet_type="primary",
        created_by=user["id"],
    )

    await sheets_service.add_result_entry(
        db_connection,
        result_sheet_id=_to_uuid(sheet["id"]),
        candidate_name="John Doe",
        party="NPP",
        votes=100,
    )

    return sheet


@pytest.mark.asyncio
async def test_create_result_sheet(db_connection):
    """Test creating a result sheet."""
    user = await create_test_user(db_connection)
    hierarchy = await create_test_hierarchy(db_connection, user["organization_id"])
    election_data = await create_test_election(db_connection, user["organization_id"], user["id"])
    election = election_data["election"]
    position = election_data["position"]

    sheet = await sheets_service.create_result_sheet(
        db_connection,
        election_id=_to_uuid(election["id"]),
        position_id=_to_uuid(position["id"]),
        polling_station_id=_to_uuid(hierarchy["polling_station"]["id"]),
        sheet_type="primary",
        created_by=user["id"],
    )

    assert sheet is not None
    assert sheet["election_id"] == election["id"]
    assert sheet["position_id"] == position["id"]
    assert sheet["polling_station_id"] == hierarchy["polling_station"]["id"]
    assert sheet["sheet_type"] == "primary"
    assert sheet["status"] == "draft"


@pytest.mark.asyncio
async def test_get_result_sheet(db_connection):
    """Test getting a result sheet by ID."""
    user = await create_test_user(db_connection)
    hierarchy = await create_test_hierarchy(db_connection, user["organization_id"])
    election_data = await create_test_election(db_connection, user["organization_id"], user["id"])
    election = election_data["election"]
    position = election_data["position"]

    created = await sheets_service.create_result_sheet(
        db_connection,
        election_id=_to_uuid(election["id"]),
        position_id=_to_uuid(position["id"]),
        polling_station_id=_to_uuid(hierarchy["polling_station"]["id"]),
        sheet_type="primary",
        created_by=user["id"],
    )

    sheet = await sheets_service.get_result_sheet(db_connection, _to_uuid(created["id"]))

    assert sheet is not None
    assert sheet["id"] == created["id"]
    assert "polling_station_name" in sheet or sheet.get("polling_station_id") is not None


@pytest.mark.asyncio
async def test_list_result_sheets(db_connection):
    """Test listing result sheets for an election."""
    user = await create_test_user(db_connection)
    hierarchy = await create_test_hierarchy(db_connection, user["organization_id"])
    election_data = await create_test_election(db_connection, user["organization_id"], user["id"])
    election = election_data["election"]
    position = election_data["position"]

    await sheets_service.create_result_sheet(
        db_connection,
        election_id=_to_uuid(election["id"]),
        position_id=_to_uuid(position["id"]),
        polling_station_id=_to_uuid(hierarchy["polling_station"]["id"]),
        sheet_type="primary",
        created_by=user["id"],
    )

    sheets = await sheets_service.list_result_sheets(db_connection, _to_uuid(election["id"]))

    assert len(sheets) >= 1


@pytest.mark.asyncio
async def test_add_result_entry(db_connection):
    """Test adding vote entries to a result sheet."""
    user = await create_test_user(db_connection)
    hierarchy = await create_test_hierarchy(db_connection, user["organization_id"])
    election_data = await create_test_election(db_connection, user["organization_id"], user["id"])
    election = election_data["election"]
    position = election_data["position"]

    sheet = await sheets_service.create_result_sheet(
        db_connection,
        election_id=_to_uuid(election["id"]),
        position_id=_to_uuid(position["id"]),
        polling_station_id=_to_uuid(hierarchy["polling_station"]["id"]),
        sheet_type="primary",
        created_by=user["id"],
    )

    entry = await sheets_service.add_result_entry(
        db_connection,
        result_sheet_id=_to_uuid(sheet["id"]),
        candidate_name="Jane Doe",
        party="NDC",
        votes=150,
        votes_in_words="One hundred and fifty",
    )

    assert entry is not None
    assert entry["votes_in_figures"] == 150
    assert entry["votes_in_words"] == "One hundred and fifty"
    assert entry["candidate_name"] == "Jane Doe"


@pytest.mark.asyncio
async def test_bulk_update_entries(db_connection):
    """Test bulk updating entries."""
    user = await create_test_user(db_connection)
    hierarchy = await create_test_hierarchy(db_connection, user["organization_id"])
    election_data = await create_test_election(db_connection, user["organization_id"], user["id"])
    election = election_data["election"]
    position = election_data["position"]

    sheet = await sheets_service.create_result_sheet(
        db_connection,
        election_id=_to_uuid(election["id"]),
        position_id=_to_uuid(position["id"]),
        polling_station_id=_to_uuid(hierarchy["polling_station"]["id"]),
        sheet_type="primary",
        created_by=user["id"],
    )

    entries = [
        {"candidate_name": "Candidate A", "party": "NPP", "votes": 100},
        {"candidate_name": "Candidate B", "party": "NDC", "votes": 200},
        {"candidate_name": "Candidate C", "party": "CPP", "votes": 150},
    ]

    count = await sheets_service.bulk_update_entries(db_connection, _to_uuid(sheet["id"]), entries)

    assert count == 3

    result_entries = await sheets_service.get_result_entries(db_connection, _to_uuid(sheet["id"]))
    assert len(result_entries) == 3


@pytest.mark.asyncio
async def test_submit_result_sheet(db_connection):
    """Test submitting a result sheet for verification."""
    user = await create_test_user(db_connection)
    hierarchy = await create_test_hierarchy(db_connection, user["organization_id"])
    election_data = await create_test_election(db_connection, user["organization_id"], user["id"])

    sheet = await create_sheet_with_entry(db_connection, user, hierarchy, election_data)

    submitted = await sheets_service.submit_result_sheet(db_connection, _to_uuid(sheet["id"]), user["id"])

    assert submitted is not None
    assert submitted["status"] == "submitted"
    assert submitted["submitted_at"] is not None


@pytest.mark.asyncio
async def test_submit_empty_sheet_fails(db_connection):
    """Test that submitting an empty sheet fails."""
    user = await create_test_user(db_connection)
    hierarchy = await create_test_hierarchy(db_connection, user["organization_id"])
    election_data = await create_test_election(db_connection, user["organization_id"], user["id"])
    election = election_data["election"]
    position = election_data["position"]

    sheet = await sheets_service.create_result_sheet(
        db_connection,
        election_id=_to_uuid(election["id"]),
        position_id=_to_uuid(position["id"]),
        polling_station_id=_to_uuid(hierarchy["polling_station"]["id"]),
        sheet_type="primary",
        created_by=user["id"],
    )

    with pytest.raises(ValueError, match="without vote entries"):
        await sheets_service.submit_result_sheet(db_connection, _to_uuid(sheet["id"]), user["id"])


@pytest.mark.asyncio
async def test_verify_result_sheet(db_connection):
    """Test verifying a submitted result sheet."""
    user = await create_test_user(db_connection)
    hierarchy = await create_test_hierarchy(db_connection, user["organization_id"])
    election_data = await create_test_election(db_connection, user["organization_id"], user["id"])

    sheet = await create_sheet_with_entry(db_connection, user, hierarchy, election_data)
    await sheets_service.submit_result_sheet(db_connection, _to_uuid(sheet["id"]), user["id"])

    verified = await sheets_service.verify_result_sheet(
        db_connection, _to_uuid(sheet["id"]), user["id"], notes="All good"
    )

    assert verified is not None
    assert verified["status"] == "verified"
    assert verified["verified_at"] is not None


@pytest.mark.asyncio
async def test_approve_result_sheet(db_connection):
    """Test approving a verified result sheet."""
    user = await create_test_user(db_connection)
    hierarchy = await create_test_hierarchy(db_connection, user["organization_id"])
    election_data = await create_test_election(db_connection, user["organization_id"], user["id"])

    sheet = await create_sheet_with_entry(db_connection, user, hierarchy, election_data)
    await sheets_service.submit_result_sheet(db_connection, _to_uuid(sheet["id"]), user["id"])
    await sheets_service.verify_result_sheet(db_connection, _to_uuid(sheet["id"]), user["id"])

    approved = await sheets_service.approve_result_sheet(db_connection, _to_uuid(sheet["id"]), user["id"])

    assert approved is not None
    assert approved["status"] == "approved"
    assert approved["approved_at"] is not None


@pytest.mark.asyncio
async def test_workflow_status_validation(db_connection):
    """Test that workflow status transitions are validated."""
    user = await create_test_user(db_connection)
    hierarchy = await create_test_hierarchy(db_connection, user["organization_id"])
    election_data = await create_test_election(db_connection, user["organization_id"], user["id"])
    election = election_data["election"]
    position = election_data["position"]

    sheet = await sheets_service.create_result_sheet(
        db_connection,
        election_id=_to_uuid(election["id"]),
        position_id=_to_uuid(position["id"]),
        polling_station_id=_to_uuid(hierarchy["polling_station"]["id"]),
        sheet_type="primary",
        created_by=user["id"],
    )

    with pytest.raises(ValueError, match="Cannot verify"):
        await sheets_service.verify_result_sheet(db_connection, _to_uuid(sheet["id"]), user["id"])


@pytest.mark.asyncio
async def test_reject_result_sheet(db_connection):
    """Test rejecting a result sheet."""
    user = await create_test_user(db_connection)
    hierarchy = await create_test_hierarchy(db_connection, user["organization_id"])
    election_data = await create_test_election(db_connection, user["organization_id"], user["id"])

    sheet = await create_sheet_with_entry(db_connection, user, hierarchy, election_data)
    await sheets_service.submit_result_sheet(db_connection, _to_uuid(sheet["id"]), user["id"])

    rejected = await sheets_service.reject_result_sheet(
        db_connection,
        _to_uuid(sheet["id"]),
        user["id"],
        "Vote counts don't match pink sheet",
    )

    assert rejected is not None
    assert rejected["status"] == "draft"
    assert rejected["submitted_at"] is None


@pytest.mark.asyncio
async def test_get_workflow_history(db_connection):
    """Test getting workflow history."""
    user = await create_test_user(db_connection)
    hierarchy = await create_test_hierarchy(db_connection, user["organization_id"])
    election_data = await create_test_election(db_connection, user["organization_id"], user["id"])

    sheet = await create_sheet_with_entry(db_connection, user, hierarchy, election_data)
    await sheets_service.submit_result_sheet(db_connection, _to_uuid(sheet["id"]), user["id"])
    await sheets_service.verify_result_sheet(db_connection, _to_uuid(sheet["id"]), user["id"])

    history = await sheets_service.get_workflow_history(db_connection, _to_uuid(sheet["id"]))

    assert len(history) >= 2
    actions = [h["action"] for h in history]
    assert "submitted" in actions
    assert "verified" in actions


@pytest.mark.asyncio
async def test_get_submission_progress(db_connection):
    """Test getting submission progress."""
    user = await create_test_user(db_connection)
    hierarchy = await create_test_hierarchy(db_connection, user["organization_id"])
    election_data = await create_test_election(db_connection, user["organization_id"], user["id"])
    election = election_data["election"]

    sheet = await create_sheet_with_entry(db_connection, user, hierarchy, election_data)
    await sheets_service.submit_result_sheet(db_connection, _to_uuid(sheet["id"]), user["id"])

    progress = await sheets_service.get_submission_progress(db_connection, _to_uuid(election["id"]))

    assert progress["sheets_created"] >= 1
    assert progress["submitted"] >= 1


@pytest.mark.asyncio
async def test_add_attachment(db_connection):
    """Test adding an attachment to a result sheet."""
    user = await create_test_user(db_connection)
    hierarchy = await create_test_hierarchy(db_connection, user["organization_id"])
    election_data = await create_test_election(db_connection, user["organization_id"], user["id"])
    election = election_data["election"]
    position = election_data["position"]

    sheet = await sheets_service.create_result_sheet(
        db_connection,
        election_id=_to_uuid(election["id"]),
        position_id=_to_uuid(position["id"]),
        polling_station_id=_to_uuid(hierarchy["polling_station"]["id"]),
        sheet_type="primary",
        created_by=user["id"],
    )

    attachment = await sheets_service.add_attachment(
        db_connection,
        result_sheet_id=_to_uuid(sheet["id"]),
        attachment_type="pink_sheet",
        file_url="https://storage.example.com/pink_sheet_001.jpg",
        file_name="pink_sheet_001.jpg",
        uploaded_by=user["id"],
    )

    assert attachment is not None
    assert attachment["file_type"] == "pink_sheet"
    assert attachment["file_url"] == "https://storage.example.com/pink_sheet_001.jpg"

    attachments = await sheets_service.get_attachments(db_connection, _to_uuid(sheet["id"]))
    assert len(attachments) == 1
