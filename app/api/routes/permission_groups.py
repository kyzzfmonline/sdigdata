"""API routes for permission group management."""

from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.responses import error_response, success_response
from app.services import audit, permission_groups, permissions

router = APIRouter(prefix="/rbac/permission-groups", tags=["permission-groups"])


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================


class CreatePermissionGroupRequest(BaseModel):
    """Request model for creating a permission group."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(None, max_length=500)
    permission_ids: list[UUID] = Field(default_factory=list)
    organization_id: UUID | None = None


class UpdatePermissionGroupRequest(BaseModel):
    """Request model for updating a permission group."""

    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = Field(None, max_length=500)


class ManageGroupPermissionsRequest(BaseModel):
    """Request model for adding/removing permissions."""

    permission_ids: list[UUID] = Field(..., min_items=1)


# ============================================================================
# PERMISSION GROUP ENDPOINTS
# ============================================================================


@router.get("")
async def list_permission_groups(
    organization_id: UUID | None = None,
    include_system: bool = True,
    conn=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """List all permission groups.

    Query Parameters:
    - organization_id: Filter by organization
    - include_system: Include system groups (default: true)

    Requires: roles.admin or permissions.admin permission
    """
    checker = permissions.PermissionChecker(conn)
    has_perm = await checker.has_any_permission(
        current_user["id"], [("roles", "admin"), ("permissions", "admin")]
    )

    if not has_perm:
        return error_response(
            message="Insufficient permissions",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    groups = await permission_groups.list_permission_groups(
        conn, organization_id, include_system
    )

    return success_response(
        data={"groups": groups, "count": len(groups)},
        message=f"Found {len(groups)} permission groups",
    )


@router.get("/{group_id}")
async def get_permission_group(
    group_id: UUID,
    conn=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get permission group by ID with all permissions."""
    checker = permissions.PermissionChecker(conn)
    has_perm = await checker.has_any_permission(
        current_user["id"], [("roles", "admin"), ("permissions", "admin")]
    )

    if not has_perm:
        return error_response(
            message="Insufficient permissions",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    group = await permission_groups.get_permission_group_by_id(conn, group_id)

    if not group:
        return error_response(
            message=f"Permission group {group_id} not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    return success_response(data=group, message="Permission group retrieved")


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_permission_group(
    payload: CreatePermissionGroupRequest,
    request: Request = None,
    conn=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Create a new permission group."""
    checker = permissions.PermissionChecker(conn)
    has_perm = await checker.has_permission(current_user["id"], "permissions", "admin")

    if not has_perm:
        return error_response(
            message="Insufficient permissions",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    group = await permission_groups.create_permission_group(
        conn,
        name=payload.name,
        description=payload.description,
        permission_ids=payload.permission_ids,
        organization_id=payload.organization_id,
    )

    # Audit log
    await audit.create_audit_log(
        conn=conn,
        action_type="permission_group_created",
        user_id=current_user["id"],
        resource_type="permission_groups",
        resource_id=UUID(group["id"]),
        severity=audit.AuditSeverity.INFO,
        ip_address=request.client.host if request else None,
        details={"group_name": payload.name, "permission_count": len(payload.permission_ids)},
    )

    return success_response(data=group, message=f"Permission group '{payload.name}' created")


@router.put("/{group_id}")
async def update_permission_group(
    group_id: UUID,
    payload: UpdatePermissionGroupRequest,
    request: Request = None,
    conn=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Update permission group metadata."""
    checker = permissions.PermissionChecker(conn)
    has_perm = await checker.has_permission(current_user["id"], "permissions", "admin")

    if not has_perm:
        return error_response(
            message="Insufficient permissions",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    group = await permission_groups.update_permission_group(
        conn, group_id, name=payload.name, description=payload.description
    )

    if not group:
        return error_response(
            message=f"Permission group {group_id} not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    # Audit log
    await audit.create_audit_log(
        conn=conn,
        action_type="permission_group_updated",
        user_id=current_user["id"],
        resource_type="permission_groups",
        resource_id=group_id,
        severity=audit.AuditSeverity.INFO,
        ip_address=request.client.host if request else None,
        details={"changes": payload.dict(exclude_none=True)},
    )

    return success_response(data=group, message="Permission group updated")


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_permission_group(
    group_id: UUID,
    request: Request = None,
    conn=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Delete a permission group (system groups cannot be deleted)."""
    checker = permissions.PermissionChecker(conn)
    has_perm = await checker.has_permission(current_user["id"], "permissions", "admin")

    if not has_perm:
        return error_response(
            message="Insufficient permissions",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    deleted = await permission_groups.delete_permission_group(conn, group_id)

    if not deleted:
        return error_response(
            message="Permission group not found or is a system group",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    # Audit log
    await audit.create_audit_log(
        conn=conn,
        action_type="permission_group_deleted",
        user_id=current_user["id"],
        resource_type="permission_groups",
        resource_id=group_id,
        severity=audit.AuditSeverity.WARNING,
        ip_address=request.client.host if request else None,
    )

    return None


# ============================================================================
# GROUP PERMISSIONS MANAGEMENT
# ============================================================================


@router.post("/{group_id}/permissions")
async def add_permissions_to_group(
    group_id: UUID,
    payload: ManageGroupPermissionsRequest,
    request: Request = None,
    conn=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Add permissions to a group."""
    checker = permissions.PermissionChecker(conn)
    has_perm = await checker.has_permission(current_user["id"], "permissions", "admin")

    if not has_perm:
        return error_response(
            message="Insufficient permissions",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    count = await permission_groups.add_permissions_to_group(
        conn, group_id, payload.permission_ids
    )

    # Audit log
    await audit.create_audit_log(
        conn=conn,
        action_type="permission_group_permissions_added",
        user_id=current_user["id"],
        resource_type="permission_groups",
        resource_id=group_id,
        severity=audit.AuditSeverity.INFO,
        ip_address=request.client.host if request else None,
        details={"added_count": count},
    )

    return success_response(
        data={"added_count": count},
        message=f"Added {count} permissions to group",
    )


@router.delete("/{group_id}/permissions")
async def remove_permissions_from_group(
    group_id: UUID,
    payload: ManageGroupPermissionsRequest,
    request: Request = None,
    conn=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Remove permissions from a group."""
    checker = permissions.PermissionChecker(conn)
    has_perm = await checker.has_permission(current_user["id"], "permissions", "admin")

    if not has_perm:
        return error_response(
            message="Insufficient permissions",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    count = await permission_groups.remove_permissions_from_group(
        conn, group_id, payload.permission_ids
    )

    # Audit log
    await audit.create_audit_log(
        conn=conn,
        action_type="permission_group_permissions_removed",
        user_id=current_user["id"],
        resource_type="permission_groups",
        resource_id=group_id,
        severity=audit.AuditSeverity.INFO,
        ip_address=request.client.host if request else None,
        details={"removed_count": count},
    )

    return success_response(
        data={"removed_count": count},
        message=f"Removed {count} permissions from group",
    )


# ============================================================================
# ROLE ASSIGNMENT
# ============================================================================


@router.post("/{group_id}/assign-to-role/{role_id}")
async def assign_group_to_role(
    group_id: UUID,
    role_id: UUID,
    request: Request = None,
    conn=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Assign all permissions from a group to a role."""
    checker = permissions.PermissionChecker(conn)
    has_perm = await checker.has_permission(current_user["id"], "roles", "admin")

    if not has_perm:
        return error_response(
            message="Insufficient permissions",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    count = await permission_groups.assign_group_to_role(conn, role_id, group_id)

    # Audit log
    await audit.create_audit_log(
        conn=conn,
        action_type="permission_group_assigned_to_role",
        user_id=current_user["id"],
        resource_type="permission_groups",
        resource_id=group_id,
        severity=audit.AuditSeverity.INFO,
        ip_address=request.client.host if request else None,
        details={"role_id": str(role_id), "permissions_added": count},
    )

    return success_response(
        data={"permissions_added": count},
        message=f"Assigned {count} permissions from group to role",
    )
