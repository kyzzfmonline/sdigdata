"""
Integration tests for forms API endpoints.
"""

import pytest


class TestFormsAPI:
    """Test forms API endpoints."""

    @pytest.mark.asyncio
    async def test_create_form(self, client, admin_auth_headers, test_organization):
        """Test creating a new form."""
        form_data = {
            "title": "Test Form",
            "description": "A test form",
            "organization_id": test_organization["id"],
            "schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "age": {"type": "integer"},
                    "location": {"type": "string"},
                },
                "required": ["name"],
            },
        }

        response = await client.post(
            "/forms", headers=admin_auth_headers, json=form_data
        )

        assert response.status_code == 201
        data = response.json()["data"]
        assert data["title"] == "Test Form"
        assert data["description"] == "A test form"
        assert data["organization_id"] == test_organization["id"]

    @pytest.mark.asyncio
    async def test_create_form_unauthorized(self, client, test_organization):
        """Test creating a form without authentication."""
        form_data = {
            "title": "Test Form",
            "organization_id": test_organization["id"],
            "schema": {"type": "object", "properties": {"field": {"type": "string"}}},
        }

        response = await client.post("/forms", json=form_data)

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_forms(self, client, admin_auth_headers, test_form):
        """Test getting list of forms."""
        response = await client.get("/forms", headers=admin_auth_headers)

        assert response.status_code == 200
        data = response.json()["data"]
        assert isinstance(data, list)
        assert len(data) >= 1

        # Check if our test form is in the list
        form_ids = [form["id"] for form in data]
        assert test_form["id"] in form_ids

    @pytest.mark.asyncio
    async def test_get_form_by_id(self, client, admin_auth_headers, test_form):
        """Test getting a specific form by ID."""
        response = await client.get(
            f"/forms/{test_form['id']}", headers=admin_auth_headers
        )

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["id"] == test_form["id"]
        assert data["title"] == test_form["title"]

    @pytest.mark.asyncio
    async def test_get_form_not_found(self, client, admin_auth_headers):
        """Test getting a non-existent form."""
        from uuid import uuid4

        response = await client.get(f"/forms/{uuid4()}", headers=admin_auth_headers)

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_form_status(self, client, admin_auth_headers, test_form):
        """Test updating form status."""
        update_data = {"status": "active"}

        response = await client.patch(
            f"/forms/{test_form['id']}/status",
            headers=admin_auth_headers,
            json=update_data,
        )

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["status"] == "active"

    @pytest.mark.asyncio
    async def test_assign_form_to_agent(
        self, client, admin_auth_headers, test_form, test_user
    ):
        """Test assigning a form to an agent."""
        assign_data = {"agent_ids": [test_user["id"]]}

        response = await client.post(
            f"/forms/{test_form['id']}/assign",
            headers=admin_auth_headers,
            json=assign_data,
        )

        assert response.status_code == 200
        data = response.json()["data"]
        assert "assignments" in data
