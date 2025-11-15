"""Form lifecycle management API routes."""

from typing import Annotated, Any
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.api.deps import get_current_user, get_db, require_admin
from app.core.responses import error_response_dict, success_response
from app.services.forms import (
    archive_form,
    decommission_form,
    get_form_by_id,
    publish_form,
    reactivate_form,
)

router = APIRouter(prefix="/forms/{form_id}", tags=["Form Lifecycle"])


class ArchiveRequest(BaseModel):
    """Request to archive a form."""

    reason: str | None = None


class DecommissionRequest(BaseModel):
    """Request to decommission a form."""

    reason: str


@router.post("/publish", response_model=dict)
async def publish_form_route(
    form_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict[str, Any], Depends(require_admin)],
) -> dict[str, Any]:
    """
    Publish a form (draft → active).

    **Requirements:**
    - Form must be in 'draft' status
    - Admin permission required

    **Response:**
    ```json
    {
        "success": true,
        "data": {
            "id": "form-uuid",
            "status": "active",
            "published_at": "2025-11-15T10:00:00Z",
            "is_public": true
        }
    }
    ```
    """
    # Check form exists and is in draft status
    form = await get_form_by_id(conn, form_id)
    if not form:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Form not found",
        )

    if form["status"] != "draft":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Form must be in 'draft' status to publish. Current status: {form['status']}",
        )

    # Publish form
    updated_form = await publish_form(conn, form_id)

    if not updated_form:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to publish form",
        )

    return success_response(
        data=updated_form,
        message="Form published successfully. It is now accepting responses.",
    )


@router.post("/archive", response_model=dict)
async def archive_form_route(
    form_id: UUID,
    request: ArchiveRequest,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict[str, Any], Depends(require_admin)],
) -> dict[str, Any]:
    """
    Archive a form (active/draft → archived).

    **Requirements:**
    - Form must be in 'active' or 'draft' status
    - Admin permission required

    **Effects:**
    - Form stops accepting new responses
    - Existing responses are preserved
    - Form can be reactivated later

    **Request Body:**
    ```json
    {
        "reason": "Data collection period ended"
    }
    ```
    """
    # Check form exists
    form = await get_form_by_id(conn, form_id)
    if not form:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Form not found",
        )

    if form["status"] not in ["draft", "active"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Form must be in 'draft' or 'active' status to archive. Current status: {form['status']}",
        )

    # Archive form
    updated_form = await archive_form(conn, form_id, reason=request.reason)

    if not updated_form:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to archive form",
        )

    return success_response(
        data=updated_form,
        message="Form archived successfully. It no longer accepts responses.",
    )


@router.post("/reactivate", response_model=dict)
async def reactivate_form_route(
    form_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict[str, Any], Depends(require_admin)],
) -> dict[str, Any]:
    """
    Reactivate an archived form (archived → active).

    **Requirements:**
    - Form must be in 'archived' status
    - Admin permission required

    **Effects:**
    - Form starts accepting responses again
    - Public access is restored
    """
    # Check form exists and is archived
    form = await get_form_by_id(conn, form_id)
    if not form:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Form not found",
        )

    if form["status"] != "archived":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Form must be in 'archived' status to reactivate. Current status: {form['status']}",
        )

    # Reactivate form
    updated_form = await reactivate_form(conn, form_id)

    if not updated_form:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reactivate form",
        )

    return success_response(
        data=updated_form,
        message="Form reactivated successfully. It is now accepting responses again.",
    )


@router.post("/decommission", response_model=dict)
async def decommission_form_route(
    form_id: UUID,
    request: DecommissionRequest,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict[str, Any], Depends(require_admin)],
) -> dict[str, Any]:
    """
    Decommission a form (archived → decommissioned).

    **Requirements:**
    - Form must be in 'archived' status
    - Admin permission required
    - Reason must be provided

    **Effects:**
    - Form is permanently sunset (FINAL STATE)
    - No responses can be submitted
    - Public access is revoked
    - Historical data is preserved
    - Cannot be undone

    **Request Body:**
    ```json
    {
        "reason": "Form replaced by new version, data migrated"
    }
    ```

    **Warning:** This is a final state. Decommissioned forms cannot be reactivated.
    """
    # Check form exists and is archived
    form = await get_form_by_id(conn, form_id)
    if not form:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Form not found",
        )

    if form["status"] != "archived":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Form must be in 'archived' status to decommission. Current status: {form['status']}. Archive the form first.",
        )

    # Get user ID
    if isinstance(current_user["id"], str):
        user_id = UUID(current_user["id"])
    else:
        user_id = current_user["id"]

    # Decommission form
    updated_form = await decommission_form(
        conn, form_id, user_id=user_id, reason=request.reason
    )

    if not updated_form:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to decommission form",
        )

    return success_response(
        data=updated_form,
        message="Form decommissioned successfully. This is a permanent action.",
    )


@router.get("/lifecycle-status", response_model=dict)
async def get_lifecycle_status(
    form_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> dict[str, Any]:
    """
    Get form lifecycle status and available actions.

    **Response:**
    ```json
    {
        "success": true,
        "data": {
            "status": "active",
            "can_accept_responses": true,
            "is_public": true,
            "published_at": "2025-11-15T10:00:00Z",
            "archived_at": null,
            "decommissioned_at": null,
            "available_actions": ["archive"]
        }
    }
    ```
    """
    form = await get_form_by_id(conn, form_id)
    if not form:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Form not found",
        )

    # Determine available actions based on current status
    available_actions = []
    if form["status"] == "draft":
        available_actions = ["publish", "archive"]
    elif form["status"] == "active":
        available_actions = ["archive"]
    elif form["status"] == "archived":
        available_actions = ["reactivate", "decommission"]
    # decommissioned has no available actions (final state)

    # Determine if form can accept responses
    can_accept_responses = form["status"] == "active" and form.get("is_public", True)

    return success_response(
        data={
            "status": form["status"],
            "can_accept_responses": can_accept_responses,
            "is_public": form.get("is_public", True),
            "published_at": form.get("published_at"),
            "archived_at": form.get("archived_at"),
            "decommissioned_at": form.get("decommissioned_at"),
            "decommission_reason": form.get("decommission_reason"),
            "available_actions": available_actions,
        }
    )
