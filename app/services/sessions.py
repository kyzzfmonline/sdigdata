"""Session management service for tracking and managing user sessions."""

import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

import asyncpg


# ============================================================================
# SESSION MANAGEMENT FUNCTIONS
# ============================================================================


def hash_token(token: str) -> str:
    """Hash a JWT token for storage.

    Args:
        token: JWT token string

    Returns:
        SHA-256 hash of the token
    """
    return hashlib.sha256(token.encode()).hexdigest()


async def create_session(
    conn: asyncpg.Connection,
    user_id: UUID,
    token: str,
    device_info: dict[str, Any] | None = None,
    ip_address: str | None = None,
    location: str | None = None,
    user_agent: str | None = None,
    expires_at: datetime | None = None,
) -> dict[str, Any]:
    """Create a new user session.

    Args:
        conn: Database connection
        user_id: User ID
        token: JWT token (will be hashed for storage)
        device_info: Device information as dict
        ip_address: IP address
        location: Geographic location
        user_agent: User agent string
        expires_at: Session expiration timestamp

    Returns:
        Created session record
    """
    token_hash = hash_token(token)

    # Default expiration to 12 hours if not provided
    if not expires_at:
        expires_at = datetime.utcnow() + timedelta(hours=12)

    result = await conn.fetchrow(
        """
        INSERT INTO user_sessions (
            user_id, token_hash, device_info, ip_address,
            location, user_agent, expires_at
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        RETURNING id, user_id, token_hash, device_info, ip_address,
                  location, user_agent, last_active_at, expires_at,
                  created_at, revoked_at
        """,
        str(user_id),
        token_hash,
        device_info,
        ip_address,
        location,
        user_agent,
        expires_at,
    )

    return dict(result) if result else {}


async def get_session_by_token(
    conn: asyncpg.Connection, token: str
) -> dict[str, Any] | None:
    """Get session by JWT token.

    Args:
        conn: Database connection
        token: JWT token

    Returns:
        Session record or None if not found
    """
    token_hash = hash_token(token)

    result = await conn.fetchrow(
        """
        SELECT
            s.id, s.user_id, s.token_hash, s.device_info,
            s.ip_address, s.location, s.user_agent,
            s.last_active_at, s.expires_at, s.created_at, s.revoked_at,
            u.username, u.email
        FROM user_sessions s
        JOIN users u ON s.user_id = u.id
        WHERE s.token_hash = $1
        AND s.revoked_at IS NULL
        AND s.expires_at > CURRENT_TIMESTAMP
        """,
        token_hash,
    )

    return dict(result) if result else None


async def update_session_activity(
    conn: asyncpg.Connection, session_id: UUID
) -> bool:
    """Update last_active_at timestamp for a session.

    Args:
        conn: Database connection
        session_id: Session ID

    Returns:
        True if updated, False otherwise
    """
    result = await conn.execute(
        """
        UPDATE user_sessions
        SET last_active_at = CURRENT_TIMESTAMP
        WHERE id = $1 AND revoked_at IS NULL
        """,
        str(session_id),
    )

    return int(result.split()[-1]) > 0 if result else False


async def list_user_sessions(
    conn: asyncpg.Connection,
    user_id: UUID,
    include_revoked: bool = False,
) -> list[dict[str, Any]]:
    """List all sessions for a user.

    Args:
        conn: Database connection
        user_id: User ID
        include_revoked: Include revoked sessions

    Returns:
        List of session records
    """
    query = """
        SELECT
            id, user_id, device_info, ip_address, location,
            user_agent, last_active_at, expires_at, created_at, revoked_at,
            CASE
                WHEN revoked_at IS NOT NULL THEN false
                WHEN expires_at < CURRENT_TIMESTAMP THEN false
                ELSE true
            END as is_active
        FROM user_sessions
        WHERE user_id = $1
    """

    if not include_revoked:
        query += " AND revoked_at IS NULL"

    query += " ORDER BY created_at DESC"

    results = await conn.fetch(query, str(user_id))
    return [dict(row) for row in results]


async def get_session_by_id(
    conn: asyncpg.Connection, session_id: UUID
) -> dict[str, Any] | None:
    """Get session by ID.

    Args:
        conn: Database connection
        session_id: Session ID

    Returns:
        Session record or None if not found
    """
    result = await conn.fetchrow(
        """
        SELECT
            s.id, s.user_id, s.device_info, s.ip_address,
            s.location, s.user_agent, s.last_active_at,
            s.expires_at, s.created_at, s.revoked_at,
            u.username, u.email
        FROM user_sessions s
        JOIN users u ON s.user_id = u.id
        WHERE s.id = $1
        """,
        str(session_id),
    )

    return dict(result) if result else None


async def revoke_session(
    conn: asyncpg.Connection, session_id: UUID
) -> bool:
    """Revoke a session.

    Args:
        conn: Database connection
        session_id: Session ID

    Returns:
        True if revoked, False if not found
    """
    result = await conn.execute(
        """
        UPDATE user_sessions
        SET revoked_at = CURRENT_TIMESTAMP
        WHERE id = $1 AND revoked_at IS NULL
        """,
        str(session_id),
    )

    return int(result.split()[-1]) > 0 if result else False


async def revoke_all_user_sessions(
    conn: asyncpg.Connection,
    user_id: UUID,
    except_session_id: UUID | None = None,
) -> int:
    """Revoke all sessions for a user.

    Args:
        conn: Database connection
        user_id: User ID
        except_session_id: Optional session ID to keep active (current session)

    Returns:
        Number of sessions revoked
    """
    if except_session_id:
        result = await conn.execute(
            """
            UPDATE user_sessions
            SET revoked_at = CURRENT_TIMESTAMP
            WHERE user_id = $1
            AND id != $2
            AND revoked_at IS NULL
            """,
            str(user_id),
            str(except_session_id),
        )
    else:
        result = await conn.execute(
            """
            UPDATE user_sessions
            SET revoked_at = CURRENT_TIMESTAMP
            WHERE user_id = $1 AND revoked_at IS NULL
            """,
            str(user_id),
        )

    return int(result.split()[-1]) if result else 0


async def cleanup_expired_sessions(
    conn: asyncpg.Connection, days_old: int = 30
) -> int:
    """Delete old expired and revoked sessions.

    Args:
        conn: Database connection
        days_old: Delete sessions older than this many days

    Returns:
        Number of sessions deleted
    """
    result = await conn.execute(
        """
        DELETE FROM user_sessions
        WHERE (
            revoked_at < CURRENT_TIMESTAMP - INTERVAL '1 day' * $1
            OR expires_at < CURRENT_TIMESTAMP - INTERVAL '1 day' * $1
        )
        """,
        days_old,
    )

    return int(result.split()[-1]) if result else 0


async def get_active_session_count(
    conn: asyncpg.Connection, user_id: UUID
) -> int:
    """Get count of active sessions for a user.

    Args:
        conn: Database connection
        user_id: User ID

    Returns:
        Count of active sessions
    """
    count = await conn.fetchval(
        """
        SELECT COUNT(*)
        FROM user_sessions
        WHERE user_id = $1
        AND revoked_at IS NULL
        AND expires_at > CURRENT_TIMESTAMP
        """,
        str(user_id),
    )

    return count or 0


async def validate_session(
    conn: asyncpg.Connection, token: str
) -> tuple[bool, dict[str, Any] | None]:
    """Validate a session token.

    Args:
        conn: Database connection
        token: JWT token

    Returns:
        Tuple of (is_valid, session_data)
    """
    session = await get_session_by_token(conn, token)

    if not session:
        return False, None

    # Check if expired
    if session["expires_at"] < datetime.utcnow():
        return False, None

    # Check if revoked
    if session["revoked_at"] is not None:
        return False, None

    # Update last active time
    await update_session_activity(conn, session["id"])

    return True, session


async def get_session_statistics(
    conn: asyncpg.Connection, user_id: UUID | None = None
) -> dict[str, Any]:
    """Get session statistics.

    Args:
        conn: Database connection
        user_id: Optional user ID to filter by

    Returns:
        Dictionary with session statistics
    """
    where_clause = f"WHERE user_id = '{user_id}'" if user_id else ""

    stats = await conn.fetchrow(
        f"""
        SELECT
            COUNT(*) as total_sessions,
            COUNT(CASE WHEN revoked_at IS NULL AND expires_at > CURRENT_TIMESTAMP THEN 1 END) as active_sessions,
            COUNT(CASE WHEN revoked_at IS NOT NULL THEN 1 END) as revoked_sessions,
            COUNT(CASE WHEN expires_at < CURRENT_TIMESTAMP THEN 1 END) as expired_sessions,
            COUNT(DISTINCT user_id) as unique_users,
            MAX(created_at) as last_session_created,
            AVG(EXTRACT(EPOCH FROM (COALESCE(revoked_at, expires_at) - created_at))) as avg_session_duration_seconds
        FROM user_sessions
        {where_clause}
        """
    )

    return dict(stats) if stats else {}


async def get_sessions_by_ip(
    conn: asyncpg.Connection, ip_address: str
) -> list[dict[str, Any]]:
    """Get all sessions from a specific IP address.

    Args:
        conn: Database connection
        ip_address: IP address

    Returns:
        List of session records
    """
    results = await conn.fetch(
        """
        SELECT
            s.id, s.user_id, s.device_info, s.ip_address,
            s.location, s.user_agent, s.last_active_at,
            s.expires_at, s.created_at, s.revoked_at,
            u.username, u.email
        FROM user_sessions s
        JOIN users u ON s.user_id = u.id
        WHERE s.ip_address = $1
        ORDER BY s.created_at DESC
        """,
        ip_address,
    )

    return [dict(row) for row in results]


async def detect_suspicious_sessions(
    conn: asyncpg.Connection, user_id: UUID
) -> list[dict[str, Any]]:
    """Detect potentially suspicious sessions for a user.

    Criteria:
    - Multiple active sessions from different locations
    - Session from unusual IP address
    - Multiple concurrent sessions

    Args:
        conn: Database connection
        user_id: User ID

    Returns:
        List of suspicious session records with reasons
    """
    # Get active sessions with location diversity
    results = await conn.fetch(
        """
        WITH session_locations AS (
            SELECT
                id, user_id, ip_address, location,
                COUNT(*) OVER (PARTITION BY user_id) as total_active,
                COUNT(DISTINCT location) OVER (PARTITION BY user_id) as distinct_locations,
                ROW_NUMBER() OVER (PARTITION BY user_id, ip_address ORDER BY created_at DESC) as ip_occurrence
            FROM user_sessions
            WHERE user_id = $1
            AND revoked_at IS NULL
            AND expires_at > CURRENT_TIMESTAMP
        )
        SELECT
            s.id, s.user_id, s.device_info, s.ip_address,
            s.location, s.user_agent, s.last_active_at,
            s.expires_at, s.created_at,
            CASE
                WHEN sl.distinct_locations > 2 THEN 'Multiple locations active'
                WHEN sl.total_active > 5 THEN 'Too many concurrent sessions'
                WHEN sl.ip_occurrence = 1 THEN 'New IP address'
                ELSE 'Unknown'
            END as suspicion_reason
        FROM user_sessions s
        JOIN session_locations sl ON s.id = sl.id
        WHERE (sl.distinct_locations > 2 OR sl.total_active > 5 OR sl.ip_occurrence = 1)
        """,
        str(user_id),
    )

    return [dict(row) for row in results]
