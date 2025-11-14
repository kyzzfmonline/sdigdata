"""ML Data Quality Service - Calculate quality scores for responses."""

from datetime import datetime
from typing import Any
from uuid import UUID

import asyncpg

from app.core.logging_config import get_logger

logger = get_logger(__name__)


def calculate_completeness_score(response_data: dict, form_schema: dict) -> float:
    """
    Calculate completeness score based on required fields.

    Args:
        response_data: The response data dictionary
        form_schema: The form schema with field definitions

    Returns:
        Score from 0.0 to 1.0
    """
    if not form_schema.get("fields"):
        return 1.0

    required_fields = [
        field["id"]
        for field in form_schema.get("fields", [])
        if field.get("required", False)
    ]

    if not required_fields:
        return 1.0

    filled_required = sum(
        1
        for field_id in required_fields
        if response_data.get(field_id)
    )

    return round(filled_required / len(required_fields), 2)


def calculate_gps_accuracy_score(response_data: dict) -> float:
    """
    Calculate GPS accuracy score.

    Args:
        response_data: The response data dictionary

    Returns:
        Score from 0.0 to 1.0
    """
    location = response_data.get("location")
    if not location:
        return 0.0

    # Check if both lat/lon exist
    if not (location.get("latitude") and location.get("longitude")):
        return 0.0

    # Validate coordinates are in valid range
    lat = location.get("latitude", 0)
    lon = location.get("longitude", 0)

    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return 0.0

    # If accuracy is provided, score based on accuracy
    accuracy = location.get("accuracy", 100)  # meters
    if accuracy <= 5:
        return 1.0
    elif accuracy <= 10:
        return 0.9
    elif accuracy <= 20:
        return 0.8
    elif accuracy <= 50:
        return 0.6
    elif accuracy <= 100:
        return 0.4
    else:
        return 0.2


def calculate_photo_quality_score(attachments: dict[str, Any] | None) -> float:
    """
    Calculate photo quality score based on attachments.

    Args:
        attachments: The attachments dictionary

    Returns:
        Score from 0.0 to 1.0
    """
    if not attachments:
        return 0.5  # Neutral score if no photos required

    photo_count = len(
        [
            v
            for v in attachments.values()
            if v and isinstance(v, str) and v.startswith("http")
        ]
    )

    if photo_count == 0:
        return 0.5
    elif photo_count >= 3:
        return 1.0
    elif photo_count == 2:
        return 0.8
    else:
        return 0.6


def calculate_response_time_score(submitted_at: Any, created_at: Any = None) -> float:
    """
    Calculate response time score (reasonable completion time).

    Args:
        submitted_at: Submission timestamp
        created_at: Form creation timestamp (optional)

    Returns:
        Score from 0.0 to 1.0
    """
    # For now, return neutral score
    # TODO: Calculate based on form complexity and reasonable completion time
    return 0.7


def calculate_consistency_score(response_data: dict) -> float:
    """
    Calculate data consistency score (detect logical inconsistencies).

    Args:
        response_data: The response data dictionary

    Returns:
        Score from 0.0 to 1.0
    """
    issues = 0

    # Check for negative numbers where they shouldn't be
    for key, value in response_data.items():
        if isinstance(value, (int, float)) and value < 0:
            # Check if this field should allow negatives
            if "age" in key.lower() or "count" in key.lower() or "size" in key.lower():
                issues += 1

    # TODO: Add more consistency checks based on business rules

    if issues == 0:
        return 1.0
    elif issues == 1:
        return 0.8
    elif issues == 2:
        return 0.6
    else:
        return 0.4


async def detect_anomaly(
    response_data: dict, form_id: UUID, conn: asyncpg.Connection
) -> tuple[bool, str | None]:
    """
    Detect if response is a statistical anomaly.

    Args:
        response_data: The response data dictionary
        form_id: The form ID
        conn: Database connection

    Returns:
        Tuple of (is_anomaly, reason)
    """
    anomalies = []

    # Check for suspiciously fast completion times (< 30 seconds)
    if "created_at" in response_data and "submitted_at" in response_data:
        try:
            created_at = datetime.fromisoformat(
                response_data["created_at"].replace("Z", "+00:00")
            )
            submitted_at = datetime.fromisoformat(
                response_data["submitted_at"].replace("Z", "+00:00")
            )
            completion_time = (submitted_at - created_at).total_seconds()

            if completion_time < 30:
                anomalies.append("Response completed suspiciously fast (< 30 seconds)")
        except (ValueError, TypeError):
            pass

    # Check for outlier numeric values compared to form averages
    for key, value in response_data.items():
        if isinstance(value, (int, float)) and key not in [
            "latitude",
            "longitude",
            "accuracy",
        ]:
            try:
                # Get form statistics for this field
                stats = await conn.fetchrow(
                    """
                    SELECT
                        AVG((data->>$1)::float) as avg_value,
                        STDDEV((data->>$1)::float) as std_dev,
                        COUNT(*) as sample_size
                    FROM responses
                    WHERE form_id = $2 AND deleted = FALSE
                    AND data->>$1 IS NOT NULL
                    AND (data->>$1)::float != 0
                    """,
                    key,
                    str(form_id),
                )

                if stats and stats.get("sample_size") and stats["sample_size"] > 5:
                    avg_value = stats.get("avg_value", 0)
                    std_dev = stats.get("std_dev", 1) or 1

                    if (
                        avg_value is not None
                        and std_dev is not None
                        and abs(value - avg_value) > 3 * std_dev
                    ):
                        anomalies.append(
                            f"Value for '{key}' ({value}) is 3+ standard deviations from mean"
                        )
            except (ValueError, TypeError):
                continue

    # Check for duplicate GPS coordinates (potential location spoofing)
    if "location" in response_data and isinstance(response_data["location"], dict):
        location = response_data["location"]
        if "latitude" in location and "longitude" in location:
            lat, lon = location["latitude"], location["longitude"]

            # Check if this exact coordinate has been used before
            duplicate_count = await conn.fetchval(
                """
                SELECT COUNT(*)
                FROM responses
                WHERE form_id = $1 AND deleted = FALSE
                AND data->'location'->>'latitude' = $2
                AND data->'location'->>'longitude' = $3
                """,
                str(form_id),
                str(lat),
                str(lon),
            )

            if duplicate_count and duplicate_count > 2:
                anomalies.append("GPS coordinates match multiple previous responses")

    # Check for copy-paste patterns (identical long text responses)
    for key, value in response_data.items():
        if isinstance(value, str) and len(value) > 100:
            # Check if this exact text appears in multiple responses
            duplicate_text_count = await conn.fetchval(
                """
                SELECT COUNT(*)
                FROM responses
                WHERE form_id = $1 AND deleted = FALSE
                AND data->>$2 = $3
                """,
                str(form_id),
                key,
                value,
            )

            if duplicate_text_count and duplicate_text_count > 1:
                anomalies.append(
                    f"Identical text in '{key}' matches {duplicate_text_count} other responses"
                )

    is_anomaly = len(anomalies) > 0
    reason = "; ".join(anomalies) if anomalies else None

    return is_anomaly, reason


def calculate_overall_quality(
    completeness: float,
    gps_accuracy: float,
    photo_quality: float,
    response_time: float,
    consistency: float,
) -> float:
    """
    Calculate overall quality score with weighted components.

    Args:
        completeness: Completeness score
        gps_accuracy: GPS accuracy score
        photo_quality: Photo quality score
        response_time: Response time score
        consistency: Consistency score

    Returns:
        Weighted overall score from 0.0 to 1.0
    """
    # Weights for different components
    weights = {
        "completeness": 0.35,  # Most important - complete data
        "gps_accuracy": 0.25,  # Critical for spatial ML
        "photo_quality": 0.15,  # Important for CV
        "response_time": 0.10,  # Less critical
        "consistency": 0.15,  # Data integrity
    }

    overall = (
        completeness * weights["completeness"]
        + gps_accuracy * weights["gps_accuracy"]
        + photo_quality * weights["photo_quality"]
        + response_time * weights["response_time"]
        + consistency * weights["consistency"]
    )

    return round(overall, 2)


async def calculate_and_store_quality(
    conn: asyncpg.Connection,
    response_id: UUID,
    response_data: dict,
    attachments: dict[str, Any] | None,
    form_schema: dict,
    submitted_at: Any,
) -> dict[str, Any] | None:
    """
    Calculate and store quality scores for a response.

    Args:
        conn: Database connection
        response_id: Response ID
        response_data: Response data dictionary
        attachments: Attachments dictionary
        form_schema: Form schema
        submitted_at: Submission timestamp

    Returns:
        Dictionary with quality scores
    """
    # Calculate component scores
    completeness = calculate_completeness_score(response_data, form_schema)
    gps_accuracy = calculate_gps_accuracy_score(response_data)
    photo_quality = calculate_photo_quality_score(attachments)
    response_time = calculate_response_time_score(submitted_at)
    consistency = calculate_consistency_score(response_data)

    # Calculate overall score
    overall = calculate_overall_quality(
        completeness, gps_accuracy, photo_quality, response_time, consistency
    )

    # Detect anomalies
    is_anomaly, anomaly_reason = await detect_anomaly(response_data, response_id, conn)

    # Determine if suitable for training
    suitable_for_training = overall >= 0.6 and not is_anomaly and completeness >= 0.8

    # Store in database
    result = await conn.fetchrow(
        """
        INSERT INTO response_quality (
            response_id, quality_score, completeness_score,
            gps_accuracy_score, photo_quality_score,
            response_time_score, consistency_score,
            is_anomaly, anomaly_reason, suitable_for_training
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        ON CONFLICT (response_id) DO UPDATE SET
            quality_score = EXCLUDED.quality_score,
            completeness_score = EXCLUDED.completeness_score,
            gps_accuracy_score = EXCLUDED.gps_accuracy_score,
            photo_quality_score = EXCLUDED.photo_quality_score,
            response_time_score = EXCLUDED.response_time_score,
            consistency_score = EXCLUDED.consistency_score,
            is_anomaly = EXCLUDED.is_anomaly,
            anomaly_reason = EXCLUDED.anomaly_reason,
            suitable_for_training = EXCLUDED.suitable_for_training,
            updated_at = CURRENT_TIMESTAMP
        RETURNING
            quality_score, completeness_score, gps_accuracy_score,
            photo_quality_score, response_time_score, consistency_score,
            is_anomaly, suitable_for_training
        """,
        str(response_id),
        overall,
        completeness,
        gps_accuracy,
        photo_quality,
        response_time,
        consistency,
        is_anomaly,
        anomaly_reason,
        suitable_for_training,
    )

    logger.info(
        f"Quality calculated for response {response_id}: "
        f"overall={overall}, suitable_for_training={suitable_for_training}"
    )

    return dict(result) if result else None


async def get_quality_scores(
    conn: asyncpg.Connection, response_id: UUID
) -> dict[str, Any] | None:
    """Get quality scores for a response."""
    result = await conn.fetchrow(
        """
        SELECT
            quality_score, completeness_score, gps_accuracy_score,
            photo_quality_score, response_time_score, consistency_score,
            is_anomaly, anomaly_reason, suitable_for_training,
            calculated_at, updated_at
        FROM response_quality
        WHERE response_id = $1
        """,
        str(response_id),
    )
    return dict(result) if result else None


async def get_form_quality_stats(
    conn: asyncpg.Connection, form_id: UUID
) -> dict[str, Any] | None:
    """Get quality statistics for a form."""
    result = await conn.fetchrow(
        """
        SELECT
            COUNT(*) as total_responses,
            AVG(rq.quality_score) as avg_quality,
            AVG(rq.completeness_score) as avg_completeness,
            AVG(rq.gps_accuracy_score) as avg_gps_accuracy,
            COUNT(*) FILTER (WHERE rq.suitable_for_training = TRUE) as training_suitable,
            COUNT(*) FILTER (WHERE rq.is_anomaly = TRUE) as anomaly_count
        FROM responses r
        LEFT JOIN response_quality rq ON r.id = rq.response_id
        WHERE r.form_id = $1
        """,
        str(form_id),
    )
    return dict(result) if result else None
