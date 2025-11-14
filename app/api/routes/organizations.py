"""Organization management routes."""

from typing import Annotated
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.api.deps import get_current_user, require_admin
from app.core.database import get_db
from app.core.responses import not_found_response, success_response
from app.services.organizations import (
    create_organization,
    get_organization_by_id,
    list_organizations,
    update_organization,
)

router = APIRouter(prefix="/organizations", tags=["Organizations"])


class OrganizationCreate(BaseModel):
    """Organization creation request."""

    name: str
    logo_url: str | None = None
    primary_color: str | None = None


class OrganizationUpdate(BaseModel):
    """Organization update request."""

    name: str | None = None
    logo_url: str | None = None
    primary_color: str | None = None


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_org(
    request: OrganizationCreate,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    admin_user: Annotated[dict, Depends(require_admin)],
):
    """
    Create a new organization (admin only).

    **Request Body:**
    ```json
    {
        "name": "Kumasi Metropolitan Assembly",
        "logo_url": "https://example.com/logo.png",
        "primary_color": "#0066CC"
    }
    ```
    """
    org = await create_organization(
        conn,
        name=request.name,
        logo_url=request.logo_url,
        primary_color=request.primary_color,
    )
    if not org:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create organization",
        )
    return success_response(data=org)


@router.get("", response_model=dict)
async def list_orgs(
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """
    List all await organizations.

    **Response:**
    ```json
    [
        {
            "id": "...",
            "name": "Kumasi Metropolitan Assembly",
            "logo_url": "...",
            "primary_color": "#0066CC",
            "created_at": "2025-11-03T10:00:00"
        }
    ]
    ```
    """
    orgs = await list_organizations(conn)
    return success_response(data=orgs)


@router.get("/{org_id}", response_model=dict)
async def get_org(
    org_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Get organization by ID."""
    org = await get_organization_by_id(conn, org_id)
    if not org:
        not_found_response("Organization not found")
    return success_response(data=org)


@router.patch("/{org_id}", response_model=dict)
async def update_org(
    org_id: UUID,
    request: OrganizationUpdate,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    admin_user: Annotated[dict, Depends(require_admin)],
):
    """
    Update organization details (admin only).

    **Request Body:**
    ```json
    {
        "name": "Updated Name",
        "logo_url": "https://example.com/new-logo.png",
        "primary_color": "#FF6600"
    }
    ```
    """
    org = await update_organization(
        conn,
        org_id=org_id,
        name=request.name,
        logo_url=request.logo_url,
        primary_color=request.primary_color,
    )
    if not org:
        not_found_response("Organization not found")
    return success_response(data=org)
