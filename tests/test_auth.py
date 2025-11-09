import pytest
from app.core.security import hash_password
from app.services import users, organizations


def test_login(client, admin_user):
    """
    Test the login endpoint.
    """
    response = client.post(
        "/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] == True
    assert data["data"]["user"]["username"] == "admin"
    assert "access_token" in data["data"]


@pytest.mark.parametrize(
    "password",
    ["weak", "password", "12345678", "Abcd1234"],
)
def test_weak_password(client, auth_token, test_organization, password):
    """Test that weak passwords are rejected."""
    response = client.post(
        "/auth/register",
        headers={"Authorization": f"Bearer {auth_token}"},
        json={
            "username": f"testuser_{password}",
            "password": password,
            "role": "agent",
            "organization_id": str(test_organization),
        },
    )
    assert response.status_code == 422


def test_strong_password(client, auth_token, test_organization):
    """Test that a strong password is accepted."""
    response = client.post(
        "/auth/register",
        headers={"Authorization": f"Bearer {auth_token}"},
        json={
            "username": "strong_user",
            "password": "StrongP@ss123!",
            "role": "agent",
            "organization_id": str(test_organization),
        },
    )
    # It could be 201 or 400 if the user already exists from a previous run
    assert response.status_code in [201, 400]
    if response.status_code == 201:
        assert response.json()["username"] == "strong_user"


def test_rate_limiting(client):
    """Test that rate limiting is triggered on failed logins."""
    for i in range(5):
        response = client.post(
            "/auth/login",
            json={"username": "ratelimit_test", "password": "wrongpass"},
        )
        assert response.status_code == 401

    response = client.post(
        "/auth/login",
        json={"username": "ratelimit_test", "password": "wrongpass"},
    )
    assert response.status_code == 429
