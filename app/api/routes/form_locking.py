"""Form locking API routes for conflict resolution."""

from typing import Annotated, Any
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.api.deps import get_current_user, get_db, require_admin
from app.core.responses import success_response
from app.services.form_locking import (
    acquire_lock,
    force_release_lock,
    get_lock_status,
    release_lock,
)

router = APIRouter(prefix="/forms/{form_id}/lock", tags=["Form Locking"])


class AcquireLockRequest(BaseModel):
    """Request to acquire a lock."""

    lock_timeout_seconds: int = 300


@router.post("", response_model=dict)
async def acquire_form_lock(
    form_id: UUID,
    request: AcquireLockRequest,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> dict[str, Any]:
    """
    Acquire exclusive lock on a form for editing.

    **Request Body:**
    - lock_timeout_seconds: Auto-release after N seconds (default: 300)

    **Response:**
    - lock_acquired: Whether lock was successfully acquired
    - lock_expires_at: When the lock will expire
    - lock_version: Current lock version for optimistic locking
    """
    result = await acquire_lock(
        conn,
        form_id=form_id,
        user_id=current_user["id"],
        timeout_seconds=request.lock_timeout_seconds,
    )

    if not result.get("lock_acquired"):
        # Return 409 Conflict if lock couldn't be acquired
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "FORM_LOCKED",
                "message": result.get("error", "Form is currently locked"),
                "locked_by": result.get("locked_by"),
                "locked_at": result.get("locked_at"),
            },
        )

    return success_response(data=result, message="Lock acquired successfully")


@router.delete("", response_model=dict)
async def release_form_lock(
    form_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> dict[str, Any]:
    """Release lock on a form."""
    success = await release_lock(conn, form_id, current_user["id"])

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lock not found or not owned by you",
        )

    return success_response(message="Lock released successfully")


@router.post("/force-unlock", response_model=dict)
async def force_unlock(
    form_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict[str, Any], Depends(require_admin)],
) -> dict[str, Any]:
    """Force unlock a form (admin only)."""
    success = await force_release_lock(conn, form_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Form not found",
        )

    return success_response(message="Lock force-released successfully")


@router.get("/status", response_model=dict)
async def check_lock_status(
    form_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> dict[str, Any]:
    """
    Check lock status of a form.

    **Response:**
    - is_locked: Whether the form is currently locked
    - locked_by: User who holds the lock (if locked)
    - locked_at: When the lock was acquired
    - lock_expires_at: When the lock will expire
    """
    status_info = await get_lock_status(conn, form_id)

    if "error" in status_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=status_info["error"],
        )

    return success_response(data=status_info)
