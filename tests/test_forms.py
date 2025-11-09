"""
Tests for form management APIs.
"""

import pytest
from uuid import uuid4


async def test_create_form(client, auth_token, test_organization):
    """
    Test creating a new form.
    """
    response = client.post(
        "/forms",
        headers={"Authorization": f"Bearer {auth_token}"},
        json={
            "title": "Test Form",
            "organization_id": str(test_organization["id"]),
            "form_schema": {
                "fields": [{"id": "test", "type": "text", "label": "Test"}]
            },
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["success"] == True
    assert data["data"]["title"] == "Test Form"
    assert "id" in data["data"]


async def test_list_forms(client, auth_token, test_organization):
    """
    Test listing all forms.
    """
    response = client.get(
        "/forms",
        headers={"Authorization": f"Bearer {auth_token}"},
    )

    response = client.get(
        "/forms",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] == True
    forms = data["data"]
    assert isinstance(forms, list)
    assert len(forms) > 0
    assert any(d["title"] == "List Test Form" for d in forms)


async def test_get_form(client, auth_token, test_organization):
    """
    Test getting a single form by ID.
    """
    # First create a form
    create_response = client.post(
        "/forms",
        headers={"Authorization": f"Bearer {auth_token}"},
        json={
            "title": "Test Form for Get",
            "organization_id": str(test_organization["id"]),
            "form_schema": {
                "fields": [{"id": "test", "type": "text", "label": "Test"}]
            },
        },
    )
    form_id = create_response.json()["data"]["id"]

    response = client.get(
        f"/forms/{form_id}",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] == True
    assert data["data"]["title"] == "Test Form for Get"
    assert data["data"]["id"] == form_id


async def test_publish_form(client, auth_token, test_organization):
    """
    Test publishing a form.
    """
    # First create a form
    create_response = client.post(
        "/forms",
        headers={"Authorization": f"Bearer {auth_token}"},
        json={
            "title": "Test Form for Publish",
            "organization_id": str(test_organization["id"]),
            "form_schema": {
                "fields": [{"id": "test", "type": "text", "label": "Test"}]
            },
        },
    )
    form_id = create_response.json()["data"]["id"]

    response = client.post(
        f"/forms/{form_id}/publish",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] == True
    assert data["data"]["status"] == "published"


async def test_assign_form(client, auth_token, test_organization, agent_user):
    """
    Test assigning a form to an agent.
    """
    # First create and publish a form
    create_response = client.post(
        "/forms",
        headers={"Authorization": f"Bearer {auth_token}"},
        json={
            "title": "Test Form for Assign",
            "organization_id": str(test_organization["id"]),
            "form_schema": {
                "fields": [{"id": "test", "type": "text", "label": "Test"}]
            },
        },
    )
    form_id = create_response.json()["data"]["id"]

    response = client.post(
        f"/forms/{form_id}/assign",
        headers={"Authorization": f"Bearer {auth_token}"},
        json={"agent_ids": [str(agent_user["id"])]},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] == True
    assignments = data["data"]["assignments"]
    assert len(assignments) == 1
    assert assignments[0]["form_id"] == form_id
    assert assignments[0]["agent_id"] == str(agent_user["id"])
