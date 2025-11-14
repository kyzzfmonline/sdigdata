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
    # Check if form is already locked
    existing_lock = await conn.fetchrow(
        """
        SELECT locked_by, locked_at, lock_version
        FROM forms
        WHERE id = $1 AND locked_by IS NOT NULL
        """,
        str(form_id),
    )

    if existing_lock:
        # Check if lock has expired
        locked_at = existing_lock["locked_at"]
        if locked_at:
            lock_expires_at = locked_at + timedelta(seconds=timeout_seconds)
            if datetime.now(timezone.utc) < lock_expires_at:
                # Lock is still active
                return {
                    "lock_acquired": False,
                    "locked_by": existing_lock["locked_by"],
                    "locked_at": locked_at,
                    "lock_expires_at": lock_expires_at,
                    "error": "Form is currently locked by another user",
                }

    # Acquire or renew lock
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

    return {"lock_acquired": False, "error": "Failed to acquire lock"}


async def release_lock(
    conn: asyncpg.Connection, form_id: UUID, user_id: UUID
) -> bool:
    """Release a lock on a form."""
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


async def force_release_lock(conn: asyncpg.Connection, form_id: UUID) -> bool:
    """Force release a lock (admin only)."""
    result = await conn.execute(
        """
        UPDATE forms
        SET locked_by = NULL, locked_at = NULL
        WHERE id = $1
        """,
        str(form_id),
    )
    return int(result.split()[-1]) > 0


async def get_lock_status(
    conn: asyncpg.Connection, form_id: UUID
) -> dict[str, Any]:
    """Get the lock status of a form."""
    result = await conn.fetchrow(
        """
        SELECT f.locked_by, f.locked_at, f.lock_version,
               u.username, u.email
        FROM forms f
        LEFT JOIN users u ON f.locked_by = u.id
        WHERE f.id = $1
        """,
        str(form_id),
    )

    if not result:
        return {"error": "Form not found"}

    if result["locked_by"]:
        # Default timeout is 5 minutes
        lock_expires_at = result["locked_at"] + timedelta(seconds=300)
        return {
            "is_locked": True,
            "locked_by": {
                "id": result["locked_by"],
                "username": result["username"],
                "email": result["email"],
            },
            "locked_at": result["locked_at"],
            "lock_expires_at": lock_expires_at,
        }

    return {"is_locked": False}


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
