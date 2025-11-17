"""Form management routes."""

from typing import Annotated, Any
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel

from app.api.deps import get_current_user, require_admin, require_forms_admin
from app.core.database import get_db
from app.core.responses import (
    not_found_response,
    success_response,
)
from app.services.forms import (
    assign_form_to_agents,
    create_form,
    delete_form,
    get_agent_assigned_forms,
    get_assigned_agents,
    get_form_assignments,
    get_form_by_id,
    list_forms,
    update_form,
    update_form_status,
)
from app.services.responses import list_responses
from app.utils.csv_export import responses_to_csv

router = APIRouter(prefix="/forms", tags=["Forms"])


class FormCreate(BaseModel):
    """Form creation request."""

    title: str
    organization_id: str
    form_schema: dict[str, Any]
    status: str = "draft"
    description: str | None = None


class FormAssignRequest(BaseModel):
    """Form assignment request."""

    agent_id: str


class FormBulkAssignRequest(BaseModel):
    """Bulk form assignment request."""

    agent_ids: list[str]
    due_date: str | None = None
    target_responses: int | None = None


class FormUpdateRequest(BaseModel):
    """Form update request."""

    title: str | None = None
    form_schema: dict[str, Any] | None = None
    status: str | None = None
    description: str | None = None


class BulkFormCreateRequest(BaseModel):
    """Bulk form creation request."""

    forms: list[FormCreate]


class BulkFormAssignRequest(BaseModel):
    """Bulk form assignment request."""

    form_ids: list[str]
    agent_ids: list[str]
    due_date: str | None = None
    target_responses: int | None = None


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_form_route(  # type: ignore[misc,no-untyped-def,no-any-unimported]
    request: FormCreate,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
):
    """
    Create a new form.

    **Request Body:**
    ```json
    {
        "title": "Household Survey 2025",
        "description": "Annual household survey for data collection",
        "organization_id": "550e8400-e29b-41d4-a716-446655440000",
        "status": "draft",
        "form_schema": {
            "branding": {
                "logo_url": "https://example.com/logo.png",
                "primary_color": "#0066CC",
                "header_text": "Kumasi Metropolitan Assembly",
                "footer_text": "Thank you for participating"
            },
            "fields": [
                {
                    "id": "name",
                    "type": "text",
                    "label": "Full Name",
                    "required": true
                },
                {
                    "id": "location",
                    "type": "gps",
                    "label": "Current Location",
                    "required": true
                }
            ]
        }
    }
    ```
    """
    # Handle "default" organization_id by using current user's organization
    if request.organization_id == "default":
        organization_id = current_user["organization_id"]
    else:
        organization_id = UUID(request.organization_id)

    form = await create_form(
        conn,
        title=request.title,
        organization_id=organization_id,
        schema=request.form_schema,
        created_by=current_user["id"],
        status=request.status,
        description=request.description,
    )
    if not form:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create form",
        )
    return success_response(data=form)


@router.get("", response_model=dict)
async def list_forms_route(  # type: ignore[misc,no-untyped-def,no-any-unimported]
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
    organization_id: str | None = None,
    form_status: str | None = None,
):
    """
    List forms with optional filters.

    **Query Parameters:**
    - organization_id: Filter by organization
    - status: Filter by status ("draft", "active", "archived", or "decommissioned")

    **Response:**
    ```json
    [
        {
            "id": "...",
            "title": "Household Survey 2025",
            "description": "Annual household survey",
            "organization_id": "...",
            "schema": {...},
            "status": "active",
            "version": 1,
            "created_by": "...",
            "created_at": "2025-11-03T10:00:00"
        }
    ]
    ```
    """
    # Validate UUID format
    org_id = None
    if organization_id:
        try:
            org_id = UUID(organization_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid organization_id format. Must be a valid UUID",
            )

    forms = await list_forms(conn, organization_id=org_id, status=form_status)
    return success_response(data=forms)


@router.get("/assigned", response_model=dict)
async def get_assigned_forms(  # type: ignore[misc,no-untyped-def,no-any-unimported]
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
):
    """
    Get all forms assigned to the current user (for agents).

    **Response:**
    ```json
    [
        {
            "id": "...",
            "title": "Household Survey 2025",
            "organization_id": "...",
            "schema": {...},
            "status": "active",
            "version": 1,
            "assigned_at": "2025-11-03T10:00:00"
        }
    ]
    ```
    """
    forms = await get_agent_assigned_forms(conn, current_user["id"])
    return success_response(data=forms)


@router.post("/bulk-create", response_model=dict, status_code=status.HTTP_201_CREATED)
async def bulk_create_forms(  # type: ignore[misc,no-untyped-def,no-any-unimported]
    request: BulkFormCreateRequest,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
):
    """
    Create multiple forms in a single request.

    **Request Body:**
    ```json
    {
        "forms": [
            {
                "title": "Household Survey Q1",
                "organization_id": "org_123",
                "form_schema": {...},
                "status": "draft",
                "description": "First quarter survey"
            },
            {
                "title": "Household Survey Q2",
                "organization_id": "org_123",
                "form_schema": {...},
                "status": "draft",
                "description": "Second quarter survey"
            }
        ]
    }
    ```

    **Response:**
    ```json
    {
        "success": true,
        "data": {
            "created": [
                {"id": "frm_123", "title": "Household Survey Q1"},
                {"id": "frm_456", "title": "Household Survey Q2"}
            ],
            "failed": []
        }
    }
    ```
    """
    created_forms = []
    failed_forms = []

    for i, form_data in enumerate(request.forms):
        try:
            # Handle "default" organization_id
            if form_data.organization_id == "default":
                organization_id = current_user["organization_id"]
            else:
                organization_id = UUID(form_data.organization_id)

            form = await create_form(
                conn,
                title=form_data.title,
                organization_id=organization_id,
                schema=form_data.form_schema,
                created_by=current_user["id"],
                status=form_data.status,
                description=form_data.description,
            )
            if not form:
                raise ValueError(f"Failed to create form {form_data.title}")
            created_forms.append({"id": str(form["id"]), "title": form["title"]})
        except Exception as e:
            failed_forms.append({"index": i, "title": form_data.title, "error": str(e)})

    return success_response(
        data={
            "created": created_forms,
            "failed": failed_forms,
            "total_requested": len(request.forms),
            "total_created": len(created_forms),
            "total_failed": len(failed_forms),
        }
    )


@router.post("/bulk-assign", response_model=dict)
async def bulk_assign_forms(
    request: BulkFormAssignRequest,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    admin_user: Annotated[dict[str, Any], Depends(require_admin)],
) -> dict[str, Any]:
    """
    Assign multiple forms to multiple agents in a single request (admin only).

    **Request Body:**
    ```json
    {
        "form_ids": ["frm_123", "frm_456"],
        "agent_ids": ["usr_789", "usr_012"],
        "due_date": "2025-02-01T00:00:00Z",
        "target_responses": 100
    }
    ```

    **Response:**
    ```json
    {
        "success": true,
        "data": {
            "assignments_created": 4,
            "forms_assigned": 2,
            "agents_assigned": 2,
            "assignments": [...]
        }
    }
    ```
    """
    form_uuids = [UUID(form_id) for form_id in request.form_ids]
    agent_uuids = [UUID(agent_id) for agent_id in request.agent_ids]

    all_assignments = []
    total_assignments = 0

    for form_id in form_uuids:
        assignments = await assign_form_to_agents(
            conn,
            form_id=form_id,
            agent_ids=agent_uuids,
            assigned_by=admin_user["id"],
            due_date=request.due_date,
            target_responses=request.target_responses,
        )
        all_assignments.extend(assignments)
        total_assignments += len(assignments)

    return success_response(
        data={
            "assignments_created": total_assignments,
            "forms_assigned": len(form_uuids),
            "agents_assigned": len(agent_uuids),
            "assignments": all_assignments,
        }
    )


@router.get("/templates", response_model=dict)
async def list_form_templates(
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
    category: str | None = None,
):
    """
    List available form templates.

    **Query Parameters:**
    - category: Filter by category (household, business, survey, etc.)

    **Response:**
    ```json
    {
        "success": true,
        "data": [
            {
                "id": "tpl_123",
                "name": "Household Census Survey",
                "description": "Standard household survey template",
                "category": "household",
                "schema": {...},
                "version": "1.0",
                "is_public": true,
                "created_by": "admin",
                "usage_count": 45
            }
        ]
    }
    ```
    """
    # Mock template data for now
    templates = [
        {
            "id": "tpl_123",
            "name": "Household Census Survey",
            "description": "Standard household survey template with GPS and photo capture",
            "category": "household",
            "schema": {
                "branding": {
                    "logo_url": "https://example.com/logo.png",
                    "primary_color": "#0066CC",
                },
                "fields": [
                    {
                        "id": "name",
                        "type": "text",
                        "label": "Household Head Name",
                        "required": True,
                    },
                    {
                        "id": "location",
                        "type": "gps",
                        "label": "Household Location",
                        "required": True,
                    },
                    {
                        "id": "photo",
                        "type": "photo",
                        "label": "Household Photo",
                        "required": False,
                    },
                ],
            },
            "version": "1.0",
            "is_public": True,
            "created_by": "admin",
            "usage_count": 45,
        },
        {
            "id": "tpl_456",
            "name": "Business Registration",
            "description": "Template for registering new businesses",
            "category": "business",
            "schema": {
                "branding": {
                    "logo_url": "https://example.com/logo.png",
                    "primary_color": "#1976d2",
                },
                "fields": [
                    {
                        "id": "business_name",
                        "type": "text",
                        "label": "Business Name",
                        "required": True,
                    },
                    {
                        "id": "owner_name",
                        "type": "text",
                        "label": "Owner Name",
                        "required": True,
                    },
                    {
                        "id": "location",
                        "type": "gps",
                        "label": "Business Location",
                        "required": True,
                    },
                ],
            },
            "version": "1.0",
            "is_public": True,
            "created_by": "admin",
            "usage_count": 23,
        },
    ]

    # Filter by category if provided
    if category:
        templates = [t for t in templates if t["category"] == category]

    return success_response(data=templates)


@router.post(
    "/{form_id}/clone", response_model=dict, status_code=status.HTTP_201_CREATED
)
async def clone_form(
    form_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
    title: str | None = None,
    description: str | None = None,
):
    """
    Clone an existing form.

    **Request Body (query parameters):**
    - title: New title for the cloned form (optional)
    - description: New description for the cloned form (optional)

    **Response:**
    ```json
    {
        "success": true,
        "data": {
            "id": "frm_456",
            "title": "Cloned Form Title",
            "description": "Cloned form description",
            "original_form_id": "frm_123",
            "cloned_at": "2025-01-01T10:00:00Z"
        }
    }
    ```
    """
    # Get the original form
    original_form = await get_form_by_id(conn, form_id)
    if not original_form:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Form not found"
        )

    # Create the cloned form
    cloned_title = title or f"{original_form['title']} (Copy)"
    cloned_description = description or f"Cloned from {original_form['title']}"

    # Handle "default" organization_id
    if original_form["organization_id"] == "default":
        organization_id = current_user["organization_id"]
    else:
        organization_id = original_form["organization_id"]

    cloned_form = await create_form(
        conn,
        title=cloned_title,
        organization_id=organization_id,
        schema=original_form["schema"],
        created_by=current_user["id"],
        status="draft",  # Cloned forms start as drafts
        description=cloned_description,
    )

    if not cloned_form:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to clone form",
        )

    return success_response(
        data={
            "id": str(cloned_form["id"]),
            "title": cloned_form["title"],
            "description": cloned_form.get("description"),
            "original_form_id": str(form_id),
            "cloned_at": cloned_form["created_at"],
        }
    )


@router.post("/{form_id}/submit-review", response_model=dict)
async def submit_form_for_review(
    form_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
    review_notes: str | None = None,
):
    """
    Submit a form for review/approval.

    **Request Body (query parameters):**
    - review_notes: Optional notes for reviewers

    **Response:**
    ```json
    {
        "success": true,
        "data": {
            "form_id": "frm_123",
            "status": "pending_review",
            "submitted_at": "2025-01-01T10:00:00Z",
            "review_notes": "Please review the new GPS field"
        }
    }
    ```
    """
    # Get the form
    form = await get_form_by_id(conn, form_id)
    if not form:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Form not found"
        )

    # Check permissions - only form creator or admin can submit for review
    if (
        current_user["role"] != "admin"
        and str(form["created_by"]) != current_user["id"]
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the form creator or admin can submit for review",
        )

    # Update form status to pending review
    # For now, just return success (would need workflow table in real implementation)
    return success_response(
        data={
            "form_id": str(form_id),
            "status": "pending_review",
            "submitted_at": "2025-01-01T10:00:00Z",  # Would be current timestamp
            "review_notes": review_notes,
        }
    )


@router.post("/{form_id}/approve", response_model=dict)
async def approve_form(
    form_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(require_admin)],
    approval_notes: str | None = None,
):
    """
    Approve a form that was submitted for review (admin only).

    **Request Body (query parameters):**
    - approval_notes: Optional approval notes

    **Response:**
    ```json
    {
        "success": true,
        "data": {
            "form_id": "frm_123",
            "status": "approved",
            "approved_by": "usr_456",
            "approved_at": "2025-01-01T10:00:00Z",
            "approval_notes": "Approved with minor changes"
        }
    }
    ```
    """
    # Get the form
    form = await get_form_by_id(conn, form_id)
    if not form:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Form not found"
        )

    # Publish the form (approval = publish = active)
    approved_form = await update_form_status(conn, form_id, "active")
    if not approved_form:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Form not found"
        )

    return success_response(
        data={
            "form_id": str(form_id),
            "status": "active",
            "approved_by": current_user["id"],
            "approved_at": "2025-01-01T10:00:00Z",  # Would be current timestamp
            "approval_notes": approval_notes,
        }
    )


@router.delete("/cleanup", response_model=dict)
async def cleanup_deleted_forms(
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(require_forms_admin)],
):
    """
    Permanently delete all soft-deleted forms (admin only).

    **Warning:** This action cannot be undone. It permanently removes all soft-deleted forms from the database.

    **Response:**
    ```json
    {
        "success": true,
        "message": "Cleaned up X deleted forms",
        "deleted_count": 3
    }
    ```
    """
    # Count how many will be deleted
    count_result = await conn.fetchval(
        "SELECT COUNT(*) FROM forms WHERE deleted = TRUE"
    )
    deleted_count = count_result or 0

    if deleted_count == 0:
        return success_response(
            message="No deleted forms to clean up", data={"deleted_count": 0}
        )

    # Permanently delete the records
    await conn.execute("DELETE FROM forms WHERE deleted = TRUE")

    return success_response(
        message=f"Cleaned up {deleted_count} deleted forms",
        data={"deleted_count": deleted_count},
    )


@router.get("/{form_id}", response_model=dict)
async def get_form(
    form_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
):
    """Get form by ID."""
    form = await get_form_by_id(conn, form_id)
    if not form:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Form not found"
        )
    return success_response(data=form)


@router.post("/{form_id}/publish", response_model=dict)
async def publish_form(
    form_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    admin_user: Annotated[dict, Depends(require_admin)],
):
    """
    Publish a form (admin only).

    Changes form status from "draft" to "active".
    """
    form = await update_form_status(conn, form_id, "active")
    if not form:
        not_found_response("Form not found")
    return success_response(data=form)


@router.post("/{form_id}/assign", response_model=dict)
async def assign_form(
    form_id: UUID,
    request: FormBulkAssignRequest,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    admin_user: Annotated[dict, Depends(require_admin)],
):
    """
    Assign form to multiple agents (admin only).

    **Request Body:**
    ```json
    {
        "agent_ids": ["660e8400-e29b-41d4-a716-446655440000", "770e8400-e29b-41d4-a716-446655440001"],
        "due_date": "2025-02-01T00:00:00Z",
        "target_responses": 100
    }
    ```

    **Response:**
    ```json
    {
        "success": true,
        "data": {
            "assignments": [
                {
                    "id": "asn_123",
                    "form_id": "frm_123",
                    "agent_id": "usr_456",
                    "assigned_at": "2025-01-05T12:00:00Z",
                    "due_date": "2025-02-01T00:00:00Z",
                    "target_responses": 100,
                    "completed_responses": 0,
                    "status": "active"
                }
            ]
        }
    }
    ```
    """
    agent_uuids = [UUID(agent_id) for agent_id in request.agent_ids]
    assignments = await assign_form_to_agents(
        conn,
        form_id=form_id,
        agent_ids=agent_uuids,
        assigned_by=admin_user["id"],
        due_date=request.due_date,
        target_responses=request.target_responses,
    )
    return success_response(data={"assignments": assignments})


@router.get("/{form_id}/agents", response_model=dict)
async def get_form_agents(
    form_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    admin_user: Annotated[dict, Depends(require_admin)],
):
    """
    Get all agents assigned to a form (admin only).

    **Response:**
    ```json
    [
        {
            "id": "...",
            "username": "john_agent",
            "role": "agent",
            "assigned_at": "2025-11-03T10:00:00"
        }
    ]
    ```
    """
    agents = get_assigned_agents(conn, form_id)
    return success_response(data=agents)


@router.put("/{form_id}", response_model=dict)
async def update_form_route(
    form_id: UUID,
    request: FormUpdateRequest,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    admin_user: Annotated[dict, Depends(require_admin)],
):
    """
    Update a form (admin only).

    **Request Body:**
    ```json
    {
        "title": "Updated Form Title",
        "description": "Updated description",
        "form_schema": {...},
        "status": "active"
    }
    ```
    """
    updated_form = await update_form(
        conn,
        form_id=form_id,
        title=request.title,
        schema=request.form_schema,
        status=request.status,
        description=request.description,
    )

    if not updated_form:
        not_found_response("Form not found")

    return success_response(data=updated_form)


@router.delete("/{form_id}", response_model=dict)
async def delete_form_route(
    form_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    admin_user: Annotated[dict, Depends(require_admin)],
):
    """
    Delete a form (admin only). This is a soft delete.

    **Response:**
    ```json
    {
        "success": true,
        "message": "Form deleted successfully"
    }
    ```
    """
    success = await delete_form(conn, form_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Form not found"
        )

    return success_response(message="Form deleted successfully")


@router.get("/{form_id}/assignments", response_model=dict)
async def get_form_assignments_route(
    form_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    admin_user: Annotated[dict, Depends(require_admin)],
):
    """
    Get all assignments for a form (admin only).

    **Response:**
    ```json
    {
        "success": true,
        "data": [
            {
                "id": "asn_123",
                "form_id": "frm_123",
                "agent_id": "usr_456",
                "agent_name": "john_agent",
                "assigned_at": "2025-01-05T12:00:00Z",
                "due_date": "2025-02-01T00:00:00Z",
                "target_responses": 100,
                "completed_responses": 45,
                "status": "active"
            }
        ]
    }
    ```
    """
    assignments = await get_form_assignments(conn, form_id)
    return success_response(data=assignments)


@router.get("/{form_id}/export")
async def export_form_responses(
    form_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    admin_user: Annotated[dict, Depends(require_admin)],
):
    """
    Export form responses as CSV (admin only).

    Returns a CSV file with all responses for the specified form.
    """
    # Get form
    form = await get_form_by_id(conn, form_id)
    if not form:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Form not found"
        )

    # Get responses
    responses = await list_responses(conn, form_id=form_id)

    # Generate CSV
    csv_content = responses_to_csv(responses, form["schema"])

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=form_{form_id}_await responses.csv"
        },
    )
