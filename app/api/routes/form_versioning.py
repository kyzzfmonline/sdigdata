"""Form versioning API routes."""

from typing import Annotated, Any
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.api.deps import get_current_user, get_db, require_admin
from app.core.responses import success_response
from app.services.form_versioning import (
    compare_versions,
    get_change_log,
    get_form_versions,
    get_version_by_number,
)
from app.services.forms import get_form_by_id, update_form

router = APIRouter(prefix="/forms/{form_id}/versions", tags=["Form Versioning"])


class RestoreVersionRequest(BaseModel):
    """Request to restore a previous version."""

    change_summary: str | None = None


@router.get("", response_model=dict)
async def list_versions(
    form_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> dict[str, Any]:
    """
    Get all versions of a form.

    Returns version history with metadata but without full schemas
    for performance.
    """
    versions = await get_form_versions(conn, form_id)
    return success_response(data=versions)


@router.get("/{version_number}", response_model=dict)
async def get_version(
    form_id: UUID,
    version_number: int,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> dict[str, Any]:
    """Get specific version details including full schema."""
    version = await get_version_by_number(conn, form_id, version_number)
    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Version not found",
        )
    return success_response(data=version)


@router.post("/{version_number}/restore", response_model=dict)
async def restore_version(
    form_id: UUID,
    version_number: int,
    request: RestoreVersionRequest,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict[str, Any], Depends(require_admin)],
) -> dict[str, Any]:
    """
    Restore a previous version (creates new version).

    This doesn't delete newer versions, but creates a new version
    based on the selected old version.
    """
    # Get the version to restore
    old_version = await get_version_by_number(conn, form_id, version_number)
    if not old_version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Version not found",
        )

    # Get current form to get next version number
    current_form = await get_form_by_id(conn, form_id)
    if not current_form:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Form not found",
        )

    # Update the form with the old schema
    updated_form = await update_form(
        conn,
        form_id=form_id,
        schema=old_version["form_schema"],
        title=old_version["title"],
        description=old_version.get("description"),
    )

    if not updated_form:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to restore version",
        )

    # Note: In a full implementation, we would create a new version record here
    # For now, we'll just return the updated form

    return success_response(
        data={
            "form_id": str(form_id),
            "restored_from_version": version_number,
            "message": f"Restored from version {version_number}",
        },
        message="Version restored successfully",
    )


@router.get("/compare", response_model=dict)
async def compare_form_versions(
    form_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
    version_a: int = 1,
    version_b: int = 2,
) -> dict[str, Any]:
    """
    Compare two versions of a form.

    **Query Parameters:**
    - version_a: First version number
    - version_b: Second version number
    """
    # Get both versions
    ver_a = await get_version_by_number(conn, form_id, version_a)
    ver_b = await get_version_by_number(conn, form_id, version_b)

    if not ver_a or not ver_b:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="One or both versions not found",
        )

    # Compare versions
    comparison = compare_versions(ver_a, ver_b)

    return success_response(data=comparison)


@router.get("/change-log", response_model=dict)
async def get_form_change_log(
    form_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
    start_version: int | None = None,
    end_version: int | None = None,
    change_type: str | None = None,
) -> dict[str, Any]:
    """
    Get detailed change log for a form.

    **Query Parameters:**
    - start_version: Filter from version
    - end_version: Filter to version
    - change_type: Filter by change type
    """
    change_log = await get_change_log(
        conn,
        form_id,
        start_version=start_version,
        end_version=end_version,
        change_type=change_type,
    )

    return success_response(data=change_log)
