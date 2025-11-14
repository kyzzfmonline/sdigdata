"""Form templates API routes."""

from typing import Annotated, Any
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.api.deps import get_current_user, get_db, require_admin
from app.core.responses import success_response
from app.services.form_templates import (
    create_template,
    delete_template,
    get_popular_templates,
    get_template_by_id,
    increment_template_usage,
    list_templates,
    update_template,
)
from app.services.forms import create_form

router = APIRouter(prefix="/form-templates", tags=["Form Templates"])


class TemplateCreate(BaseModel):
    """Template creation request."""

    name: str
    description: str | None = None
    category: str
    form_schema: dict[str, Any]
    thumbnail_url: str | None = None
    is_public: bool = False
    tags: list[str] | None = None


class TemplateUpdate(BaseModel):
    """Template update request."""

    name: str | None = None
    description: str | None = None
    form_schema: dict[str, Any] | None = None
    thumbnail_url: str | None = None
    is_public: bool | None = None
    tags: list[str] | None = None


class UseTemplateRequest(BaseModel):
    """Request to create form from template."""

    title: str | None = None
    organization_id: str = "default"


@router.get("", response_model=dict)
async def list_templates_route(
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
    category: str | None = None,
    search: str | None = None,
    is_public: bool | None = None,
    sort: str = "created_at",
    order: str = "desc",
    page: int = 1,
    limit: int = 20,
) -> dict[str, Any]:
    """
    Get available form templates.

    **Query Parameters:**
    - category: Filter by category
    - search: Search in name, description, tags
    - is_public: Filter public/private templates
    - sort: created_at, usage_count, name
    - order: asc, desc
    - page: Page number (default: 1)
    - limit: Items per page (default: 20)
    """
    templates, total = await list_templates(
        conn,
        category=category,
        search=search,
        is_public=is_public,
        organization_id=current_user["organization_id"],
        sort=sort,
        order=order,
        page=page,
        limit=limit,
    )

    total_pages = (total + limit - 1) // limit

    return success_response(
        data={
            "templates": templates,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "total_pages": total_pages,
            },
        },
        message=f"Found {total} templates",
    )


@router.get("/popular", response_model=dict)
async def get_popular(
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
    limit: int = 10,
) -> dict[str, Any]:
    """Get most popular templates by usage count."""
    templates = await get_popular_templates(conn, limit=limit)
    return success_response(data=templates)


@router.get("/{template_id}", response_model=dict)
async def get_template(
    template_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> dict[str, Any]:
    """Get full template details including form schema."""
    template = await get_template_by_id(conn, template_id)
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )
    return success_response(data=template)


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_template_route(
    request: TemplateCreate,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict[str, Any], Depends(require_admin)],
) -> dict[str, Any]:
    """Create a new template (admin only)."""
    template = await create_template(
        conn,
        name=request.name,
        category=request.category,
        form_schema=request.form_schema,
        created_by=current_user["id"],
        description=request.description,
        thumbnail_url=request.thumbnail_url,
        is_public=request.is_public,
        organization_id=current_user["organization_id"],
        tags=request.tags,
    )

    if not template:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create template",
        )

    return success_response(data=template, message="Template created successfully")


@router.put("/{template_id}", response_model=dict)
async def update_template_route(
    template_id: UUID,
    request: TemplateUpdate,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict[str, Any], Depends(require_admin)],
) -> dict[str, Any]:
    """Update a template (admin only)."""
    template = await update_template(
        conn,
        template_id=template_id,
        name=request.name,
        description=request.description,
        form_schema=request.form_schema,
        thumbnail_url=request.thumbnail_url,
        is_public=request.is_public,
        tags=request.tags,
    )

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )

    return success_response(data=template, message="Template updated successfully")


@router.delete("/{template_id}", response_model=dict)
async def delete_template_route(
    template_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict[str, Any], Depends(require_admin)],
) -> dict[str, Any]:
    """Delete a template (admin only)."""
    success = await delete_template(conn, template_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )
    return success_response(message="Template deleted successfully")


@router.post("/{template_id}/use", response_model=dict, status_code=status.HTTP_201_CREATED)
async def use_template(
    template_id: UUID,
    request: UseTemplateRequest,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> dict[str, Any]:
    """
    Create a new form from a template.

    This increments the template's usage count and creates a new form
    with the template's schema.
    """
    # Get the template
    template = await get_template_by_id(conn, template_id)
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )

    # Determine organization
    if request.organization_id == "default":
        organization_id = current_user["organization_id"]
    else:
        organization_id = UUID(request.organization_id)

    # Create form from template
    form_title = request.title or f"{template['name']} - Copy"

    form = await create_form(
        conn,
        title=form_title,
        organization_id=organization_id,
        schema=template["form_schema"],
        created_by=current_user["id"],
        status="draft",
        description=template.get("description"),
    )

    if not form:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create form from template",
        )

    # Increment template usage
    await increment_template_usage(conn, template_id)

    return success_response(
        data={
            "form_id": str(form["id"]),
            "title": form["title"],
            "status": form["status"],
            "created_at": form["created_at"],
        },
        message="Form created from template successfully",
    )
