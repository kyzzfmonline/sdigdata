import pytest
import json
import tempfile
import os
import time
import httpx


@pytest.mark.asyncio
async def test_public_form_access(client):
    """Test public form retrieval."""
    print("Testing public form access...")

    # First, try to create an admin user and login
    bootstrap_response = await client.post(
        "/auth/bootstrap-admin",
        json={"username": "admin", "password": "SecurePass123!"},
    )

    login_response = await client.post(
        "/auth/login",
        json={"username": "admin", "password": "SecurePass123!"},
    )

    if login_response.status_code != 200:
        print("❌ Admin login failed - trying with existing admin")
        # Try with default admin credentials
        login_response = await client.post(
            "/auth/login", json={"username": "admin", "password": "admin123"}
        )
        if login_response.status_code != 200:
            print("❌ All admin login attempts failed")
            assert False, "Admin login failed"

    token = login_response.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Create a test organization
    org_response = await client.post(
        "/organizations",
        headers=headers,
        json={
            "name": "Test Organization",
            "logo_url": None,
            "primary_color": "#0066CC",
        },
    )

    if org_response.status_code != 201:
        print("❌ Organization creation failed")
        print(f"Response: {org_response.text}")
        assert False, "Organization creation failed"

    org_data = org_response.json()["data"]
    org_id = org_data["id"]

    # Create a test form
    form_response = await client.post(
        "/forms",
        headers=headers,
        json={
            "title": "Public Test Survey",
            "organization_id": org_id,
            "status": "published",
            "form_schema": {
                "branding": {
                    "logo_url": "https://example.com/logo.png",
                    "primary_color": "#0066CC",
                    "header_text": "Test Organization",
                    "footer_text": "Thank you for participating",
                },
                "fields": [
                    {
                        "id": "name",
                        "type": "text",
                        "label": "Full Name",
                        "required": True,
                    },
                    {"id": "age", "type": "number", "label": "Age", "required": True},
                ],
            },
        },
    )

    if form_response.status_code != 201:
        print("❌ Form creation failed")
        print(f"Response: {form_response.text}")
        assert False, "Form creation failed"

    form_data = form_response.json()["data"]
    form_id = form_data["id"]

    print(f"✅ Created test form: {form_id}")

    # Test public form access (no authentication required)
    public_form_response = await client.get(f"/public/forms/{form_id}")

    if public_form_response.status_code != 200:
        print("❌ Public form access failed")
        print(f"Response: {public_form_response.text}")
        assert False, "Public form access failed"

    public_form_data = public_form_response.json()["data"]

    # Verify the response structure
    required_fields = ["id", "title", "schema", "status", "version"]
    for field in required_fields:
        if field not in public_form_data:
            print(f"❌ Missing field in public form response: {field}")
            assert False, f"Missing field in public form response: {field}"

    # Verify sensitive data is excluded
    sensitive_fields = ["created_by", "organization_id"]
    for field in sensitive_fields:
        if field in public_form_data:
            print(f"❌ Sensitive field exposed in public response: {field}")
            assert False, f"Sensitive field exposed in public response: {field}"

    print("✅ Public form access working correctly")
    return form_id


@pytest.mark.asyncio
async def test_anonymous_submission(client):
    """Test anonymous response submission."""
    print("Testing anonymous submission...")

    # First get a form ID by creating a form
    bootstrap_response = await client.post(
        "/auth/bootstrap-admin",
        json={"username": "admin", "password": "SecurePass123!"},
    )

    login_response = await client.post(
        "/auth/login",
        json={"username": "admin", "password": "SecurePass123!"},
    )

    admin_token = login_response.json().get("access_token")
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Create a test organization
    org_response = await client.post(
        "/organizations",
        headers=headers,
        json={
            "name": "Anon Submission Org",
            "logo_url": None,
            "primary_color": "#0066CC",
        },
    )
    org_id = org_response.json()["data"]["id"]

    # Create a test form
    form_data = {
        "title": "Test Public Form",
        "organization_id": org_id,
        "description": "A test form for anonymous submissions",
        "form_schema": {
            "type": "object",
            "properties": {"name": {"type": "string"}, "age": {"type": "number"}},
            "required": ["name"],
        },
        "status": "published",
    }

    form_response = await client.post(
        "/forms",
        json=form_data,
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    if form_response.status_code != 201:
        print(f"❌ Form creation failed: {form_response.status_code}")
        assert False, "Form creation failed"

    form_id = form_response.json()["data"]["id"]
    print(f"Created test form with ID: {form_id}")

    # Test rate limiting by making multiple submissions quickly
    submission_data = {"data": {"name": "John Doe", "age": 30}, "attachments": {}}

    # Make multiple submissions to test rate limiting
    successful_submissions = 0
    rate_limited = False

    for i in range(15):  # Try up to 15 submissions
        response = await client.post(
            f"/public/forms/{form_id}/responses", json=submission_data
        )

        if response.status_code == 200:
            successful_submissions += 1
            print(f"✅ Submission {i + 1} successful")
        elif response.status_code == 429:
            rate_limited = True
            print(f"✅ Rate limiting triggered on submission {i + 1}")
            break
        else:
            print(
                f"❌ Submission {i + 1} failed with unexpected status: {response.status_code}"
            )
            print(f"Response: {response.text}")
            assert False, "Submission failed with unexpected status"

        # Small delay to avoid overwhelming
        time.sleep(0.1)

    assert successful_submissions >= 5 and rate_limited, f"Expected at least 5 successful submissions and rate limiting, got {successful_submissions} successes, rate_limited={rate_limited}"
    print("✅ Anonymous submission and rate limiting working correctly")


@pytest.mark.asyncio
async def test_file_upload_integration(client, auth_token):
    """Test that file uploads work with anonymous submissions."""
    print("Testing file upload integration...")

    # Create a dummy file for upload
    file_content = b"test file content"
    file_name = "test_upload.txt"
    content_type = "text/plain"

    # 1. Get a presigned URL
    presign_response = await client.post(
        "/files/presign",
        headers={"Authorization": f"Bearer {auth_token}"},
        json={"filename": file_name, "content_type": content_type},
    )
    assert presign_response.status_code == 200
    presign_data = presign_response.json()["data"]
    upload_url = presign_data["upload_url"]
    file_url = presign_data["file_url"]

    # 2. Upload the file to the presigned URL
    upload_response = await client.put(
        upload_url,
        headers={"Content-Type": content_type},
        content=file_content,
    )
    assert upload_response.status_code == 200

    print("✅ File upload integration test completed.")
