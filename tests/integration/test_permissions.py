"""
Integration tests for permissions service functions with actual database calls.
"""

from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.services.permissions import (
    PermissionChecker,
    check_permission,
    require_permission,
)


class TestPermissionsServiceIntegration:
    """Integration tests for permissions service with real database calls."""

    @pytest.mark.asyncio
    async def test_permission_checker_has_permission_true(
        self, db_connection, test_user
    ):
        """Test PermissionChecker.has_permission returns True when user has permission."""
        checker = PermissionChecker(db_connection)

        # Test if agent user has permission to read forms (should be true based on migration)
        result = await checker.has_permission(test_user["id"], "forms", "read")

        assert result is True

    @pytest.mark.asyncio
    async def test_permission_checker_has_permission_false(
        self, db_connection, test_user
    ):
        """Test PermissionChecker.has_permission returns False when user lacks permission."""
        checker = PermissionChecker(db_connection)

        # Test if agent user has permission to delete organizations (should be false)
        result = await checker.has_permission(
            test_user["id"], "organizations", "delete"
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_permission_checker_has_any_permission(
        self, db_connection, test_user
    ):
        """Test PermissionChecker.has_any_permission."""
        checker = PermissionChecker(db_connection)

        # Test multiple permissions - agent should have forms read
        permissions = [("forms", "read"), ("responses", "create")]
        result = await checker.has_any_permission(test_user["id"], permissions)

        assert result is True

        # Test permissions agent shouldn't have
        permissions = [("organizations", "delete"), ("users", "delete")]
        result = await checker.has_any_permission(test_user["id"], permissions)

        assert result is False

    @pytest.mark.asyncio
    async def test_check_permission_true(self, db_connection, test_user):
        """Test check_permission convenience function returns True."""
        result = await check_permission(db_connection, test_user["id"], "forms", "read")

        assert result is True

    @pytest.mark.asyncio
    async def test_check_permission_false(self, db_connection, test_user):
        """Test check_permission convenience function returns False."""
        result = await check_permission(
            db_connection, test_user["id"], "organizations", "delete"
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_require_permission_success(self, db_connection, test_user):
        """Test require_permission doesn't raise when user has permission."""
        # Should not raise
        await require_permission(db_connection, test_user["id"], "forms", "read")

    @pytest.mark.asyncio
    async def test_require_permission_failure(self, db_connection, test_user):
        """Test require_permission raises HTTPException when user lacks permission."""
        with pytest.raises(HTTPException) as exc_info:
            await require_permission(
                db_connection, test_user["id"], "organizations", "delete"
            )

        assert exc_info.value.status_code == 403
        assert "Insufficient permissions" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_admin_has_all_permissions(self, db_connection, admin_user):
        """Test that admin user has all permissions."""
        checker = PermissionChecker(db_connection)

        # Test various permissions that admin should have
        permissions_to_test = [
            ("users", "create"),
            ("forms", "read"),
            ("responses", "update"),
            ("analytics", "view"),
        ]

        for resource, action in permissions_to_test:
            result = await checker.has_permission(admin_user["id"], resource, action)
            assert result is True, f"Admin should have {resource}:{action} permission"

        # Test that admin does NOT have organizations:delete (excluded by migration)
        result = await checker.has_permission(
            admin_user["id"], "organizations", "delete"
        )
        assert result is False, "Admin should NOT have organizations:delete permission"

    @pytest.mark.asyncio
    async def test_nonexistent_user_permissions(self, db_connection):
        """Test permissions for non-existent user."""
        checker = PermissionChecker(db_connection)
        fake_user_id = uuid4()

        result = await checker.has_permission(fake_user_id, "forms", "read")
        assert result is False

    @pytest.mark.asyncio
    async def test_get_user_permissions(self, db_connection, test_user):
        """Test getting all permissions for a user."""
        checker = PermissionChecker(db_connection)

        permissions = await checker.get_user_permissions(test_user["id"])

        assert isinstance(permissions, list)
        assert len(permissions) > 0  # Agent should have some permissions

        # Check that permissions have the expected structure
        for perm in permissions:
            assert "resource" in perm
            assert "action" in perm

    @pytest.mark.asyncio
    async def test_get_user_roles(self, db_connection, test_user):
        """Test getting roles for a user."""
        checker = PermissionChecker(db_connection)

        roles = await checker.get_user_roles(test_user["id"])

        assert isinstance(roles, list)
        assert len(roles) > 0  # User should have at least one role

        # Check that roles have the expected structure
        for role in roles:
            assert "name" in role
            assert "is_active" in role
