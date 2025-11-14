"""
Unit tests for organization service functions.
"""

import pytest

from app.services.organizations import (
    create_organization,
    get_first_organization,
    get_organization_by_id,
)


class TestOrganizationService:
    """Test organization service functions."""

    @pytest.mark.asyncio
    async def test_create_organization(self, db_connection):
        """Test creating a new organization."""
        org = await create_organization(
            db_connection,
            name="Test Organization",
            logo_url="https://example.com/logo.png",
            primary_color="#FF0000",
        )

        assert org is not None
        assert org["name"] == "Test Organization"
        assert org["logo_url"] == "https://example.com/logo.png"
        assert org["primary_color"] == "#FF0000"

    @pytest.mark.asyncio
    async def test_create_organization_minimal(self, db_connection):
        """Test creating an organization with minimal data."""
        org = await create_organization(
            db_connection, name="Minimal Org", logo_url=None, primary_color=None
        )

        assert org is not None
        assert org["name"] == "Minimal Org"
        assert org["logo_url"] is None
        assert org["primary_color"] is None

    @pytest.mark.asyncio
    async def test_get_organization_by_id(self, db_connection):
        """Test getting organization by ID."""
        # Create organization first
        created_org = await create_organization(
            db_connection, name="Test Org for Get", logo_url=None, primary_color=None
        )

        # Get organization by ID
        org = await get_organization_by_id(db_connection, created_org["id"])

        assert org is not None
        assert org["id"] == created_org["id"]
        assert org["name"] == "Test Org for Get"

    @pytest.mark.asyncio
    async def test_get_organization_by_id_not_found(self, db_connection):
        """Test getting non-existent organization by ID."""
        from uuid import uuid4

        org = await get_organization_by_id(db_connection, uuid4())

        assert org is None

    @pytest.mark.asyncio
    async def test_get_first_organization(self, db_connection):
        """Test getting the first organization."""
        # Create an organization
        created_org = await create_organization(
            db_connection, name="First Org", logo_url=None, primary_color=None
        )

        # Get first organization
        org = await get_first_organization(db_connection)

        assert org is not None
        assert org["id"] == created_org["id"]
        assert org["name"] == "First Org"
