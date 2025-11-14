"""API routes for RBAC (Role-Based Access Control) management."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.responses import error_response, success_response
from app.services import rbac

router = APIRouter(prefix="/rbac", tags=["rbac"])


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================


class RoleCreate(BaseModel):
    """Request model for creating a role."""

    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = Field(None, max_length=500)


class RoleUpdate(BaseModel):
    """Request model for updating a role."""

    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = Field(None, max_length=500)


class PermissionCreate(BaseModel):
    """Request model for creating a permission."""

    name: str = Field(..., min_length=1, max_length=100)
    resource: str = Field(..., min_length=1, max_length=50)
    action: str = Field(..., min_length=1, max_length=50)
    description: str | None = Field(None, max_length=500)


class AssignPermissions(BaseModel):
    """Request model for assigning permissions to a role."""

    permission_ids: list[UUID] = Field(..., min_items=1)


class AssignRole(BaseModel):
    """Request model for assigning a role to a user."""

    role_id: UUID
    expires_at: str | None = Field(None, description="ISO 8601 timestamp for role expiration")
    reason: str | None = Field(None, max_length=500, description="Reason for assignment")


# ============================================================================
# ROLE ENDPOINTS
# ============================================================================


@router.get("/roles")
async def list_roles(
    conn=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """List all roles with permission and user counts.

    Requires: roles.admin permission
    """
    # Check permission
    user_perms = await rbac.get_user_permissions(conn, current_user["id"])
    if not any(p["resource"] == "roles" and p["action"] == "admin" for p in user_perms):
        return error_response(
            message="Insufficient permissions",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    roles = await rbac.list_roles(conn)
    return success_response(
        data={"roles": roles, "count": len(roles)},
        message=f"Found {len(roles)} roles",
    )


@router.get("/roles/{role_id}")
async def get_role(
    role_id: UUID,
    conn=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get role details with permissions.

    Requires: roles.admin permission
    """
    # Check permission
    user_perms = await rbac.get_user_permissions(conn, current_user["id"])
    if not any(p["resource"] == "roles" and p["action"] == "admin" for p in user_perms):
        return error_response(
            message="Insufficient permissions",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    role = await rbac.get_role_by_id(conn, role_id)
    if not role:
        return error_response(
            message=f"Role {role_id} not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    return success_response(data=role, message="Role retrieved successfully")


@router.post("/roles", status_code=status.HTTP_201_CREATED)
async def create_role(
    payload: RoleCreate,
    conn=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Create a new role.

    Requires: roles.admin permission
    """
    # Check permission
    user_perms = await rbac.get_user_permissions(conn, current_user["id"])
    if not any(p["resource"] == "roles" and p["action"] == "admin" for p in user_perms):
        return error_response(
            message="Insufficient permissions",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    try:
        role = await rbac.create_role(
            conn, name=payload.name, description=payload.description
        )
        return success_response(
            data=role,
            message=f"Role '{payload.name}' created successfully",
        )
    except Exception as e:
        if "unique constraint" in str(e).lower():
            return error_response(
                message=f"Role '{payload.name}' already exists",
                status_code=status.HTTP_409_CONFLICT,
            )
        raise


@router.put("/roles/{role_id}")
async def update_role(
    role_id: UUID,
    payload: RoleUpdate,
    conn=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Update a role.

    Requires: roles.admin permission
    """
    # Check permission
    user_perms = await rbac.get_user_permissions(conn, current_user["id"])
    if not any(p["resource"] == "roles" and p["action"] == "admin" for p in user_perms):
        return error_response(
            message="Insufficient permissions",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    # Check role exists
    existing = await rbac.get_role_by_id(conn, role_id)
    if not existing:
        return error_response(
            message=f"Role {role_id} not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    try:
        role = await rbac.update_role(
            conn, role_id, name=payload.name, description=payload.description
        )
        return success_response(data=role, message="Role updated successfully")
    except Exception as e:
        if "unique constraint" in str(e).lower():
            return error_response(
                message=f"Role name '{payload.name}' already exists",
                status_code=status.HTTP_409_CONFLICT,
            )
        raise


@router.delete("/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_role(
    role_id: UUID,
    conn=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Delete a role.

    Requires: roles.admin permission
    """
    # Check permission
    user_perms = await rbac.get_user_permissions(conn, current_user["id"])
    if not any(p["resource"] == "roles" and p["action"] == "admin" for p in user_perms):
        return error_response(
            message="Insufficient permissions",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    deleted = await rbac.delete_role(conn, role_id)
    if not deleted:
        return error_response(
            message=f"Role {role_id} not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    return None


# ============================================================================
# PERMISSION ENDPOINTS
# ============================================================================


@router.get("/permissions")
async def list_permissions(
    resource: str | None = None,
    conn=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """List all permissions, optionally filtered by resource.

    Requires: permissions.admin permission
    """
    # Check permission
    user_perms = await rbac.get_user_permissions(conn, current_user["id"])
    if not any(
        p["resource"] == "permissions" and p["action"] == "admin" for p in user_perms
    ):
        return error_response(
            message="Insufficient permissions",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    permissions = await rbac.list_permissions(conn, resource=resource)
    return success_response(
        data={"permissions": permissions, "count": len(permissions)},
        message=f"Found {len(permissions)} permissions",
    )


@router.post("/permissions", status_code=status.HTTP_201_CREATED)
async def create_permission(
    payload: PermissionCreate,
    conn=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Create a new permission.

    Requires: permissions.admin permission
    """
    # Check permission
    user_perms = await rbac.get_user_permissions(conn, current_user["id"])
    if not any(
        p["resource"] == "permissions" and p["action"] == "admin" for p in user_perms
    ):
        return error_response(
            message="Insufficient permissions",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    try:
        permission = await rbac.create_permission(
            conn,
            name=payload.name,
            resource=payload.resource,
            action=payload.action,
            description=payload.description,
        )
        return success_response(
            data=permission,
            message=f"Permission '{payload.resource}.{payload.action}' created successfully",
        )
    except Exception as e:
        if "unique constraint" in str(e).lower():
            return error_response(
                message=f"Permission '{payload.resource}.{payload.action}' already exists",
                status_code=status.HTTP_409_CONFLICT,
            )
        raise


@router.delete("/permissions/{permission_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_permission(
    permission_id: UUID,
    conn=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Delete a permission.

    Requires: permissions.admin permission
    """
    # Check permission
    user_perms = await rbac.get_user_permissions(conn, current_user["id"])
    if not any(
        p["resource"] == "permissions" and p["action"] == "admin" for p in user_perms
    ):
        return error_response(
            message="Insufficient permissions",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    deleted = await rbac.delete_permission(conn, permission_id)
    if not deleted:
        return error_response(
            message=f"Permission {permission_id} not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    return None


# ============================================================================
# ROLE-PERMISSION ENDPOINTS
# ============================================================================


@router.get("/roles/{role_id}/permissions")
async def get_role_permissions(
    role_id: UUID,
    conn=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get all permissions for a role.

    Requires: roles.admin permission
    """
    # Check permission
    user_perms = await rbac.get_user_permissions(conn, current_user["id"])
    if not any(p["resource"] == "roles" and p["action"] == "admin" for p in user_perms):
        return error_response(
            message="Insufficient permissions",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    # Check role exists
    role = await rbac.get_role_by_id(conn, role_id)
    if not role:
        return error_response(
            message=f"Role {role_id} not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    permissions = await rbac.get_role_permissions(conn, role_id)
    return success_response(
        data={"permissions": permissions, "count": len(permissions)},
        message=f"Role has {len(permissions)} permissions",
    )


@router.post("/roles/{role_id}/permissions")
async def assign_permissions_to_role(
    role_id: UUID,
    payload: AssignPermissions,
    conn=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Assign permissions to a role.

    Requires: roles.admin permission
    """
    # Check permission
    user_perms = await rbac.get_user_permissions(conn, current_user["id"])
    if not any(p["resource"] == "roles" and p["action"] == "admin" for p in user_perms):
        return error_response(
            message="Insufficient permissions",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    # Check role exists
    role = await rbac.get_role_by_id(conn, role_id)
    if not role:
        return error_response(
            message=f"Role {role_id} not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    count = await rbac.assign_permissions_to_role(conn, role_id, payload.permission_ids)
    return success_response(
        data={"assigned_count": count},
        message=f"Assigned {count} permissions to role",
    )


@router.delete("/roles/{role_id}/permissions")
async def revoke_permissions_from_role(
    role_id: UUID,
    payload: AssignPermissions,
    conn=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Revoke permissions from a role.

    Requires: roles.admin permission
    """
    # Check permission
    user_perms = await rbac.get_user_permissions(conn, current_user["id"])
    if not any(p["resource"] == "roles" and p["action"] == "admin" for p in user_perms):
        return error_response(
            message="Insufficient permissions",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    count = await rbac.revoke_permissions_from_role(
        conn, role_id, payload.permission_ids
    )
    return success_response(
        data={"revoked_count": count},
        message=f"Revoked {count} permissions from role",
    )


# ============================================================================
# USER-ROLE ENDPOINTS
# ============================================================================


@router.get("/users/{user_id}/roles")
async def get_user_roles(
    user_id: UUID,
    conn=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get all roles assigned to a user.

    Requires: users.admin permission OR querying own user
    """
    # Check permission (can view own roles or need users.admin)
    user_perms = await rbac.get_user_permissions(conn, current_user["id"])
    is_self = str(user_id) == str(current_user["id"])
    has_admin = any(p["resource"] == "users" and p["action"] == "admin" for p in user_perms)

    if not is_self and not has_admin:
        return error_response(
            message="Insufficient permissions",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    roles = await rbac.get_user_roles(conn, user_id)
    return success_response(
        data={"roles": roles, "count": len(roles)},
        message=f"User has {len(roles)} roles",
    )


@router.post("/users/{user_id}/roles")
async def assign_role_to_user(
    user_id: UUID,
    payload: AssignRole,
    conn=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Assign a role to a user.

    Requires: users.admin permission
    """
    # Check permission
    user_perms = await rbac.get_user_permissions(conn, current_user["id"])
    if not any(p["resource"] == "users" and p["action"] == "admin" for p in user_perms):
        return error_response(
            message="Insufficient permissions",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    # Check role exists
    role = await rbac.get_role_by_id(conn, payload.role_id)
    if not role:
        return error_response(
            message=f"Role {payload.role_id} not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    assigned = await rbac.assign_role_to_user(conn, user_id, payload.role_id)
    if assigned:
        return success_response(
            message=f"Role '{role['name']}' assigned to user successfully"
        )
    else:
        return success_response(message="User already has this role")


@router.delete("/users/{user_id}/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_role_from_user(
    user_id: UUID,
    role_id: UUID,
    conn=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Revoke a role from a user.

    Requires: users.admin permission
    """
    # Check permission
    user_perms = await rbac.get_user_permissions(conn, current_user["id"])
    if not any(p["resource"] == "users" and p["action"] == "admin" for p in user_perms):
        return error_response(
            message="Insufficient permissions",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    revoked = await rbac.revoke_role_from_user(conn, user_id, role_id)
    if not revoked:
        return error_response(
            message="User does not have this role",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    return None


@router.get("/users/{user_id}/permissions")
async def get_user_permissions(
    user_id: UUID,
    conn=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get all effective permissions for a user (aggregated from all roles).

    Requires: users.admin permission OR querying own user
    """
    # Check permission (can view own permissions or need users.admin)
    user_perms = await rbac.get_user_permissions(conn, current_user["id"])
    is_self = str(user_id) == str(current_user["id"])
    has_admin = any(p["resource"] == "users" and p["action"] == "admin" for p in user_perms)

    if not is_self and not has_admin:
        return error_response(
            message="Insufficient permissions",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    permissions = await rbac.get_user_permissions(conn, user_id)
    return success_response(
        data={"permissions": permissions, "count": len(permissions)},
        message=f"User has {len(permissions)} effective permissions",
    )


@router.get("/roles/{role_id}/users")
async def get_role_users(
    role_id: UUID,
    conn=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get all users assigned to a role.

    Requires: roles.admin permission
    """
    # Check permission
    user_perms = await rbac.get_user_permissions(conn, current_user["id"])
    if not any(p["resource"] == "roles" and p["action"] == "admin" for p in user_perms):
        return error_response(
            message="Insufficient permissions",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    # Check role exists
    role = await rbac.get_role_by_id(conn, role_id)
    if not role:
        return error_response(
            message=f"Role {role_id} not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    users = await rbac.get_role_users(conn, role_id)
    return success_response(
        data={"users": users, "count": len(users)},
        message=f"Role has {len(users)} users",
    )


# ============================================================================
# ROLE EXPIRATION ENDPOINTS
# ============================================================================


@router.get("/roles/expiring")
async def get_expiring_roles(
    days: int = 7,
    conn=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get roles that are expiring soon.

    Query Parameters:
    - days: Days until expiry to filter (default: 7)

    Requires: users.admin permission

    Useful for admin dashboards to track temporary access.
    """
    # Check permission
    user_perms = await rbac.get_user_permissions(conn, current_user["id"])
    if not any(p["resource"] == "users" and p["action"] == "admin" for p in user_perms):
        return error_response(
            message="Insufficient permissions",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    results = await conn.fetch(
        """
        SELECT
            ur.id, ur.user_id, ur.role_id, ur.expires_at, ur.assigned_at, ur.reason,
            u.username, u.email,
            r.name as role_name,
            EXTRACT(DAY FROM (ur.expires_at - CURRENT_TIMESTAMP)) as days_remaining
        FROM user_roles ur
        JOIN users u ON ur.user_id = u.id
        JOIN roles r ON ur.role_id = r.id
        WHERE ur.expires_at IS NOT NULL
        AND ur.expires_at > CURRENT_TIMESTAMP
        AND ur.expires_at <= CURRENT_TIMESTAMP + INTERVAL '1 day' * $1
        AND ur.is_active = TRUE
        ORDER BY ur.expires_at ASC
        """,
        days,
    )

    expiring = [dict(row) for row in results]

    return success_response(
        data={"expiring_assignments": expiring, "count": len(expiring)},
        message=f"Found {len(expiring)} roles expiring in the next {days} days",
    )


@router.get("/roles/expired")
async def get_expired_roles(
    conn=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get roles that have expired but not yet deactivated.

    Requires: users.admin permission
    """
    # Check permission
    user_perms = await rbac.get_user_permissions(conn, current_user["id"])
    if not any(p["resource"] == "users" and p["action"] == "admin" for p in user_perms):
        return error_response(
            message="Insufficient permissions",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    results = await conn.fetch(
        """
        SELECT
            ur.id, ur.user_id, ur.role_id, ur.expires_at, ur.assigned_at, ur.reason,
            u.username, u.email,
            r.name as role_name
        FROM user_roles ur
        JOIN users u ON ur.user_id = u.id
        JOIN roles r ON ur.role_id = r.id
        WHERE ur.expires_at IS NOT NULL
        AND ur.expires_at < CURRENT_TIMESTAMP
        AND ur.is_active = TRUE
        ORDER BY ur.expires_at DESC
        """,
    )

    expired = [dict(row) for row in results]

    return success_response(
        data={"expired_assignments": expired, "count": len(expired)},
        message=f"Found {len(expired)} expired role assignments",
    )


@router.post("/roles/expire-old")
async def expire_old_roles(
    conn=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Deactivate expired role assignments.

    This should be run periodically (e.g., daily cron job).

    Requires: users.admin permission
    """
    # Check permission
    user_perms = await rbac.get_user_permissions(conn, current_user["id"])
    if not any(p["resource"] == "users" and p["action"] == "admin" for p in user_perms):
        return error_response(
            message="Insufficient permissions",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    result = await conn.execute(
        """
        UPDATE user_roles
        SET is_active = FALSE
        WHERE expires_at IS NOT NULL
        AND expires_at < CURRENT_TIMESTAMP
        AND is_active = TRUE
        """,
    )

    expired_count = int(result.split()[-1]) if result else 0

    return success_response(
        data={"expired_count": expired_count},
        message=f"Deactivated {expired_count} expired role assignments",
    )
