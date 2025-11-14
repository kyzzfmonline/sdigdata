"""Notification service functions."""

import json
from uuid import UUID

import asyncpg


async def create_notification(
    conn: asyncpg.Connection,
    user_id: UUID,
    notification_type: str,
    title: str,
    message: str,
    data: dict | None = None,
) -> dict | None:
    """Create a new notification."""
    result = await conn.fetchrow(
        """
        INSERT INTO notifications (user_id, type, title, message, data)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING id, user_id, type, title, message, data, read, created_at
        """,
        user_id,
        notification_type,
        title,
        message,
        json.dumps(data) if data else None,
    )
    if result:
        result_dict = dict(result)
        if result_dict.get("data"):
            result_dict["data"] = (
                json.loads(result_dict["data"])
                if isinstance(result_dict["data"], str)
                else result_dict["data"]
            )
        return result_dict
    return None


async def get_user_notifications(
    conn: asyncpg.Connection,
    user_id: UUID,
    unread_only: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    """Get notifications for a user."""
    if unread_only:
        query = """
            SELECT id, user_id, type, title, message, data, read, created_at
            FROM notifications
            WHERE user_id = $1 AND read = FALSE
            ORDER BY created_at DESC LIMIT $2 OFFSET $3
        """
    else:
        query = """
            SELECT id, user_id, type, title, message, data, read, created_at
            FROM notifications
            WHERE user_id = $1
            ORDER BY created_at DESC LIMIT $2 OFFSET $3
        """

    results = await conn.fetch(query, user_id, limit, offset)
    return [dict(row) for row in results]


async def get_unread_count(conn: asyncpg.Connection, user_id: UUID) -> int:
    """Get count of unread notifications for a user."""
    result = await conn.fetchrow(
        """
        SELECT COUNT(*) as count
        FROM notifications
        WHERE user_id = $1 AND read = FALSE
        """,
        user_id,
    )
    return result["count"] if result else 0


async def mark_notification_read(
    conn: asyncpg.Connection,
    notification_id: UUID,
    user_id: UUID,
) -> bool:
    """Mark a notification as read."""
    result = await conn.execute(
        """
        UPDATE notifications
        SET read = TRUE
        WHERE id = $1 AND user_id = $2
        """,
        notification_id,
        user_id,
    )
    return int(result.split()[-1]) > 0


async def mark_all_read(conn: asyncpg.Connection, user_id: UUID) -> int:
    """Mark all notifications as read for a user."""
    result = await conn.execute(
        """
        UPDATE notifications
        SET read = TRUE
        WHERE user_id = $1 AND read = FALSE
        """,
        user_id,
    )
    return int(result.split()[-1])


async def delete_notification(
    conn: asyncpg.Connection,
    notification_id: UUID,
    user_id: UUID,
) -> bool:
    """Delete a notification."""
    result = await conn.execute(
        """
        DELETE FROM notifications
        WHERE id = $1 AND user_id = $2
        """,
        notification_id,
        user_id,
    )
    return int(result.split()[-1]) > 0
