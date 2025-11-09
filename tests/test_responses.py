"""
Tests for response submission and retrieval APIs.
"""

import pytest
from uuid import uuid4


@pytest.fixture(scope="module")
async def published_form(client, auth_token, test_organization):
    """
    Create and publish a form for testing responses.
    """
    # Create a draft form first
    create_response = client.post(
        "/forms",
        headers={"Authorization": f"Bearer {auth_token}"},
        json={
            "title": "Response Test Form",
            "organization_id": str(test_organization["id"]),
            "form_schema": {
                "fields": [
                    {"id": "name", "type": "text", "label": "Full Name"},
                    {"id": "age", "type": "number", "label": "Age"},
                ]
            },
            "status": "draft",
        },
    )
    form_id = create_response.json()["data"]["id"]

    # Publish the form
    client.post(
        f"/forms/{form_id}/publish",
        headers={"Authorization": f"Bearer {auth_token}"},
    )

    return await get_form_data(client, auth_token, form_id)


async def get_form_data(client, auth_token, form_id):
    """Helper to get form data by ID."""
    response = client.get(
        f"/forms/{form_id}", headers={"Authorization": f"Bearer {auth_token}"}
    )
    return response.json()["data"]


async def test_submit_response_as_admin(client, auth_token, published_form):
    """
    Test submitting a response as an admin.
    """
    response = client.post(
        "/responses",
        headers={"Authorization": f"Bearer {auth_token}"},
        json={
            "form_id": published_form["id"],
            "data": {"name": "Admin User", "age": 40},
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["success"] == True
    response_data = data["data"]
    assert response_data["form_id"] == published_form["id"]
    assert response_data["data"]["name"] == "Admin User"


async def test_submit_response_as_agent(client, auth_token, agent_user, published_form):
    """
    Test submitting a response as an assigned agent.
    """
    # Assign agent to the form
    client.post(
        f"/forms/{published_form['id']}/assign",
        headers={"Authorization": f"Bearer {auth_token}"},
        json={"agent_ids": [str(agent_user["id"])]},
    )

    # Get agent auth token
    agent_auth_response = client.post(
        "/auth/login",
        json={"username": agent_user["username"], "password": "agent123"},
    )
    agent_auth_token = agent_auth_response.json()["data"]["access_token"]

    response = client.post(
        "/responses",
        headers={"Authorization": f"Bearer {agent_auth_token}"},
        json={
            "form_id": published_form["id"],
            "data": {"name": "Agent User", "age": 30},
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["success"] == True
    response_data = data["data"]
    assert response_data["form_id"] == published_form["id"]
    assert response_data["data"]["name"] == "Agent User"


async def test_submit_response_to_unpublished_form(
    client, auth_token, test_organization
):
    """
    Test that submitting a response to an unpublished form fails.
    """
    # Create a draft form
    create_response = client.post(
        "/forms",
        headers={"Authorization": f"Bearer {auth_token}"},
        json={
            "title": "Draft Form",
            "organization_id": str(test_organization["id"]),
            "form_schema": {},
            "status": "draft",
        },
    )
    form_id = create_response.json()["data"]["id"]

    response = client.post(
        "/responses",
        headers={"Authorization": f"Bearer {auth_token}"},
        json={
            "form_id": form_id,
            "data": {"name": "Test"},
        },
    )
    assert response.status_code == 400


async def test_response_view_modes(client, auth_token, test_organization):
    """
    Test different response view modes (table, chart, time_series, map, summary).
    """
    # Create a unique form for this test
    create_response = client.post(
        "/forms",
        headers={"Authorization": f"Bearer {auth_token}"},
        json={
            "title": "View Mode Test Form",
            "organization_id": str(test_organization["id"]),
            "form_schema": {
                "fields": [
                    {"id": "name", "type": "text", "label": "Full Name"},
                    {"id": "age", "type": "number", "label": "Age"},
                    {"id": "location", "type": "location", "label": "Location"},
                ]
            },
            "status": "draft",
        },
    )
    form_id = create_response.json()["data"]["id"]

    # Publish the form
    client.post(
        f"/forms/{form_id}/publish",
        headers={"Authorization": f"Bearer {auth_token}"},
    )

    published_form = await get_form_data(client, auth_token, form_id)

    # First, submit some test responses
    responses_data = [
        {
            "name": "Alice",
            "age": 25,
            "location": {"latitude": 40.7128, "longitude": -74.0060},
        },
        {
            "name": "Bob",
            "age": 30,
            "location": {"latitude": 34.0522, "longitude": -118.2437},
        },
        {
            "name": "Charlie",
            "age": 35,
            "location": {"latitude": 41.8781, "longitude": -87.6298},
        },
        {
            "name": "Alice",
            "age": 28,
            "location": {"latitude": 40.7128, "longitude": -74.0060},
        },  # Duplicate for aggregation
    ]

    submitted_responses = []
    for data in responses_data:
        response = client.post(
            "/responses",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "form_id": published_form["id"],
                "data": data,
            },
        )
        assert response.status_code == 201
        submitted_responses.append(response.json()["data"])

    # Test table view (default)
    table_response = client.get(
        f"/responses?form_id={published_form['id']}",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert table_response.status_code == 200
    table_data = table_response.json()
    assert table_data["success"] == True
    assert "data" in table_data
    assert "pagination" in table_data["data"]
    assert len(table_data["data"]["data"]) == 4

    # Test chart view with group_by
    chart_response = client.get(
        f"/responses?form_id={published_form['id']}&view=chart&group_by=name&aggregate=count",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert chart_response.status_code == 200
    chart_data = chart_response.json()
    assert chart_data["success"] == True
    assert "chart_data" in chart_data["data"]
    assert "chart_type" in chart_data["data"]
    assert "group_by" in chart_data["data"]
    assert "aggregate" in chart_data["data"]

    # Should have 3 groups (Alice, Bob, Charlie)
    assert len(chart_data["data"]["chart_data"]) == 3

    # Test time series view
    time_series_response = client.get(
        f"/responses?form_id={published_form['id']}&view=time_series&time_granularity=day",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert time_series_response.status_code == 200
    ts_data = time_series_response.json()
    assert ts_data["success"] == True
    assert "time_series" in ts_data["data"]
    assert "granularity" in ts_data["data"]

    # Test map view
    map_response = client.get(
        f"/responses?form_id={published_form['id']}&view=map",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert map_response.status_code == 200
    map_data = map_response.json()
    assert map_data["success"] == True
    assert "map_data" in map_data["data"]
    assert "total_points" in map_data["data"]

    # Should have 4 points
    assert len(map_data["data"]["map_data"]) == 4

    # Test summary view
    summary_response = client.get(
        f"/responses?form_id={published_form['id']}&view=summary",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert summary_response.status_code == 200
    summary_data = summary_response.json()
    assert summary_data["success"] == True
    assert "total_responses" in summary_data["data"]
    assert "date_range" in summary_data["data"]
    assert "submission_types" in summary_data["data"]
    assert summary_data["data"]["total_responses"] == 4


async def test_response_view_modes_error_handling(
    client, auth_token, test_organization
):
    """
    Test error handling in view modes with invalid parameters.
    """
    # Create a test form
    create_response = client.post(
        "/forms",
        headers={"Authorization": f"Bearer {auth_token}"},
        json={
            "title": "Error Test Form",
            "organization_id": str(test_organization["id"]),
            "form_schema": {
                "fields": [
                    {"id": "name", "type": "text", "label": "Full Name"},
                    {"id": "age", "type": "number", "label": "Age"},
                ]
            },
            "status": "draft",
        },
    )
    form_id = create_response.json()["data"]["id"]

    # Publish the form
    client.post(
        f"/forms/{form_id}/publish",
        headers={"Authorization": f"Bearer {auth_token}"},
    )

    # Test chart view without group_by (should fail)
    chart_response = client.get(
        f"/responses?form_id={form_id}&view=chart",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert chart_response.status_code == 400
    response_data = chart_response.json()
    assert response_data["success"] == False
    assert "group_by parameter is required" in response_data["message"]

    # Test invalid view mode (caught by FastAPI validation)
    invalid_view_response = client.get(
        f"/responses?form_id={form_id}&view=invalid_view",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert invalid_view_response.status_code == 422  # FastAPI validation error

    # Test invalid form_id format
    invalid_form_response = client.get(
        "/responses?form_id=invalid-uuid",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert invalid_form_response.status_code == 400
    response_data = invalid_form_response.json()
    assert response_data["success"] == False
    assert "Invalid form_id format" in response_data["message"]


async def test_response_view_modes_empty_data(client, auth_token, test_organization):
    """
    Test view modes with empty or minimal data.
    """
    # Create a test form
    create_response = client.post(
        "/forms",
        headers={"Authorization": f"Bearer {auth_token}"},
        json={
            "title": "Empty Test Form",
            "organization_id": str(test_organization["id"]),
            "form_schema": {"fields": []},
            "status": "draft",
        },
    )
    form_id = create_response.json()["data"]["id"]

    # Publish the form
    client.post(
        f"/forms/{form_id}/publish",
        headers={"Authorization": f"Bearer {auth_token}"},
    )

    # Test view modes that work without additional parameters
    simple_views = [
        (
            "table",
            lambda data: data["data"]["pagination"]["total"] == 0
            and len(data["data"]["data"]) == 0,
        ),
        ("map", lambda data: data["data"]["total_points"] == 0),
        ("summary", lambda data: data["data"]["total_responses"] == 0),
    ]

    for view, validator in simple_views:
        response = client.get(
            f"/responses?form_id={form_id}&view={view}",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert validator(data)

    # Test that chart view requires group_by
    chart_response = client.get(
        f"/responses?form_id={form_id}&view=chart",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert chart_response.status_code == 400
    assert "group_by parameter is required" in chart_response.json()["message"]


async def test_delete_response(client, auth_token, test_organization):
    """
    Test deleting a response (admin only).
    """
    # Create a test form
    create_form_response = client.post(
        "/forms",
        headers={"Authorization": f"Bearer {auth_token}"},
        json={
            "title": "Delete Test Form",
            "organization_id": str(test_organization["id"]),
            "form_schema": {
                "fields": [
                    {"id": "name", "type": "text", "label": "Full Name"},
                ]
            },
            "status": "draft",
        },
    )
    form_id = create_form_response.json()["data"]["id"]

    # Publish the form
    client.post(
        f"/forms/{form_id}/publish",
        headers={"Authorization": f"Bearer {auth_token}"},
    )

    # Submit a response via public endpoint
    submit_response = client.post(
        f"/public/forms/{form_id}/responses",
        json={
            "data": {"name": "Test User"},
        },
    )
    response_id = submit_response.json()["data"]["id"]

    # Delete the response
    delete_response = client.delete(
        f"/responses/{response_id}",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert delete_response.status_code == 200
    assert delete_response.json()["success"] == True
    assert "deleted successfully" in delete_response.json()["message"]

    # Verify response is gone (soft deleted)
    get_response = client.get(
        f"/responses/{response_id}",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert get_response.status_code == 404
