"""
Integration tests for authentication service functions with real database calls.
"""

import pytest

from app.core.security import create_access_token, hash_password, verify_password
from app.services.users import get_user_by_username


class TestAuthService:
    """Test authentication service functions."""

    @pytest.mark.asyncio
    async def test_get_user_by_username(self, db_connection, test_user):
        """Test getting user by username."""
        user = await get_user_by_username(db_connection, test_user["username"])

        assert user is not None
        assert user["username"] == test_user["username"]
        assert user["role"] == test_user["role"]

    @pytest.mark.asyncio
    async def test_get_user_by_username_not_found(self, db_connection):
        """Test getting non-existent user."""
        user = await get_user_by_username(db_connection, "nonexistent")

        assert user is None

    def test_verify_password_correct(self):
        """Test password verification with correct password."""
        password = "testpass123"
        hashed = hash_password(password)

        assert verify_password(password, hashed) is True

    def test_verify_password_incorrect(self):
        """Test password verification with incorrect password."""
        password = "testpass123"
        wrong_password = "wrongpass"
        hashed = hash_password(password)

        assert verify_password(wrong_password, hashed) is False

    def test_create_access_token(self, test_user):
        """Test JWT token creation."""
        data = {"sub": str(test_user["id"])}
        token = create_access_token(data)

        assert isinstance(token, str)
        assert len(token) > 0
        # JWT tokens have 3 parts separated by dots
        assert len(token.split(".")) == 3
