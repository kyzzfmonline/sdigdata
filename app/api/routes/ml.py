"""ML/AI data export routes for training datasets and await analytics."""

from typing import Annotated, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Response, Query
from datetime import datetime
import asyncpg
import json

from app.core.database import get_db
from app.core.logging_config import get_logger
from app.api.deps import get_current_user, require_admin
from app.services.forms import get_form_by_id

router = APIRouter(prefix="/ml", tags=["ML & AI"])
logger = get_logger(__name__)


@router.get("/training-data", response_model=list[dict])
async def get_training_data(
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    admin_user: Annotated[dict, Depends(require_admin)],
    form_id: Optional[str] = None,
    min_quality: float = Query(
        0.6, ge=0.0, le=1.0, description="Minimum quality score"
    ),
    suitable_only: bool = Query(
        True, description="Only return responses suitable for training"
    ),
    limit: Optional[int] = Query(
        None, ge=1, le=10000, description="Maximum number of records"
    ),
):
    """
    Get high-quality responses suitable for ML training.

    **Query Parameters:**
    - form_id: Filter by specific form (optional)
    - min_quality: Minimum quality score (0.0-1.0, default: 0.6)
    - suitable_only: Only include responses marked suitable for training (default: true)
    - limit: Maximum number of records to return (optional, max: 10000)

    **Response:**
    ```json
    [
        {
            "id": "...",
            "form_id": "...",
            "data": {...},
            "attachments": {...},
            "submitted_at": "2025-11-03T10:00:00",
            "quality_score": 0.85,
            "completeness_score": 0.90,
            "gps_accuracy_score": 0.80,
            "latitude": 6.6885,
            "longitude": -1.6244
        }
    ]
    ```
    """
    # Validate form_id if provided
    parsed_form_id = None
    if form_id:
        try:
            parsed_form_id = UUID(form_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid form_id format. Must be a valid UUID",
            )

    # Build query using the ML training view
    query = """
        SELECT
            id,
            form_id,
            data,
            attachments,
            submitted_at,
            quality_score,
            completeness_score,
            gps_accuracy_score,
            ml_training_consent,
            anonymization_level,
            longitude,
            latitude
        FROM vw_ml_training_data
        WHERE quality_score >= %s
    """
    params = [min_quality]

    if parsed_form_id:
        query += " AND form_id = %s"
        params.append(str(parsed_form_id))

    if suitable_only:
        # Additional filter beyond the view's base filter
        query += " AND quality_score >= %s"
        params.append(0.6)

    query += " ORDER BY quality_score DESC, submitted_at DESC"

    if limit:
        query += " LIMIT %s"
        params.append(limit)

    with conn.cursor() as cur:
        cur.execute(query, params)
        results = cur.fetchall()

    logger.info(
        f"ML training data exported: {len(results)} records, "
        f"min_quality={min_quality}, form_id={form_id}, "
        f"by user {admin_user['username']}"
    )

    return results


@router.get("/spatial-data")
async def get_spatial_data(
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    admin_user: Annotated[dict, Depends(require_admin)],
    form_id: Optional[str] = None,
    min_quality: float = Query(0.5, ge=0.0, le=1.0),
    format: str = Query("geojson", pattern="^(geojson|json)$"),
):
    """
    Export spatial data in GeoJSON format for geospatial ML.

    **Query Parameters:**
    - form_id: Filter by specific form (optional)
    - min_quality: Minimum quality score (default: 0.5)
    - format: Output format (geojson or json, default: geojson)

    **GeoJSON Response:**
    ```json
    {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [-1.6244, 6.6885]
                },
                "properties": {
                    "id": "...",
                    "form_id": "...",
                    "quality_score": 0.85,
                    "submitted_at": "2025-11-03T10:00:00",
                    "data": {...}
                }
            }
        ]
    }
    ```
    """
    # Validate form_id
    parsed_form_id = None
    if form_id:
        try:
            parsed_form_id = UUID(form_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid form_id format"
            )

    # Query spatial data
    query = """
        SELECT
            id,
            form_id,
            data,
            attachments,
            submitted_at,
            quality_score,
            completeness_score,
            gps_accuracy_score,
            longitude,
            latitude
        FROM vw_ml_training_data
        WHERE quality_score >= %s
        AND longitude IS NOT NULL
        AND latitude IS NOT NULL
    """
    params = [min_quality]

    if parsed_form_id:
        query += " AND form_id = %s"
        params.append(str(parsed_form_id))

    query += " ORDER BY submitted_at DESC"

    with conn.cursor() as cur:
        cur.execute(query, params)
        results = cur.fetchall()

    if format == "geojson":
        # Convert to GeoJSON FeatureCollection
        features = []
        for row in results:
            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [float(row["longitude"]), float(row["latitude"])],
                },
                "properties": {
                    "id": str(row["id"]),
                    "form_id": str(row["form_id"]),
                    "quality_score": float(row["quality_score"])
                    if row["quality_score"]
                    else None,
                    "completeness_score": float(row["completeness_score"])
                    if row["completeness_score"]
                    else None,
                    "gps_accuracy_score": float(row["gps_accuracy_score"])
                    if row["gps_accuracy_score"]
                    else None,
                    "submitted_at": row["submitted_at"].isoformat()
                    if row["submitted_at"]
                    else None,
                    "data": row["data"],
                    "attachments": row["attachments"],
                },
            }
            features.append(feature)

        geojson = {"type": "FeatureCollection", "features": features}

        logger.info(
            f"GeoJSON spatial data exported: {len(features)} features, "
            f"form_id={form_id}, by user {admin_user['username']}"
        )

        return Response(
            content=json.dumps(geojson, indent=2),
            media_type="application/geo+json",
            headers={
                "Content-Disposition": f"attachment; filename=spatial_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.geojson"
            },
        )
    else:
        # Return as regular JSON
        return results


@router.get("/quality-stats", response_model=dict)
async def get_quality_statistics(
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    admin_user: Annotated[dict, Depends(require_admin)],
    form_id: Optional[str] = None,
):
    """
    Get data quality statistics for ML planning.

    **Query Parameters:**
    - form_id: Get stats for specific form (optional, if omitted returns overall stats)

    **Response:**
    ```json
    {
        "total_responses": 1500,
        "avg_quality_score": 0.75,
        "avg_completeness": 0.82,
        "avg_gps_accuracy": 0.70,
        "training_suitable_count": 1200,
        "training_suitable_percentage": 80.0,
        "anomaly_count": 45,
        "anomaly_percentage": 3.0,
        "quality_distribution": {
            "excellent": 450,
            "good": 750,
            "fair": 255,
            "poor": 45
        },
        "form_id": "..." // only if form_id provided
    }
    ```
    """
    # Validate form_id
    parsed_form_id = None
    if form_id:
        try:
            parsed_form_id = UUID(form_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid form_id format"
            )

    if parsed_form_id:
        # Get stats for specific form
        stats = await conn.fetchrow(
            """
            SELECT
                COUNT(*) as total_responses,
                AVG(rq.quality_score) as avg_quality,
                AVG(rq.completeness_score) as avg_completeness,
                AVG(rq.gps_accuracy_score) as avg_gps_accuracy,
                COUNT(*) FILTER (WHERE rq.suitable_for_training = TRUE) as training_suitable,
                COUNT(*) FILTER (WHERE rq.is_anomaly = TRUE) as anomaly_count,
                COUNT(*) FILTER (WHERE rq.quality_score >= 0.8) as excellent,
                COUNT(*) FILTER (WHERE rq.quality_score >= 0.6 AND rq.quality_score < 0.8) as good,
                COUNT(*) FILTER (WHERE rq.quality_score >= 0.4 AND rq.quality_score < 0.6) as fair,
                COUNT(*) FILTER (WHERE rq.quality_score < 0.4) as poor
            FROM responses r
            LEFT JOIN response_quality rq ON r.id = rq.response_id
            WHERE r.form_id = $1
            """,
            str(parsed_form_id),
        )
    else:
        # Get overall stats
        stats = await conn.fetchrow(
            """
            SELECT
                COUNT(*) as total_responses,
                AVG(rq.quality_score) as avg_quality,
                AVG(rq.completeness_score) as avg_completeness,
                AVG(rq.gps_accuracy_score) as avg_gps_accuracy,
                COUNT(*) FILTER (WHERE rq.suitable_for_training = TRUE) as training_suitable,
                COUNT(*) FILTER (WHERE rq.is_anomaly = TRUE) as anomaly_count,
                COUNT(*) FILTER (WHERE rq.quality_score >= 0.8) as excellent,
                COUNT(*) FILTER (WHERE rq.quality_score >= 0.6 AND rq.quality_score < 0.8) as good,
                COUNT(*) FILTER (WHERE rq.quality_score >= 0.4 AND rq.quality_score < 0.6) as fair,
                COUNT(*) FILTER (WHERE rq.quality_score < 0.4) as poor
            FROM responses r
            LEFT JOIN response_quality rq ON r.id = rq.response_id
            """
        )

    total = stats["total_responses"] or 0

    result = {
        "total_responses": total,
        "avg_quality_score": round(float(stats["avg_quality"] or 0), 2),
        "avg_completeness": round(float(stats["avg_completeness"] or 0), 2),
        "avg_gps_accuracy": round(float(stats["avg_gps_accuracy"] or 0), 2),
        "training_suitable_count": stats["training_suitable"] or 0,
        "training_suitable_percentage": round(
            (stats["training_suitable"] or 0) / total * 100, 1
        )
        if total > 0
        else 0.0,
        "anomaly_count": stats["anomaly_count"] or 0,
        "anomaly_percentage": round((stats["anomaly_count"] or 0) / total * 100, 1)
        if total > 0
        else 0.0,
        "quality_distribution": {
            "excellent": stats["excellent"] or 0,  # >= 0.8
            "good": stats["good"] or 0,  # 0.6-0.8
            "fair": stats["fair"] or 0,  # 0.4-0.6
            "poor": stats["poor"] or 0,  # < 0.4
        },
    }

    if parsed_form_id:
        result["form_id"] = str(parsed_form_id)

    logger.info(
        f"Quality statistics retrieved: {total} total responses, "
        f"form_id={form_id}, by user {admin_user['username']}"
    )

    return result


@router.get("/datasets", response_model=list[dict])
async def list_ml_datasets(
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    admin_user: Annotated[dict, Depends(require_admin)],
):
    """
    List available ML datasets from the data catalog.

    **Response:**
    ```json
    [
        {
            "id": "...",
            "dataset_name": "household_survey_2025_q1",
            "dataset_type": "spatial",
            "title": "Household Survey Q1 2025",
            "description": "...",
            "total_records": 1500,
            "quality_rating": 0.85,
            "ml_task_types": ["classification", "regression"],
            "geographic_coverage": "Kumasi Metro Area",
            "date_range_start": "2025-01-01T00:00:00",
            "date_range_end": "2025-03-31T23:59:59",
            "access_level": "internal"
        }
    ]
    ```
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                id,
                dataset_name,
                dataset_type,
                title,
                description,
                keywords,
                total_records,
                total_size_mb,
                quality_rating,
                completeness_rating,
                ml_task_types,
                recommended_models,
                geographic_coverage,
                date_range_start,
                date_range_end,
                access_level,
                license_type,
                created_at,
                updated_at,
                last_refreshed_at
            FROM data_catalog
            WHERE access_level IN ('public', 'internal')
            ORDER BY updated_at DESC
            """
        )
        datasets = cur.fetchall()

    logger.info(
        f"ML datasets listed: {len(datasets)} datasets, "
        f"by user {admin_user['username']}"
    )

    return datasets


@router.get("/temporal-trends", response_model=list[dict])
async def get_temporal_trends(
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    admin_user: Annotated[dict, Depends(require_admin)],
    form_id: Optional[str] = None,
    days: int = Query(30, ge=1, le=365, description="Number of days to retrieve"),
):
    """
    Get temporal trends for time-series ML analysis.

    **Query Parameters:**
    - form_id: Filter by specific form (optional)
    - days: Number of days of historical data (default: 30, max: 365)

    **Response:**
    ```json
    [
        {
            "form_id": "...",
            "collection_date": "2025-11-03",
            "daily_responses": 45,
            "avg_daily_quality": 0.78,
            "unique_agents": 12
        }
    ]
    ```
    """
    # Validate form_id
    parsed_form_id = None
    if form_id:
        try:
            parsed_form_id = UUID(form_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid form_id format"
            )

    query = """
        SELECT
            form_id,
            collection_date,
            daily_responses,
            avg_daily_quality,
            unique_agents
        FROM vw_temporal_trends
        WHERE collection_date >= CURRENT_DATE - INTERVAL '%s days'
    """
    params = [days]

    if parsed_form_id:
        query += " AND form_id = %s"
        params.append(str(parsed_form_id))

    query += " ORDER BY collection_date DESC"

    with conn.cursor() as cur:
        cur.execute(query, params)
        results = cur.fetchall()

    logger.info(
        f"Temporal trends retrieved: {len(results)} data points, "
        f"days={days}, form_id={form_id}, by user {admin_user['username']}"
    )

    return results


@router.get("/bulk-export")
async def bulk_export_for_ml(
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    admin_user: Annotated[dict, Depends(require_admin)],
    form_id: str = Query(..., description="Form ID to export"),
    format: str = Query("json", pattern="^(json|jsonl)$"),
    min_quality: float = Query(0.6, ge=0.0, le=1.0),
    include_metadata: bool = Query(
        True, description="Include quality scores and metadata"
    ),
):
    """
    Bulk export responses for ML pipelines.

    **Query Parameters:**
    - form_id: Form ID to export (required)
    - format: Output format (json or jsonl, default: json)
    - min_quality: Minimum quality score (default: 0.6)
    - include_metadata: Include quality scores and metadata (default: true)

    **JSON Response:**
    ```json
    {
        "export_info": {
            "form_id": "...",
            "form_title": "Household Survey 2025",
            "exported_at": "2025-11-03T10:00:00",
            "total_records": 1200,
            "min_quality": 0.6,
            "exported_by": "admin"
        },
        "data": [
            {
                "id": "...",
                "response_data": {...},
                "attachments": {...},
                "submitted_at": "2025-11-03T10:00:00",
                "metadata": {
                    "quality_score": 0.85,
                    "completeness_score": 0.90,
                    "gps_accuracy_score": 0.80,
                    "latitude": 6.6885,
                    "longitude": -1.6244
                }
            }
        ]
    }
    ```

    **JSONL Response:** (Each line is a separate JSON object)
    ```
    {"id":"...","response_data":{...},"metadata":{...}}
    {"id":"...","response_data":{...},"metadata":{...}}
    ```
    """
    # Validate form_id
    try:
        parsed_form_id = UUID(form_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid form_id format"
        )

    # Get form info
    form = await get_form_by_id(conn, parsed_form_id)
    if not form:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Form not found"
        )

    # Query data
    query = """
        SELECT
            id,
            data as response_data,
            attachments,
            submitted_at,
            quality_score,
            completeness_score,
            gps_accuracy_score,
            latitude,
            longitude
        FROM vw_ml_training_data
        WHERE form_id = %s
        AND quality_score >= %s
        ORDER BY submitted_at ASC
    """

    with conn.cursor() as cur:
        cur.execute(query, (str(parsed_form_id), min_quality))
        results = cur.fetchall()

    # Format response
    if format == "jsonl":
        # JSON Lines format - one JSON object per line
        lines = []
        for row in results:
            record = {
                "id": str(row["id"]),
                "response_data": row["response_data"],
                "attachments": row["attachments"],
                "submitted_at": row["submitted_at"].isoformat()
                if row["submitted_at"]
                else None,
            }

            if include_metadata:
                record["metadata"] = {
                    "quality_score": float(row["quality_score"])
                    if row["quality_score"]
                    else None,
                    "completeness_score": float(row["completeness_score"])
                    if row["completeness_score"]
                    else None,
                    "gps_accuracy_score": float(row["gps_accuracy_score"])
                    if row["gps_accuracy_score"]
                    else None,
                    "latitude": float(row["latitude"]) if row["latitude"] else None,
                    "longitude": float(row["longitude"]) if row["longitude"] else None,
                }

            lines.append(json.dumps(record))

        content = "\n".join(lines)
        media_type = "application/x-ndjson"
        filename = (
            f"ml_export_{form_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"
        )

    else:
        # Regular JSON format with metadata
        data_records = []
        for row in results:
            record = {
                "id": str(row["id"]),
                "response_data": row["response_data"],
                "attachments": row["attachments"],
                "submitted_at": row["submitted_at"].isoformat()
                if row["submitted_at"]
                else None,
            }

            if include_metadata:
                record["metadata"] = {
                    "quality_score": float(row["quality_score"])
                    if row["quality_score"]
                    else None,
                    "completeness_score": float(row["completeness_score"])
                    if row["completeness_score"]
                    else None,
                    "gps_accuracy_score": float(row["gps_accuracy_score"])
                    if row["gps_accuracy_score"]
                    else None,
                    "latitude": float(row["latitude"]) if row["latitude"] else None,
                    "longitude": float(row["longitude"]) if row["longitude"] else None,
                }

            data_records.append(record)

        export_package = {
            "export_info": {
                "form_id": str(parsed_form_id),
                "form_title": form["title"],
                "exported_at": datetime.now().isoformat(),
                "total_records": len(data_records),
                "min_quality": min_quality,
                "exported_by": admin_user["username"],
            },
            "data": data_records,
        }

        content = json.dumps(export_package, indent=2)
        media_type = "application/json"
        filename = (
            f"ml_export_{form_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )

    logger.info(
        f"ML bulk export completed: {len(results)} records, "
        f"form_id={form_id}, format={format}, min_quality={min_quality}, "
        f"by user {admin_user['username']}"
    )

    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
