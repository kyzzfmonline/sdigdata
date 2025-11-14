"""API routes for API key management."""

from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.responses import error_response, success_response
from app.services import api_keys, audit

router = APIRouter(prefix="/users/me/api-keys", tags=["api-keys"])


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================


class CreateAPIKeyRequest(BaseModel):
    """Request model for creating an API key."""

    name: str = Field(..., min_length=1, max_length=255, description="Friendly name")
    scopes: list[str] | None = Field(
        None, description="Permission scopes (e.g., ['forms:read', 'responses:create'])"
    )
    expires_in_days: int | None = Field(
        None, ge=1, le=3650, description="Expiration in days (max 10 years)"
    )


class UpdateAPIKeyRequest(BaseModel):
    """Request model for updating an API key."""

    name: str | None = Field(None, min_length=1, max_length=255)
    scopes: list[str] | None = None


# ============================================================================
# ENDPOINTS
# ============================================================================


@router.get("")
async def list_my_api_keys(
    include_revoked: bool = False,
    conn=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """List all API keys for the current user.

    Query Parameters:
    - include_revoked: Include revoked/expired keys (default: false)
    """
    keys = await api_keys.list_user_api_keys(
        conn, current_user["id"], include_revoked=include_revoked
    )

    return success_response(
        data={"keys": keys, "count": len(keys)},
        message=f"Found {len(keys)} API keys",
    )


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_api_key(
    payload: CreateAPIKeyRequest,
    request: Request = None,
    conn=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Create a new API key.

    **IMPORTANT:** The full API key is only shown once in the response.
    Store it securely - you won't be able to retrieve it again!
    """
    new_key = await api_keys.create_api_key(
        conn,
        user_id=current_user["id"],
        name=payload.name,
        scopes=payload.scopes,
        expires_in_days=payload.expires_in_days,
    )

    # Create audit log
    await audit.create_audit_log(
        conn=conn,
        action_type=audit.AuditAction.API_KEY_CREATED,
        user_id=current_user["id"],
        resource_type="api_keys",
        resource_id=UUID(new_key["id"]),
        severity=audit.AuditSeverity.INFO,
        ip_address=request.client.host if request else None,
        user_agent=request.headers.get("user-agent") if request else None,
        details={
            "key_name": payload.name,
            "scopes": payload.scopes,
            "expires_in_days": payload.expires_in_days,
        },
    )

    return success_response(
        data=new_key,
        message=f"API key '{payload.name}' created successfully",
    )


@router.get("/{key_id}")
async def get_api_key(
    key_id: UUID,
    conn=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get details of a specific API key."""
    key = await api_keys.get_api_key_by_id(conn, key_id)

    if not key:
        return error_response(
            message=f"API key {key_id} not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    # Verify key belongs to current user
    if str(key["user_id"]) != str(current_user["id"]):
        return error_response(
            message="You can only view your own API keys",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    return success_response(data=key, message="API key retrieved successfully")


@router.put("/{key_id}")
async def update_api_key(
    key_id: UUID,
    payload: UpdateAPIKeyRequest,
    request: Request = None,
    conn=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Update API key metadata (name, scopes).

    Note: You cannot change the key itself - use rotation for that.
    """
    # Verify ownership
    key = await api_keys.get_api_key_by_id(conn, key_id)
    if not key or str(key["user_id"]) != str(current_user["id"]):
        return error_response(
            message="API key not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    updated_key = await api_keys.update_api_key(
        conn, key_id, name=payload.name, scopes=payload.scopes
    )

    # Create audit log
    await audit.create_audit_log(
        conn=conn,
        action_type="api_key_updated",
        user_id=current_user["id"],
        resource_type="api_keys",
        resource_id=key_id,
        severity=audit.AuditSeverity.INFO,
        ip_address=request.client.host if request else None,
        details={"changes": payload.dict(exclude_none=True)},
    )

    return success_response(data=updated_key, message="API key updated successfully")


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(
    key_id: UUID,
    request: Request = None,
    conn=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Revoke an API key permanently.

    Revoked keys cannot be used and cannot be reactivated.
    """
    # Verify ownership
    key = await api_keys.get_api_key_by_id(conn, key_id)
    if not key or str(key["user_id"]) != str(current_user["id"]):
        return error_response(
            message="API key not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    revoked = await api_keys.revoke_api_key(conn, key_id)
    if not revoked:
        return error_response(
            message="API key could not be revoked",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    # Create audit log
    await audit.create_audit_log(
        conn=conn,
        action_type=audit.AuditAction.API_KEY_REVOKED,
        user_id=current_user["id"],
        resource_type="api_keys",
        resource_id=key_id,
        severity=audit.AuditSeverity.WARNING,
        ip_address=request.client.host if request else None,
        details={"key_name": key["name"], "key_prefix": key["key_prefix"]},
    )

    return None


@router.post("/{key_id}/rotate", status_code=status.HTTP_201_CREATED)
async def rotate_api_key(
    key_id: UUID,
    request: Request = None,
    conn=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Rotate an API key (revoke old, create new).

    The old key is revoked and a new key with the same settings is created.
    **IMPORTANT:** The new full key is only shown in this response!
    """
    # Verify ownership
    key = await api_keys.get_api_key_by_id(conn, key_id)
    if not key or str(key["user_id"]) != str(current_user["id"]):
        return error_response(
            message="API key not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    new_key = await api_keys.rotate_api_key(conn, key_id)
    if not new_key:
        return error_response(
            message="Failed to rotate API key",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    # Create audit log
    await audit.create_audit_log(
        conn=conn,
        action_type="api_key_rotated",
        user_id=current_user["id"],
        resource_type="api_keys",
        resource_id=UUID(new_key["id"]),
        severity=audit.AuditSeverity.WARNING,
        ip_address=request.client.host if request else None,
        details={
            "old_key_id": str(key_id),
            "new_key_id": new_key["id"],
            "key_name": key["name"],
        },
    )

    return success_response(
        data=new_key,
        message="API key rotated successfully. Store the new key securely!",
    )


@router.get("/{key_id}/usage")
async def get_api_key_usage(
    key_id: UUID,
    days: int = 30,
    conn=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get usage statistics for an API key.

    Query Parameters:
    - days: Number of days to analyze (default: 30)

    Note: Detailed usage requires request logging to be implemented.
    """
    # Verify ownership
    key = await api_keys.get_api_key_by_id(conn, key_id)
    if not key or str(key["user_id"]) != str(current_user["id"]):
        return error_response(
            message="API key not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    usage = await api_keys.get_api_key_usage(conn, key_id, days=days)

    return success_response(data=usage, message="Usage statistics retrieved")


@router.get("/stats/overview")
async def get_api_key_statistics(
    conn=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get API key statistics for the current user."""
    stats = await api_keys.get_api_key_statistics(conn, current_user["id"])

    return success_response(data=stats, message="Statistics retrieved")
