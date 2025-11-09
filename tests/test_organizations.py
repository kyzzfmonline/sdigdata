"""
Tests for organization management APIs.
"""

import pytest
from uuid import uuid4


async def test_create_organization(client, auth_token):
    """
    Test creating a new organization.
    """
    response = client.post(
        "/organizations",
        headers={"Authorization": f"Bearer {auth_token}"},
        json={
            "name": "Test Organization",
            "logo_url": "https://example.com/logo.png",
            "primary_color": "#000000",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["success"] == True
    assert data["data"]["name"] == "Test Organization"
    assert "id" in data["data"]


def test_create_organization_unauthorized(client):
    """
    Test that creating an organization fails without authentication.
    """
    response = client.post(
        "/organizations",
        json={"name": "Unauthorized Test"},
    )
    assert response.status_code == 403


async def test_list_organizations(client, auth_token):
    """
    Test listing all organizations.
    """
    # Create an org first
    client.post(
        "/organizations",
        headers={"Authorization": f"Bearer {auth_token}"},
        json={"name": "List Test Org"},
    )

    response = client.get(
        "/organizations",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] == True
    orgs = data["data"]
    assert isinstance(orgs, list)
    assert len(orgs) > 0
    assert any(d["name"] == "List Test Org" for d in orgs)


async def test_get_organization(client, auth_token):
    """
    Test getting a single organization by ID.
    """
    # Create an org first
    create_response = client.post(
        "/organizations",
        headers={"Authorization": f"Bearer {auth_token}"},
        json={"name": "Get Test Org"},
    )
    org_id = create_response.json()["data"]["id"]

    response = client.get(
        f"/organizations/{org_id}",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] == True
    assert data["data"]["name"] == "Get Test Org"
    assert data["data"]["id"] == org_id


async def test_get_nonexistent_organization(client, auth_token):
    """
    Test that getting a nonexistent organization returns 404.
    """
    non_existent_id = uuid4()
    response = client.get(
        f"/organizations/{non_existent_id}",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 404


async def test_update_organization(client, auth_token):
    """
    Test updating an organization.
    """
    # Create an org first
    create_response = client.post(
        "/organizations",
        headers={"Authorization": f"Bearer {auth_token}"},
        json={"name": "Update Test Org"},
    )
    org_id = create_response.json()["data"]["id"]

    response = client.patch(
        f"/organizations/{org_id}",
        headers={"Authorization": f"Bearer {auth_token}"},
        json={"name": "Updated Org Name"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] == True
    assert data["data"]["name"] == "Updated Org Name"

    # Verify the change
    get_response = client.get(
        f"/organizations/{org_id}",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert get_response.json()["data"]["name"] == "Updated Org Name"
