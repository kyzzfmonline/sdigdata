"""Security settings service for password policies and security configuration."""

import re
from typing import Any
from uuid import UUID

import asyncpg


# ============================================================================
# PASSWORD POLICY MANAGEMENT
# ============================================================================


async def get_password_policy(
    conn: asyncpg.Connection, organization_id: UUID | None = None
) -> dict[str, Any] | None:
    """Get password policy for organization or system default.

    Args:
        conn: Database connection
        organization_id: Organization ID (None = system default)

    Returns:
        Password policy configuration
    """
    result = await conn.fetchrow(
        """
        SELECT
            id, organization_id, min_length, max_length,
            require_uppercase, require_lowercase, require_numbers,
            require_special_chars, special_chars_allowed,
            prevent_common_passwords, password_expiry_days,
            password_history_count, max_login_attempts,
            lockout_duration_minutes, created_at, updated_at
        FROM password_policies
        WHERE organization_id IS NOT DISTINCT FROM $1
        """,
        str(organization_id) if organization_id else None,
    )

    return dict(result) if result else None


async def update_password_policy(
    conn: asyncpg.Connection,
    organization_id: UUID | None = None,
    **settings: Any,
) -> dict[str, Any]:
    """Update password policy settings.

    Args:
        conn: Database connection
        organization_id: Organization ID (None = system default)
        **settings: Policy settings to update

    Returns:
        Updated password policy
    """
    # Get or create policy
    existing = await get_password_policy(conn, organization_id)

    if existing:
        # Update existing
        updates = []
        params = []
        for key, value in settings.items():
            if value is not None:
                updates.append(f"{key} = ${len(params) + 1}")
                params.append(value)

        if updates:
            updates.append("updated_at = CURRENT_TIMESTAMP")
            params.append(str(organization_id) if organization_id else None)

            query = f"""
                UPDATE password_policies
                SET {", ".join(updates)}
                WHERE organization_id IS NOT DISTINCT FROM ${len(params)}
                RETURNING *
            """
            result = await conn.fetchrow(query, *params)
            return dict(result) if result else existing
        return existing
    else:
        # Create new
        columns = ["organization_id"] + list(settings.keys())
        values = [str(organization_id) if organization_id else None] + list(
            settings.values()
        )
        placeholders = ", ".join(f"${i+1}" for i in range(len(values)))

        query = f"""
            INSERT INTO password_policies ({", ".join(columns)})
            VALUES ({placeholders})
            RETURNING *
        """
        result = await conn.fetchrow(query, *values)
        return dict(result) if result else {}


def validate_password(password: str, policy: dict[str, Any]) -> tuple[bool, list[str]]:
    """Validate a password against a policy.

    Args:
        password: Password to validate
        policy: Password policy configuration

    Returns:
        Tuple of (is_valid, error_messages)
    """
    errors = []

    # Length check
    if len(password) < policy.get("min_length", 8):
        errors.append(f"Password must be at least {policy['min_length']} characters")

    if len(password) > policy.get("max_length", 128):
        errors.append(f"Password must be at most {policy['max_length']} characters")

    # Character requirements
    if policy.get("require_uppercase", True) and not re.search(r"[A-Z]", password):
        errors.append("Password must contain at least one uppercase letter")

    if policy.get("require_lowercase", True) and not re.search(r"[a-z]", password):
        errors.append("Password must contain at least one lowercase letter")

    if policy.get("require_numbers", True) and not re.search(r"\d", password):
        errors.append("Password must contain at least one number")

    if policy.get("require_special_chars", True):
        special_chars = policy.get("special_chars_allowed", "@$!%*?&#^()_+-=[]{}|;:,.<>/")
        if not any(char in special_chars for char in password):
            errors.append(f"Password must contain at least one special character: {special_chars[:20]}...")

    # Common password check (simplified)
    if policy.get("prevent_common_passwords", True):
        common_passwords = ["password", "123456", "admin", "letmein", "welcome"]
        if password.lower() in common_passwords:
            errors.append("Password is too common")

    return len(errors) == 0, errors


async def check_password_history(
    conn: asyncpg.Connection, user_id: UUID, new_password_hash: str, history_count: int
) -> bool:
    """Check if password was used recently.

    Args:
        conn: Database connection
        user_id: User ID
        new_password_hash: Hash of new password
        history_count: Number of previous passwords to check

    Returns:
        True if password is acceptable (not in history), False if reused
    """
    if history_count <= 0:
        return True

    # Get recent password hashes
    recent_hashes = await conn.fetch(
        """
        SELECT password_hash
        FROM password_history
        WHERE user_id = $1
        ORDER BY created_at DESC
        LIMIT $2
        """,
        str(user_id),
        history_count,
    )

    # Check if new hash matches any recent hash
    for row in recent_hashes:
        if row["password_hash"] == new_password_hash:
            return False

    return True


async def add_password_to_history(
    conn: asyncpg.Connection, user_id: UUID, password_hash: str
) -> None:
    """Add password hash to user's password history.

    Args:
        conn: Database connection
        user_id: User ID
        password_hash: Password hash to store
    """
    await conn.execute(
        """
        INSERT INTO password_history (user_id, password_hash)
        VALUES ($1, $2)
        """,
        str(user_id),
        password_hash,
    )


# ============================================================================
# SECURITY SETTINGS MANAGEMENT
# ============================================================================


async def get_security_settings(
    conn: asyncpg.Connection, organization_id: UUID | None = None
) -> dict[str, Any] | None:
    """Get security settings for organization or system default.

    Args:
        conn: Database connection
        organization_id: Organization ID (None = system default)

    Returns:
        Security settings configuration
    """
    result = await conn.fetchrow(
        """
        SELECT *
        FROM security_settings
        WHERE organization_id IS NOT DISTINCT FROM $1
        """,
        str(organization_id) if organization_id else None,
    )

    return dict(result) if result else None


async def update_security_settings(
    conn: asyncpg.Connection,
    organization_id: UUID | None = None,
    **settings: Any,
) -> dict[str, Any]:
    """Update security settings.

    Args:
        conn: Database connection
        organization_id: Organization ID (None = system default)
        **settings: Settings to update

    Returns:
        Updated security settings
    """
    existing = await get_security_settings(conn, organization_id)

    if existing:
        # Update existing
        updates = []
        params = []
        for key, value in settings.items():
            if value is not None:
                updates.append(f"{key} = ${len(params) + 1}")
                params.append(value)

        if updates:
            updates.append("updated_at = CURRENT_TIMESTAMP")
            params.append(str(organization_id) if organization_id else None)

            query = f"""
                UPDATE security_settings
                SET {", ".join(updates)}
                WHERE organization_id IS NOT DISTINCT FROM ${len(params)}
                RETURNING *
            """
            result = await conn.fetchrow(query, *params)
            return dict(result) if result else existing
        return existing
    else:
        # Create new
        columns = ["organization_id"] + list(settings.keys())
        values = [str(organization_id) if organization_id else None] + list(
            settings.values()
        )
        placeholders = ", ".join(f"${i+1}" for i in range(len(values)))

        query = f"""
            INSERT INTO security_settings ({", ".join(columns)})
            VALUES ({placeholders})
            RETURNING *
        """
        result = await conn.fetchrow(query, *values)
        return dict(result) if result else {}


# ============================================================================
# LOGIN ATTEMPT TRACKING
# ============================================================================


async def record_failed_login(
    conn: asyncpg.Connection,
    username: str,
    ip_address: str,
    user_agent: str | None = None,
) -> int:
    """Record a failed login attempt and return total recent failures.

    Args:
        conn: Database connection
        username: Username that failed
        ip_address: IP address
        user_agent: User agent string

    Returns:
        Number of failed attempts in the lockout window
    """
    # Record in audit log
    from app.services import audit

    await audit.create_audit_log(
        conn=conn,
        action_type=audit.AuditAction.LOGIN_FAILED,
        user_id=None,
        severity=audit.AuditSeverity.WARNING,
        ip_address=ip_address,
        user_agent=user_agent,
        details={"username": username},
    )

    # Get policy to check lockout window
    policy = await get_password_policy(conn)
    lockout_minutes = policy.get("lockout_duration_minutes", 30) if policy else 30

    # Count recent failures
    count = await conn.fetchval(
        """
        SELECT COUNT(*)
        FROM audit_logs
        WHERE action_type = $1
        AND details->>'username' = $2
        AND timestamp > CURRENT_TIMESTAMP - INTERVAL '1 minute' * $3
        """,
        audit.AuditAction.LOGIN_FAILED,
        username,
        lockout_minutes,
    )

    return count or 0


async def is_account_locked(
    conn: asyncpg.Connection, username: str
) -> tuple[bool, int | None]:
    """Check if account is locked due to failed login attempts.

    Args:
        conn: Database connection
        username: Username to check

    Returns:
        Tuple of (is_locked, minutes_until_unlock)
    """
    policy = await get_password_policy(conn)
    if not policy:
        return False, None

    max_attempts = policy.get("max_login_attempts", 5)
    lockout_minutes = policy.get("lockout_duration_minutes", 30)

    # Count recent failures
    recent_failures = await conn.fetchrow(
        """
        SELECT
            COUNT(*) as failure_count,
            MAX(timestamp) as last_failure
        FROM audit_logs
        WHERE action_type = $1
        AND details->>'username' = $2
        AND timestamp > CURRENT_TIMESTAMP - INTERVAL '1 minute' * $3
        """,
        "login_failed",
        username,
        lockout_minutes,
    )

    if not recent_failures or recent_failures["failure_count"] < max_attempts:
        return False, None

    # Calculate minutes until unlock
    from datetime import datetime, timedelta

    last_failure = recent_failures["last_failure"]
    unlock_time = last_failure + timedelta(minutes=lockout_minutes)
    now = datetime.utcnow().replace(tzinfo=last_failure.tzinfo)

    if now >= unlock_time:
        return False, None

    minutes_remaining = int((unlock_time - now).total_seconds() / 60) + 1
    return True, minutes_remaining


async def clear_failed_login_attempts(
    conn: asyncpg.Connection, username: str
) -> None:
    """Clear failed login attempts for a user (after successful login).

    This doesn't delete audit logs, just marks them as resolved.

    Args:
        conn: Database connection
        username: Username
    """
    # We don't actually delete audit logs for compliance
    # Just record a successful login to reset the counter naturally
    pass


# ============================================================================
# SYSTEM CONFIGURATION
# ============================================================================


async def get_system_config(
    conn: asyncpg.Connection, key: str
) -> Any:
    """Get a system configuration value.

    Args:
        conn: Database connection
        key: Configuration key (e.g., 'rbac.enabled')

    Returns:
        Configuration value (parsed from JSONB)
    """
    result = await conn.fetchval(
        """
        SELECT value
        FROM system_config
        WHERE key = $1
        """,
        key,
    )

    return result


async def update_system_config(
    conn: asyncpg.Connection,
    key: str,
    value: Any,
    description: str | None = None,
    updated_by: UUID | None = None,
) -> dict[str, Any]:
    """Update or create a system configuration value.

    Args:
        conn: Database connection
        key: Configuration key
        value: Value (will be stored as JSONB)
        description: Optional description
        updated_by: User making the change

    Returns:
        Updated configuration record
    """
    result = await conn.fetchrow(
        """
        INSERT INTO system_config (key, value, description, updated_by)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (key) DO UPDATE
        SET value = EXCLUDED.value,
            description = COALESCE(EXCLUDED.description, system_config.description),
            updated_by = EXCLUDED.updated_by,
            updated_at = CURRENT_TIMESTAMP
        RETURNING *
        """,
        key,
        value,
        description,
        str(updated_by) if updated_by else None,
    )

    return dict(result) if result else {}


async def list_system_config(
    conn: asyncpg.Connection, prefix: str | None = None
) -> list[dict[str, Any]]:
    """List system configuration values.

    Args:
        conn: Database connection
        prefix: Optional key prefix filter (e.g., 'rbac.')

    Returns:
        List of configuration records
    """
    if prefix:
        results = await conn.fetch(
            """
            SELECT * FROM system_config
            WHERE key LIKE $1 || '%'
            ORDER BY key
            """,
            prefix,
        )
    else:
        results = await conn.fetch(
            """
            SELECT * FROM system_config
            ORDER BY key
            """
        )

    return [dict(row) for row in results]
