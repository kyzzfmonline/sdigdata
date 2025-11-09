"""Form management routes."""

from typing import Annotated, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Response
from pydantic import BaseModel, ConfigDict
import asyncpg

from app.core.database import get_db
from app.core.responses import (
    success_response,
    error_response,
    paginated_response,
    not_found_response,
    forbidden_response,
)
from app.services.forms import (
    create_form,
    get_form_by_id,
    list_forms,
    update_form_status,
    update_form,
    delete_form,
    assign_form_to_agent,
    assign_form_to_agents,
    get_assigned_agents,
    get_agent_assigned_forms,
    get_form_assignments,
)
from app.services.responses import list_responses
from app.utils.csv_export import responses_to_csv
from app.api.deps import get_current_user, require_admin, require_forms_admin

router = APIRouter(prefix="/forms", tags=["Forms"])


class FormCreate(BaseModel):
    """Form creation request."""

    title: str
    organization_id: str
    form_schema: dict
    status: str = "draft"
    description: Optional[str] = None


class FormAssignRequest(BaseModel):
    """Form assignment request."""

    agent_id: str


class FormBulkAssignRequest(BaseModel):
    """Bulk form assignment request."""

    agent_ids: list[str]
    due_date: Optional[str] = None
    target_responses: Optional[int] = None


class FormUpdateRequest(BaseModel):
    """Form update request."""

    title: Optional[str] = None
    form_schema: Optional[dict] = None
    status: Optional[str] = None
    description: Optional[str] = None


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_form_route(
    request: FormCreate,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
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
    return success_response(data=form)


@router.get("", response_model=dict)
async def list_forms_route(
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    organization_id: Optional[str] = None,
    form_status: Optional[str] = None,
):
    """
    List forms with optional filters.

    **Query Parameters:**
    - organization_id: Filter by organization
    - status: Filter by status ("draft" or "published")

    **Response:**
    ```json
    [
        {
            "id": "...",
            "title": "Household Survey 2025",
            "description": "Annual household survey",
            "organization_id": "...",
            "schema": {...},
            "status": "published",
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
async def get_assigned_forms(
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
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
            "status": "published",
            "version": 1,
            "assigned_at": "2025-11-03T10:00:00"
        }
    ]
    ```
    """
    forms = await get_agent_assigned_forms(conn, current_user["id"])
    return success_response(data=forms)


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
    current_user: Annotated[dict, Depends(get_current_user)],
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

    Changes form status from "draft" to "published".
    """
    form = await update_form_status(conn, form_id, "published")
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
        "status": "published"
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
