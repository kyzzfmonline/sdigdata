"""Unit tests for collation service."""

import pytest
from uuid import UUID, uuid4
from datetime import datetime, timedelta

from app.services import collation as collation_service
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


async def create_test_election(db_connection, org_id, user_id):
    """Helper to create a test election."""
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
    return election


# ============================================
# COLLATION OFFICERS TESTS
# ============================================


@pytest.mark.asyncio
async def test_create_collation_officer(db_connection):
    """Test creating a collation officer."""
    user = await create_test_user(db_connection)

    officer = await collation_service.create_collation_officer(
        db_connection,
        user_id=user["id"],
        organization_id=user["organization_id"],
        officer_type="presiding",
        level="polling_station",
        id_number="GHA-1234567890",
        phone="+233201234567",
    )

    assert officer is not None
    assert officer["officer_type"] == "presiding"
    assert officer["level"] == "polling_station"
    assert officer["id_number"] == "GHA-1234567890"


@pytest.mark.asyncio
async def test_get_collation_officer(db_connection):
    """Test getting a collation officer."""
    user = await create_test_user(db_connection)

    created = await collation_service.create_collation_officer(
        db_connection,
        user_id=user["id"],
        organization_id=user["organization_id"],
        officer_type="returning",
        level="constituency",
    )

    # Get by officer_id
    officer = await collation_service.get_collation_officer(
        db_connection, officer_id=_to_uuid(created["id"])
    )
    assert officer is not None
    assert officer["officer_type"] == "returning"

    # Get by user_id
    officer = await collation_service.get_collation_officer(
        db_connection, user_id=user["id"]
    )
    assert officer is not None


@pytest.mark.asyncio
async def test_list_collation_officers(db_connection):
    """Test listing collation officers."""
    user1 = await create_test_user(db_connection)
    user2 = await create_test_user(db_connection)

    await collation_service.create_collation_officer(
        db_connection,
        user_id=user1["id"],
        organization_id=user1["organization_id"],
        officer_type="presiding",
        level="polling_station",
    )
    await collation_service.create_collation_officer(
        db_connection,
        user_id=user2["id"],
        organization_id=user2["organization_id"],
        officer_type="returning",
        level="constituency",
    )

    # List all
    officers = await collation_service.list_collation_officers(db_connection)
    assert len(officers) >= 2

    # Filter by type
    presiding = await collation_service.list_collation_officers(
        db_connection, officer_type="presiding"
    )
    assert all(o["officer_type"] == "presiding" for o in presiding)


# ============================================
# COLLATION CENTERS TESTS
# ============================================


@pytest.mark.asyncio
async def test_create_collation_center(db_connection):
    """Test creating a collation center."""
    user = await create_test_user(db_connection)
    hierarchy = await create_test_hierarchy(db_connection, user["organization_id"])

    center = await collation_service.create_collation_center(
        db_connection,
        organization_id=user["organization_id"],
        name=f"EA Collation Center {uuid4().hex[:6]}",
        level="electoral_area",
        electoral_area_id=_to_uuid(hierarchy["electoral_area"]["id"]),
        address="123 Main Street",
    )

    assert center is not None
    assert center["level"] == "electoral_area"
    assert "123 Main Street" in (center.get("address") or "")


@pytest.mark.asyncio
async def test_list_collation_centers(db_connection):
    """Test listing collation centers."""
    user = await create_test_user(db_connection)
    hierarchy = await create_test_hierarchy(db_connection, user["organization_id"])

    await collation_service.create_collation_center(
        db_connection,
        organization_id=user["organization_id"],
        name=f"EA Center {uuid4().hex[:6]}",
        level="electoral_area",
        electoral_area_id=_to_uuid(hierarchy["electoral_area"]["id"]),
    )
    await collation_service.create_collation_center(
        db_connection,
        organization_id=user["organization_id"],
        name=f"Const Center {uuid4().hex[:6]}",
        level="constituency",
        constituency_id=_to_uuid(hierarchy["constituency"]["id"]),
    )

    centers = await collation_service.list_collation_centers(db_connection)
    assert len(centers) >= 2


# ============================================
# INCIDENTS TESTS
# ============================================


@pytest.mark.asyncio
async def test_report_incident(db_connection):
    """Test reporting an incident."""
    user = await create_test_user(db_connection)
    hierarchy = await create_test_hierarchy(db_connection, user["organization_id"])
    election = await create_test_election(db_connection, user["organization_id"], user["id"])

    incident = await collation_service.report_incident(
        db_connection,
        election_id=_to_uuid(election["id"]),
        polling_station_id=_to_uuid(hierarchy["polling_station"]["id"]),
        incident_type="equipment_failure",
        category="technical",
        severity="medium",
        title="Voting machine malfunction",
        description="One of the voting machines stopped working",
        reported_by=user["id"],
    )

    assert incident is not None
    assert incident["incident_type"] == "equipment_failure"
    assert incident["severity"] == "medium"
    assert incident["status"] == "open"


@pytest.mark.asyncio
async def test_list_incidents(db_connection):
    """Test listing incidents."""
    user = await create_test_user(db_connection)
    hierarchy = await create_test_hierarchy(db_connection, user["organization_id"])
    election = await create_test_election(db_connection, user["organization_id"], user["id"])

    await collation_service.report_incident(
        db_connection,
        election_id=_to_uuid(election["id"]),
        polling_station_id=_to_uuid(hierarchy["polling_station"]["id"]),
        incident_type="protest",
        category="civil",
        severity="high",
        title="Voter protest",
        description="Voters protesting outside polling station",
        reported_by=user["id"],
    )

    incidents = await collation_service.list_incidents(
        db_connection, _to_uuid(election["id"])
    )
    assert len(incidents) >= 1


@pytest.mark.asyncio
async def test_resolve_incident(db_connection):
    """Test resolving an incident."""
    user = await create_test_user(db_connection)
    hierarchy = await create_test_hierarchy(db_connection, user["organization_id"])
    election = await create_test_election(db_connection, user["organization_id"], user["id"])

    incident = await collation_service.report_incident(
        db_connection,
        election_id=_to_uuid(election["id"]),
        polling_station_id=_to_uuid(hierarchy["polling_station"]["id"]),
        incident_type="irregularity",
        category="procedural",
        severity="low",
        title="Minor issue",
        description="Minor procedural issue",
        reported_by=user["id"],
    )

    resolved = await collation_service.resolve_incident(
        db_connection,
        _to_uuid(incident["id"]),
        user["id"],
        "Issue was investigated and resolved",
    )

    assert resolved is not None
    assert resolved["status"] == "resolved"
    assert resolved["resolution"] == "Issue was investigated and resolved"


# ============================================
# COLLATION DASHBOARD TESTS
# ============================================


@pytest.mark.asyncio
async def test_get_collation_dashboard(db_connection):
    """Test getting collation dashboard data."""
    user = await create_test_user(db_connection)
    election = await create_test_election(db_connection, user["organization_id"], user["id"])

    dashboard = await collation_service.get_collation_dashboard(
        db_connection, _to_uuid(election["id"])
    )

    assert dashboard is not None
    assert "election" in dashboard
    assert "summary" in dashboard
    assert "status_breakdown" in dashboard


@pytest.mark.asyncio
async def test_get_live_feed(db_connection):
    """Test getting live collation feed."""
    user = await create_test_user(db_connection)
    election = await create_test_election(db_connection, user["organization_id"], user["id"])

    feed = await collation_service.get_live_feed(
        db_connection, _to_uuid(election["id"])
    )

    # Feed may be empty if no activity yet
    assert isinstance(feed, list)
