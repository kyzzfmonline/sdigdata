"""API key management service for programmatic access."""

import secrets
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

import asyncpg
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

# Initialize Argon2 hasher
ph = PasswordHasher()


# ============================================================================
# API KEY GENERATION AND MANAGEMENT
# ============================================================================


def generate_api_key() -> tuple[str, str, str]:
    """Generate a new API key.

    Returns:
        Tuple of (full_key, key_hash, key_prefix)
        - full_key: The complete API key to show user (ONLY show once!)
        - key_hash: Argon2 hash for storage
        - key_prefix: First 10 characters for identification
    """
    # Generate a secure random key (32 bytes = 64 hex characters)
    key_bytes = secrets.token_bytes(32)
    full_key = f"sk_live_{key_bytes.hex()}"

    # Hash the key for storage using Argon2
    key_hash = ph.hash(full_key)

    # Get prefix for identification
    key_prefix = full_key[:15] + "..."

    return full_key, key_hash, key_prefix


def verify_api_key(key: str, key_hash: str) -> bool:
    """Verify an API key against its hash.

    Args:
        key: The API key to verify
        key_hash: The stored Argon2 hash

    Returns:
        True if key matches, False otherwise
    """
    try:
        ph.verify(key_hash, key)
        return True
    except (VerifyMismatchError, Exception):
        return False


async def create_api_key(
    conn: asyncpg.Connection,
    user_id: UUID,
    name: str,
    scopes: list[str] | None = None,
    expires_in_days: int | None = None,
) -> dict[str, Any]:
    """Create a new API key for a user.

    Args:
        conn: Database connection
        user_id: User ID
        name: Friendly name for the key
        scopes: List of permission scopes (e.g., ["forms:read", "responses:create"])
        expires_in_days: Optional expiration in days (None = no expiration)

    Returns:
        Created API key record WITH the full key (ONLY returned once!)
    """
    full_key, key_hash, key_prefix = generate_api_key()

    expires_at = None
    if expires_in_days:
        expires_at = datetime.utcnow() + timedelta(days=expires_in_days)

    result = await conn.fetchrow(
        """
        INSERT INTO api_keys (
            user_id, name, key_hash, key_prefix, scopes, expires_at
        )
        VALUES ($1, $2, $3, $4, $5, $6)
        RETURNING id, user_id, name, key_prefix, scopes,
                  last_used_at, expires_at, created_at, revoked_at
        """,
        str(user_id),
        name,
        key_hash,
        key_prefix,
        scopes,
        expires_at,
    )

    key_data = dict(result) if result else {}
    # Include the full key ONLY in the creation response
    key_data["key"] = full_key
    key_data["warning"] = "Store this key securely - it will not be shown again!"

    return key_data


async def list_user_api_keys(
    conn: asyncpg.Connection,
    user_id: UUID,
    include_revoked: bool = False,
) -> list[dict[str, Any]]:
    """List all API keys for a user.

    Args:
        conn: Database connection
        user_id: User ID
        include_revoked: Include revoked keys

    Returns:
        List of API key records (WITHOUT full keys)
    """
    query = """
        SELECT
            id, user_id, name, key_prefix, scopes,
            last_used_at, expires_at, created_at, revoked_at,
            CASE
                WHEN revoked_at IS NOT NULL THEN false
                WHEN expires_at IS NOT NULL AND expires_at < CURRENT_TIMESTAMP THEN false
                ELSE true
            END as is_active
        FROM api_keys
        WHERE user_id = $1
    """

    if not include_revoked:
        query += " AND revoked_at IS NULL"

    query += " ORDER BY created_at DESC"

    results = await conn.fetch(query, str(user_id))
    return [dict(row) for row in results]


async def get_api_key_by_id(
    conn: asyncpg.Connection, key_id: UUID
) -> dict[str, Any] | None:
    """Get API key by ID.

    Args:
        conn: Database connection
        key_id: API key ID

    Returns:
        API key record (WITHOUT full key)
    """
    result = await conn.fetchrow(
        """
        SELECT
            k.id, k.user_id, k.name, k.key_prefix, k.scopes,
            k.last_used_at, k.expires_at, k.created_at, k.revoked_at,
            u.username, u.email
        FROM api_keys k
        JOIN users u ON k.user_id = u.id
        WHERE k.id = $1
        """,
        str(key_id),
    )

    return dict(result) if result else None


async def get_api_key_by_key(
    conn: asyncpg.Connection, key: str
) -> dict[str, Any] | None:
    """Get API key by the actual key string (for authentication).

    Args:
        conn: Database connection
        key: The full API key string

    Returns:
        API key record with user info if valid and active, None otherwise
    """
    # Extract prefix to narrow down search
    if not key.startswith("sk_live_"):
        return None

    key_prefix = key[:15] + "..."

    # Get all keys with this prefix
    candidates = await conn.fetch(
        """
        SELECT
            k.id, k.user_id, k.name, k.key_hash, k.key_prefix, k.scopes,
            k.last_used_at, k.expires_at, k.created_at, k.revoked_at,
            u.username, u.email, u.deleted
        FROM api_keys k
        JOIN users u ON k.user_id = u.id
        WHERE k.key_prefix = $1
        AND k.revoked_at IS NULL
        AND (k.expires_at IS NULL OR k.expires_at > CURRENT_TIMESTAMP)
        """,
        key_prefix,
    )

    # Check each candidate
    for candidate in candidates:
        if verify_api_key(key, candidate["key_hash"]):
            # Update last used timestamp
            await conn.execute(
                """
                UPDATE api_keys
                SET last_used_at = CURRENT_TIMESTAMP
                WHERE id = $1
                """,
                candidate["id"],
            )

            # Return key data without hash
            key_data = dict(candidate)
            del key_data["key_hash"]
            return key_data

    return None


async def revoke_api_key(conn: asyncpg.Connection, key_id: UUID) -> bool:
    """Revoke an API key.

    Args:
        conn: Database connection
        key_id: API key ID

    Returns:
        True if revoked, False if not found
    """
    result = await conn.execute(
        """
        UPDATE api_keys
        SET revoked_at = CURRENT_TIMESTAMP
        WHERE id = $1 AND revoked_at IS NULL
        """,
        str(key_id),
    )

    return int(result.split()[-1]) > 0 if result else False


async def rotate_api_key(
    conn: asyncpg.Connection, key_id: UUID
) -> dict[str, Any] | None:
    """Rotate an API key (revoke old, create new with same settings).

    Args:
        conn: Database connection
        key_id: API key ID to rotate

    Returns:
        New API key record WITH full key, or None if original not found
    """
    # Get existing key
    old_key = await get_api_key_by_id(conn, key_id)
    if not old_key:
        return None

    # Revoke old key
    await revoke_api_key(conn, key_id)

    # Create new key with same settings
    expires_in_days = None
    if old_key["expires_at"]:
        # Calculate remaining days
        remaining = old_key["expires_at"] - datetime.utcnow()
        expires_in_days = max(1, remaining.days)

    new_key = await create_api_key(
        conn,
        user_id=old_key["user_id"],
        name=old_key["name"],
        scopes=old_key["scopes"],
        expires_in_days=expires_in_days,
    )

    return new_key


async def update_api_key(
    conn: asyncpg.Connection,
    key_id: UUID,
    name: str | None = None,
    scopes: list[str] | None = None,
) -> dict[str, Any] | None:
    """Update API key metadata (name, scopes).

    Args:
        conn: Database connection
        key_id: API key ID
        name: New name
        scopes: New scopes

    Returns:
        Updated API key record
    """
    updates: list[str] = []
    params: list[Any] = []

    if name is not None:
        updates.append(f"name = ${len(params) + 1}")
        params.append(name)

    if scopes is not None:
        updates.append(f"scopes = ${len(params) + 1}")
        params.append(scopes)

    if not updates:
        return await get_api_key_by_id(conn, key_id)

    params.append(str(key_id))

    query = f"""
        UPDATE api_keys
        SET {", ".join(updates)}
        WHERE id = ${len(params)}
        RETURNING id, user_id, name, key_prefix, scopes,
                  last_used_at, expires_at, created_at, revoked_at
    """

    result = await conn.fetchrow(query, *params)
    return dict(result) if result else None


async def get_api_key_usage(
    conn: asyncpg.Connection, key_id: UUID, days: int = 30
) -> dict[str, Any]:
    """Get usage statistics for an API key.

    Note: This requires request logging to be implemented.
    Currently returns basic info from the key record.

    Args:
        conn: Database connection
        key_id: API key ID
        days: Number of days to look back

    Returns:
        Usage statistics
    """
    key = await get_api_key_by_id(conn, key_id)
    if not key:
        return {}

    # TODO: When request logging is implemented, query actual usage
    # For now, return basic info
    return {
        "key_id": str(key_id),
        "last_used_at": key["last_used_at"],
        "created_at": key["created_at"],
        "is_active": key["revoked_at"] is None
        and (
            key["expires_at"] is None or key["expires_at"] > datetime.utcnow()
        ),
        "note": "Detailed usage statistics require request logging to be implemented",
    }


async def cleanup_expired_api_keys(
    conn: asyncpg.Connection, days_old: int = 90
) -> int:
    """Delete old expired and revoked API keys.

    Args:
        conn: Database connection
        days_old: Delete keys older than this many days

    Returns:
        Number of keys deleted
    """
    result = await conn.execute(
        """
        DELETE FROM api_keys
        WHERE (
            revoked_at < CURRENT_TIMESTAMP - INTERVAL '1 day' * $1
            OR (expires_at IS NOT NULL AND expires_at < CURRENT_TIMESTAMP - INTERVAL '1 day' * $1)
        )
        """,
        days_old,
    )

    return int(result.split()[-1]) if result else 0


async def validate_api_key_scopes(
    key_scopes: list[str] | None, required_scope: str
) -> bool:
    """Check if an API key has a required scope.

    Args:
        key_scopes: List of scopes the key has
        required_scope: Scope needed (e.g., "forms:read")

    Returns:
        True if key has the scope, False otherwise
    """
    if not key_scopes:
        # No scopes = full access (backward compatibility)
        return True

    # Check for exact match
    if required_scope in key_scopes:
        return True

    # Check for wildcard (e.g., "forms:*" matches "forms:read")
    resource, action = required_scope.split(":", 1)
    wildcard = f"{resource}:*"
    if wildcard in key_scopes:
        return True

    # Check for global wildcard
    if "*:*" in key_scopes or "*" in key_scopes:
        return True

    return False


async def get_api_key_statistics(
    conn: asyncpg.Connection, user_id: UUID | None = None
) -> dict[str, Any]:
    """Get API key statistics.

    Args:
        conn: Database connection
        user_id: Optional user ID to filter by

    Returns:
        Dictionary with API key statistics
    """
    where_clause = f"WHERE user_id = '{user_id}'" if user_id else ""

    stats = await conn.fetchrow(
        f"""
        SELECT
            COUNT(*) as total_keys,
            COUNT(CASE WHEN revoked_at IS NULL AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP) THEN 1 END) as active_keys,
            COUNT(CASE WHEN revoked_at IS NOT NULL THEN 1 END) as revoked_keys,
            COUNT(CASE WHEN expires_at IS NOT NULL AND expires_at < CURRENT_TIMESTAMP THEN 1 END) as expired_keys,
            COUNT(DISTINCT user_id) as unique_users,
            MAX(created_at) as last_key_created,
            MAX(last_used_at) as last_key_used
        FROM api_keys
        {where_clause}
        """
    )

    return dict(stats) if stats else {}
