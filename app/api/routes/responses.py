"""Response collection routes."""

from typing import Annotated, Optional, Any
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, field_validator, model_validator
import asyncpg
import sys

from app.core.database import get_db
from app.core.logging_config import get_logger
from app.core.responses import (
    success_response,
    error_response,
    paginated_response,
    not_found_response,
    forbidden_response,
)
from app.services.responses import (
    create_response,
    get_response_by_id,
    list_responses,
    aggregate_data,
    create_time_series_data,
    prepare_map_data,
    calculate_summary_stats,
    delete_response,
)
from app.services.forms import get_form_by_id, get_agent_assigned_forms
from app.services.ml_quality import calculate_and_store_quality
from app.api.deps import get_current_user, require_admin, require_responses_admin

router = APIRouter(prefix="/responses", tags=["Responses"])
logger = get_logger(__name__)


class ResponseCreate(BaseModel):
    """Response submission request with comprehensive validation."""

    form_id: str
    data: dict
    attachments: Optional[dict] = None

    @field_validator("data")
    @classmethod
    def validate_data(cls, v: dict) -> dict:
        """
        Validate response data to prevent attacks:
        - JSON bomb (excessive nesting)
        - Excessive payload size
        - Invalid data types
        """
        # Check maximum depth to prevent JSON bombs
        max_depth = 10
        if _get_dict_depth(v) > max_depth:
            raise ValueError(f"Data nesting exceeds maximum depth of {max_depth}")

        # Check maximum size (approximate, in bytes)
        import json

        data_str = json.dumps(v)
        max_size_bytes = 1_000_000  # 1 MB limit
        if sys.getsizeof(data_str) > max_size_bytes:
            raise ValueError(
                f"Data payload exceeds maximum size of {max_size_bytes} bytes"
            )

        # Check for excessively long strings
        max_string_length = 10_000
        if not _validate_string_lengths(v, max_string_length):
            raise ValueError(
                f"Data contains strings exceeding maximum length of {max_string_length}"
            )

        return v

    @field_validator("attachments")
    @classmethod
    def validate_attachments(cls, v: Optional[dict]) -> Optional[dict]:
        """Validate attachments structure."""
        if v is None:
            return v

        # Check maximum depth
        max_depth = 5
        if _get_dict_depth(v) > max_depth:
            raise ValueError(
                f"Attachments nesting exceeds maximum depth of {max_depth}"
            )

        # Validate all values are strings (URLs)
        if not _validate_attachment_urls(v):
            raise ValueError("All attachment values must be valid URL strings")

        return v


def _get_dict_depth(d: Any, current_depth: int = 0) -> int:
    """Recursively calculate maximum nesting depth of a dictionary."""
    if not isinstance(d, dict):
        return current_depth

    if not d:  # Empty dict
        return current_depth

    return max(_get_dict_depth(v, current_depth + 1) for v in d.values())


def _validate_string_lengths(data: Any, max_length: int) -> bool:
    """Recursively validate that all strings in data are within max_length."""
    if isinstance(data, str):
        return len(data) <= max_length
    elif isinstance(data, dict):
        return all(_validate_string_lengths(v, max_length) for v in data.values())
    elif isinstance(data, list):
        return all(_validate_string_lengths(item, max_length) for item in data)
    else:
        return True  # Non-string types are OK


def _validate_attachment_urls(attachments: dict) -> bool:
    """Validate that all attachment values are strings (URLs)."""
    for value in attachments.values():
        if isinstance(value, dict):
            if not _validate_attachment_urls(value):
                return False
        elif not isinstance(value, str):
            return False
    return True


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
async def submit_response(
    request: ResponseCreate,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """
    Submit a form response with validation.

    **Security & Business Logic**:
    - Agents can only submit responses to forms they're assigned to
    - Form must be published (not draft)
    - All validation logged for audit

    **Request Body:**
    ```json
    {
        "form_id": "770e8400-e29b-41d4-a716-446655440000",
        "data": {
            "name": "John Doe",
            "age": 35,
            "location": {
                "latitude": 6.6885,
                "longitude": -1.6244
            },
            "household_size": 5
        },
        "attachments": {
            "photo": "https://spaces.example.com/bucket/photo123.jpg",
            "signature": "https://spaces.example.com/bucket/sig456.png"
        }
    }
    ```

    **Response:**
    ```json
    {
        "id": "...",
        "form_id": "...",
        "submitted_by": "...",
        "data": {...},
        "attachments": {...},
        "submitted_at": "2025-11-03T10:00:00"
    }
    ```
    """
    form_id = UUID(request.form_id)

    # Get the form
    form = await get_form_by_id(conn, form_id)
    if not form:
        logger.warning(f"Response submission failed: form not found - {form_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Form not found"
        )

    # Check if form is published
    if form["status"] != "published":
        logger.warning(
            f"Response submission failed: form not published - {form_id} "
            f"(status: {form['status']}) by user {current_user['username']}"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot submit responses to unpublished forms",
        )

    # If user is an agent, verify they're assigned to this form
    if current_user["role"] == "agent":
        assigned_forms = await get_agent_assigned_forms(conn, current_user["id"])
        assigned_form_ids = [str(f["id"]) for f in assigned_forms]

        if str(form_id) not in assigned_form_ids:
            logger.warning(
                f"Response submission failed: agent not assigned - "
                f"Form: {form_id}, Agent: {current_user['username']}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not assigned to this form",
            )

    # Create the response
    try:
        response = await create_response(
            conn,
            form_id=form_id,
            submitted_by=current_user["id"],
            data=request.data,
            attachments=request.attachments,
        )

        if not response:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create response",
            )

        # Calculate and store ML quality scores
        try:
            quality_scores = await calculate_and_store_quality(
                conn,
                response_id=UUID(response["id"]),
                response_data=request.data,
                attachments=request.attachments,
                form_schema=form.get("schema", {}),
                submitted_at=response["submitted_at"],
            )

            if quality_scores:
                logger.info(
                    f"Response submitted with quality score: {quality_scores.get('quality_score', 0)} - "
                    f"Form: {form_id}, User: {current_user['username']}, Response ID: {response['id']}"
                )
        except Exception as quality_error:
            # Don't fail the submission if quality calculation fails
            logger.warning(
                f"Quality calculation failed for response {response['id']}: {quality_error}"
            )

        return success_response(data=response)

    except Exception as e:
        logger.error(
            f"Error submitting response - Form: {form_id}, "
            f"User: {current_user['username']}: {str(e)}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while submitting the response",
        )


@router.get("", response_model=dict)
async def list_responses_route(
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    form_id: Optional[str] = None,
    view: Optional[str] = Query(
        None,
        pattern="^(table|chart|time_series|map|summary)$",
        description="View mode: table, chart, time_series, map, summary",
    ),
    group_by: Optional[str] = Query(
        None, description="Field to group by for charts/aggregations"
    ),
    aggregate: Optional[str] = Query(
        None, pattern="^(count|sum|avg|min|max)$", description="Aggregation function"
    ),
    chart_type: Optional[str] = Query(
        None, pattern="^(bar|pie|line|scatter|histogram)$", description="Chart type"
    ),
    date_field: Optional[str] = Query(
        "submitted_at", description="Date field for time series"
    ),
    time_granularity: Optional[str] = Query(
        "day", pattern="^(hour|day|week|month|year)$", description="Time granularity"
    ),
    limit: Optional[int] = Query(
        100, ge=1, le=1000, description="Maximum records to return"
    ),
    offset: Optional[int] = Query(0, ge=0, description="Pagination offset"),
):
    """
    List responses with optional filters and view modes.

    **Query Parameters:**
    - form_id: Filter by form
    - view: View mode (table, chart, time_series, map, summary)
    - group_by: Field to group by for aggregations
    - aggregate: Aggregation function (count, sum, avg, min, max)
    - chart_type: Chart type (bar, pie, line, scatter, histogram)
    - date_field: Date field for time series (default: submitted_at)
    - time_granularity: Time grouping (hour, day, week, month, year)
    - limit: Maximum records (1-1000, default: 100)
    - offset: Pagination offset (default: 0)

    **Default Response (view=table or not specified):**
    ```json
    {
        "success": true,
        "data": {
            "responses": [...],
            "total": 150,
            "limit": 100,
            "offset": 0
        }
    }
    ```

    **Chart View Response (view=chart):**
    ```json
    {
        "success": true,
        "data": {
            "chart_data": [
                {"label": "Category A", "value": 45, "percentage": 30.0},
                {"label": "Category B", "value": 105, "percentage": 70.0}
            ],
            "chart_type": "pie",
            "group_by": "location",
            "aggregate": "count"
        }
    }
    ```

    **Time Series Response (view=time_series):**
    ```json
    {
        "success": true,
        "data": {
            "time_series": [
                {"date": "2025-11-01", "value": 25},
                {"date": "2025-11-02", "value": 30}
            ],
            "granularity": "day",
            "date_field": "submitted_at"
        }
    }
    ```
    """
    # Validate UUID format
    parsed_form_id = None
    if form_id:
        try:
            parsed_form_id = UUID(form_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid form_id format. Must be a valid UUID",
            )

    # Ensure pagination parameters have defaults
    actual_limit = limit if limit is not None else 100
    actual_offset = offset if offset is not None else 0

    # Get raw responses data
    if current_user["role"] == "agent":
        # Agents can see their own authenticated responses AND anonymous responses from forms they're assigned to
        if parsed_form_id:
            # Check if agent is assigned to this specific form
            assigned_forms = await get_agent_assigned_forms(conn, current_user["id"])
            assigned_form_ids = [str(f["id"]) for f in assigned_forms]

            if str(parsed_form_id) in assigned_form_ids:
                # Agent is assigned to this form - can see all responses (including anonymous)
                raw_responses = await list_responses(conn, form_id=parsed_form_id)
            else:
                # Agent is not assigned - can only see their own authenticated responses
                raw_responses = await list_responses(
                    conn, form_id=parsed_form_id, agent_id=current_user["id"]
                )
        else:
            # No specific form - get agent's responses across all assigned forms
            raw_responses = await list_responses(conn, agent_id=current_user["id"])
    else:
        # Admin can see all responses
        raw_responses = await list_responses(conn, form_id=parsed_form_id)

    # Apply view transformations
    try:
        if view == "table" or not view:
            # Default table view with pagination
            total = len(raw_responses)
            paginated_responses = raw_responses[
                actual_offset : actual_offset + actual_limit
            ]
            page = (actual_offset // actual_limit) + 1 if actual_limit > 0 else 1
            return paginated_response(
                items=paginated_responses, page=page, limit=actual_limit, total=total
            )

        elif view == "chart":
            if not group_by:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="group_by parameter is required for chart view",
                )

            # For chart view, we aggregate by the group_by field itself
            # If aggregate requires a field (sum, avg, min, max), use the group_by field
            chart_data = aggregate_data(
                raw_responses, group_by, aggregate or "count", group_by
            )

            return success_response(
                data={
                    "chart_data": chart_data,
                    "chart_type": chart_type or "bar",
                    "group_by": group_by,
                    "aggregate": aggregate or "count",
                }
            )

        elif view == "time_series":
            time_series_data = create_time_series_data(
                raw_responses,
                date_field or "submitted_at",
                time_granularity or "day",
                aggregate or "count",
            )

            return success_response(
                data={
                    "time_series": time_series_data,
                    "granularity": time_granularity or "day",
                    "date_field": date_field or "submitted_at",
                    "aggregate": aggregate or "count",
                }
            )

        elif view == "map":
            map_data = prepare_map_data(raw_responses)

            return success_response(
                data={"map_data": map_data, "total_points": len(map_data)}
            )

        elif view == "summary":
            summary = calculate_summary_stats(raw_responses)

            return success_response(data=summary)

        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid view mode: {view}",
            )
    except HTTPException:
        # Re-raise HTTPExceptions (like validation errors) without logging them as errors
        raise
    except Exception as e:
        logger.error(
            f"Error processing view mode '{view}' for user {current_user['username']}: {str(e)}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while processing the {view} view. Please check your parameters and try again.",
        )


@router.delete("/cleanup", response_model=dict)
async def cleanup_deleted_responses(
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(require_responses_admin)],
):
    """
    Permanently delete all soft-deleted responses (admin only).

    **Warning:** This action cannot be undone. It permanently removes all soft-deleted responses from the database.

    **Response:**
    ```json
    {
        "success": true,
        "message": "Cleaned up X deleted responses",
        "deleted_count": 5
    }
    ```
    """
    # Count how many will be deleted
    count_result = await conn.fetchval(
        "SELECT COUNT(*) FROM responses WHERE deleted = TRUE"
    )
    deleted_count = count_result or 0

    if deleted_count == 0:
        return success_response(
            message="No deleted responses to clean up", data={"deleted_count": 0}
        )

    # Permanently delete the records
    await conn.execute("DELETE FROM responses WHERE deleted = TRUE")

    return success_response(
        message=f"Cleaned up {deleted_count} deleted responses",
        data={"deleted_count": deleted_count},
    )


@router.get("/{response_id}", response_model=dict)
async def get_response(
    response_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Get response by ID."""
    response = await get_response_by_id(conn, response_id)
    if not response:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Response not found"
        )

    # Permission-based access control
    if current_user["role"] == "agent":
        # Agents can view their own authenticated responses AND anonymous responses
        # (since anonymous responses belong to their organization's forms)
        if (
            response["submission_type"] == "authenticated"
            and str(response["submitted_by"]) != current_user["id"]
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
            )
        # Anonymous responses are allowed for agents (they can see responses from their org's forms)

    # Admins can see all responses

    return success_response(data=response)


@router.delete("/{response_id}", response_model=dict)
async def delete_response_route(
    response_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """
    Delete a response (admin only). This is a soft delete.

    **Response:**
    ```json
    {
        "success": true,
        "message": "Response deleted successfully"
    }
    ```
    """
    # Only admins can delete responses
    if current_user["role"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required"
        )

    # Check if response exists and get its details for permission check
    response = await get_response_by_id(conn, response_id)
    if not response:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Response not found"
        )

    success = await delete_response(conn, response_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Response not found"
        )

    return success_response(message="Response deleted successfully")
