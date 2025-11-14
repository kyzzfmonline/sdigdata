"""
Unit tests for form service functions.
"""

import pytest

from app.services.forms import create_form, get_form_by_id


class TestFormService:
    """Test form service functions."""

    @pytest.mark.asyncio
    async def test_create_form(self, db_connection, test_organization, admin_user):
        """Test creating a new form."""
        schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}, "age": {"type": "integer"}},
            "required": ["name"],
        }

        form = await create_form(
            db_connection,
            title="Test Form",
            organization_id=test_organization["id"],
            schema=schema,
            created_by=admin_user["id"],
            status="draft",
            description="A test form",
        )

        assert form is not None
        assert form["title"] == "Test Form"
        assert form["organization_id"] == test_organization["id"]
        assert form["created_by"] == admin_user["id"]
        assert form["status"] == "draft"
        assert form["description"] == "A test form"
        assert form["schema"]["type"] == "object"

    @pytest.mark.asyncio
    async def test_create_form_minimal(
        self, db_connection, test_organization, admin_user
    ):
        """Test creating a form with minimal data."""
        schema = {"type": "object", "properties": {"field1": {"type": "string"}}}

        form = await create_form(
            db_connection,
            title="Minimal Form",
            organization_id=test_organization["id"],
            schema=schema,
            created_by=admin_user["id"],
        )

        assert form is not None
        assert form["title"] == "Minimal Form"
        assert form["status"] == "draft"  # Default status
        assert form["description"] is None

    @pytest.mark.asyncio
    async def test_get_form_by_id(self, db_connection, test_organization, admin_user):
        """Test getting form by ID."""
        # Create form first
        schema = {"type": "object", "properties": {"test": {"type": "string"}}}
        created_form = await create_form(
            db_connection,
            title="Form for Get Test",
            organization_id=test_organization["id"],
            schema=schema,
            created_by=admin_user["id"],
        )

        # Get form by ID
        form = await get_form_by_id(db_connection, created_form["id"])

        assert form is not None
        assert form["id"] == created_form["id"]
        assert form["title"] == "Form for Get Test"

    @pytest.mark.asyncio
    async def test_get_form_by_id_not_found(self, db_connection):
        """Test getting non-existent form by ID."""
        from uuid import uuid4

        form = await get_form_by_id(db_connection, uuid4())

        assert form is None
