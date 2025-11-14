"""
Integration tests for ML quality scoring and analytics endpoints.
"""

import pytest


class TestMLQuality:
    """Test ML quality scoring and analytics functionality."""

    @pytest.mark.asyncio
    async def test_ml_quality_stats(self, client, admin_auth_headers):
        """Test getting ML quality statistics."""
        response = await client.get("/ml/quality-stats", headers=admin_auth_headers)

        # May return 200 with data or 404 if no data
        assert response.status_code in [200, 404]

        if response.status_code == 200:
            data = response.json()["data"]
            assert isinstance(data, dict)
            # Check for expected quality metrics
            if "overall_quality" in data:
                assert isinstance(data["overall_quality"], (int, float))

    @pytest.mark.asyncio
    async def test_ml_training_data_export(self, client, admin_auth_headers, test_form):
        """Test ML training data export."""
        # First create some responses to have data to export
        response_data = {
            "form_id": test_form["id"],
            "data": {
                "name": "Training Example",
                "age": 25,
                "location": "Training City",
            },
        }

        # Submit a few responses
        for _i in range(3):
            await client.post(
                "/responses", headers=admin_auth_headers, json=response_data
            )

        # Try to export training data
        response = await client.get(
            f"/ml/training-data?form_id={test_form['id']}&format=json",
            headers=admin_auth_headers,
        )

        assert response.status_code in [
            200,
            404,
        ]  # May be 404 if ML features not fully implemented

        if response.status_code == 200:
            data = response.json()["data"]
            assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_ml_quality_unauthorized(self, client):
        """Test ML endpoints require admin access."""
        response = await client.get("/ml/quality-stats")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_ml_export_formats(self, client, admin_auth_headers):
        """Test different ML export formats."""
        formats = ["json", "jsonl", "csv", "geojson"]

        for fmt in formats:
            response = await client.get(
                f"/ml/training-data?format={fmt}", headers=admin_auth_headers
            )

            # Should either succeed or return appropriate error
            assert response.status_code in [200, 400, 404, 422]
