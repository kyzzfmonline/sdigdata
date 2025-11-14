"""
Integration tests for responses service functions with real database calls.
"""

from uuid import uuid4

import pytest

from app.services.responses import create_response, get_response_by_id


class TestResponsesService:
    """Test responses service functions."""

    @pytest.mark.asyncio
    async def test_create_response(self, db_connection, test_form, test_user):
        """Test creating a response."""
        data = {"name": "John Doe", "age": 30, "location": "Test City"}

        response = await create_response(
            db_connection,
            form_id=test_form["id"],
            submitted_by=test_user["id"],
            data=data,
        )

        assert response is not None
        assert response["form_id"] == test_form["id"]
        assert response["submitted_by"] == test_user["id"]
        assert response["data"] == data
        assert "id" in response

    @pytest.mark.asyncio
    async def test_get_response_by_id(self, db_connection, test_form, test_user):
        """Test getting response by ID."""
        # First create a response
        data = {"name": "Jane Doe", "age": 25}
        created_response = await create_response(
            db_connection,
            form_id=test_form["id"],
            submitted_by=test_user["id"],
            data=data,
        )

        # Then get it back
        response = await get_response_by_id(db_connection, created_response["id"])

        assert response is not None
        assert response["id"] == created_response["id"]
        assert response["data"] == data

    @pytest.mark.asyncio
    async def test_get_response_by_id_not_found(self, db_connection):
        """Test getting non-existent response."""
        response = await get_response_by_id(db_connection, uuid4())

        assert response is None
