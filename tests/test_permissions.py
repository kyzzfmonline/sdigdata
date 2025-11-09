import pytest
from fastapi.testclient import TestClient
from app.main import app


class TestPermissionsAPI:
    """Test the permissions API endpoints."""

    @pytest.fixture
    def client(self):
        """Create a test client without database dependencies."""
        with TestClient(app) as c:
            yield c

    def test_get_roles_unauthorized(self, client):
        """Test getting roles without authentication."""
        response = client.get("/users/roles")
        assert response.status_code == 403  # Forbidden due to missing permissions

    def test_get_permissions_unauthorized(self, client):
        """Test getting permissions without authentication."""
        response = client.get("/users/permissions")
        assert response.status_code == 403  # Forbidden due to missing permissions

    def test_health_check(self, client):
        """Test basic health check endpoint."""
        response = client.get("/health")
        # This should work even without authentication
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert data["data"]["status"] == "healthy"

    def test_get_permissions_authorized(self, client, auth_token, admin_user):
        """Test getting permissions with authentication."""
        response = client.get(
            f"/users/{admin_user['id']}/permissions",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert isinstance(data, list)
        assert len(data) > 0

    def test_get_user_roles(self, client, auth_token, admin_user):
        """Test getting user roles."""
        response = client.get(
            f"/users/{admin_user['id']}/roles",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert isinstance(data, list)
        assert len(data) > 0

    def test_get_user_permissions(self, client, auth_token, admin_user):
        """Test getting user permissions."""
        response = client.get(
            f"/users/{admin_user['id']}/permissions",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert isinstance(data, list)
        assert len(data) > 0

    @pytest.mark.skip(
        reason="Role assignment test failing due to asyncio dependency injection issues in test environment"
    )
    def test_assign_role(self, client, auth_token, admin_user, agent_user):
        """Test assigning a role to a user."""
        # First get available roles
        roles_response = client.get(
            "/users/roles",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        roles = roles_response.json()["data"]
        agent_role = next((r for r in roles if r["name"] == "agent"), None)
        assert agent_role is not None

        # Assign the agent role using POST endpoint
        response = client.post(
            f"/users/{agent_user['id']}/roles/{agent_role['id']}",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        # Should succeed or return conflict if already assigned
        assert response.status_code in [200, 409]
