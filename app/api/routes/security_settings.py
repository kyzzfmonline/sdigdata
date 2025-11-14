"""API routes for security settings management."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.responses import error_response, success_response
from app.services import audit, permissions, security_settings

router = APIRouter(prefix="/settings/security", tags=["security-settings"])


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================


class PasswordPolicyUpdate(BaseModel):
    """Request model for updating password policy."""

    min_length: int | None = Field(None, ge=1, le=128)
    max_length: int | None = Field(None, ge=1, le=256)
    require_uppercase: bool | None = None
    require_lowercase: bool | None = None
    require_numbers: bool | None = None
    require_special_chars: bool | None = None
    special_chars_allowed: str | None = None
    prevent_common_passwords: bool | None = None
    password_expiry_days: int | None = Field(None, ge=0)
    password_history_count: int | None = Field(None, ge=0)
    max_login_attempts: int | None = Field(None, ge=1)
    lockout_duration_minutes: int | None = Field(None, ge=1)


class SecuritySettingsUpdate(BaseModel):
    """Request model for updating security settings."""

    # Session settings
    session_timeout_minutes: int | None = Field(None, ge=1)
    absolute_timeout_hours: int | None = Field(None, ge=1)
    idle_timeout_minutes: int | None = Field(None, ge=1)
    max_concurrent_sessions: int | None = Field(None, ge=1)
    require_reauth_for_sensitive_actions: bool | None = None
    force_logout_on_password_change: bool | None = None
    remember_me_enabled: bool | None = None
    remember_me_duration_days: int | None = Field(None, ge=1)

    # Organization security
    allow_public_forms: bool | None = None
    require_email_verification: bool | None = None
    allowed_email_domains: list[str] | None = None
    enforce_2fa_for_all: bool | None = None
    enforce_2fa_for_roles: list[str] | None = None
    data_retention_days: int | None = Field(None, ge=1)
    auto_logout_inactive_users_days: int | None = Field(None, ge=1)
    ip_whitelist_enabled: bool | None = None


class SystemConfigUpdate(BaseModel):
    """Request model for updating system configuration."""

    value: Any


class ValidatePasswordRequest(BaseModel):
    """Request model for password validation."""

    password: str


# ============================================================================
# PASSWORD POLICY ENDPOINTS
# ============================================================================


@router.get("/password-policy")
async def get_password_policy(
    organization_id: UUID | None = None,
    conn=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get password policy configuration.

    Query Parameters:
    - organization_id: Get org-specific policy (default: system-wide)

    Returns the password policy that applies to the user's organization
    or the system default.
    """
    policy = await security_settings.get_password_policy(conn, organization_id)

    if not policy:
        return error_response(
            message="Password policy not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    return success_response(data=policy, message="Password policy retrieved")


@router.put("/password-policy")
async def update_password_policy(
    payload: PasswordPolicyUpdate,
    organization_id: UUID | None = None,
    request: Request = None,
    conn=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Update password policy configuration.

    Query Parameters:
    - organization_id: Update org-specific policy (default: system-wide)

    Requires: system.admin permission
    """
    # Check permission
    checker = permissions.PermissionChecker(conn)
    has_perm = await checker.has_permission(current_user["id"], "system", "admin")

    if not has_perm:
        return error_response(
            message="Insufficient permissions",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    updates = payload.dict(exclude_none=True)
    policy = await security_settings.update_password_policy(
        conn, organization_id, **updates
    )

    # Create audit log
    await audit.create_audit_log(
        conn=conn,
        action_type=audit.AuditAction.SECURITY_SETTINGS_CHANGED,
        user_id=current_user["id"],
        resource_type="password_policies",
        resource_id=UUID(policy["id"]),
        severity=audit.AuditSeverity.WARNING,
        ip_address=request.client.host if request else None,
        details={"changes": updates, "organization_id": str(organization_id) if organization_id else None},
    )

    return success_response(data=policy, message="Password policy updated")


@router.post("/password-policy/validate")
async def validate_password(
    payload: ValidatePasswordRequest,
    organization_id: UUID | None = None,
    conn=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Validate a password against the current policy.

    Useful for client-side validation before submission.
    """
    policy = await security_settings.get_password_policy(conn, organization_id)

    if not policy:
        return error_response(
            message="Password policy not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    is_valid, errors = security_settings.validate_password(payload.password, policy)

    return success_response(
        data={"is_valid": is_valid, "errors": errors if not is_valid else []},
        message="Password is valid" if is_valid else "Password does not meet policy requirements",
    )


# ============================================================================
# SECURITY SETTINGS ENDPOINTS
# ============================================================================


@router.get("")
async def get_security_settings(
    organization_id: UUID | None = None,
    conn=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get security settings configuration.

    Query Parameters:
    - organization_id: Get org-specific settings (default: system-wide)
    """
    settings = await security_settings.get_security_settings(conn, organization_id)

    if not settings:
        return error_response(
            message="Security settings not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    return success_response(data=settings, message="Security settings retrieved")


@router.put("")
async def update_security_settings(
    payload: SecuritySettingsUpdate,
    organization_id: UUID | None = None,
    request: Request = None,
    conn=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Update security settings configuration.

    Query Parameters:
    - organization_id: Update org-specific settings (default: system-wide)

    Requires: system.admin permission
    """
    # Check permission
    checker = permissions.PermissionChecker(conn)
    has_perm = await checker.has_permission(current_user["id"], "system", "admin")

    if not has_perm:
        return error_response(
            message="Insufficient permissions",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    updates = payload.dict(exclude_none=True)
    settings = await security_settings.update_security_settings(
        conn, organization_id, **updates
    )

    # Create audit log
    await audit.create_audit_log(
        conn=conn,
        action_type=audit.AuditAction.SECURITY_SETTINGS_CHANGED,
        user_id=current_user["id"],
        resource_type="security_settings",
        resource_id=UUID(settings["id"]),
        severity=audit.AuditSeverity.WARNING,
        ip_address=request.client.host if request else None,
        details={"changes": updates},
    )

    return success_response(data=settings, message="Security settings updated")


# ============================================================================
# SYSTEM CONFIGURATION ENDPOINTS
# ============================================================================


@router.get("/system-config")
async def list_system_config(
    prefix: str | None = None,
    conn=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """List system configuration values.

    Query Parameters:
    - prefix: Filter by key prefix (e.g., 'rbac.', 'features.')

    Requires: system.admin permission
    """
    # Check permission
    checker = permissions.PermissionChecker(conn)
    has_perm = await checker.has_permission(current_user["id"], "system", "admin")

    if not has_perm:
        return error_response(
            message="Insufficient permissions",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    configs = await security_settings.list_system_config(conn, prefix)

    return success_response(
        data={"configs": configs, "count": len(configs)},
        message=f"Found {len(configs)} configuration values",
    )


@router.get("/system-config/{key}")
async def get_system_config(
    key: str,
    conn=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get a specific system configuration value.

    Requires: system.admin permission
    """
    # Check permission
    checker = permissions.PermissionChecker(conn)
    has_perm = await checker.has_permission(current_user["id"], "system", "admin")

    if not has_perm:
        return error_response(
            message="Insufficient permissions",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    value = await security_settings.get_system_config(conn, key)

    if value is None:
        return error_response(
            message=f"Configuration '{key}' not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    return success_response(data={"key": key, "value": value}, message="Configuration retrieved")


@router.put("/system-config/{key}")
async def update_system_config(
    key: str,
    payload: SystemConfigUpdate,
    request: Request = None,
    conn=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Update a system configuration value.

    Requires: system.admin permission
    """
    # Check permission
    checker = permissions.PermissionChecker(conn)
    has_perm = await checker.has_permission(current_user["id"], "system", "admin")

    if not has_perm:
        return error_response(
            message="Insufficient permissions",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    config = await security_settings.update_system_config(
        conn, key, payload.value, updated_by=current_user["id"]
    )

    # Create audit log
    await audit.create_audit_log(
        conn=conn,
        action_type=audit.AuditAction.SYSTEM_CONFIG_CHANGED,
        user_id=current_user["id"],
        severity=audit.AuditSeverity.WARNING,
        ip_address=request.client.host if request else None,
        details={"key": key, "value": payload.value},
    )

    return success_response(data=config, message=f"Configuration '{key}' updated")


# ============================================================================
# LOGIN TRACKING ENDPOINTS
# ============================================================================


@router.get("/login-history")
async def get_login_history(
    days: int = 30,
    conn=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get login history for the current user.

    Query Parameters:
    - days: Number of days to look back (default: 30)

    Returns successful and failed login attempts.
    """
    # Get login events from audit logs
    login_events = await conn.fetch(
        """
        SELECT
            action_type, ip_address, user_agent, timestamp, details
        FROM audit_logs
        WHERE user_id = $1
        AND action_type IN ('login', 'login_failed', 'logout')
        AND timestamp >= CURRENT_TIMESTAMP - INTERVAL '1 day' * $2
        ORDER BY timestamp DESC
        LIMIT 100
        """,
        str(current_user["id"]),
        days,
    )

    events = [dict(row) for row in login_events]

    return success_response(
        data={"events": events, "count": len(events)},
        message=f"Found {len(events)} login events in the past {days} days",
    )


@router.get("/account-status")
async def get_account_status(
    conn=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get current account security status.

    Returns information about:
    - Account lockout status
    - Recent failed login attempts
    - Active sessions count
    - API keys count
    """
    username = current_user["username"]

    # Check if locked
    is_locked, minutes_remaining = await security_settings.is_account_locked(
        conn, username
    )

    # Get recent failed attempts
    policy = await security_settings.get_password_policy(conn)
    lockout_minutes = policy.get("lockout_duration_minutes", 30) if policy else 30

    failed_count = await conn.fetchval(
        """
        SELECT COUNT(*)
        FROM audit_logs
        WHERE action_type = 'login_failed'
        AND details->>'username' = $1
        AND timestamp > CURRENT_TIMESTAMP - INTERVAL '1 minute' * $2
        """,
        username,
        lockout_minutes,
    )

    # Get active sessions count
    from app.services import sessions

    active_sessions = await sessions.get_active_session_count(conn, current_user["id"])

    # Get API keys count
    from app.services import api_keys

    stats = await api_keys.get_api_key_statistics(conn, current_user["id"])

    return success_response(
        data={
            "is_locked": is_locked,
            "minutes_until_unlock": minutes_remaining,
            "recent_failed_attempts": failed_count or 0,
            "active_sessions": active_sessions,
            "active_api_keys": stats.get("active_keys", 0),
        },
        message="Account status retrieved",
    )
