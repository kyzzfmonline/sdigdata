"""
Integration tests for organizations service functions with real database calls.
"""

import pytest

from app.services.organizations import create_organization, get_organization_by_id


class TestOrganizationsService:
    """Test organizations service functions."""

    @pytest.mark.asyncio
    async def test_create_organization(self, db_connection):
        """Test creating an organization."""
        name = "Test Organization"
        logo_url = "https://example.com/logo.png"
        primary_color = "#FF0000"

        org = await create_organization(
            db_connection, name=name, logo_url=logo_url, primary_color=primary_color
        )

        assert org is not None
        assert org["name"] == name
        assert org["logo_url"] == logo_url
        assert org["primary_color"] == primary_color
        assert "id" in org

    @pytest.mark.asyncio
    async def test_get_organization_by_id(self, db_connection, test_organization):
        """Test getting organization by ID."""
        org = await get_organization_by_id(db_connection, test_organization["id"])

        assert org is not None
        assert org["id"] == test_organization["id"]
        assert org["name"] == test_organization["name"]

    @pytest.mark.asyncio
    async def test_get_organization_by_id_not_found(self, db_connection):
        """Test getting non-existent organization."""
        from uuid import uuid4

        org = await get_organization_by_id(db_connection, uuid4())

        assert org is None
