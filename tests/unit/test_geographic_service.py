"""Unit tests for geographic service."""

import pytest
from uuid import UUID, uuid4

from app.services import geographic as geo_service
from app.services.organizations import create_organization


async def create_test_org(db_connection):
    """Helper to create a test organization."""
    org = await create_organization(
        db_connection,
        name=f"Test Org {uuid4().hex[:8]}",
        logo_url=None,
        primary_color=None,
    )
    # org["id"] may already be a UUID object from asyncpg
    org_id = org["id"]
    if isinstance(org_id, UUID):
        return org_id
    return UUID(str(org_id))


@pytest.mark.asyncio
async def test_create_region(db_connection):
    """Test creating a region."""
    org_id = await create_test_org(db_connection)

    region = await geo_service.create_region(
        db_connection,
        organization_id=org_id,
        name="Greater Accra",
        code="GAR",
        metadata={"capital": "Accra"},
    )

    assert region is not None
    assert region["name"] == "Greater Accra"
    assert region["code"] == "GAR"
    assert region["metadata"]["capital"] == "Accra"
    assert "id" in region


@pytest.mark.asyncio
async def test_get_region(db_connection):
    """Test getting a region by ID."""
    org_id = await create_test_org(db_connection)

    # Create a region first
    created = await geo_service.create_region(
        db_connection,
        organization_id=org_id,
        name="Ashanti",
        code="ASH",
    )

    # Fetch it
    region = await geo_service.get_region(db_connection, UUID(created["id"]))

    assert region is not None
    assert region["name"] == "Ashanti"
    assert region["code"] == "ASH"


@pytest.mark.asyncio
async def test_list_regions(db_connection):
    """Test listing regions."""
    org_id = await create_test_org(db_connection)

    # Create multiple regions
    await geo_service.create_region(db_connection, organization_id=org_id, name="Region A", code="RA")
    await geo_service.create_region(db_connection, organization_id=org_id, name="Region B", code="RB")

    regions, total = await geo_service.list_regions(db_connection, organization_id=org_id)

    assert total >= 2
    region_names = [r["name"] for r in regions]
    assert "Region A" in region_names
    assert "Region B" in region_names


@pytest.mark.asyncio
async def test_update_region(db_connection):
    """Test updating a region."""
    org_id = await create_test_org(db_connection)

    region = await geo_service.create_region(
        db_connection,
        organization_id=org_id,
        name="Old Name",
        code="OLD",
    )

    updated = await geo_service.update_region(
        db_connection,
        UUID(region["id"]),
        organization_id=org_id,
        name="New Name",
    )

    assert updated is not None
    assert updated["name"] == "New Name"
    assert updated["code"] == "OLD"  # Code unchanged


@pytest.mark.asyncio
async def test_create_constituency(db_connection):
    """Test creating a constituency."""
    org_id = await create_test_org(db_connection)

    # Create region first
    region = await geo_service.create_region(
        db_connection, organization_id=org_id, name="Test Region", code="TR"
    )

    constituency = await geo_service.create_constituency(
        db_connection,
        organization_id=org_id,
        region_id=UUID(region["id"]),
        name="Ashaiman",
        code="ASH-001",
    )

    assert constituency is not None
    assert constituency["name"] == "Ashaiman"
    assert constituency["code"] == "ASH-001"
    assert constituency["region_id"] == region["id"]


@pytest.mark.asyncio
async def test_list_constituencies_by_region(db_connection):
    """Test listing constituencies filtered by region."""
    org_id = await create_test_org(db_connection)

    # Create two regions
    region1 = await geo_service.create_region(
        db_connection, organization_id=org_id, name="Region 1", code="R1"
    )
    region2 = await geo_service.create_region(
        db_connection, organization_id=org_id, name="Region 2", code="R2"
    )

    # Create constituencies in each
    await geo_service.create_constituency(
        db_connection, organization_id=org_id, region_id=UUID(region1["id"]), name="Const 1A", code="C1A"
    )
    await geo_service.create_constituency(
        db_connection, organization_id=org_id, region_id=UUID(region1["id"]), name="Const 1B", code="C1B"
    )
    await geo_service.create_constituency(
        db_connection, organization_id=org_id, region_id=UUID(region2["id"]), name="Const 2A", code="C2A"
    )

    # Filter by region1
    constituencies, total = await geo_service.list_constituencies(
        db_connection, organization_id=org_id, region_id=UUID(region1["id"])
    )

    assert total == 2
    names = [c["name"] for c in constituencies]
    assert "Const 1A" in names
    assert "Const 1B" in names
    assert "Const 2A" not in names


@pytest.mark.asyncio
async def test_create_electoral_area(db_connection):
    """Test creating an electoral area."""
    org_id = await create_test_org(db_connection)

    region = await geo_service.create_region(
        db_connection, organization_id=org_id, name="Region", code="REG"
    )
    constituency = await geo_service.create_constituency(
        db_connection, organization_id=org_id, region_id=UUID(region["id"]), name="Constituency", code="CON"
    )

    electoral_area = await geo_service.create_electoral_area(
        db_connection,
        organization_id=org_id,
        constituency_id=UUID(constituency["id"]),
        name="Electoral Area 1",
        code="EA001",
    )

    assert electoral_area is not None
    assert electoral_area["name"] == "Electoral Area 1"
    assert electoral_area["code"] == "EA001"


@pytest.mark.asyncio
async def test_create_polling_station(db_connection):
    """Test creating a polling station."""
    org_id = await create_test_org(db_connection)

    region = await geo_service.create_region(
        db_connection, organization_id=org_id, name="Test Region", code="TR"
    )
    constituency = await geo_service.create_constituency(
        db_connection, organization_id=org_id, region_id=UUID(region["id"]), name="Test Const", code="TC"
    )
    electoral_area = await geo_service.create_electoral_area(
        db_connection, organization_id=org_id, constituency_id=UUID(constituency["id"]), name="Test EA", code="TEA"
    )

    station = await geo_service.create_polling_station(
        db_connection,
        organization_id=org_id,
        electoral_area_id=UUID(electoral_area["id"]),
        name="Community Center",
        code="PS001",
        address="123 Main Street",
        registered_voters=500,
    )

    assert station is not None
    assert station["name"] == "Community Center"
    assert station["code"] == "PS001"
    assert station["registered_voters"] == 500


@pytest.mark.asyncio
async def test_get_polling_station_with_hierarchy(db_connection):
    """Test getting polling station with full hierarchy."""
    org_id = await create_test_org(db_connection)

    region = await geo_service.create_region(
        db_connection, organization_id=org_id, name="Greater Accra", code="GAR"
    )
    constituency = await geo_service.create_constituency(
        db_connection, organization_id=org_id, region_id=UUID(region["id"]), name="Tema West", code="TW"
    )
    electoral_area = await geo_service.create_electoral_area(
        db_connection, organization_id=org_id, constituency_id=UUID(constituency["id"]), name="Community 5", code="C5"
    )
    station = await geo_service.create_polling_station(
        db_connection,
        organization_id=org_id,
        electoral_area_id=UUID(electoral_area["id"]),
        name="Primary School",
        code="PS-C5-001",
    )

    full_station = await geo_service.get_polling_station_with_hierarchy(
        db_connection, UUID(station["id"])
    )

    assert full_station is not None
    assert full_station["name"] == "Primary School"
    assert full_station["electoral_area_name"] == "Community 5"
    assert full_station["constituency_name"] == "Tema West"
    assert full_station["region_name"] == "Greater Accra"


@pytest.mark.asyncio
async def test_get_hierarchy_stats(db_connection):
    """Test getting hierarchy statistics."""
    org_id = await create_test_org(db_connection)

    # Create some hierarchy
    region = await geo_service.create_region(
        db_connection, organization_id=org_id, name="Stats Region", code="SR"
    )
    constituency = await geo_service.create_constituency(
        db_connection, organization_id=org_id, region_id=UUID(region["id"]), name="Stats Const", code="SC"
    )
    electoral_area = await geo_service.create_electoral_area(
        db_connection, organization_id=org_id, constituency_id=UUID(constituency["id"]), name="Stats EA", code="SEA"
    )
    await geo_service.create_polling_station(
        db_connection,
        organization_id=org_id,
        electoral_area_id=UUID(electoral_area["id"]),
        name="Stats Station",
        code="SS1",
        registered_voters=1000,
    )

    stats = await geo_service.get_hierarchy_stats(db_connection, organization_id=org_id)

    assert stats["total_regions"] >= 1
    assert stats["total_constituencies"] >= 1
    assert stats["total_electoral_areas"] >= 1
    assert stats["total_polling_stations"] >= 1
    assert stats["total_registered_voters"] >= 1000
