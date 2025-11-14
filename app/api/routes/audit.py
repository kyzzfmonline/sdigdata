"""API routes for audit log management."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.responses import error_response, success_response
from app.services import audit, permissions

router = APIRouter(prefix="/audit-logs", tags=["audit-logs"])


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================


class AuditLogResponse(BaseModel):
    """Response model for audit log entry."""

    id: UUID
    user_id: UUID | None
    username: str | None
    email: str | None
    action_type: str
    resource_type: str | None
    resource_id: UUID | None
    severity: str
    ip_address: str | None
    user_agent: str | None
    details: dict | None
    timestamp: datetime


class AuditLogsListResponse(BaseModel):
    """Response model for list of audit logs."""

    logs: list[dict]
    pagination: dict


# ============================================================================
# ENDPOINTS
# ============================================================================


@router.get("")
async def list_audit_logs(
    user_id: UUID | None = Query(None, description="Filter by user ID"),
    action_type: str | None = Query(None, description="Filter by action type"),
    resource_type: str | None = Query(None, description="Filter by resource type"),
    resource_id: UUID | None = Query(None, description="Filter by resource ID"),
    severity: Literal["info", "warning", "critical"] | None = Query(
        None, description="Filter by severity"
    ),
    start_date: datetime | None = Query(None, description="Filter from date"),
    end_date: datetime | None = Query(None, description="Filter to date"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(50, ge=1, le=200, description="Results per page"),
    conn=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """List audit logs with filtering and pagination.

    Requires: system.audit permission

    Query Parameters:
    - user_id: Filter by user
    - action_type: Filter by action (login, logout, role_assigned, etc.)
    - resource_type: Filter by resource (users, roles, forms, etc.)
    - resource_id: Filter by specific resource
    - severity: Filter by severity (info, warning, critical)
    - start_date: Start date (ISO 8601)
    - end_date: End date (ISO 8601)
    - page: Page number (default: 1)
    - limit: Results per page (default: 50, max: 200)
    """
    # Check permission
    checker = permissions.PermissionChecker(conn)
    has_perm = await checker.has_permission(current_user["id"], "system", "audit")

    if not has_perm:
        return error_response(
            message="Insufficient permissions to view audit logs",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    # Fetch audit logs
    logs, total = await audit.list_audit_logs(
        conn,
        user_id=user_id,
        action_type=action_type,
        resource_type=resource_type,
        resource_id=resource_id,
        severity=severity,
        start_date=start_date.isoformat() if start_date else None,
        end_date=end_date.isoformat() if end_date else None,
        page=page,
        limit=limit,
    )

    total_pages = (total + limit - 1) // limit if total > 0 else 0

    return success_response(
        data={
            "logs": logs,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "total_pages": total_pages,
            },
        },
        message=f"Found {len(logs)} audit logs",
    )


@router.get("/{log_id}")
async def get_audit_log(
    log_id: UUID,
    conn=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get a specific audit log entry by ID.

    Requires: system.audit permission
    """
    # Check permission
    checker = permissions.PermissionChecker(conn)
    has_perm = await checker.has_permission(current_user["id"], "system", "audit")

    if not has_perm:
        return error_response(
            message="Insufficient permissions to view audit logs",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    log = await audit.get_audit_log_by_id(conn, log_id)

    if not log:
        return error_response(
            message=f"Audit log {log_id} not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    return success_response(data=log, message="Audit log retrieved successfully")


@router.get("/users/{user_id}/summary")
async def get_user_activity_summary(
    user_id: UUID,
    days: int = Query(30, ge=1, le=365, description="Number of days to look back"),
    conn=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get activity summary for a user.

    Requires: system.audit permission OR viewing own activity

    Query Parameters:
    - days: Number of days to analyze (default: 30, max: 365)
    """
    # Check permission (can view own activity or need system.audit)
    checker = permissions.PermissionChecker(conn)
    is_self = str(user_id) == str(current_user["id"])
    has_audit_perm = await checker.has_permission(
        current_user["id"], "system", "audit"
    )

    if not is_self and not has_audit_perm:
        return error_response(
            message="Insufficient permissions to view user activity",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    summary = await audit.get_user_activity_summary(conn, user_id, days=days)

    return success_response(
        data=summary,
        message=f"Activity summary for past {days} days",
    )


@router.get("/export")
async def export_audit_logs(
    start_date: datetime | None = Query(None, description="Start date"),
    end_date: datetime | None = Query(None, description="End date"),
    user_id: UUID | None = Query(None, description="Filter by user"),
    action_type: str | None = Query(None, description="Filter by action type"),
    format: Literal["json", "csv"] = Query("json", description="Export format"),
    conn=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Export audit logs for compliance reporting.

    Requires: system.audit permission

    Query Parameters:
    - start_date: Start date (ISO 8601)
    - end_date: End date (ISO 8601)
    - user_id: Filter by user
    - action_type: Filter by action type
    - format: Export format (json, csv)

    Note: This endpoint returns all matching logs without pagination.
    Use with caution for large date ranges.
    """
    # Check permission
    checker = permissions.PermissionChecker(conn)
    has_perm = await checker.has_permission(current_user["id"], "system", "audit")

    if not has_perm:
        return error_response(
            message="Insufficient permissions to export audit logs",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    logs = await audit.export_audit_logs(
        conn,
        start_date=start_date.isoformat() if start_date else None,
        end_date=end_date.isoformat() if end_date else None,
        user_id=user_id,
        action_type=action_type,
    )

    if format == "csv":
        # Convert to CSV format
        import csv
        import io

        output = io.StringIO()
        if logs:
            fieldnames = logs[0].keys()
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(logs)

        from fastapi.responses import StreamingResponse

        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=audit_logs_{datetime.now().strftime('%Y%m%d')}.csv"
            },
        )

    return success_response(
        data={"logs": logs, "count": len(logs)},
        message=f"Exported {len(logs)} audit logs",
    )


@router.get("/stats/overview")
async def get_audit_stats(
    days: int = Query(7, ge=1, le=90, description="Number of days to analyze"),
    conn=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get audit log statistics and overview.

    Requires: system.audit permission

    Query Parameters:
    - days: Number of days to analyze (default: 7, max: 90)
    """
    # Check permission
    checker = permissions.PermissionChecker(conn)
    has_perm = await checker.has_permission(current_user["id"], "system", "audit")

    if not has_perm:
        return error_response(
            message="Insufficient permissions to view audit statistics",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    # Get statistics
    stats = await conn.fetchrow(
        """
        SELECT
            COUNT(*) as total_events,
            COUNT(DISTINCT user_id) as unique_users,
            COUNT(CASE WHEN severity = 'critical' THEN 1 END) as critical_events,
            COUNT(CASE WHEN severity = 'warning' THEN 1 END) as warning_events,
            COUNT(CASE WHEN severity = 'info' THEN 1 END) as info_events,
            COUNT(CASE WHEN action_type LIKE '%login%' THEN 1 END) as auth_events,
            COUNT(CASE WHEN action_type LIKE '%role%' OR action_type LIKE '%permission%' THEN 1 END) as rbac_events
        FROM audit_logs
        WHERE timestamp >= CURRENT_TIMESTAMP - INTERVAL '1 day' * $1
        """,
        days,
    )

    # Get top action types
    top_actions = await conn.fetch(
        """
        SELECT action_type, COUNT(*) as count
        FROM audit_logs
        WHERE timestamp >= CURRENT_TIMESTAMP - INTERVAL '1 day' * $1
        GROUP BY action_type
        ORDER BY count DESC
        LIMIT 10
        """,
        days,
    )

    # Get top users by activity
    top_users = await conn.fetch(
        """
        SELECT
            u.id, u.username, u.email,
            COUNT(*) as event_count
        FROM audit_logs al
        JOIN users u ON al.user_id = u.id
        WHERE al.timestamp >= CURRENT_TIMESTAMP - INTERVAL '1 day' * $1
        GROUP BY u.id, u.username, u.email
        ORDER BY event_count DESC
        LIMIT 10
        """,
        days,
    )

    return success_response(
        data={
            "period_days": days,
            "overview": dict(stats) if stats else {},
            "top_actions": [dict(row) for row in top_actions],
            "top_users": [dict(row) for row in top_users],
        },
        message=f"Audit statistics for past {days} days",
    )
