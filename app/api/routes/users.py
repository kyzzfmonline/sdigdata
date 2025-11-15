"""User management routes."""

from typing import Annotated, Any, cast
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field, field_validator

from app.api.deps import (
    get_current_user,
    get_current_user_with_password,
    require_admin,
    require_users_admin,
    require_users_read,
)
from app.core.database import get_db
from app.core.logging_config import get_logger
from app.core.responses import (
    error_response,
    forbidden_response,
    not_found_response,
    paginated_response,
    success_response,
)
from app.core.security import hash_password, verify_password
from app.core.validation import PasswordValidator
from app.services.permissions import PermissionChecker
from app.services.users import (
    create_user,
    delete_user,
    get_user_by_id,
    get_user_preferences,
    list_users,
    update_notification_preferences,
    update_theme_preferences,
    update_user,
    update_user_password,
)

router = APIRouter(prefix="/users", tags=["User Management"])
logger = get_logger(__name__)


class UserUpdateRequest(BaseModel):
    """User update request."""

    username: str | None = Field(None, min_length=3, max_length=50)
    email: str | None = Field(None, max_length=255)
    role: str | None = Field(None, description="User role: 'admin' or 'agent'")
    status: str | None = Field(
        None, description="User status: 'active', 'inactive', 'suspended'"
    )

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str | None) -> str | None:
        if v is not None and v not in ["admin", "agent"]:
            raise ValueError("Role must be 'admin' or 'agent'")
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str | None) -> str | None:
        if v is not None and v not in ["active", "inactive", "suspended"]:
            raise ValueError("Status must be 'active', 'inactive', or 'suspended'")
        return v


class PasswordChangeRequest(BaseModel):
    """Password change request."""

    current_password: str = Field(..., min_length=8, max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate password strength."""
        is_valid, error = PasswordValidator.validate(v)
        if not is_valid:
            raise ValueError(error)
        return v


class NotificationPreferencesRequest(BaseModel):
    """Notification preferences update request."""

    email_notifications: bool | None = None
    form_assignments: bool | None = None
    responses: bool | None = None
    system_updates: bool | None = None


class ThemePreferencesRequest(BaseModel):
    """Theme preferences update request."""

    theme: str | None = Field(None, description="Theme: 'light', 'dark', or 'system'")
    compact_mode: bool | None = None

    @field_validator("theme")
    @classmethod
    def validate_theme(cls, v: str | None) -> str | None:
        if v is not None and v not in ["light", "dark", "system"]:
            raise ValueError("Theme must be 'light', 'dark', or 'system'")
        return v


class BulkUserCreateRequest(BaseModel):
    """Bulk user creation request."""

    users: list[
        dict
    ]  # List of user objects with username, password, role, organization_id
    organization_id: str | None = None  # Default organization for all users

    @field_validator("users")
    @classmethod
    def validate_users(cls, v: list[dict]) -> list[dict]:
        """Validate bulk user data."""
        if not v:
            raise ValueError("Users list cannot be empty")

        max_users = 100  # Limit bulk creation size
        if len(v) > max_users:
            raise ValueError(f"Cannot create more than {max_users} users at once")

        required_fields = ["username", "password", "role"]
        for i, user_data in enumerate(v):
            missing_fields = [
                field for field in required_fields if field not in user_data
            ]
            if missing_fields:
                raise ValueError(f"User {i}: Missing required fields: {missing_fields}")

        return v


@router.get("", response_model=dict)
async def get_users(
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    role: str | None = Query(None, description="Filter by role (admin, agent)"),
    status: str | None = Query(
        None, description="Filter by status (active, inactive, suspended)"
    ),
    search: str | None = Query(None, description="Search term for username or email"),
    sort: str = Query(
        "created_at",
        description="Sort field (created_at, username, email, role, status, last_login)",
    ),
    order: str = Query("desc", description="Sort order (asc, desc)"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
):
    """
    Get all users with advanced filtering, sorting, and pagination (admin only).

    **Query Parameters:**
    - role: Filter by role (admin, agent)
    - status: Filter by status (active, inactive, suspended)
    - search: Search term for username or email
    - sort: Sort field (created_at, username, email, role, status, last_login)
    - order: Sort order (asc, desc)
    - page: Page number (default: 1)
    - limit: Items per page (default: 20, max: 100)

    **Response:**
    ```json
    {
        "success": true,
        "data": {
            "users": [...],
            "pagination": {
                "page": 1,
                "limit": 20,
                "total": 156,
                "total_pages": 8
            },
            "filters": {
                "roles": ["admin", "agent"],
                "statuses": ["active", "inactive", "suspended"]
            }
        }
    }
    ```
    """
    # Check if user has permission to read users
    # For now, keep backward compatibility with role check, but this should be updated to use permissions
    if current_user["role"] != "admin":
        forbidden_response("Only admins can list users")

    # Calculate offset
    offset = (page - 1) * limit

    # Get users with advanced filtering
    users, total = await list_users(
        conn=conn,
        organization_id=None,  # Could be filtered by current user's org if needed
        role=role,
        status=status,
        search=search,
        sort=sort,
        order=order,
        limit=limit,
        offset=offset,
    )

    # Remove password hashes
    safe_users = [
        {k: v for k, v in user.items() if k != "password_hash"} for user in users
    ]

    return paginated_response(
        items=safe_users,
        page=page,
        limit=limit,
        total=total,
        filters={
            "roles": ["admin", "agent"],
            "statuses": ["active", "inactive", "suspended"],
        },
    )


@router.get("/me", response_model=dict)
async def get_current_user_profile(
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """
    Get current user's profile.

    **Response:**
    ```json
    {
        "success": true,
        "data": {
            "id": "usr_123",
            "username": "john_agent",
            "email": "john@sdigdata.gov.gh",
            "role": "agent",
            "status": "active",
            "organization_id": "...",
            "created_at": "2024-01-01T00:00:00Z",
            "last_login": "2025-01-05T10:00:00Z"
        }
    }
    ```
    """
    user_data = {k: v for k, v in current_user.items() if k != "password_hash"}
    return success_response(data=user_data)


@router.put("/me", response_model=dict)
async def update_current_user_profile(
    request: UserUpdateRequest,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """
    Update current user's profile.

    Users can update their own username and email, but not role or status.

    **Request Body:**
    ```json
    {
        "username": "updated_username",
        "email": "new_email@sdigdata.gov.gh"
    }
    ```
    """
    # Users cannot change their own role or status
    if request.role is not None or request.status is not None:
        forbidden_response("You cannot change your own role or status")

    updated_user = await update_user(
        conn,
        user_id=current_user["id"],
        username=request.username,
        email=request.email,
    )

    if not updated_user:
        not_found_response("User not found")

    user_data = {
        k: v
        for k, v in cast(dict[str, Any], updated_user).items()
        if k != "password_hash"
    }
    return success_response(data=user_data)


@router.post("/me/password", response_model=dict)
async def change_password(
    request: PasswordChangeRequest,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user_with_password)],
):
    """
    Change current user's password.

    **Request Body:**
    ```json
    {
        "current_password": "OldPassword123!",
        "new_password": "NewPassword456!"
    }
    ```
    """
    # Verify current password
    if not verify_password(request.current_password, current_user["password_hash"]):
        raise error_response("Current password is incorrect")

    # Hash new password
    new_password_hash = hash_password(request.new_password)

    # Update password
    success = await update_user_password(
        conn,
        user_id=current_user["id"],
        password_hash=new_password_hash,
    )

    if not success:
        raise error_response(
            "Failed to update password",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    logger.info(f"Password changed for user: {current_user['username']}")

    return success_response(message="Password updated successfully")


@router.get("/me/notifications", response_model=dict)
async def get_notification_preferences(  # type: ignore[misc]
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """
    Get current user's notification preferences.

    **Response:**
    ```json
    {
        "success": true,
        "data": {
            "email_notifications": true,
            "form_assignments": true,
            "responses": true,
            "system_updates": true
        }
    }
    ```
    """
    preferences = await get_user_preferences(conn, current_user["id"])
    if not preferences:
        # This shouldn't happen since user is authenticated, but handle gracefully
        error_response(
            "Failed to load user preferences",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    # Return only notification preferences
    assert preferences is not None  # MyPy type narrowing
    notification_data = {
        "email_notifications": preferences["email_notifications"],
        "form_assignments": preferences["form_assignments"],
        "responses": preferences["responses"],
        "system_updates": preferences["system_updates"],
    }

    return success_response(data=notification_data)


@router.put("/me/notifications", response_model=dict)
async def update_notification_preferences_route(
    request: NotificationPreferencesRequest,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """
    Update current user's notification preferences.

    **Request Body:**
    ```json
    {
        "email_notifications": true,
        "form_assignments": false,
        "responses": true,
        "system_updates": false
    }
    ```

    **Response:**
    ```json
    {
        "success": true,
        "message": "Preferences updated"
    }
    ```
    """
    success = await update_notification_preferences(
        conn,
        user_id=current_user["id"],
        email_notifications=request.email_notifications,
        form_assignments=request.form_assignments,
        responses=request.responses,
        system_updates=request.system_updates,
    )

    if not success:
        error_response(
            "Failed to update preferences",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    return success_response(message="Preferences updated")


@router.get("/me/preferences", response_model=dict)
async def get_theme_preferences(  # type: ignore[misc]
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """
    Get current user's theme preferences.

    **Response:**
    ```json
    {
        "success": true,
        "data": {
            "theme": "dark",
            "compact_mode": false
        }
    }
    ```
    """
    preferences = await get_user_preferences(conn, current_user["id"])
    if not preferences:
        not_found_response("User not found")

    # Return only theme-related preferences
    assert preferences is not None  # MyPy type narrowing
    theme_data = {
        "theme": preferences["theme"] if preferences["theme"] is not None else "system",
        "compact_mode": preferences["compact_mode"]
        if preferences["compact_mode"] is not None
        else False,
    }

    return success_response(data=theme_data)


@router.put("/me/preferences", response_model=dict)
async def update_theme_preferences_route(
    request: ThemePreferencesRequest,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """
    Update current user's theme preferences.

    **Request Body:**
    ```json
    {
        "theme": "dark",
        "compact_mode": true
    }
    ```

    **Response:**
    ```json
    {
        "success": true,
        "message": "Preferences updated"
    }
    ```
    """
    success = await update_theme_preferences(
        conn,
        user_id=current_user["id"],
        theme=request.theme,
        compact_mode=request.compact_mode,
    )

    if not success:
        error_response(
            "Failed to update preferences",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    return success_response(message="Preferences updated")


# Role and Permission Management Endpoints (Admin Only)


@router.get("/roles", response_model=dict)
async def get_roles(
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(require_users_admin)],
):
    """
    Get all roles (admin only).

    **Response:**
    ```json
    {
        "success": true,
        "data": [
            {
                "id": "role_123",
                "name": "super_admin",
                "description": "Super administrator",
                "level": 100,
                "is_system_role": true
            }
        ]
    }
    ```
    """
    rows = await conn.fetch(
        """
        SELECT id, name, description, level, organization_id, is_system_role, created_at
        FROM roles
        ORDER BY level DESC, name
        """
    )
    roles = [dict(row) for row in rows]
    return success_response(data=roles)


@router.get("/permissions", response_model=dict)
async def get_permissions(
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(require_users_admin)],
):
    """
    Get all permissions (admin only).

    **Response:**
    ```json
    {
        "success": true,
        "data": [
            {
                "id": "perm_123",
                "name": "users:create",
                "description": "Create new users",
                "resource": "users",
                "action": "create"
            }
        ]
    }
    ```
    """
    rows = await conn.fetch(
        """
        SELECT id, name, description, resource, action, created_at
        FROM permissions
        ORDER BY resource, action
        """
    )
    permissions = [dict(row) for row in rows]
    return success_response(data=permissions)


@router.get("/{user_id}/roles", response_model=dict)
async def get_user_roles(
    user_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(require_users_read)],
):
    """
    Get roles assigned to a user (admin only).

    **Response:**
    ```json
    {
        "success": true,
        "data": [
            {
                "id": "role_123",
                "name": "super_admin",
                "description": "Super administrator",
                "level": 100,
                "assigned_at": "2025-01-01T00:00:00Z",
                "expires_at": null
            }
        ]
    }
    ```
    """
    checker = PermissionChecker(conn)
    roles = await checker.get_user_roles(user_id)
    return success_response(data=roles)


@router.get("/me/permissions", response_model=dict)
async def get_my_permissions(
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """
    Get current user's permissions and roles.

    **Response:**
    ```json
    {
        "success": true,
        "data": {
            "permissions": [
                {
                    "name": "users:create",
                    "resource": "users",
                    "action": "create",
                    "description": "Create new users"
                }
            ],
            "roles": [
                {
                    "id": "...",
                    "name": "admin",
                    "level": 100
                }
            ]
        }
    }
    ```
    """
    checker = PermissionChecker(conn)
    permissions = await checker.get_user_permissions(current_user["id"])
    roles = await checker.get_user_roles(current_user["id"])
    return success_response(data={"permissions": permissions, "roles": roles})


@router.get("/me/responses")
async def get_my_responses(
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    form_id: str | None = Query(None, description="Filter by form ID"),
    status: str | None = Query(None, description="Filter by status (draft, submitted, reviewed)"),
    limit: int = Query(20, ge=1, le=100, description="Maximum records to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    sort_by: str = Query("submitted_at", description="Field to sort by"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$", description="Sort order"),
):
    """
    Get responses submitted by the current authenticated user.

    This endpoint allows any authenticated user to view their own form submissions.
    No special permissions required - users can always view their own data.

    **Query Parameters:**
    - form_id: Filter responses by specific form (optional)
    - status: Filter by submission status (optional)
    - limit: Number of responses per page (1-100, default: 20)
    - offset: Pagination offset (default: 0)
    - sort_by: Field to sort by (default: submitted_at)
    - sort_order: Sort direction - asc or desc (default: desc)

    **Response:**
    ```json
    {
        "success": true,
        "data": {
            "responses": [
                {
                    "id": "550e8400-e29b-41d4-a716-446655440000",
                    "form_id": "...",
                    "data": {...},
                    "submitted_at": "2025-11-15T10:30:00Z",
                    "status": "submitted"
                }
            ],
            "pagination": {
                "page": 1,
                "limit": 20,
                "total": 45,
                "total_pages": 3
            }
        }
    }
    ```
    """
    from app.services.responses import list_responses

    # Parse form_id if provided
    parsed_form_id = None
    if form_id:
        try:
            parsed_form_id = UUID(form_id)
        except ValueError:
            raise error_response(
                message="Invalid form_id format. Must be a valid UUID",
                status_code=status.HTTP_400_BAD_REQUEST
            )

    # Get user's responses
    # current_user["id"] might already be a UUID object from asyncpg
    if isinstance(current_user["id"], str):
        user_id = UUID(current_user["id"])
    else:
        user_id = current_user["id"]
    all_responses_raw = await list_responses(
        conn,
        form_id=parsed_form_id,
        submitted_by=user_id
    )

    # Ensure all UUIDs are converted to strings
    all_responses = []
    for resp in all_responses_raw:
        # Deep copy and ensure all values are JSON-serializable
        clean_resp = {}
        for k, v in resp.items():
            if v is None:
                clean_resp[k] = None
            elif hasattr(v, '__class__') and 'UUID' in v.__class__.__name__:
                clean_resp[k] = str(v)
            else:
                clean_resp[k] = v
        all_responses.append(clean_resp)

    # Filter by status if provided
    if status:
        all_responses = [r for r in all_responses if r.get("status") == status]

    # Sort responses
    reverse = (sort_order == "desc")
    try:
        all_responses.sort(
            key=lambda x: x.get(sort_by, ""),
            reverse=reverse
        )
    except (KeyError, TypeError):
        # If sort field doesn't exist or can't be compared, skip sorting
        pass

    # Calculate total
    total = len(all_responses)

    # Paginate
    paginated_responses = all_responses[offset:offset + limit]

    # Calculate page number
    page = (offset // limit) + 1 if limit > 0 else 1

    # Use custom JSON encoding to handle all types
    from app.core.responses import CustomJSONEncoder
    from fastapi.responses import JSONResponse
    import json

    response_data = paginated_response(
        items=paginated_responses,
        page=page,
        limit=limit,
        total=total,
        message=f"Found {total} response(s) submitted by you"
    )

    # Serialize with custom encoder and return as JSONResponse
    json_str = json.dumps(response_data, cls=CustomJSONEncoder)
    return JSONResponse(content=json.loads(json_str))


@router.get("/{user_id}/permissions", response_model=dict)
async def get_user_permissions(
    user_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(require_users_read)],
):
    """
    Get all permissions for a user (admin only).

    **Response:**
    ```json
    {
        "success": true,
        "data": [
            {
                "name": "users:create",
                "resource": "users",
                "action": "create",
                "description": "Create new users"
            }
        ]
    }
    ```
    """
    checker = PermissionChecker(conn)
    permissions = await checker.get_user_permissions(user_id)
    return success_response(data=permissions)


@router.post("/{user_id}/roles/{role_id}", response_model=dict)
async def assign_user_role(
    user_id: UUID,
    role_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(require_users_admin)],
):
    """
    Assign a role to a user (admin only).

    **Response:**
    ```json
    {
        "success": true,
        "message": "Role assigned successfully"
    }
    ```
    """
    # Check if role exists
    role_exists = await conn.fetchval(
        "SELECT EXISTS(SELECT 1 FROM roles WHERE id = $1)", role_id
    )
    if not role_exists:
        error_response("Role not found", status_code=status.HTTP_404_NOT_FOUND)

    # Check if user exists
    user_exists = await conn.fetchval(
        "SELECT EXISTS(SELECT 1 FROM users WHERE id = $1 AND deleted = FALSE)", user_id
    )
    if not user_exists:
        error_response("User not found", status_code=status.HTTP_404_NOT_FOUND)

    # Assign role (upsert to handle duplicates)
    await conn.execute(
        """
        INSERT INTO user_roles (user_id, role_id, assigned_by, assigned_at, is_active)
        VALUES ($1, $2, $3, CURRENT_TIMESTAMP, TRUE)
        ON CONFLICT (user_id, role_id) WHERE is_active = TRUE
        DO UPDATE SET
            assigned_by = EXCLUDED.assigned_by,
            assigned_at = CURRENT_TIMESTAMP,
            is_active = TRUE
        """,
        user_id,
        role_id,
        UUID(current_user["id"]),
    )

    return success_response(message="Role assigned successfully")


@router.delete("/{user_id}/roles/{role_id}", response_model=dict)
async def remove_user_role(
    user_id: UUID,
    role_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(require_users_admin)],
):
    """
    Remove a role from a user (admin only).

    **Response:**
    ```json
    {
        "success": true,
        "message": "Role removed successfully"
    }
    ```
    """
    result = await conn.execute(
        """
        UPDATE user_roles
        SET is_active = FALSE
        WHERE user_id = $1 AND role_id = $2 AND is_active = TRUE
        """,
        user_id,
        role_id,
    )

    if int(result.split()[-1]) == 0:
        error_response(
            "Role assignment not found", status_code=status.HTTP_404_NOT_FOUND
        )

    return success_response(message="Role removed successfully")


@router.post("/bulk-create", response_model=dict, status_code=status.HTTP_201_CREATED)
async def bulk_create_users(
    request: BulkUserCreateRequest,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    admin_user: Annotated[dict, Depends(require_admin)],
):
    """
    Create multiple users in a single request (admin only).

    **Request Body:**
    ```json
    {
        "organization_id": "org_123",
        "users": [
            {
                "username": "agent1",
                "password": "SecurePass123!",
                "role": "agent",
                "email": "agent1@org.com"
            },
            {
                "username": "agent2",
                "password": "SecurePass456!",
                "role": "agent",
                "email": "agent2@org.com"
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
                {"id": "usr_123", "username": "agent1"},
                {"id": "usr_456", "username": "agent2"}
            ],
            "failed": [],
            "total_requested": 2,
            "total_created": 2,
            "total_failed": 0
        }
    }
    ```
    """
    created_users = []
    failed_users = []

    for i, user_data in enumerate(request.users):
        try:
            # Use provided organization_id or default from request
            org_id = user_data.get("organization_id") or request.organization_id
            if not org_id:
                raise ValueError("organization_id is required")

            # Hash password
            password_hash = hash_password(user_data["password"])

            # Create user
            user = await create_user(
                conn,
                username=user_data["username"],
                password_hash=password_hash,
                role=user_data["role"],
                organization_id=UUID(org_id),
            )

            if not user:
                raise ValueError(f"Failed to create user {user_data['username']}")

            created_users.append(
                {
                    "id": str(user["id"]),
                    "username": user["username"],
                    "role": user["role"],
                }
            )

        except Exception as e:
            failed_users.append(
                {
                    "index": i,
                    "username": user_data.get("username", "unknown"),
                    "error": str(e),
                }
            )

    return success_response(
        data={
            "created": created_users,
            "failed": failed_users,
            "total_requested": len(request.users),
            "total_created": len(created_users),
            "total_failed": len(failed_users),
        }
    )


@router.delete("/cleanup", response_model=dict)
async def cleanup_deleted_users(
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(require_users_admin)],
):
    """
    Permanently delete all soft-deleted users (admin only).

    **Warning:** This action cannot be undone. It permanently removes all soft-deleted users from the database.

    **Response:**
    ```json
    {
        "success": true,
        "message": "Cleaned up X deleted users",
        "deleted_count": 2
    }
    ```
    """
    # Count how many will be deleted
    count_result = await conn.fetchval(
        "SELECT COUNT(*) FROM users WHERE deleted = TRUE"
    )
    deleted_count = count_result or 0

    if deleted_count == 0:
        return success_response(
            message="No deleted users to clean up", data={"deleted_count": 0}
        )

    # Permanently delete the records
    await conn.execute("DELETE FROM users WHERE deleted = TRUE")

    return success_response(
        message=f"Cleaned up {deleted_count} deleted users",
        data={"deleted_count": deleted_count},
    )


@router.get("/{user_id}", response_model=dict)
async def get_user(  # type: ignore[misc]
    user_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """
    Get user by ID (admin only or own profile).

    **Response:**
    ```json
    {
        "success": true,
        "data": {
            "id": "usr_123",
            "username": "john_agent",
            "email": "john@sdigdata.gov.gh",
            "role": "agent",
            "status": "active",
            "organization_id": "...",
            "created_at": "2024-01-01T00:00:00Z",
            "last_login": "2025-01-05T10:00:00Z"
        }
    }
    """
    # Users can only view their own profile unless they're admin
    if current_user["role"] != "admin" and str(user_id) != current_user["id"]:
        forbidden_response("You can only view your own profile")

    user = await get_user_by_id(conn, user_id)
    if not user:
        not_found_response("User not found")

    user_data = {
        k: v for k, v in cast(dict[str, Any], user).items() if k != "password_hash"
    }
    return success_response(data=user_data)


@router.put("/{user_id}", response_model=dict)
async def update_user_route(
    user_id: UUID,
    request: UserUpdateRequest,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    admin_user: Annotated[dict, Depends(require_admin)],
):
    """
    Update user by ID (admin only).

    **Request Body:**
    ```json
    {
        "username": "updated_name",
        "email": "updated@sdigdata.gov.gh",
        "role": "admin",
        "status": "active"
    }
    ```
    """
    updated_user = await update_user(
        conn,
        user_id=user_id,
        username=request.username,
        email=request.email,
        role=request.role,
        status=request.status,
    )

    if not updated_user:
        not_found_response("User not found")

    logger.info(f"User {user_id} updated by admin {admin_user['username']}")

    user_data = {k: v for k, v in updated_user.items() if k != "password_hash"}
    return success_response(data=user_data)


@router.delete("/{user_id}", response_model=dict)
async def delete_user_route(
    user_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    admin_user: Annotated[dict, Depends(require_admin)],
):
    """
    Delete user by ID (admin only).

    **Response:**
    ```json
    {
        "success": true,
        "message": "User deleted successfully"
    }
    ```
    """
    # Prevent admin from deleting themselves
    if str(user_id) == admin_user["id"]:
        error_response("You cannot delete your own account")

    success = await delete_user(conn, user_id)
    if not success:
        not_found_response("User not found")

    logger.info(f"User {user_id} deleted by admin {admin_user['username']}")

    return success_response(message="User deleted successfully")
