"""Response service functions."""

from datetime import datetime, timedelta
import json
from typing import Any
from uuid import UUID

import asyncpg


async def create_response(
    conn: asyncpg.Connection,
    form_id: UUID,
    submitted_by: UUID | None,
    data: dict,
    attachments: dict | None = None,
    submission_type: str = "authenticated",
    submitter_ip: str | None = None,
    user_agent: str | None = None,
    anonymous_metadata: dict | None = None,
) -> dict | None:
    """Create a new form response."""
    # Get form to obtain organization_id
    from app.services.forms import get_form_by_id

    form = await get_form_by_id(conn, form_id)
    if not form:
        return None

    result = await conn.fetchrow(
        """
        INSERT INTO responses (form_id, organization_id, submitted_by, data, attachments, submission_type, submitter_ip, user_agent, anonymous_metadata, status)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        RETURNING id, form_id, organization_id, submitted_by, data, attachments, submitted_at, submission_type, submitter_ip, user_agent, anonymous_metadata, status
        """,
        str(form_id),
        str(form["organization_id"]),
        str(submitted_by) if submitted_by else None,
        json.dumps(data),
        json.dumps(attachments) if attachments else None,
        submission_type,
        submitter_ip,
        user_agent,
        json.dumps(anonymous_metadata) if anonymous_metadata else None,
        'submitted',
    )
    if result:
        result_dict = dict(result)
        result_dict["data"] = (
            json.loads(result_dict["data"])
            if isinstance(result_dict["data"], str)
            else result_dict["data"]
        )
        if result_dict.get("attachments"):
            result_dict["attachments"] = (
                json.loads(result_dict["attachments"])
                if isinstance(result_dict["attachments"], str)
                else result_dict["attachments"]
            )
        if result_dict.get("anonymous_metadata"):
            result_dict["anonymous_metadata"] = (
                json.loads(result_dict["anonymous_metadata"])
                if isinstance(result_dict["anonymous_metadata"], str)
                else result_dict["anonymous_metadata"]
            )
        return result_dict
    return None


async def get_response_by_id(
    conn: asyncpg.Connection, response_id: UUID
) -> dict | None:
    """Get response by ID."""
    result = await conn.fetchrow(
        """
        SELECT r.id, r.form_id, r.submitted_by, r.data, r.attachments, r.submitted_at,
                r.submission_type, r.submitter_ip, r.anonymous_metadata,
                COALESCE(u.username, 'Anonymous') as submitted_by_username
        FROM responses r
        LEFT JOIN users u ON r.submitted_by = u.id
        WHERE r.id = $1 AND r.deleted = FALSE
        """,
        str(response_id),
    )
    if result:
        result_dict = dict(result)

        # Convert IP address objects to strings
        if result_dict.get("submitter_ip"):
            result_dict["submitter_ip"] = str(result_dict["submitter_ip"])

        result_dict["data"] = (
            json.loads(result_dict["data"])
            if isinstance(result_dict["data"], str)
            else result_dict["data"]
        )
        if result_dict.get("attachments"):
            result_dict["attachments"] = (
                json.loads(result_dict["attachments"])
                if isinstance(result_dict["attachments"], str)
                else result_dict["attachments"]
            )
        if result_dict.get("anonymous_metadata"):
            result_dict["anonymous_metadata"] = (
                json.loads(result_dict["anonymous_metadata"])
                if isinstance(result_dict["anonymous_metadata"], str)
                else result_dict["anonymous_metadata"]
            )
        return result_dict
    return None


async def list_responses(
    conn: asyncpg.Connection,
    form_id: UUID | None = None,
    submitted_by: UUID | None = None,
    agent_id: UUID | None = None,
) -> list[dict]:
    """List responses with optional filters."""
    query = """
        SELECT r.id, r.form_id, r.submitted_by, r.data, r.attachments, r.submitted_at,
               r.submission_type, r.submitter_ip, r.anonymous_metadata,
               COALESCE(u.username, 'Anonymous') as submitted_by_username
        FROM responses r
        LEFT JOIN users u ON r.submitted_by::text = u.id::text
        WHERE r.deleted = FALSE
    """
    params: list[str] = []

    if form_id:
        query += f" AND r.form_id::text = ${len(params) + 1}"
        params.append(str(form_id))

    if submitted_by:
        query += f" AND r.submitted_by::text = ${len(params) + 1}"
        params.append(str(submitted_by))

    if agent_id:
        # For agents, show their own authenticated responses AND anonymous responses from their organization's forms
        query += f" AND (r.submitted_by::text = ${len(params) + 1} OR r.submission_type = 'anonymous')"
        params.append(str(agent_id))

    query += " ORDER BY r.submitted_at DESC"

    results = await conn.fetch(query, *params)
    output = []
    for result in results:
        result_dict = dict(result)

        # Convert UUID objects to strings for JSON serialization
        for key in ['id', 'form_id', 'submitted_by']:
            if key in result_dict and result_dict[key] is not None:
                result_dict[key] = str(result_dict[key])

        # Convert datetime objects to ISO format strings
        from datetime import datetime
        for key in ['submitted_at']:
            if key in result_dict and result_dict[key] is not None:
                if isinstance(result_dict[key], datetime):
                    result_dict[key] = result_dict[key].isoformat()

        # Convert IP address objects to strings for JSON serialization
        if result_dict.get("submitter_ip"):
            result_dict["submitter_ip"] = str(result_dict["submitter_ip"])

        # Safely parse JSON data
        try:
            result_dict["data"] = (
                json.loads(result_dict["data"])
                if isinstance(result_dict["data"], str)
                else result_dict["data"]
            )
        except (json.JSONDecodeError, TypeError):
            # If JSON is invalid, keep as string or set to empty dict
            result_dict["data"] = (
                result_dict["data"] if isinstance(result_dict["data"], dict) else {}
            )

        # Safely parse attachments
        if result_dict.get("attachments"):
            try:
                result_dict["attachments"] = (
                    json.loads(result_dict["attachments"])
                    if isinstance(result_dict["attachments"], str)
                    else result_dict["attachments"]
                )
            except (json.JSONDecodeError, TypeError):
                result_dict["attachments"] = {}

        output.append(result_dict)
    return output


async def get_form_responses_count(conn: asyncpg.Connection, form_id: UUID) -> int:
    """Get count of responses for a form."""
    result = await conn.fetchval(
        "SELECT COUNT(*) FROM responses WHERE form_id = $1", str(form_id)
    )
    return result if result else 0


def aggregate_data(
    responses: list[dict], group_by: str, aggregate: str, field: str | None = None
) -> list[dict]:
    """Aggregate response data by group and function."""
    from collections import defaultdict
    import statistics

    groups = defaultdict(list)

    # Group responses
    for response in responses:
        key = _get_nested_value(response["data"], group_by)
        if key is not None:
            groups[key].append(response)

    result = []
    for group_key, group_responses in groups.items():
        value = float(len(group_responses))  # Default to count

        if aggregate == "count":
            value = len(group_responses)
        elif field and aggregate in ["sum", "avg", "min", "max"]:
            values: list[int | float] = []
            for resp in group_responses:
                val = _get_nested_value(resp["data"], field)
                if isinstance(val, (int, float)) and not isinstance(val, bool):
                    values.append(val)
            if values:
                try:
                    if aggregate == "sum":
                        value = sum(values)
                    elif aggregate == "avg":
                        value = statistics.mean(values)
                    elif aggregate == "min":
                        value = min(values)
                    elif aggregate == "max":
                        value = max(values)
                    else:
                        value = len(group_responses)  # Fallback to count
                except (ValueError, TypeError, statistics.StatisticsError):
                    value = len(
                        group_responses
                    )  # Fallback to count on calculation error
            # else: keep default value = len(group_responses)

        total_responses = len(responses)
        percentage = (
            (len(group_responses) / total_responses * 100) if total_responses > 0 else 0
        )

        result.append(
            {
                "label": str(group_key),
                "value": value,
                "count": len(group_responses),
                "percentage": round(percentage, 1),
            }
        )

    return sorted(result, key=lambda x: x["value"], reverse=True)


def create_time_series_data(
    responses: list[dict],
    date_field: str | None,
    granularity: str | None,
    aggregate: str,
    field: str | None = None,
) -> list[dict]:
    """Create time series data from responses."""
    from collections import defaultdict
    from datetime import datetime
    import statistics

    groups = defaultdict(list)

    # Group by time period
    for response in responses:
        date_value = response.get(date_field, response["submitted_at"])
        if isinstance(date_value, str):
            try:
                date_value = datetime.fromisoformat(date_value.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                continue  # Skip responses with invalid dates
        elif not isinstance(date_value, datetime):
            continue  # Skip responses without valid dates

        period_key = _get_time_period_key(date_value, granularity or "day")
        groups[period_key].append(response)

    result = []
    for period_key, period_responses in sorted(groups.items()):
        value = float(len(period_responses))  # Default to count

        if aggregate == "count":
            value = len(period_responses)
        elif field and aggregate in ["sum", "avg", "min", "max"]:
            values: list[int | float] = []
            for resp in period_responses:
                val = _get_nested_value(resp["data"], field)
                if isinstance(val, (int, float)):
                    values.append(val)
            if values:
                if aggregate == "sum":
                    value = sum(values)
                elif aggregate == "avg":
                    value = statistics.mean(values)
                elif aggregate == "min":
                    value = min(values)
                elif aggregate == "max":
                    value = max(values)
                # else: keep default value = 0
            # else: keep default value = len(period_responses)

        result.append(
            {"date": period_key, "value": value, "count": len(period_responses)}
        )

    return result


def prepare_map_data(responses: list[dict]) -> list[dict]:
    """Prepare data for map visualization."""
    map_data = []

    for response in responses:
        location = _get_nested_value(response["data"], "location")
        if location and isinstance(location, dict):
            # Try different possible field names for latitude/longitude
            lat = location.get("latitude") or location.get("lat")
            lng = (
                location.get("longitude") or location.get("lng") or location.get("lon")
            )

            if lat is not None and lng is not None:
                try:
                    # Ensure coordinates are valid numbers
                    lat_float = float(lat)
                    lng_float = float(lng)

                    # Basic coordinate validation
                    if -90 <= lat_float <= 90 and -180 <= lng_float <= 180:
                        map_data.append(
                            {
                                "id": str(response["id"]),
                                "latitude": lat_float,
                                "longitude": lng_float,
                                "submitted_at": response["submitted_at"],
                                "data": response["data"],
                            }
                        )
                except (ValueError, TypeError):
                    continue  # Skip invalid coordinates

    return map_data


def calculate_summary_stats(responses: list[dict]) -> dict:
    """Calculate summary statistics for responses."""
    if not responses:
        return {
            "total_responses": 0,
            "date_range": {"start": None, "end": None},
            "submission_types": {"authenticated": 0, "anonymous": 0},
        }

    # Basic counts
    total = len(responses)
    submission_types = {"authenticated": 0, "anonymous": 0}

    for resp in responses:
        sub_type = resp.get("submission_type", "authenticated")
        if sub_type in submission_types:
            submission_types[sub_type] += 1
        else:
            submission_types[sub_type] = 1

    # Date range - handle various date formats
    dates = []
    start_date = None
    end_date = None
    for resp in responses:
        date_value = resp.get("submitted_at")
        if date_value:
            if isinstance(date_value, str):
                try:
                    # Try to parse as ISO format
                    datetime.fromisoformat(date_value.replace("Z", "+00:00"))
                    dates.append(date_value)  # Keep original string format
                except (ValueError, TypeError):
                    continue  # Skip invalid dates
            elif isinstance(date_value, datetime):
                dates.append(date_value.isoformat())
            else:
                continue  # Skip non-date values

    if dates:
        dates.sort()
        start_date = dates[0]
        end_date = dates[-1]
    else:
        start_date = end_date = None

    return {
        "total_responses": total,
        "date_range": {"start": start_date, "end": end_date},
        "submission_types": submission_types,
    }


def _get_nested_value(data: dict, path: str) -> Any:
    """Get nested value from dict using dot notation."""
    keys = path.split(".")
    current = data

    try:
        for key in keys:
            if isinstance(current, dict):
                current = current[key]
            else:
                return None
        return current
    except (KeyError, TypeError):
        return None


def _get_time_period_key(date: datetime, granularity: str | None) -> str:
    """Get time period key for grouping."""
    actual_granularity = granularity or "day"
    if actual_granularity == "hour":
        return date.strftime("%Y-%m-%d %H:00")
    elif actual_granularity == "day":
        return date.strftime("%Y-%m-%d")
    elif actual_granularity == "week":
        # Get Monday of the week
        monday = date - timedelta(days=date.weekday())
        return monday.strftime("%Y-%m-%d")
    elif actual_granularity == "month":
        return date.strftime("%Y-%m")
    elif actual_granularity == "year":
        return date.strftime("%Y")
    else:
        return date.strftime("%Y-%m-%d")


async def delete_response(conn: asyncpg.Connection, response_id: UUID) -> bool:
    """Soft delete a response."""
    result = await conn.execute(
        """
        UPDATE responses
        SET deleted = TRUE, deleted_at = CURRENT_TIMESTAMP
        WHERE id = $1 AND deleted = FALSE
        """,
        str(response_id),
    )
    return int(result.split()[-1]) > 0
