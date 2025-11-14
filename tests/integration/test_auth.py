"""
Integration tests for authentication endpoints.
"""

import pytest


class TestAuthAPI:
    """Test authentication API endpoints."""

    @pytest.mark.asyncio
    async def test_health_check(self, async_client):
        """Test health check endpoint."""
        response = await async_client.get("/health")

        assert response.status_code == 200
        data = response.json()["data"]
        assert "status" in data
        assert "checks" in data

    @pytest.mark.asyncio
    async def test_cors_test_endpoint(self, async_client):
        """Test CORS test endpoint."""
        response = await async_client.get("/cors-test")

        assert response.status_code == 200
        data = response.json()["data"]
        assert "message" in data
        assert "CORS is working!" in data["message"]

    @pytest.mark.asyncio
    async def test_login_success(self, async_client, test_user):
        """Test successful login."""
        response = await async_client.post(
            "/auth/login",
            json={"username": test_user["username"], "password": test_user["password"]},
        )

        assert response.status_code == 200
        data = response.json()["data"]
        assert "access_token" in data
        assert "token_type" in data
        assert data["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, async_client, test_user):
        """Test login with wrong password."""
        response = await async_client.post(
            "/auth/login",
            json={"username": test_user["username"], "password": "wrongpassword"},
        )

        assert response.status_code == 401
        data = response.json()
        assert data["success"] is False
        assert "Invalid credentials" in data["message"]

    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self, async_client):
        """Test login with non-existent user."""
        response = await async_client.post(
            "/auth/login", json={"username": "nonexistent", "password": "password"}
        )

        assert response.status_code == 401
        data = response.json()
        assert data["success"] is False

    @pytest.mark.asyncio
    async def test_verify_token(self, async_client, auth_headers):
        """Test token verification endpoint."""
        response = await async_client.get("/auth/verify", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()["data"]
        assert "user" in data
        assert "username" in data["user"]

    @pytest.mark.asyncio
    async def test_verify_token_no_auth(self, async_client):
        """Test token verification without authentication."""
        response = await async_client.get("/auth/verify")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_verify_token_invalid(self, async_client):
        """Test token verification with invalid token."""
        response = await async_client.get(
            "/auth/verify", headers={"Authorization": "Bearer invalid_token"}
        )

        assert response.status_code == 401
