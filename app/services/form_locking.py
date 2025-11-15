"""Form locking service for conflict resolution."""

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import asyncpg


async def acquire_lock(
    conn: asyncpg.Connection,
    form_id: UUID,
    user_id: UUID,
    timeout_seconds: int = 300,
) -> dict[str, Any]:
    """Acquire an exclusive lock on a form for editing."""
    try:
        # Check if form is already locked
        existing_lock = await conn.fetchrow(
            """
            SELECT locked_by, locked_at, lock_version
            FROM forms
            WHERE id = $1 AND locked_by IS NOT NULL
            """,
            str(form_id),
        )
    except Exception as e:
        return {"lock_acquired": False, "error": f"Database error: {str(e)}"}

    if existing_lock:
        # Check if lock has expired
        locked_at = existing_lock["locked_at"]
        if locked_at:
            lock_expires_at = locked_at + timedelta(seconds=timeout_seconds)
            if datetime.now(timezone.utc) < lock_expires_at:
                # Lock is still active - check if it's the same user
                locked_by_str = str(existing_lock["locked_by"])
                user_id_str = str(user_id)

                if locked_by_str != user_id_str:
                    # Different user has the lock
                    return {
                        "lock_acquired": False,
                        "locked_by": existing_lock["locked_by"],
                        "locked_at": locked_at,
                        "lock_expires_at": lock_expires_at,
                        "error": "Form is currently locked by another user",
                    }
                # Same user - allow lock renewal (continue to acquire/renew section)

    # Acquire or renew lock
    try:
        result = await conn.fetchrow(
            """
            UPDATE forms
            SET locked_by = $1, locked_at = CURRENT_TIMESTAMP
            WHERE id = $2
            RETURNING lock_version, locked_at
            """,
            str(user_id),
            str(form_id),
        )

        if result:
            lock_expires_at = result["locked_at"] + timedelta(seconds=timeout_seconds)
            return {
                "lock_acquired": True,
                "lock_expires_at": lock_expires_at,
                "lock_version": result["lock_version"],
            }

        return {"lock_acquired": False, "error": "Form not found"}
    except Exception as e:
        return {"lock_acquired": False, "error": f"Failed to acquire lock: {str(e)}"}


async def release_lock(
    conn: asyncpg.Connection, form_id: UUID, user_id: UUID
) -> bool:
    """Release a lock on a form."""
    try:
        result = await conn.execute(
            """
            UPDATE forms
            SET locked_by = NULL, locked_at = NULL
            WHERE id = $1 AND locked_by = $2
            """,
            str(form_id),
            str(user_id),
        )
        return int(result.split()[-1]) > 0
    except Exception:
        return False


async def force_release_lock(conn: asyncpg.Connection, form_id: UUID) -> bool:
    """Force release a lock (admin only)."""
    try:
        result = await conn.execute(
            """
            UPDATE forms
            SET locked_by = NULL, locked_at = NULL
            WHERE id = $1
            """,
            str(form_id),
        )
        return int(result.split()[-1]) > 0
    except Exception:
        return False


async def get_lock_status(
    conn: asyncpg.Connection, form_id: UUID, current_user_id: UUID | None = None
) -> dict[str, Any]:
    """Get the lock status of a form.

    Args:
        conn: Database connection
        form_id: UUID of the form
        current_user_id: UUID of the current authenticated user (optional)

    Returns:
        Lock status including can_edit and can_force_unlock fields
    """
    try:
        result = await conn.fetchrow(
            """
            SELECT f.locked_by, f.locked_at, f.lock_version,
                   u.username, u.email
            FROM forms f
            LEFT JOIN users u ON f.locked_by::text = u.id::text
            WHERE f.id = $1
            """,
            str(form_id),
        )

        if not result:
            return {"error": "Form not found"}

        # No lock exists
        if not result["locked_by"]:
            return {
                "is_locked": False,
                "can_edit": True,
                "can_force_unlock": False,
                "reason": None,
            }

        # Lock exists - check if expired
        locked_at = result["locked_at"]
        lock_expires_at = locked_at + timedelta(seconds=300)  # 5 min default
        is_expired = datetime.now(timezone.utc) >= lock_expires_at

        if is_expired:
            return {
                "is_locked": False,
                "can_edit": True,
                "can_force_unlock": False,
                "reason": "Previous lock expired",
            }

        # Lock is active - determine permissions
        locked_by_str = str(result["locked_by"])
        current_user_str = str(current_user_id) if current_user_id else None
        is_owner = current_user_str and (locked_by_str == current_user_str)

        # Check if current user is admin (for force unlock)
        can_force_unlock = False
        if current_user_id:
            from app.services.rbac import get_user_roles

            user_roles = await get_user_roles(conn, current_user_id)
            role_names = [role["name"].lower() for role in user_roles]
            can_force_unlock = any(
                role in ["admin", "super_admin", "super admin", "system_admin"]
                for role in role_names
            )

        # Prepare reason message
        reason = None if is_owner else f"Locked by {result['username']}"

        return {
            "is_locked": True,
            "locked_by": {
                "id": result["locked_by"],
                "username": result["username"],
                "email": result["email"],
            },
            "locked_at": result["locked_at"],
            "lock_expires_at": lock_expires_at,
            "can_edit": is_owner,  # True only if same user owns the lock
            "can_force_unlock": can_force_unlock,  # True if admin
            "reason": reason,
        }
    except Exception as e:
        return {"error": f"Failed to get lock status: {str(e)}"}


async def increment_lock_version(conn: asyncpg.Connection, form_id: UUID) -> int:
    """Increment the lock version for optimistic locking."""
    result = await conn.fetchval(
        """
        UPDATE forms
        SET lock_version = lock_version + 1
        WHERE id = $1
        RETURNING lock_version
        """,
        str(form_id),
    )
    return result or 1


async def check_version_conflict(
    conn: asyncpg.Connection, form_id: UUID, expected_version: int
) -> bool:
    """Check if there's a version conflict."""
    current_version = await conn.fetchval(
        "SELECT lock_version FROM forms WHERE id = $1",
        str(form_id),
    )
    return current_version != expected_version


async def cleanup_expired_locks(
    conn: asyncpg.Connection, timeout_seconds: int = 300
) -> int:
    """Clean up expired locks."""
    cutoff_time = datetime.now(timezone.utc) - timedelta(seconds=timeout_seconds)

    result = await conn.execute(
        """
        UPDATE forms
        SET locked_by = NULL, locked_at = NULL
        WHERE locked_by IS NOT NULL AND locked_at < $1
        """,
        cutoff_time,
    )
    return int(result.split()[-1])
