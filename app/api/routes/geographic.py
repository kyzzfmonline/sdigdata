"""Geographic hierarchy API routes.

Manages regions, constituencies, electoral areas, and polling stations.
"""

from typing import Annotated
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.core.responses import success_response
from app.api.deps import get_current_user
from app.services import geographic as geo_service

router = APIRouter(prefix="/geographic", tags=["Geographic Hierarchy"])


# ============================================
# PYDANTIC MODELS
# ============================================


class RegionCreate(BaseModel):
    """Create region request."""

    name: str = Field(..., min_length=2, max_length=100)
    code: str = Field(..., min_length=2, max_length=20)
    metadata: dict | None = None


class RegionUpdate(BaseModel):
    """Update region request."""

    name: str | None = None
    code: str | None = None
    metadata: dict | None = None


class ConstituencyCreate(BaseModel):
    """Create constituency request."""

    name: str = Field(..., min_length=2, max_length=100)
    code: str = Field(..., min_length=2, max_length=20)
    region_id: UUID
    metadata: dict | None = None


class ElectoralAreaCreate(BaseModel):
    """Create electoral area request."""

    name: str = Field(..., min_length=2, max_length=100)
    code: str = Field(..., min_length=2, max_length=20)
    constituency_id: UUID
    metadata: dict | None = None


class PollingStationCreate(BaseModel):
    """Create polling station request."""

    name: str = Field(..., min_length=2, max_length=200)
    code: str = Field(..., min_length=2, max_length=30)
    electoral_area_id: UUID
    address: str | None = None
    gps_coordinates: str | None = None
    registered_voters: int = 0
    metadata: dict | None = None


class PollingStationUpdate(BaseModel):
    """Update polling station request."""

    name: str | None = None
    address: str | None = None
    gps_coordinates: str | None = None
    registered_voters: int | None = None
    metadata: dict | None = None


# ============================================
# REGIONS
# ============================================


@router.get("/regions")
async def list_regions(
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """List all regions."""
    regions = await geo_service.list_regions(conn)
    return success_response(data={"regions": regions, "count": len(regions)})


@router.post("/regions")
async def create_region(
    request: RegionCreate,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Create a new region."""
    region = await geo_service.create_region(
        conn,
        name=request.name,
        code=request.code,
        metadata=request.metadata,
    )
    return success_response(data=region, message="Region created successfully")


@router.get("/regions/{region_id}")
async def get_region(
    region_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Get a region by ID."""
    region = await geo_service.get_region(conn, region_id)
    if not region:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Region not found",
        )
    return success_response(data=region)


@router.patch("/regions/{region_id}")
async def update_region(
    region_id: UUID,
    request: RegionUpdate,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Update a region."""
    updates = request.model_dump(exclude_unset=True)
    region = await geo_service.update_region(conn, region_id, **updates)
    if not region:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Region not found",
        )
    return success_response(data=region, message="Region updated successfully")


@router.delete("/regions/{region_id}")
async def delete_region(
    region_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Delete a region."""
    success = await geo_service.delete_region(conn, region_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete region (may have constituencies)",
        )
    return success_response(message="Region deleted successfully")


# ============================================
# CONSTITUENCIES
# ============================================


@router.get("/constituencies")
async def list_constituencies(
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    region_id: UUID | None = None,
):
    """List constituencies, optionally filtered by region."""
    constituencies = await geo_service.list_constituencies(conn, region_id=region_id)
    return success_response(
        data={"constituencies": constituencies, "count": len(constituencies)}
    )


@router.post("/constituencies")
async def create_constituency(
    request: ConstituencyCreate,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Create a new constituency."""
    constituency = await geo_service.create_constituency(
        conn,
        name=request.name,
        code=request.code,
        region_id=request.region_id,
        metadata=request.metadata,
    )
    return success_response(data=constituency, message="Constituency created successfully")


@router.get("/constituencies/{constituency_id}")
async def get_constituency(
    constituency_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Get a constituency by ID."""
    constituency = await geo_service.get_constituency(conn, constituency_id)
    if not constituency:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Constituency not found",
        )
    return success_response(data=constituency)


# ============================================
# ELECTORAL AREAS
# ============================================


@router.get("/electoral-areas")
async def list_electoral_areas(
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    constituency_id: UUID | None = None,
):
    """List electoral areas, optionally filtered by constituency."""
    areas = await geo_service.list_electoral_areas(conn, constituency_id=constituency_id)
    return success_response(data={"electoral_areas": areas, "count": len(areas)})


@router.post("/electoral-areas")
async def create_electoral_area(
    request: ElectoralAreaCreate,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Create a new electoral area."""
    area = await geo_service.create_electoral_area(
        conn,
        name=request.name,
        code=request.code,
        constituency_id=request.constituency_id,
        metadata=request.metadata,
    )
    return success_response(data=area, message="Electoral area created successfully")


# ============================================
# POLLING STATIONS
# ============================================


@router.get("/polling-stations")
async def list_polling_stations(
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    electoral_area_id: UUID | None = None,
    constituency_id: UUID | None = None,
    region_id: UUID | None = None,
    limit: int = 100,
    offset: int = 0,
):
    """List polling stations with filtering."""
    stations = await geo_service.list_polling_stations(
        conn,
        electoral_area_id=electoral_area_id,
        constituency_id=constituency_id,
        region_id=region_id,
        limit=limit,
        offset=offset,
    )
    return success_response(data={"polling_stations": stations, "count": len(stations)})


@router.post("/polling-stations")
async def create_polling_station(
    request: PollingStationCreate,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Create a new polling station."""
    station = await geo_service.create_polling_station(
        conn,
        name=request.name,
        code=request.code,
        electoral_area_id=request.electoral_area_id,
        address=request.address,
        gps_coordinates=request.gps_coordinates,
        registered_voters=request.registered_voters,
        metadata=request.metadata,
    )
    return success_response(data=station, message="Polling station created successfully")


@router.get("/polling-stations/{station_id}")
async def get_polling_station(
    station_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Get a polling station with its full hierarchy."""
    station = await geo_service.get_polling_station_with_hierarchy(conn, station_id)
    if not station:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Polling station not found",
        )
    return success_response(data=station)


@router.patch("/polling-stations/{station_id}")
async def update_polling_station(
    station_id: UUID,
    request: PollingStationUpdate,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Update a polling station."""
    updates = request.model_dump(exclude_unset=True)
    station = await geo_service.update_polling_station(conn, station_id, **updates)
    if not station:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Polling station not found",
        )
    return success_response(data=station, message="Polling station updated successfully")


# ============================================
# STATISTICS
# ============================================


@router.get("/stats")
async def get_hierarchy_stats(
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Get overall geographic hierarchy statistics."""
    stats = await geo_service.get_hierarchy_stats(conn)
    return success_response(data=stats)


@router.get("/regions/{region_id}/breakdown")
async def get_region_breakdown(
    region_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Get detailed breakdown for a region."""
    breakdown = await geo_service.get_region_breakdown(conn, region_id)
    return success_response(data=breakdown)
