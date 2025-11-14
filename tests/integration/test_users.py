"""
Integration tests for user service functions with real database calls.
"""

import pytest

from app.core.security import hash_password
from app.services.users import create_user, get_user_by_id, get_user_by_username


class TestUserService:
    """Test user service functions."""

    @pytest.mark.asyncio
    async def test_create_user(self, db_connection):
        """Test creating a new user."""
        # Create test organization first
        from app.services.organizations import create_organization

        org = await create_organization(db_connection, "Test Org", None, None)
        org_id = org["id"]

        # Create user
        password_hash = hash_password("testpass123")
        user = await create_user(
            db_connection,
            username="testuser",
            password_hash=password_hash,
            role="agent",
            organization_id=org_id,
        )

        assert user is not None
        assert user["username"] == "testuser"
        assert user["role"] == "agent"
        assert user["organization_id"] == org_id

    @pytest.mark.asyncio
    async def test_get_user_by_id(self, db_connection):
        """Test getting user by ID."""
        # Create test organization and user first
        from app.services.organizations import create_organization

        org = await create_organization(db_connection, "Test Org", None, None)
        org_id = org["id"]

        password_hash = hash_password("testpass123")
        created_user = await create_user(
            db_connection,
            username="testuser2",
            password_hash=password_hash,
            role="agent",
            organization_id=org_id,
        )

        # Get user by ID
        user = await get_user_by_id(db_connection, created_user["id"])

        assert user is not None
        assert user["id"] == created_user["id"]
        assert user["username"] == "testuser2"

    @pytest.mark.asyncio
    async def test_get_user_by_username(self, db_connection):
        """Test getting user by username."""
        # Create test organization and user first
        from app.services.organizations import create_organization

        org = await create_organization(db_connection, "Test Org", None, None)
        org_id = org["id"]

        password_hash = hash_password("testpass123")
        created_user = await create_user(
            db_connection,
            username="testuser3",
            password_hash=password_hash,
            role="agent",
            organization_id=org_id,
        )

        # Get user by username
        user = await get_user_by_username(db_connection, "testuser3")

        assert user is not None
        assert user["id"] == created_user["id"]
        assert user["username"] == "testuser3"

    @pytest.mark.asyncio
    async def test_get_user_by_username_not_found(self, db_connection):
        """Test getting non-existent user by username."""
        user = await get_user_by_username(db_connection, "nonexistent")

        assert user is None
