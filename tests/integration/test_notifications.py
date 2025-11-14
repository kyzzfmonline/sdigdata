"""
Integration tests for notifications service functions with real database calls.
"""

from uuid import uuid4

import pytest

from app.services.notifications import (
    create_notification,
    delete_notification,
    get_unread_count,
    get_user_notifications,
    mark_all_read,
    mark_notification_read,
)


class TestNotificationsService:
    """Test notifications service functions."""

    @pytest.mark.asyncio
    async def test_create_notification(self, db_connection, test_user):
        """Test creating a notification."""
        data = {"form_id": str(uuid4()), "action": "submitted"}

        result = await create_notification(
            db_connection,
            user_id=test_user["id"],
            notification_type="form_submission",
            title="New Form Submission",
            message="A new form has been submitted",
            data=data,
        )

        assert result is not None
        assert result["user_id"] == test_user["id"]
        assert result["type"] == "form_submission"
        assert result["title"] == "New Form Submission"
        assert result["message"] == "A new form has been submitted"
        assert result["data"] == data  # Should be parsed back to dict
        assert result["read"] is False
        assert "id" in result
        assert "created_at" in result

    @pytest.mark.asyncio
    async def test_create_notification_no_data(self, db_connection, test_user):
        """Test creating a notification without data."""

        result = await create_notification(
            db_connection,
            user_id=test_user["id"],
            notification_type="system",
            title="System Update",
            message="System has been updated",
        )

        assert result is not None
        assert result["data"] is None

    @pytest.mark.asyncio
    async def test_get_user_notifications_all(self, db_connection, test_user):
        """Test getting all notifications for a user."""

        # Create some test notifications
        await create_notification(
            db_connection,
            user_id=test_user["id"],
            notification_type="test1",
            title="Test 1",
            message="Message 1",
        )
        await create_notification(
            db_connection,
            user_id=test_user["id"],
            notification_type="test2",
            title="Test 2",
            message="Message 2",
        )

        notifications = await get_user_notifications(db_connection, test_user["id"])

        assert len(notifications) >= 2
        # Should be ordered by created_at DESC
        assert notifications[0]["created_at"] >= notifications[1]["created_at"]

    @pytest.mark.asyncio
    async def test_get_user_notifications_unread_only(self, db_connection, test_user):
        """Test getting only unread notifications."""

        # Create read and unread notifications
        read_notif = await create_notification(
            db_connection,
            user_id=test_user["id"],
            notification_type="read",
            title="Read",
            message="This is read",
        )

        # Mark one as read
        await mark_notification_read(db_connection, read_notif["id"], test_user["id"])

        unread_notifications = await get_user_notifications(
            db_connection, test_user["id"], unread_only=True
        )

        assert len(unread_notifications) >= 1
        assert all(not notif["read"] for notif in unread_notifications)

    @pytest.mark.asyncio
    async def test_get_user_notifications_with_limit_offset(
        self, db_connection, test_user
    ):
        """Test pagination of notifications."""

        # Create multiple notifications
        for i in range(5):
            await create_notification(
                db_connection,
                user_id=test_user["id"],
                notification_type=f"type{i}",
                title=f"Title {i}",
                message=f"Message {i}",
            )

        # Get first 2
        notifications = await get_user_notifications(
            db_connection, test_user["id"], limit=2, offset=0
        )
        assert len(notifications) == 2

        # Get next 2
        notifications_page2 = await get_user_notifications(
            db_connection, test_user["id"], limit=2, offset=2
        )
        assert len(notifications_page2) == 2

        # Should be different notifications
        assert notifications[0]["id"] != notifications_page2[0]["id"]

    @pytest.mark.asyncio
    async def test_get_unread_count(self, db_connection, test_user):
        """Test getting unread notification count."""

        # Initially should be 0
        count = await get_unread_count(db_connection, test_user["id"])
        assert count == 0

        # Create some notifications
        await create_notification(
            db_connection,
            user_id=test_user["id"],
            notification_type="test1",
            title="Test 1",
            message="Message 1",
        )
        await create_notification(
            db_connection,
            user_id=test_user["id"],
            notification_type="test2",
            title="Test 2",
            message="Message 2",
        )

        # Should have 2 unread
        count = await get_unread_count(db_connection, test_user["id"])
        assert count == 2

        # Mark one as read
        notifications = await get_user_notifications(
            db_connection, test_user["id"], limit=1
        )
        await mark_notification_read(
            db_connection, notifications[0]["id"], test_user["id"]
        )

        # Should have 1 unread
        count = await get_unread_count(db_connection, test_user["id"])
        assert count == 1

    @pytest.mark.asyncio
    async def test_mark_notification_read(self, db_connection, test_user):
        """Test marking a notification as read."""

        # Create notification
        notification = await create_notification(
            db_connection,
            user_id=test_user["id"],
            notification_type="test",
            title="Test",
            message="Test message",
        )
        assert notification["read"] is False

        # Mark as read
        success = await mark_notification_read(
            db_connection, notification["id"], test_user["id"]
        )
        assert success is True

        # Verify it's marked as read
        notifications = await get_user_notifications(
            db_connection, test_user["id"], unread_only=True
        )
        assert len([n for n in notifications if n["id"] == notification["id"]]) == 0

    @pytest.mark.asyncio
    async def test_mark_notification_read_wrong_user(
        self, db_connection, test_user, admin_user
    ):
        """Test marking notification read fails for wrong user."""

        # Create notification for test_user
        notification = await create_notification(
            db_connection,
            user_id=test_user["id"],
            notification_type="test",
            title="Test",
            message="Test message",
        )

        # Try to mark as read for admin_user
        success = await mark_notification_read(
            db_connection, notification["id"], admin_user["id"]
        )
        assert success is False

    @pytest.mark.asyncio
    async def test_mark_all_read(self, db_connection, test_user):
        """Test marking all notifications as read."""

        # Create multiple unread notifications
        for i in range(3):
            await create_notification(
                db_connection,
                user_id=test_user["id"],
                notification_type=f"type{i}",
                title=f"Title {i}",
                message=f"Message {i}",
            )

        # Verify they are unread
        count = await get_unread_count(db_connection, test_user["id"])
        assert count == 3

        # Mark all as read
        marked_count = await mark_all_read(db_connection, test_user["id"])
        assert marked_count == 3

        # Verify all are read
        count = await get_unread_count(db_connection, test_user["id"])
        assert count == 0

    @pytest.mark.asyncio
    async def test_delete_notification(self, db_connection, test_user):
        """Test deleting a notification."""

        # Create notification
        notification = await create_notification(
            db_connection,
            user_id=test_user["id"],
            notification_type="test",
            title="Test",
            message="Test message",
        )

        # Delete it
        success = await delete_notification(
            db_connection, notification["id"], test_user["id"]
        )
        assert success is True

        # Verify it's gone
        notifications = await get_user_notifications(db_connection, test_user["id"])
        assert len([n for n in notifications if n["id"] == notification["id"]]) == 0

    @pytest.mark.asyncio
    async def test_delete_notification_wrong_user(
        self, db_connection, test_user, admin_user
    ):
        """Test deleting notification fails for wrong user."""

        # Create notification for test_user
        notification = await create_notification(
            db_connection,
            user_id=test_user["id"],
            notification_type="test",
            title="Test",
            message="Test message",
        )

        # Try to delete as admin_user
        success = await delete_notification(
            db_connection, notification["id"], admin_user["id"]
        )
        assert success is False

        # Verify it's still there
        notifications = await get_user_notifications(db_connection, test_user["id"])
        assert len([n for n in notifications if n["id"] == notification["id"]]) == 1
