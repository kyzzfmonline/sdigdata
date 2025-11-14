"""Audit logging service for tracking security-relevant actions."""

from typing import Any
from uuid import UUID
import asyncpg


# ============================================================================
# AUDIT LOG TYPES
# ============================================================================

# Action types for audit logs
class AuditAction:
    """Standard audit action types."""

    # Authentication
    LOGIN = "login"
    LOGOUT = "logout"
    LOGIN_FAILED = "login_failed"
    PASSWORD_RESET = "password_reset"
    PASSWORD_CHANGED = "password_changed"

    # Role and Permission Management
    ROLE_ASSIGNED = "role_assigned"
    ROLE_REVOKED = "role_revoked"
    PERMISSION_GRANTED = "permission_granted"
    PERMISSION_REVOKED = "permission_revoked"
    ROLE_CREATED = "role_created"
    ROLE_UPDATED = "role_updated"
    ROLE_DELETED = "role_deleted"

    # User Management
    USER_CREATED = "user_created"
    USER_UPDATED = "user_updated"
    USER_DELETED = "user_deleted"
    USER_DISABLED = "user_disabled"
    USER_ENABLED = "user_enabled"

    # Data Access
    DATA_ACCESSED = "data_accessed"
    DATA_EXPORTED = "data_exported"
    FORM_CREATED = "form_created"
    FORM_UPDATED = "form_updated"
    FORM_DELETED = "form_deleted"
    RESPONSE_CREATED = "response_created"
    RESPONSE_UPDATED = "response_updated"
    RESPONSE_DELETED = "response_deleted"

    # Security Events
    SESSION_REVOKED = "session_revoked"
    API_KEY_CREATED = "api_key_created"
    API_KEY_REVOKED = "api_key_revoked"
    TWO_FA_ENABLED = "2fa_enabled"
    TWO_FA_DISABLED = "2fa_disabled"
    SECURITY_SETTINGS_CHANGED = "security_settings_changed"

    # System Events
    SYSTEM_CONFIG_CHANGED = "system_config_changed"
    IP_WHITELIST_UPDATED = "ip_whitelist_updated"


class AuditSeverity:
    """Severity levels for audit logs."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


# ============================================================================
# AUDIT LOG FUNCTIONS
# ============================================================================


async def create_audit_log(
    conn: asyncpg.Connection,
    action_type: str,
    user_id: UUID | None = None,
    resource_type: str | None = None,
    resource_id: UUID | None = None,
    severity: str = AuditSeverity.INFO,
    ip_address: str | None = None,
    user_agent: str | None = None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create an audit log entry.

    Args:
        conn: Database connection
        action_type: Type of action (use AuditAction constants)
        user_id: ID of user performing action (None for system actions)
        resource_type: Type of resource affected (users, roles, forms, etc.)
        resource_id: ID of specific resource affected
        severity: Log severity (info, warning, critical)
        ip_address: IP address of user
        user_agent: User agent string
        details: Additional details as JSON

    Returns:
        Created audit log entry
    """
    result = await conn.fetchrow(
        """
        INSERT INTO audit_logs (
            user_id, action_type, resource_type, resource_id,
            severity, ip_address, user_agent, details
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        RETURNING id, user_id, action_type, resource_type, resource_id,
                  severity, ip_address, user_agent, details, timestamp
        """,
        str(user_id) if user_id else None,
        action_type,
        resource_type,
        str(resource_id) if resource_id else None,
        severity,
        ip_address,
        user_agent,
        details,
    )

    return dict(result) if result else {}


async def list_audit_logs(
    conn: asyncpg.Connection,
    user_id: UUID | None = None,
    action_type: str | None = None,
    resource_type: str | None = None,
    resource_id: UUID | None = None,
    severity: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    page: int = 1,
    limit: int = 50,
) -> tuple[list[dict[str, Any]], int]:
    """List audit logs with filters and pagination.

    Args:
        conn: Database connection
        user_id: Filter by user ID
        action_type: Filter by action type
        resource_type: Filter by resource type
        resource_id: Filter by specific resource ID
        severity: Filter by severity level
        start_date: Filter logs after this timestamp
        end_date: Filter logs before this timestamp
        page: Page number (1-indexed)
        limit: Number of results per page

    Returns:
        Tuple of (logs list, total count)
    """
    # Build WHERE clause dynamically
    conditions = []
    params: list[Any] = []
    param_num = 1

    if user_id:
        conditions.append(f"user_id = ${param_num}")
        params.append(str(user_id))
        param_num += 1

    if action_type:
        conditions.append(f"action_type = ${param_num}")
        params.append(action_type)
        param_num += 1

    if resource_type:
        conditions.append(f"resource_type = ${param_num}")
        params.append(resource_type)
        param_num += 1

    if resource_id:
        conditions.append(f"resource_id = ${param_num}")
        params.append(str(resource_id))
        param_num += 1

    if severity:
        conditions.append(f"severity = ${param_num}")
        params.append(severity)
        param_num += 1

    if start_date:
        conditions.append(f"timestamp >= ${param_num}")
        params.append(start_date)
        param_num += 1

    if end_date:
        conditions.append(f"timestamp <= ${param_num}")
        params.append(end_date)
        param_num += 1

    where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

    # Get total count
    count_query = f"SELECT COUNT(*) FROM audit_logs {where_clause}"
    total_count = await conn.fetchval(count_query, *params)

    # Get paginated logs
    offset = (page - 1) * limit
    logs_query = f"""
        SELECT
            al.id, al.user_id, al.action_type, al.resource_type, al.resource_id,
            al.severity, al.ip_address, al.user_agent, al.details, al.timestamp,
            u.username, u.email
        FROM audit_logs al
        LEFT JOIN users u ON al.user_id = u.id
        {where_clause}
        ORDER BY al.timestamp DESC
        LIMIT ${param_num} OFFSET ${param_num + 1}
    """
    params.extend([limit, offset])

    results = await conn.fetch(logs_query, *params)
    logs = [dict(row) for row in results]

    return logs, total_count or 0


async def get_audit_log_by_id(
    conn: asyncpg.Connection, log_id: UUID
) -> dict[str, Any] | None:
    """Get a specific audit log entry by ID.

    Args:
        conn: Database connection
        log_id: Audit log ID

    Returns:
        Audit log entry or None if not found
    """
    result = await conn.fetchrow(
        """
        SELECT
            al.id, al.user_id, al.action_type, al.resource_type, al.resource_id,
            al.severity, al.ip_address, al.user_agent, al.details, al.timestamp,
            u.username, u.email
        FROM audit_logs al
        LEFT JOIN users u ON al.user_id = u.id
        WHERE al.id = $1
        """,
        str(log_id),
    )

    return dict(result) if result else None


async def get_user_activity_summary(
    conn: asyncpg.Connection, user_id: UUID, days: int = 30
) -> dict[str, Any]:
    """Get activity summary for a user over the past N days.

    Args:
        conn: Database connection
        user_id: User ID
        days: Number of days to look back

    Returns:
        Activity summary with action counts
    """
    summary = await conn.fetchrow(
        """
        SELECT
            COUNT(*) as total_actions,
            COUNT(DISTINCT DATE(timestamp)) as active_days,
            COUNT(CASE WHEN severity = 'critical' THEN 1 END) as critical_events,
            COUNT(CASE WHEN severity = 'warning' THEN 1 END) as warning_events,
            MAX(timestamp) as last_activity
        FROM audit_logs
        WHERE user_id = $1
        AND timestamp >= CURRENT_TIMESTAMP - INTERVAL '1 day' * $2
        """,
        str(user_id),
        days,
    )

    # Get action type breakdown
    action_breakdown = await conn.fetch(
        """
        SELECT action_type, COUNT(*) as count
        FROM audit_logs
        WHERE user_id = $1
        AND timestamp >= CURRENT_TIMESTAMP - INTERVAL '1 day' * $2
        GROUP BY action_type
        ORDER BY count DESC
        LIMIT 10
        """,
        str(user_id),
        days,
    )

    return {
        "summary": dict(summary) if summary else {},
        "top_actions": [dict(row) for row in action_breakdown],
    }


async def cleanup_old_audit_logs(
    conn: asyncpg.Connection, retention_days: int = 365
) -> int:
    """Delete audit logs older than retention period.

    Args:
        conn: Database connection
        retention_days: Number of days to retain logs

    Returns:
        Number of logs deleted
    """
    result = await conn.execute(
        """
        DELETE FROM audit_logs
        WHERE timestamp < CURRENT_TIMESTAMP - INTERVAL '1 day' * $1
        """,
        retention_days,
    )

    return int(result.split()[-1]) if result else 0


async def export_audit_logs(
    conn: asyncpg.Connection,
    start_date: str | None = None,
    end_date: str | None = None,
    user_id: UUID | None = None,
    action_type: str | None = None,
) -> list[dict[str, Any]]:
    """Export audit logs for compliance reporting.

    Args:
        conn: Database connection
        start_date: Start date for export
        end_date: End date for export
        user_id: Filter by user
        action_type: Filter by action type

    Returns:
        List of all matching audit logs (no pagination)
    """
    conditions = []
    params: list[Any] = []
    param_num = 1

    if start_date:
        conditions.append(f"timestamp >= ${param_num}")
        params.append(start_date)
        param_num += 1

    if end_date:
        conditions.append(f"timestamp <= ${param_num}")
        params.append(end_date)
        param_num += 1

    if user_id:
        conditions.append(f"user_id = ${param_num}")
        params.append(str(user_id))
        param_num += 1

    if action_type:
        conditions.append(f"action_type = ${param_num}")
        params.append(action_type)
        param_num += 1

    where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

    query = f"""
        SELECT
            al.id, al.user_id, u.username, u.email,
            al.action_type, al.resource_type, al.resource_id,
            al.severity, al.ip_address, al.user_agent,
            al.details, al.timestamp
        FROM audit_logs al
        LEFT JOIN users u ON al.user_id = u.id
        {where_clause}
        ORDER BY al.timestamp DESC
    """

    results = await conn.fetch(query, *params)
    return [dict(row) for row in results]
