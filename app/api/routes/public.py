"""Public form routes for anonymous access."""

from typing import Annotated
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from app.core.database import get_db
from app.core.logging_config import get_logger
from app.core.rate_limiting import anonymous_rate_limiter
from app.core.responses import (
    success_response,
)
from app.services.forms import get_form_by_id
from app.services.ml_quality import calculate_and_store_quality
from app.services.responses import create_response

router = APIRouter(prefix="/public", tags=["Public"])
logger = get_logger(__name__)


class PublicResponseCreate(BaseModel):
    """Anonymous response submission request."""

    data: dict
    attachments: dict | None = None


@router.get("/forms/{form_id}")
async def get_public_form(
    form_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
):
    """
    Get a published form for public access (no authentication required).
    """
    try:
        # Get the form
        form = await get_form_by_id(conn, form_id)
        if not form:
            logger.warning(f"Public form access failed: form not found - {form_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Form not found"
            )

        # Check if form is published
        if form["status"] != "active":
            logger.warning(
                f"Public form access failed: form not published - {form_id} "
                f"(status: {form['status']})"
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Form not found"
            )

        # Return public form data (exclude sensitive information)
        public_form = {
            "id": str(form["id"]),
            "title": form["title"],
            "description": form.get("description"),
            "schema": form["schema"],
            "status": form["status"],
            "version": form["version"],
            "created_at": form["created_at"],
            "updated_at": form.get("updated_at"),
            "published_at": form.get("published_at"),
        }

        return success_response(data=public_form)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_public_form: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        )


@router.post("/forms/{form_id}/responses")
async def submit_public_response(
    form_id: UUID,
    request: PublicResponseCreate,
    http_request: Request,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
):
    """
    Submit an anonymous response to a published form.

    **Purpose:** Allow anonymous users to submit responses to published forms

    **Requirements:**
    - No authentication required
    - Only accept submissions for published forms
    - Include rate limiting to prevent abuse
    - Validate form data against schema
    - Store responses with anonymous submitter info
    - Support file attachments via the existing upload flow

    **Security Considerations:**
    - Rate limiting: Max 10 submissions per IP per hour
    - Input validation and sanitization
    - File upload validation
    - CAPTCHA integration (recommended for production)
    - Audit logging for all submissions

    **Request Body:**
    ```json
    {
      "data": {
        "field_id_1": "user_input",
        "field_id_2": 25,
        "location": {
          "latitude": 6.6885,
          "longitude": -1.6244
        }
      },
      "attachments": {
        "photo": "https://storage.example.com/uploads/uuid.jpg"
      }
    }
    ```

    **Response:**
    ```json
    {
      "success": true,
      "data": {
        "id": "response-uuid",
        "form_id": "form-uuid",
        "submitted_at": "2025-11-09T08:13:20Z",
        "data": {...},
        "attachments": {...}
      }
    }
    ```
    """
    # Get client IP address
    client_ip = http_request.client.host if http_request.client else None
    user_agent = http_request.headers.get("user-agent")

    logger.info(
        f"Anonymous response submission attempt for form {form_id} from IP: {client_ip}"
    )

    # Check rate limiting
    if client_ip:
        allowed, error_msg = anonymous_rate_limiter.check_submission_allowed(client_ip)
        if not allowed:
            logger.warning(
                f"Anonymous submission rate limited: {client_ip} - {error_msg}"
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=error_msg,
            )

    # Get the form
    form = await get_form_by_id(conn, form_id)
    if not form:
        logger.warning(f"Anonymous submission failed: form not found - {form_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Form not found"
        )

    # Check if form is published
    if form["status"] != "active":
        logger.warning(
            f"Anonymous submission failed: form not published - {form_id} "
            f"(status: {form['status']})"
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Form not found"
        )

    # Record the submission attempt
    if client_ip:
        anonymous_rate_limiter.record_submission(client_ip)

    # Create anonymous metadata
    anonymous_metadata = {
        "ip_address": client_ip,
        "user_agent": user_agent,
        "submission_method": "public_form",
        "timestamp": None,  # Will be set by the database
    }

    try:
        # Create the response with anonymous submission type
        response = await create_response(
            conn,
            form_id=form_id,
            submitted_by=None,  # Anonymous submission
            data=request.data,
            attachments=request.attachments,
            submission_type="anonymous",
            submitter_ip=client_ip,
            user_agent=user_agent,
            anonymous_metadata=anonymous_metadata,
        )

        if not response:
            logger.error(f"Failed to create anonymous response for form {form_id}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create response",
            )

        # Calculate and store ML quality scores (if available)
        try:
            quality_scores = await calculate_and_store_quality(
                conn,
                response_id=UUID(response["id"]),
                response_data=request.data,
                attachments=request.attachments,
                form_schema=form.get("schema", {}),
                submitted_at=response["submitted_at"],
            )

            logger.info(
                f"Anonymous response submitted with quality score: {quality_scores.get('quality_score', 0)} - "
                f"Form: {form_id}, Response ID: {response['id']}, IP: {client_ip}"
            )
        except Exception as quality_error:
            # Don't fail the submission if quality calculation fails
            logger.warning(
                f"Quality calculation failed for anonymous response {response['id']}: {quality_error}"
            )

        # Return public response data (exclude sensitive information)
        public_response = {
            "id": str(response["id"]),
            "form_id": str(response["form_id"]),
            "submitted_at": response["submitted_at"],
            "data": response["data"],
            "attachments": response.get("attachments"),
        }

        return success_response(data=public_response)

    except Exception as e:
        logger.error(
            f"Error submitting anonymous response - Form: {form_id}, "
            f"IP: {client_ip}: {e!s}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while submitting the response",
        )
