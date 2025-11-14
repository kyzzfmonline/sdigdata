"""API routes for session management."""

from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.responses import error_response, success_response
from app.services import audit, sessions

router = APIRouter(prefix="/users/me/sessions", tags=["sessions"])


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================


class SessionResponse(BaseModel):
    """Response model for session."""

    id: UUID
    device_info: dict | None
    ip_address: str | None
    location: str | None
    user_agent: str | None
    last_active_at: str
    expires_at: str
    created_at: str
    is_active: bool


# ============================================================================
# ENDPOINTS
# ============================================================================


@router.get("")
async def list_my_sessions(
    include_revoked: bool = False,
    request: Request = None,
    conn=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """List all sessions for the current user.

    Query Parameters:
    - include_revoked: Include revoked/expired sessions (default: false)

    Returns list of all active and optionally inactive sessions.
    Each session includes device info, location, and activity status.
    """
    user_sessions = await sessions.list_user_sessions(
        conn, current_user["id"], include_revoked=include_revoked
    )

    # Mark current session
    if request and hasattr(request.state, "session_id"):
        current_session_id = str(request.state.session_id)
        for session in user_sessions:
            session["is_current"] = str(session["id"]) == current_session_id
    else:
        for session in user_sessions:
            session["is_current"] = False

    return success_response(
        data={"sessions": user_sessions, "count": len(user_sessions)},
        message=f"Found {len(user_sessions)} sessions",
    )


@router.get("/{session_id}")
async def get_session(
    session_id: UUID,
    conn=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get details of a specific session.

    Users can only view their own sessions.
    """
    session = await sessions.get_session_by_id(conn, session_id)

    if not session:
        return error_response(
            message=f"Session {session_id} not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    # Verify session belongs to current user
    if str(session["user_id"]) != str(current_user["id"]):
        return error_response(
            message="You can only view your own sessions",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    return success_response(data=session, message="Session retrieved successfully")


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_session(
    session_id: UUID,
    request: Request = None,
    conn=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Revoke a specific session (logout from that device).

    Users can only revoke their own sessions.
    Warning: Revoking your current session will log you out.
    """
    # Get session to verify ownership
    session = await sessions.get_session_by_id(conn, session_id)

    if not session:
        return error_response(
            message=f"Session {session_id} not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    # Verify session belongs to current user
    if str(session["user_id"]) != str(current_user["id"]):
        return error_response(
            message="You can only revoke your own sessions",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    # Revoke the session
    revoked = await sessions.revoke_session(conn, session_id)

    if not revoked:
        return error_response(
            message="Session could not be revoked",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    # Create audit log
    await audit.create_audit_log(
        conn=conn,
        action_type=audit.AuditAction.SESSION_REVOKED,
        user_id=current_user["id"],
        resource_type="sessions",
        resource_id=session_id,
        severity=audit.AuditSeverity.INFO,
        ip_address=request.client.host if request else None,
        user_agent=request.headers.get("user-agent") if request else None,
        details={
            "session_id": str(session_id),
            "device": session.get("device_info", {}).get("device", "Unknown"),
            "ip_address": session.get("ip_address"),
        },
    )

    return None


@router.delete("", status_code=status.HTTP_200_OK)
async def revoke_all_sessions(
    keep_current: bool = True,
    request: Request = None,
    conn=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Revoke all sessions for the current user (logout from all devices).

    Query Parameters:
    - keep_current: Keep the current session active (default: true)

    This is useful for logging out all other devices while staying
    logged in on the current device.
    """
    current_session_id = None
    if keep_current and request and hasattr(request.state, "session_id"):
        current_session_id = request.state.session_id

    revoked_count = await sessions.revoke_all_user_sessions(
        conn, current_user["id"], except_session_id=current_session_id
    )

    # Create audit log
    await audit.create_audit_log(
        conn=conn,
        action_type=audit.AuditAction.LOGOUT,
        user_id=current_user["id"],
        severity=audit.AuditSeverity.WARNING,
        ip_address=request.client.host if request else None,
        user_agent=request.headers.get("user-agent") if request else None,
        details={
            "action": "revoke_all_sessions",
            "revoked_count": revoked_count,
            "kept_current": keep_current,
        },
    )

    return success_response(
        data={"revoked_count": revoked_count},
        message=f"Revoked {revoked_count} sessions",
    )


@router.get("/stats/overview")
async def get_session_statistics(
    conn=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get session statistics for the current user.

    Returns:
    - Total sessions
    - Active sessions
    - Revoked sessions
    - Expired sessions
    - Average session duration
    """
    stats = await sessions.get_session_statistics(conn, current_user["id"])

    return success_response(data=stats, message="Session statistics retrieved")


@router.get("/security/suspicious")
async def detect_suspicious_activity(
    conn=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Detect suspicious session activity for the current user.

    Analyzes session patterns to identify:
    - Multiple concurrent sessions from different locations
    - Unusually high number of active sessions
    - Sessions from new/unusual IP addresses

    Returns list of sessions that appear suspicious with reasons.
    """
    suspicious = await sessions.detect_suspicious_sessions(conn, current_user["id"])

    if suspicious:
        # Create audit log for suspicious activity detection
        await audit.create_audit_log(
            conn=conn,
            action_type="suspicious_activity_detected",
            user_id=current_user["id"],
            severity=audit.AuditSeverity.WARNING,
            details={
                "suspicious_session_count": len(suspicious),
                "reasons": [s["suspicion_reason"] for s in suspicious],
            },
        )

    return success_response(
        data={"suspicious_sessions": suspicious, "count": len(suspicious)},
        message=f"Found {len(suspicious)} suspicious sessions"
        if suspicious
        else "No suspicious activity detected",
    )


# ============================================================================
# ADMIN ENDPOINTS
# ============================================================================


@router.get(
    "/admin/all",
    tags=["admin", "sessions"],
)
async def list_all_sessions(
    user_id: UUID | None = None,
    ip_address: str | None = None,
    active_only: bool = True,
    conn=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """List all sessions (admin only).

    Query Parameters:
    - user_id: Filter by user ID
    - ip_address: Filter by IP address
    - active_only: Show only active sessions (default: true)

    Requires: system.admin permission
    """
    # Check admin permission
    from app.services import permissions

    checker = permissions.PermissionChecker(conn)
    has_perm = await checker.has_permission(current_user["id"], "system", "admin")

    if not has_perm:
        return error_response(
            message="Insufficient permissions",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    if ip_address:
        # Get sessions by IP
        session_list = await sessions.get_sessions_by_ip(conn, ip_address)
        if active_only:
            session_list = [
                s
                for s in session_list
                if s["revoked_at"] is None
                and s["expires_at"] > sessions.datetime.utcnow()
            ]
    elif user_id:
        # Get sessions by user
        session_list = await sessions.list_user_sessions(
            conn, user_id, include_revoked=not active_only
        )
    else:
        # Get all sessions (use with caution!)
        query = """
            SELECT
                s.id, s.user_id, s.device_info, s.ip_address,
                s.location, s.user_agent, s.last_active_at,
                s.expires_at, s.created_at, s.revoked_at,
                u.username, u.email
            FROM user_sessions s
            JOIN users u ON s.user_id = u.id
        """
        if active_only:
            query += " WHERE s.revoked_at IS NULL AND s.expires_at > CURRENT_TIMESTAMP"
        query += " ORDER BY s.created_at DESC LIMIT 1000"

        results = await conn.fetch(query)
        session_list = [dict(row) for row in results]

    return success_response(
        data={"sessions": session_list, "count": len(session_list)},
        message=f"Found {len(session_list)} sessions",
    )


@router.post(
    "/admin/cleanup",
    tags=["admin", "sessions"],
)
async def cleanup_old_sessions(
    days_old: int = 30,
    conn=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Clean up old expired and revoked sessions (admin only).

    Query Parameters:
    - days_old: Delete sessions older than this many days (default: 30)

    Requires: system.admin permission
    """
    # Check admin permission
    from app.services import permissions

    checker = permissions.PermissionChecker(conn)
    has_perm = await checker.has_permission(current_user["id"], "system", "admin")

    if not has_perm:
        return error_response(
            message="Insufficient permissions",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    deleted_count = await sessions.cleanup_expired_sessions(conn, days_old)

    # Create audit log
    await audit.create_audit_log(
        conn=conn,
        action_type="session_cleanup",
        user_id=current_user["id"],
        severity=audit.AuditSeverity.INFO,
        details={
            "deleted_count": deleted_count,
            "days_old_threshold": days_old,
        },
    )

    return success_response(
        data={"deleted_count": deleted_count},
        message=f"Cleaned up {deleted_count} old sessions",
    )
