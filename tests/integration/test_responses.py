"""
Integration tests for responses API endpoints.
"""

import pytest


class TestResponsesAPI:
    """Test responses API endpoints."""

    @pytest.mark.asyncio
    async def test_submit_response(self, client, auth_headers, test_form):
        """Test submitting a form response."""
        response_data = {
            "form_id": test_form["id"],
            "data": {"name": "John Doe", "age": 30, "location": "Test City"},
        }

        response = await client.post(
            "/responses", headers=auth_headers, json=response_data
        )

        assert response.status_code == 201
        data = response.json()["data"]
        assert data["form_id"] == test_form["id"]
        assert data["data"]["name"] == "John Doe"

    @pytest.mark.asyncio
    async def test_submit_response_unauthorized(self, client, test_form):
        """Test submitting response without authentication."""
        response_data = {"form_id": test_form["id"], "data": {"name": "Test"}}

        response = await client.post("/responses", json=response_data)

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_responses(self, client, admin_auth_headers, test_form):
        """Test getting responses for a form."""
        # First submit a response
        response_data = {"form_id": test_form["id"], "data": {"name": "Test Response"}}

        await client.post("/responses", headers=admin_auth_headers, json=response_data)

        # Now get responses
        response = await client.get(
            f"/responses?form_id={test_form['id']}", headers=admin_auth_headers
        )

        assert response.status_code == 200
        data = response.json()["data"]
        assert isinstance(data, list)
        assert len(data) >= 1

    @pytest.mark.asyncio
    async def test_get_response_by_id(self, client, admin_auth_headers, test_form):
        """Test getting a specific response by ID."""
        # First create a response
        response_data = {
            "form_id": test_form["id"],
            "data": {"name": "Specific Response"},
        }

        create_response = await client.post(
            "/responses", headers=admin_auth_headers, json=response_data
        )

        response_id = create_response.json()["data"]["id"]

        # Now get the specific response
        response = await client.get(
            f"/responses/{response_id}", headers=admin_auth_headers
        )

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["id"] == response_id
        assert data["data"]["name"] == "Specific Response"

    @pytest.mark.asyncio
    async def test_get_response_not_found(self, client, admin_auth_headers):
        """Test getting a non-existent response."""
        from uuid import uuid4

        response = await client.get(f"/responses/{uuid4()}", headers=admin_auth_headers)

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_submit_invalid_response(self, client, auth_headers, test_form):
        """Test submitting invalid response data."""
        # Submit response with missing required field
        response_data = {
            "form_id": test_form["id"],
            "data": {
                "age": 25,
                "location": "Test City",
                # Missing required "name" field
            },
        }

        response = await client.post(
            "/responses", headers=auth_headers, json=response_data
        )

        # Should fail validation
        assert response.status_code == 422
