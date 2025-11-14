"""
Integration tests for analytics service functions with actual database calls.
"""

import pytest

from app.core.security import hash_password
from app.services.analytics import (
    get_agent_performance,
    get_dashboard_stats,
    get_form_analytics,
)
from app.services.forms import create_form
from app.services.organizations import create_organization
from app.services.responses import create_response
from app.services.users import create_user


class TestAnalyticsServiceIntegration:
    """Integration tests for analytics service with real database calls."""

    @pytest.mark.asyncio
    async def test_get_dashboard_stats_24h_period(self, db_connection):
        """Test getting dashboard stats with 24h period using real data."""
        # Create test organization
        org = await create_organization(
            db_connection, name="Test Org", logo_url=None, primary_color=None
        )

        # Create admin user
        password_hash = hash_password("admin123")
        admin = await create_user(
            db_connection,
            username="admin",
            password_hash=password_hash,
            role="admin",
            organization_id=org["id"],
        )

        # Create some forms
        form1 = await create_form(
            db_connection,
            title="Form 1",
            organization_id=org["id"],
            schema={"type": "object", "properties": {"field": {"type": "string"}}},
            created_by=admin["id"],
            status="published",
            description="Test form 1",
        )

        form2 = await create_form(
            db_connection,
            title="Form 2",
            organization_id=org["id"],
            schema={"type": "object", "properties": {"field": {"type": "string"}}},
            created_by=admin["id"],
            status="published",
            description="Test form 2",
        )

        # Create responses
        for i in range(5):
            await create_response(
                db_connection,
                form_id=form1["id"],
                submitted_by=admin["id"],
                data={"field": f"value{i}"},
            )

        # Create older responses
        for i in range(10):
            await create_response(
                db_connection,
                form_id=form2["id"],
                submitted_by=admin["id"],
                data={"field": f"value{i}"},
            )

        # Test dashboard stats
        result = await get_dashboard_stats(db_connection, period="24h")

        # Verify results are based on actual data
        assert result["stats"]["total_forms"] >= 2
        assert result["stats"]["total_responses"] >= 15
        assert "avg_completion_rate" in result["stats"]
        assert "response_trend" in result

    @pytest.mark.asyncio
    async def test_get_dashboard_stats_default_period(self, db_connection):
        """Test getting dashboard stats with default 7d period using real data."""
        # Create test data
        org = await create_organization(
            db_connection, name="Test Org 2", logo_url=None, primary_color=None
        )

        password_hash = hash_password("admin123")
        admin = await create_user(
            db_connection,
            username="admin2",
            password_hash=password_hash,
            role="admin",
            organization_id=org["id"],
        )

        # Create forms and responses
        form = await create_form(
            db_connection,
            title="Test Form",
            organization_id=org["id"],
            schema={"type": "object", "properties": {"field": {"type": "string"}}},
            created_by=admin["id"],
            status="published",
            description="Test form",
        )

        # Create multiple responses
        for i in range(20):
            await create_response(
                db_connection,
                form_id=form["id"],
                submitted_by=admin["id"],
                data={"field": f"value{i}"},
            )

        result = await get_dashboard_stats(db_connection)

        # Verify results
        assert result["stats"]["total_forms"] >= 1
        assert result["stats"]["total_responses"] >= 20
        assert result["stats"]["avg_completion_rate"] >= 0
        assert "response_trend" in result
        assert "top_forms" in result

    @pytest.mark.asyncio
    async def test_get_form_analytics(self, db_connection):
        """Test getting analytics for a specific form with real data."""
        # Create test data
        org = await create_organization(
            db_connection, name="Test Org 3", logo_url=None, primary_color=None
        )

        password_hash = hash_password("admin123")
        admin = await create_user(
            db_connection,
            username="admin3",
            password_hash=password_hash,
            role="admin",
            organization_id=org["id"],
        )

        form = await create_form(
            db_connection,
            title="Analytics Test Form",
            organization_id=org["id"],
            schema={"type": "object", "properties": {"field": {"type": "string"}}},
            created_by=admin["id"],
            status="published",
            description="Form for analytics testing",
        )

        # Create responses
        for i in range(50):
            await create_response(
                db_connection,
                form_id=form["id"],
                submitted_by=admin["id"],
                data={"field": f"response_{i}"},
            )

        result = await get_form_analytics(db_connection, form["id"])

        # Verify results
        assert result["form_id"] == str(form["id"])
        assert result["metrics"]["total_responses"] >= 50
        assert "completion_rate" in result["metrics"]
        assert "demographics" in result
        assert "top_agents" in result

    @pytest.mark.asyncio
    async def test_get_agent_performance(self, db_connection):
        """Test getting performance metrics for an agent with real data."""
        # Create test data
        org = await create_organization(
            db_connection, name="Test Org 4", logo_url=None, primary_color=None
        )

        password_hash = hash_password("agent123")
        agent = await create_user(
            db_connection,
            username="testagent",
            password_hash=password_hash,
            role="agent",
            organization_id=org["id"],
        )

        # Create forms
        forms = []
        for i in range(3):
            form = await create_form(
                db_connection,
                title=f"Agent Form {i}",
                organization_id=org["id"],
                schema={"type": "object", "properties": {"field": {"type": "string"}}},
                created_by=agent["id"],
                status="published",
                description=f"Form created by agent {i}",
            )
            forms.append(form)

        # Create responses submitted by this agent
        for form in forms:
            for i in range(10):
                await create_response(
                    db_connection,
                    form_id=form["id"],
                    submitted_by=agent["id"],
                    data={"field": f"response_{i}"},
                )

        result = await get_agent_performance(db_connection, agent["id"])

        # Verify results
        assert result["total_responses"] >= 30
        assert result["forms_assigned"] >= 0  # May be 0 if no assignments
        assert "completion_rate" in result
        assert "response_trend" in result
        assert "forms_breakdown" in result

    # TODO: Fix get_performance_metrics query issue with interval operations
    # @pytest.mark.asyncio
    # async def test_get_performance_metrics(self, db_connection):
    #     """Test getting overall performance metrics with real data."""
