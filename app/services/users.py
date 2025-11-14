"""User service functions."""

from datetime import datetime
from typing import Any
from uuid import UUID

import asyncpg


async def create_user(  # type: ignore[no-any-unimported]
    conn: asyncpg.Connection,
    username: str,
    password_hash: str,
    role: str,
    organization_id: UUID,
) -> dict[str, Any] | None:
    """Create a new user."""
    result = await conn.fetchrow(
        """
        INSERT INTO users (username, password_hash, role, organization_id)
        VALUES ($1, $2, $3, $4)
        RETURNING id, username, role, organization_id, created_at
        """,
        username,
        password_hash,
        role,
        str(organization_id),
    )
    return dict(result) if result else None


async def get_user_by_id(  # type: ignore[no-any-unimported]
    conn: asyncpg.Connection, user_id: UUID
) -> dict[str, Any] | None:
    """Get user by ID."""
    result = await conn.fetchrow(
        """
        SELECT id, username, password_hash, role, organization_id, created_at
        FROM users
        WHERE id = $1 AND deleted = FALSE
        """,
        str(user_id),
    )
    return dict(result) if result else None


async def get_user_by_username(  # type: ignore[no-any-unimported]
    conn: asyncpg.Connection, username: str
) -> dict[str, Any] | None:
    """Get user by username."""
    result = await conn.fetchrow(
        """
        SELECT id, username, password_hash, role, organization_id, created_at
        FROM users
        WHERE username = $1 AND deleted = FALSE
        """,
        username,
    )
    return dict(result) if result else None


async def list_users(  # type: ignore[no-any-unimported]
    conn: asyncpg.Connection,
    organization_id: UUID | None = None,
    role: str | None = None,
    status: str | None = None,
    search: str | None = None,
    sort: str = "created_at",
    order: str = "desc",
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    """List users with advanced filtering, sorting, and pagination."""
    # Build the main query
    query = """
        SELECT id, username, email, role, status, organization_id, created_at, last_login
        FROM users
        WHERE deleted = FALSE
    """
    count_query = "SELECT COUNT(*) FROM users WHERE deleted = FALSE"
    params: list[str | int] = []
    param_num = 1

    # Add filters
    if organization_id:
        query += f" AND organization_id = ${param_num}"
        count_query += f" AND organization_id = ${param_num}"
        params.append(str(organization_id))
        param_num += 1

    if role:
        query += f" AND role = ${param_num}"
        count_query += f" AND role = ${param_num}"
        params.append(role)
        param_num += 1

    if status:
        query += f" AND status = ${param_num}"
        count_query += f" AND status = ${param_num}"
        params.append(status)
        param_num += 1

    if search:
        search_term = f"%{search}%"
        query += f" AND (username ILIKE ${param_num} OR email ILIKE ${param_num})"
        count_query += f" AND (username ILIKE ${param_num} OR email ILIKE ${param_num})"
        params.append(search_term)
        param_num += 1

    # Add sorting
    valid_sort_fields = [
        "created_at",
        "username",
        "email",
        "role",
        "status",
        "last_login",
    ]
    if sort not in valid_sort_fields:
        sort = "created_at"

    if order not in ["asc", "desc"]:
        order = "desc"

    query += f" ORDER BY {sort} {order}"

    # Add pagination
    query += f" LIMIT ${param_num} OFFSET ${param_num + 1}"
    params.extend([limit, offset])

    # Execute queries
    rows = await conn.fetch(query, *params)
    total_count = await conn.fetchval(
        count_query, *params[:-2]
    )  # Remove limit/offset params

    return [dict(row) for row in rows], int(total_count or 0)


async def delete_user(conn: asyncpg.Connection, user_id: UUID) -> bool:  # type: ignore[no-any-unimported]
    """Delete a user."""
    result = await conn.execute("DELETE FROM users WHERE id = $1", str(user_id))
    # Extract row count from result string like "DELETE 1"
    return int(result.split()[-1]) > 0


async def update_user_last_login(conn: asyncpg.Connection, user_id: UUID) -> None:  # type: ignore[no-any-unimported]
    """Update user's last login timestamp."""
    await conn.execute(
        """
        UPDATE users
        SET last_login = CURRENT_TIMESTAMP
        WHERE id = $1
        """,
        str(user_id),
    )


async def update_user(  # type: ignore[no-any-unimported]
    conn: asyncpg.Connection,
    user_id: UUID,
    username: str | None = None,
    email: str | None = None,
    role: str | None = None,
    status: str | None = None,
) -> dict[str, Any] | None:
    """Update user information."""
    updates = []
    params = []
    param_num = 1

    if username is not None:
        updates.append(f"username = ${param_num}")
        params.append(username)
        param_num += 1

    if email is not None:
        updates.append(f"email = ${param_num}")
        params.append(email)
        param_num += 1

    if role is not None:
        updates.append(f"role = ${param_num}")
        params.append(role)
        param_num += 1

    if status is not None:
        updates.append(f"status = ${param_num}")
        params.append(status)
        param_num += 1

    if not updates:
        return await get_user_by_id(conn, user_id)

    updates.append("updated_at = CURRENT_TIMESTAMP")
    params.append(str(user_id))

    query = f"""
        UPDATE users
        SET {", ".join(updates)}
        WHERE id = ${param_num}
        RETURNING id, username, email, role, status, organization_id, created_at, updated_at, last_login
    """

    result = await conn.fetchrow(query, *params)
    return dict(result) if result else None


async def update_user_password(  # type: ignore[no-any-unimported]
    conn: asyncpg.Connection,
    user_id: UUID,
    password_hash: str,
) -> bool:
    """Update user password."""
    result = await conn.execute(
        """
        UPDATE users
        SET password_hash = $1, updated_at = CURRENT_TIMESTAMP
        WHERE id = $2
        """,
        password_hash,
        str(user_id),
    )
    # Extract row count from result string like "UPDATE 1"
    return int(result.split()[-1]) > 0


async def get_user_preferences(  # type: ignore[no-any-unimported]
    conn: asyncpg.Connection,
    user_id: UUID,
) -> dict[str, Any] | None:
    """Get user preferences."""
    result = await conn.fetchrow(
        """
        SELECT email_notifications, form_assignments, responses, system_updates, theme, compact_mode
        FROM users
        WHERE id = $1 AND deleted = FALSE
        """,
        str(user_id),
    )
    return dict(result) if result else None


async def update_notification_preferences(  # type: ignore[no-any-unimported]
    conn: asyncpg.Connection,
    user_id: UUID,
    email_notifications: bool | None = None,
    form_assignments: bool | None = None,
    responses: bool | None = None,
    system_updates: bool | None = None,
) -> bool:
    """Update user notification preferences."""
    updates: list[str] = []
    params: list[bool | str] = []
    param_num = 1

    if email_notifications is not None:
        updates.append(f"email_notifications = ${param_num}")
        params.append(email_notifications)
        param_num += 1

    if form_assignments is not None:
        updates.append(f"form_assignments = ${param_num}")
        params.append(form_assignments)
        param_num += 1

    if responses is not None:
        updates.append(f"responses = ${param_num}")
        params.append(responses)
        param_num += 1

    if system_updates is not None:
        updates.append(f"system_updates = ${param_num}")
        params.append(system_updates)
        param_num += 1

    if not updates:
        return True

    updates.append("updated_at = CURRENT_TIMESTAMP")
    params.append(str(user_id))

    query = f"""
        UPDATE users
        SET {", ".join(updates)}
        WHERE id = ${param_num}
    """

    result = await conn.execute(query, *params)
    # Extract row count from result string like "UPDATE 1"
    return int(result.split()[-1]) > 0


async def update_theme_preferences(  # type: ignore[no-any-unimported]
    conn: asyncpg.Connection,
    user_id: UUID,
    theme: str | None = None,
    compact_mode: bool | None = None,
) -> bool:
    """Update user theme preferences."""
    updates: list[str] = []
    params: list[str | bool] = []
    param_num = 1

    if theme is not None:
        updates.append(f"theme = ${param_num}")
        params.append(theme)
        param_num += 1

    if compact_mode is not None:
        updates.append(f"compact_mode = ${param_num}")
        params.append(compact_mode)
        param_num += 1

    if not updates:
        return True

    updates.append("updated_at = CURRENT_TIMESTAMP")
    params.append(str(user_id))

    query = f"""
        UPDATE users
        SET {", ".join(updates)}
        WHERE id = ${param_num}
    """

    result = await conn.execute(query, *params)
    # Extract row count from result string like "UPDATE 1"
    return int(result.split()[-1]) > 0


async def get_user_by_email(  # type: ignore[no-any-unimported]
    conn: asyncpg.Connection, email: str
) -> dict[str, Any] | None:
    """Get user by email address."""
    result = await conn.fetchrow(
        """
        SELECT id, username, email, role, organization_id, created_at
        FROM users
        WHERE email = $1 AND deleted = FALSE
        """,
        email,
    )
    return dict(result) if result else None


async def create_password_reset_token(  # type: ignore[no-any-unimported]
    conn: asyncpg.Connection,
    user_id: UUID,
    email: str,
    token_hash: str,
    expires_at: datetime,
) -> dict[str, Any] | None:
    """Create a password reset token."""
    # First, mark any existing unused tokens for this user as used
    await conn.execute(
        """
        UPDATE password_reset_tokens
        SET used = TRUE, used_at = CURRENT_TIMESTAMP
        WHERE user_id = $1 AND used = FALSE
        """,
        str(user_id),
    )

    # Create new token
    result = await conn.fetchrow(
        """
        INSERT INTO password_reset_tokens (user_id, email, token_hash, expires_at)
        VALUES ($1, $2, $3, $4)
        RETURNING id, user_id, email, token_hash, expires_at, used, created_at
        """,
        str(user_id),
        email,
        token_hash,
        expires_at,
    )
    return dict(result) if result else None


async def get_password_reset_token(  # type: ignore[no-any-unimported]
    conn: asyncpg.Connection,
    token_hash: str,
) -> dict[str, Any] | None:
    """Get password reset token by hash."""
    result = await conn.fetchrow(
        """
        SELECT id, user_id, email, token_hash, expires_at, used, created_at, used_at
        FROM password_reset_tokens
        WHERE token_hash = $1 AND used = FALSE AND expires_at > CURRENT_TIMESTAMP
        """,
        token_hash,
    )
    return dict(result) if result else None


async def mark_token_used(  # type: ignore[no-any-unimported]
    conn: asyncpg.Connection,
    token_id: UUID,
) -> bool:
    """Mark a password reset token as used."""
    result = await conn.execute(
        """
        UPDATE password_reset_tokens
        SET used = TRUE, used_at = CURRENT_TIMESTAMP
        WHERE id = $1 AND used = FALSE
        """,
        str(token_id),
    )
    # Extract row count from result string like "UPDATE 1"
    return int(result.split()[-1]) > 0


async def cleanup_expired_tokens(conn: asyncpg.Connection) -> int:  # type: ignore[no-any-unimported]
    """Clean up expired password reset tokens."""
    result = await conn.execute(
        """
        DELETE FROM password_reset_tokens
        WHERE expires_at < CURRENT_TIMESTAMP OR (used = TRUE AND used_at < CURRENT_TIMESTAMP - INTERVAL '30 days')
        """,
    )
    # Extract row count from result string like "DELETE 5"
    return int(result.split()[-1])
