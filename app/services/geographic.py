"""Geographic hierarchy service functions."""

import json
from typing import Any
from uuid import UUID

import asyncpg


def _parse_row(row: asyncpg.Record | None) -> dict[str, Any] | None:
    """Parse a database row into a dict with proper type conversions."""
    if not row:
        return None

    result = dict(row)

    # Convert UUID fields to strings
    uuid_fields = (
        "id", "organization_id", "region_id", "constituency_id",
        "electoral_area_id", "polling_station_id"
    )
    for field in uuid_fields:
        if result.get(field) is not None:
            result[field] = str(result[field])

    # Parse JSONB fields
    for field in ("metadata", "boundary_geojson", "accessibility_features"):
        if result.get(field) and isinstance(result[field], str):
            result[field] = json.loads(result[field])

    return result


# ============================================
# REGIONS (Level 1)
# ============================================


async def create_region(
    conn: asyncpg.Connection,
    organization_id: UUID,
    name: str,
    code: str | None = None,
    description: str | None = None,
    population: int | None = None,
    registered_voters: int | None = None,
    gps_lat: float | None = None,
    gps_lng: float | None = None,
    boundary_geojson: dict | None = None,
    metadata: dict | None = None,
) -> dict[str, Any] | None:
    """Create a new region."""
    result = await conn.fetchrow(
        """
        INSERT INTO regions (
            organization_id, name, code, description, population,
            registered_voters, gps_lat, gps_lng, boundary_geojson, metadata
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        RETURNING *
        """,
        str(organization_id),
        name,
        code,
        description,
        population,
        registered_voters,
        gps_lat,
        gps_lng,
        json.dumps(boundary_geojson) if boundary_geojson else None,
        json.dumps(metadata or {}),
    )
    return _parse_row(result)


async def get_region(
    conn: asyncpg.Connection,
    region_id: UUID,
    organization_id: UUID | None = None,
) -> dict[str, Any] | None:
    """Get a region by ID."""
    query = "SELECT * FROM regions WHERE id = $1 AND deleted = FALSE"
    params: list[Any] = [str(region_id)]

    if organization_id:
        query += " AND organization_id = $2"
        params.append(str(organization_id))

    result = await conn.fetchrow(query, *params)
    return _parse_row(result)


async def list_regions(
    conn: asyncpg.Connection,
    organization_id: UUID,
    status: str | None = None,
    search: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    """List regions with optional filtering."""
    query = "SELECT * FROM regions WHERE organization_id = $1 AND deleted = FALSE"
    count_query = "SELECT COUNT(*) FROM regions WHERE organization_id = $1 AND deleted = FALSE"
    params: list[Any] = [str(organization_id)]
    param_num = 2

    if status:
        query += f" AND status = ${param_num}"
        count_query += f" AND status = ${param_num}"
        params.append(status)
        param_num += 1

    if search:
        query += f" AND (name ILIKE ${param_num} OR code ILIKE ${param_num})"
        count_query += f" AND (name ILIKE ${param_num} OR code ILIKE ${param_num})"
        params.append(f"%{search}%")
        param_num += 1

    total = await conn.fetchval(count_query, *params)

    query += f" ORDER BY name ASC LIMIT ${param_num} OFFSET ${param_num + 1}"
    params.extend([limit, offset])

    rows = await conn.fetch(query, *params)
    return [_parse_row(row) for row in rows], total or 0


async def update_region(
    conn: asyncpg.Connection,
    region_id: UUID,
    organization_id: UUID,
    **kwargs,
) -> dict[str, Any] | None:
    """Update a region."""
    updates = []
    params: list[Any] = []
    param_num = 1

    allowed_fields = {
        "name", "code", "description", "population", "registered_voters",
        "gps_lat", "gps_lng", "boundary_geojson", "metadata", "status"
    }

    for key, value in kwargs.items():
        if key in allowed_fields and value is not None:
            if key in ("boundary_geojson", "metadata"):
                value = json.dumps(value)
            updates.append(f"{key} = ${param_num}")
            params.append(value)
            param_num += 1

    if not updates:
        return await get_region(conn, region_id, organization_id)

    updates.append("updated_at = CURRENT_TIMESTAMP")
    params.extend([str(region_id), str(organization_id)])

    query = f"""
        UPDATE regions
        SET {", ".join(updates)}
        WHERE id = ${param_num} AND organization_id = ${param_num + 1} AND deleted = FALSE
        RETURNING *
    """

    result = await conn.fetchrow(query, *params)
    return _parse_row(result)


async def delete_region(
    conn: asyncpg.Connection,
    region_id: UUID,
    organization_id: UUID,
) -> bool:
    """Soft delete a region."""
    result = await conn.execute(
        """
        UPDATE regions
        SET deleted = TRUE, status = 'inactive', updated_at = CURRENT_TIMESTAMP
        WHERE id = $1 AND organization_id = $2 AND deleted = FALSE
        """,
        str(region_id),
        str(organization_id),
    )
    return int(result.split()[-1]) > 0


# ============================================
# CONSTITUENCIES (Level 2)
# ============================================


async def create_constituency(
    conn: asyncpg.Connection,
    organization_id: UUID,
    region_id: UUID,
    name: str,
    code: str | None = None,
    description: str | None = None,
    constituency_type: str = "parliamentary",
    population: int | None = None,
    registered_voters: int | None = None,
    gps_lat: float | None = None,
    gps_lng: float | None = None,
    metadata: dict | None = None,
) -> dict[str, Any] | None:
    """Create a new constituency."""
    result = await conn.fetchrow(
        """
        INSERT INTO constituencies (
            organization_id, region_id, name, code, description,
            constituency_type, population, registered_voters,
            gps_lat, gps_lng, metadata
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
        RETURNING *
        """,
        str(organization_id),
        str(region_id),
        name,
        code,
        description,
        constituency_type,
        population,
        registered_voters,
        gps_lat,
        gps_lng,
        json.dumps(metadata or {}),
    )
    return _parse_row(result)


async def get_constituency(
    conn: asyncpg.Connection,
    constituency_id: UUID,
    organization_id: UUID | None = None,
) -> dict[str, Any] | None:
    """Get a constituency by ID."""
    query = "SELECT * FROM constituencies WHERE id = $1 AND deleted = FALSE"
    params: list[Any] = [str(constituency_id)]

    if organization_id:
        query += " AND organization_id = $2"
        params.append(str(organization_id))

    result = await conn.fetchrow(query, *params)
    return _parse_row(result)


async def list_constituencies(
    conn: asyncpg.Connection,
    organization_id: UUID,
    region_id: UUID | None = None,
    status: str | None = None,
    search: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    """List constituencies with optional filtering."""
    query = "SELECT * FROM constituencies WHERE organization_id = $1 AND deleted = FALSE"
    count_query = "SELECT COUNT(*) FROM constituencies WHERE organization_id = $1 AND deleted = FALSE"
    params: list[Any] = [str(organization_id)]
    param_num = 2

    if region_id:
        query += f" AND region_id = ${param_num}"
        count_query += f" AND region_id = ${param_num}"
        params.append(str(region_id))
        param_num += 1

    if status:
        query += f" AND status = ${param_num}"
        count_query += f" AND status = ${param_num}"
        params.append(status)
        param_num += 1

    if search:
        query += f" AND (name ILIKE ${param_num} OR code ILIKE ${param_num})"
        count_query += f" AND (name ILIKE ${param_num} OR code ILIKE ${param_num})"
        params.append(f"%{search}%")
        param_num += 1

    total = await conn.fetchval(count_query, *params)

    query += f" ORDER BY name ASC LIMIT ${param_num} OFFSET ${param_num + 1}"
    params.extend([limit, offset])

    rows = await conn.fetch(query, *params)
    return [_parse_row(row) for row in rows], total or 0


# ============================================
# ELECTORAL AREAS (Level 3)
# ============================================


async def create_electoral_area(
    conn: asyncpg.Connection,
    organization_id: UUID,
    constituency_id: UUID,
    name: str,
    code: str | None = None,
    description: str | None = None,
    population: int | None = None,
    registered_voters: int | None = None,
    gps_lat: float | None = None,
    gps_lng: float | None = None,
    metadata: dict | None = None,
) -> dict[str, Any] | None:
    """Create a new electoral area."""
    result = await conn.fetchrow(
        """
        INSERT INTO electoral_areas (
            organization_id, constituency_id, name, code, description,
            population, registered_voters, gps_lat, gps_lng, metadata
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        RETURNING *
        """,
        str(organization_id),
        str(constituency_id),
        name,
        code,
        description,
        population,
        registered_voters,
        gps_lat,
        gps_lng,
        json.dumps(metadata or {}),
    )
    return _parse_row(result)


async def list_electoral_areas(
    conn: asyncpg.Connection,
    organization_id: UUID,
    constituency_id: UUID | None = None,
    status: str | None = None,
    search: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    """List electoral areas with optional filtering."""
    query = "SELECT * FROM electoral_areas WHERE organization_id = $1 AND deleted = FALSE"
    count_query = "SELECT COUNT(*) FROM electoral_areas WHERE organization_id = $1 AND deleted = FALSE"
    params: list[Any] = [str(organization_id)]
    param_num = 2

    if constituency_id:
        query += f" AND constituency_id = ${param_num}"
        count_query += f" AND constituency_id = ${param_num}"
        params.append(str(constituency_id))
        param_num += 1

    if status:
        query += f" AND status = ${param_num}"
        count_query += f" AND status = ${param_num}"
        params.append(status)
        param_num += 1

    if search:
        query += f" AND (name ILIKE ${param_num} OR code ILIKE ${param_num})"
        count_query += f" AND (name ILIKE ${param_num} OR code ILIKE ${param_num})"
        params.append(f"%{search}%")
        param_num += 1

    total = await conn.fetchval(count_query, *params)

    query += f" ORDER BY name ASC LIMIT ${param_num} OFFSET ${param_num + 1}"
    params.extend([limit, offset])

    rows = await conn.fetch(query, *params)
    return [_parse_row(row) for row in rows], total or 0


# ============================================
# POLLING STATIONS (Level 4)
# ============================================


async def create_polling_station(
    conn: asyncpg.Connection,
    organization_id: UUID,
    electoral_area_id: UUID,
    name: str,
    code: str | None = None,
    station_number: str | None = None,
    address: str | None = None,
    facility_type: str | None = None,
    registered_voters: int = 0,
    gps_lat: float | None = None,
    gps_lng: float | None = None,
    accessibility_features: list | None = None,
    contact_phone: str | None = None,
    metadata: dict | None = None,
) -> dict[str, Any] | None:
    """Create a new polling station."""
    result = await conn.fetchrow(
        """
        INSERT INTO polling_stations (
            organization_id, electoral_area_id, name, code, station_number,
            address, facility_type, registered_voters, gps_lat, gps_lng,
            accessibility_features, contact_phone, metadata
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
        RETURNING *
        """,
        str(organization_id),
        str(electoral_area_id),
        name,
        code,
        station_number,
        address,
        facility_type,
        registered_voters,
        gps_lat,
        gps_lng,
        json.dumps(accessibility_features or []),
        contact_phone,
        json.dumps(metadata or {}),
    )
    return _parse_row(result)


async def get_polling_station(
    conn: asyncpg.Connection,
    station_id: UUID,
    organization_id: UUID | None = None,
) -> dict[str, Any] | None:
    """Get a polling station by ID."""
    query = "SELECT * FROM polling_stations WHERE id = $1 AND deleted = FALSE"
    params: list[Any] = [str(station_id)]

    if organization_id:
        query += " AND organization_id = $2"
        params.append(str(organization_id))

    result = await conn.fetchrow(query, *params)
    return _parse_row(result)


async def list_polling_stations(
    conn: asyncpg.Connection,
    organization_id: UUID,
    electoral_area_id: UUID | None = None,
    constituency_id: UUID | None = None,
    region_id: UUID | None = None,
    status: str | None = None,
    search: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    """List polling stations with optional filtering."""
    query = """
        SELECT ps.* FROM polling_stations ps
        JOIN electoral_areas ea ON ps.electoral_area_id = ea.id
        JOIN constituencies c ON ea.constituency_id = c.id
        WHERE ps.organization_id = $1 AND ps.deleted = FALSE
    """
    count_query = """
        SELECT COUNT(*) FROM polling_stations ps
        JOIN electoral_areas ea ON ps.electoral_area_id = ea.id
        JOIN constituencies c ON ea.constituency_id = c.id
        WHERE ps.organization_id = $1 AND ps.deleted = FALSE
    """
    params: list[Any] = [str(organization_id)]
    param_num = 2

    if electoral_area_id:
        query += f" AND ps.electoral_area_id = ${param_num}"
        count_query += f" AND ps.electoral_area_id = ${param_num}"
        params.append(str(electoral_area_id))
        param_num += 1

    if constituency_id:
        query += f" AND ea.constituency_id = ${param_num}"
        count_query += f" AND ea.constituency_id = ${param_num}"
        params.append(str(constituency_id))
        param_num += 1

    if region_id:
        query += f" AND c.region_id = ${param_num}"
        count_query += f" AND c.region_id = ${param_num}"
        params.append(str(region_id))
        param_num += 1

    if status:
        query += f" AND ps.status = ${param_num}"
        count_query += f" AND ps.status = ${param_num}"
        params.append(status)
        param_num += 1

    if search:
        query += f" AND (ps.name ILIKE ${param_num} OR ps.code ILIKE ${param_num})"
        count_query += f" AND (ps.name ILIKE ${param_num} OR ps.code ILIKE ${param_num})"
        params.append(f"%{search}%")
        param_num += 1

    total = await conn.fetchval(count_query, *params)

    query += f" ORDER BY ps.name ASC LIMIT ${param_num} OFFSET ${param_num + 1}"
    params.extend([limit, offset])

    rows = await conn.fetch(query, *params)
    return [_parse_row(row) for row in rows], total or 0


async def get_polling_station_with_hierarchy(
    conn: asyncpg.Connection,
    station_id: UUID,
) -> dict[str, Any] | None:
    """Get a polling station with full hierarchy information."""
    result = await conn.fetchrow(
        """
        SELECT
            ps.*,
            ea.name as electoral_area_name,
            ea.code as electoral_area_code,
            c.id as constituency_id,
            c.name as constituency_name,
            c.code as constituency_code,
            r.id as region_id,
            r.name as region_name,
            r.code as region_code
        FROM polling_stations ps
        JOIN electoral_areas ea ON ps.electoral_area_id = ea.id
        JOIN constituencies c ON ea.constituency_id = c.id
        JOIN regions r ON c.region_id = r.id
        WHERE ps.id = $1 AND ps.deleted = FALSE
        """,
        str(station_id),
    )

    if not result:
        return None

    data = _parse_row(result)
    if data:
        data["hierarchy"] = {
            "electoral_area": {
                "id": str(result["electoral_area_id"]),
                "name": result["electoral_area_name"],
                "code": result["electoral_area_code"],
            },
            "constituency": {
                "id": str(result["constituency_id"]),
                "name": result["constituency_name"],
                "code": result["constituency_code"],
            },
            "region": {
                "id": str(result["region_id"]),
                "name": result["region_name"],
                "code": result["region_code"],
            },
        }
    return data


# ============================================
# HIERARCHY STATISTICS
# ============================================


async def get_hierarchy_stats(
    conn: asyncpg.Connection,
    organization_id: UUID,
) -> dict[str, Any]:
    """Get statistics about the geographic hierarchy."""
    stats = await conn.fetchrow(
        """
        SELECT
            (SELECT COUNT(*) FROM regions WHERE organization_id = $1 AND deleted = FALSE) as total_regions,
            (SELECT COUNT(*) FROM constituencies WHERE organization_id = $1 AND deleted = FALSE) as total_constituencies,
            (SELECT COUNT(*) FROM electoral_areas WHERE organization_id = $1 AND deleted = FALSE) as total_electoral_areas,
            (SELECT COUNT(*) FROM polling_stations WHERE organization_id = $1 AND deleted = FALSE) as total_polling_stations,
            (SELECT COALESCE(SUM(registered_voters), 0) FROM polling_stations WHERE organization_id = $1 AND deleted = FALSE) as total_registered_voters
        """,
        str(organization_id),
    )

    return {
        "total_regions": stats["total_regions"],
        "total_constituencies": stats["total_constituencies"],
        "total_electoral_areas": stats["total_electoral_areas"],
        "total_polling_stations": stats["total_polling_stations"],
        "total_registered_voters": stats["total_registered_voters"],
    }


async def get_region_breakdown(
    conn: asyncpg.Connection,
    organization_id: UUID,
) -> list[dict[str, Any]]:
    """Get breakdown of polling stations and voters by region."""
    rows = await conn.fetch(
        """
        SELECT
            r.id,
            r.name,
            r.code,
            COUNT(DISTINCT c.id) as constituency_count,
            COUNT(DISTINCT ea.id) as electoral_area_count,
            COUNT(DISTINCT ps.id) as polling_station_count,
            COALESCE(SUM(ps.registered_voters), 0) as registered_voters
        FROM regions r
        LEFT JOIN constituencies c ON c.region_id = r.id AND c.deleted = FALSE
        LEFT JOIN electoral_areas ea ON ea.constituency_id = c.id AND ea.deleted = FALSE
        LEFT JOIN polling_stations ps ON ps.electoral_area_id = ea.id AND ps.deleted = FALSE
        WHERE r.organization_id = $1 AND r.deleted = FALSE
        GROUP BY r.id, r.name, r.code
        ORDER BY r.name
        """,
        str(organization_id),
    )

    return [
        {
            "id": str(row["id"]),
            "name": row["name"],
            "code": row["code"],
            "constituency_count": row["constituency_count"],
            "electoral_area_count": row["electoral_area_count"],
            "polling_station_count": row["polling_station_count"],
            "registered_voters": row["registered_voters"],
        }
        for row in rows
    ]
