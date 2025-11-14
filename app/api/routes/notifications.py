"""Notification routes."""
# type: ignore

from typing import Annotated
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import get_current_user
from app.core.database import get_db
from app.services.notifications import (
    delete_notification,
    get_unread_count,
    get_user_notifications,
    mark_all_read,
    mark_notification_read,
)

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("")
async def get_notifications(
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    unread_only: bool = Query(False, description="Show only unread notifications"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(50, ge=1, le=100, description="Items per page"),
):
    """
    Get user notifications with pagination.

    **Query Parameters:**
    - unread_only: Filter to only unread notifications
    - page: Page number (default: 1)
    - limit: Items per page (default: 50)

    **Response:**
    ```json
    {
        "success": true,
        "data": [
            {
                "id": "not_123",
                "type": "form_assigned",
                "title": "New form assigned",
                "message": "You have been assigned to Census 2025",
                "data": {
                    "form_id": "frm_123",
                    "form_name": "Census 2025"
                },
                "read": false,
                "created_at": "2025-01-05T10:00:00Z"
            }
        ],
        "unread_count": 3
    }
    ```
    """
    try:
        offset = (page - 1) * limit
        user_id = current_user["id"]
        notifications = await get_user_notifications(
            conn,
            user_id=user_id,
            unread_only=unread_only,
            limit=limit,
            offset=offset,
        )

        unread_count = await get_unread_count(conn, user_id)

        return {"success": True, "data": notifications, "unread_count": unread_count}
    except Exception as e:
        print(f"Error in get_notifications: {e}")
        import traceback

        traceback.print_exc()
        raise


@router.get("/recent")
async def get_recent_notifications(
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    limit: int = Query(
        10, ge=1, le=50, description="Number of recent notifications to return"
    ),
):
    """
    Get recent notifications for topbar dropdown.

    **Query Parameters:**
    - limit: Number of notifications to return (default: 10, max: 50)

    **Response:**
    ```json
    {
        "success": true,
        "data": {
            "notifications": [
                {
                    "id": "notif-123",
                    "type": "response",
                    "title": "New Response Submitted",
                    "message": "Community Survey received a new response",
                    "timestamp": "2024-11-08T10:30:00Z",
                    "read": false,
                    "priority": "normal",
                    "action_url": "/responses?form=community-survey"
                }
            ],
            "unread_count": 3
        }
    }
    ```
    """
    try:
        # Get recent notifications
        recent_notifications = await get_user_notifications(
            conn,
            user_id=current_user["id"],
            unread_only=False,
            limit=limit,
            offset=0,
        )

        # Get unread count
        unread_count = await get_unread_count(conn, current_user["id"])

        # Format notifications for dropdown
        formatted_notifications = []
        for notification in recent_notifications:
            # Generate title based on type
            if notification["type"] == "form_assigned":
                title = "New Form Assigned"
                action_url = f"/forms/{notification.get('data', {}).get('form_id', '')}"
            elif notification["type"] == "response":
                title = "New Response Submitted"
                action_url = (
                    f"/responses?form={notification.get('data', {}).get('form_id', '')}"
                )
            else:
                title = "Notification"
                action_url = "/notifications"

            formatted_notifications.append(
                {
                    "id": str(notification["id"]),
                    "type": notification["type"],
                    "title": title,
                    "message": notification["message"],
                    "timestamp": notification["created_at"].isoformat()
                    if notification["created_at"]
                    else None,
                    "read": notification["read"],
                    "priority": "normal",  # Could be enhanced based on type/urgency
                    "action_url": action_url,
                }
            )

        return {
            "success": True,
            "data": {
                "notifications": formatted_notifications,
                "unread_count": unread_count,
            },
        }
    except Exception as e:
        print(f"Error in get_recent_notifications: {e}")
        import traceback

        traceback.print_exc()
        raise


@router.put("/{notification_id}/read", response_model=dict)
async def mark_read(
    notification_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """
    Mark notification as read.

    **Response:**
    ```json
    {
        "success": true,
        "message": "Notification marked as read"
    }
    ```
    """
    success = await mark_notification_read(
        conn, notification_id=notification_id, user_id=current_user["id"]
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found"
        )

    return {"success": True, "message": "Notification marked as read"}


@router.put("/read-all", response_model=dict)
async def mark_all_read_route(
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """
    Mark all notifications as read.

    **Response:**
    ```json
    {
        "success": true,
        "message": "All notifications marked as read",
        "count": 5
    }
    ```
    """
    count = await mark_all_read(conn, current_user["id"])

    return {
        "success": True,
        "message": "All notifications marked as read",
        "count": count,
    }


@router.delete("/{notification_id}", response_model=dict)
async def delete_notification_route(
    notification_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """
    Delete notification.

    **Response:**
    ```json
    {
        "success": true,
        "message": "Notification deleted"
    }
    ```
    """
    success = await delete_notification(
        conn, notification_id=notification_id, user_id=current_user["id"]
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found"
        )

    return {"success": True, "message": "Notification deleted"}
