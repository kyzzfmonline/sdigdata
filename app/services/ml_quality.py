"""ML Data Quality Service - Calculate quality scores for responses."""

import asyncpg
from typing import Optional, Dict, Any
from uuid import UUID
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
        1 for field_id in required_fields
        if field_id in response_data and response_data[field_id]
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


def calculate_photo_quality_score(attachments: dict) -> float:
    """
    Calculate photo quality score based on attachments.

    Args:
        attachments: The attachments dictionary

    Returns:
        Score from 0.0 to 1.0
    """
    if not attachments:
        return 0.5  # Neutral score if no photos required

    photo_count = len([
        v for v in attachments.values()
        if v and isinstance(v, str) and v.startswith("http")
    ])

    if photo_count == 0:
        return 0.5
    elif photo_count >= 3:
        return 1.0
    elif photo_count == 2:
        return 0.8
    else:
        return 0.6


def calculate_response_time_score(submitted_at, created_at=None) -> float:
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


def detect_anomaly(response_data: dict, form_id: UUID, conn: asyncpg.Connection) -> tuple[bool, Optional[str]]:
    """
    Detect if response is a statistical anomaly.

    Args:
        response_data: The response data dictionary
        form_id: The form ID
        conn: Database connection

    Returns:
        Tuple of (is_anomaly, reason)
    """
    # TODO: Implement statistical anomaly detection
    # - Compare numeric values to form averages
    # - Check for duplicate GPS coordinates
    # - Flag suspiciously fast completion times
    # - Detect copy-paste patterns

    return False, None


def calculate_overall_quality(
    completeness: float,
    gps_accuracy: float,
    photo_quality: float,
    response_time: float,
    consistency: float
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
        "completeness": 0.35,   # Most important - complete data
        "gps_accuracy": 0.25,   # Critical for spatial ML
        "photo_quality": 0.15,  # Important for CV
        "response_time": 0.10,  # Less critical
        "consistency": 0.15     # Data integrity
    }

    overall = (
        completeness * weights["completeness"] +
        gps_accuracy * weights["gps_accuracy"] +
        photo_quality * weights["photo_quality"] +
        response_time * weights["response_time"] +
        consistency * weights["consistency"]
    )

    return round(overall, 2)


async def calculate_and_store_quality(conn: asyncpg.Connection,
    response_id: UUID,
    response_data: dict,
    attachments: Optional[dict],
    form_schema: dict,
    submitted_at
) -> Dict[str, Any]:
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
    is_anomaly, anomaly_reason = detect_anomaly(response_data, response_id, conn)

    # Determine if suitable for training
    suitable_for_training = (
        overall >= 0.6 and
        not is_anomaly and
        completeness >= 0.8
    )

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
        str(response_id), overall, completeness, gps_accuracy,
        photo_quality, response_time, consistency,
        is_anomaly, anomaly_reason, suitable_for_training
    )

    logger.info(
        f"Quality calculated for response {response_id}: "
        f"overall={overall}, suitable_for_training={suitable_for_training}"
    )

    return dict(result) if result else None


async def get_quality_scores(conn: asyncpg.Connection, response_id: UUID) -> Optional[dict]:
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
        str(response_id)
    )
    return dict(result) if result else None


async def get_form_quality_stats(conn: asyncpg.Connection, form_id: UUID) -> dict:
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
        str(form_id)
    )
    return dict(result) if result else None
