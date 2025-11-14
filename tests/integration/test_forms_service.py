"""
Integration tests for forms service functions with real database calls.
"""

from uuid import uuid4

import pytest

from app.services.forms import create_form, get_form_by_id


class TestFormsService:
    """Test forms service functions."""

    @pytest.mark.asyncio
    async def test_create_form(self, db_connection, test_organization, admin_user):
        """Test creating a form."""
        title = "Test Form"
        schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}, "age": {"type": "integer"}},
            "required": ["name"],
        }
        created_by = admin_user["id"]
        status = "draft"
        description = "Test form description"

        form = await create_form(
            db_connection,
            title=title,
            organization_id=test_organization["id"],
            schema=schema,
            created_by=created_by,
            status=status,
            description=description,
        )

        assert form is not None
        assert form["title"] == title
        assert form["organization_id"] == test_organization["id"]
        assert form["schema"] == schema
        assert form["created_by"] == created_by
        assert form["status"] == status
        assert form["description"] == description
        assert "id" in form

    @pytest.mark.asyncio
    async def test_get_form_by_id(self, db_connection, test_form):
        """Test getting form by ID."""
        form = await get_form_by_id(db_connection, test_form["id"])

        assert form is not None
        assert form["id"] == test_form["id"]
        assert form["title"] == test_form["title"]

    @pytest.mark.asyncio
    async def test_get_form_by_id_not_found(self, db_connection):
        """Test getting non-existent form."""
        form = await get_form_by_id(db_connection, uuid4())

        assert form is None
