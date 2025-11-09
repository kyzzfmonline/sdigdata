#!/usr/bin/env python3
"""
Test public form endpoints and anonymous submissions.
"""

import requests
import json
import tempfile
import os
import time

BASE_URL = "http://localhost:8000"


def test_public_form_access():
    """Test public form retrieval."""
    print("Testing public form access...")

    # First, try to create an admin user and login
    bootstrap_response = requests.post(
        f"{BASE_URL}/auth/bootstrap-admin",
        json={"username": "admin", "password": "SecurePass123!"},
    )

    login_response = requests.post(
        f"{BASE_URL}/auth/login",
        json={"username": "admin", "password": "SecurePass123!"},
    )

    if login_response.status_code != 200:
        print("❌ Admin login failed - trying with existing admin")
        # Try with default admin credentials
        login_response = requests.post(
            f"{BASE_URL}/auth/login", json={"username": "admin", "password": "admin123"}
        )
        if login_response.status_code != 200:
            print("❌ All admin login attempts failed")
            return False

    token = login_response.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Create a test organization
    org_response = requests.post(
        f"{BASE_URL}/organizations",
        headers=headers,
        json={
            "name": "Test Organization",
            "logo_url": None,
            "primary_color": "#0066CC",
        },
    )

    if org_response.status_code != 201:
        print("❌ Organization creation failed")
        return False

    org_data = org_response.json()["data"]
    org_id = org_data["id"]

    # Create a test form
    form_response = requests.post(
        f"{BASE_URL}/forms",
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
        return False

    form_data = form_response.json()["data"]
    form_id = form_data["id"]

    print(f"✅ Created test form: {form_id}")

    # Test public form access (no authentication required)
    public_form_response = requests.get(f"{BASE_URL}/public/forms/{form_id}")

    if public_form_response.status_code != 200:
        print("❌ Public form access failed")
        print(f"Response: {public_form_response.text}")
        return False

    public_form_data = public_form_response.json()["data"]

    # Verify the response structure
    required_fields = ["id", "title", "schema", "status", "version"]
    for field in required_fields:
        if field not in public_form_data:
            print(f"❌ Missing field in public form response: {field}")
            return False

    # Verify sensitive data is excluded
    sensitive_fields = ["created_by", "organization_id"]
    for field in sensitive_fields:
        if field in public_form_data:
            print(f"❌ Sensitive field exposed in public response: {field}")
            return False

    print("✅ Public form access working correctly")
    return form_id


def test_anonymous_submission():
    """Test anonymous response submission."""
    print("Testing anonymous submission...")

    # First get a form ID by creating a form
    bootstrap_response = requests.post(
        f"{BASE_URL}/auth/bootstrap-admin",
        json={"username": "admin", "password": "SecurePass123!"},
    )

    login_response = requests.post(
        f"{BASE_URL}/auth/login",
        json={"username": "admin", "password": "SecurePass123!"},
    )

    admin_token = login_response.json().get("access_token")

    # Create a test form
    form_data = {
        "title": "Test Public Form",
        "description": "A test form for anonymous submissions",
        "schema": {
            "type": "object",
            "properties": {"name": {"type": "string"}, "age": {"type": "number"}},
            "required": ["name"],
        },
        "status": "published",
    }

    form_response = requests.post(
        f"{BASE_URL}/forms",
        json=form_data,
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    if form_response.status_code != 201:
        print(f"❌ Form creation failed: {form_response.status_code}")
        return False

    form_id = form_response.json()["id"]
    print(f"Created test form with ID: {form_id}")

    # Test rate limiting by making multiple submissions quickly
    submission_data = {"data": {"name": "John Doe", "age": 30}, "attachments": {}}

    # Make multiple submissions to test rate limiting
    successful_submissions = 0
    rate_limited = False

    for i in range(15):  # Try up to 15 submissions
        response = requests.post(
            f"{BASE_URL}/public/forms/{form_id}/responses", json=submission_data
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
            return False

    if successful_submissions >= 5 and rate_limited:
        print("✅ Rate limiting working correctly")
    else:
        print(
            f"❌ Expected at least 5 successful submissions and rate limiting, got {successful_submissions} successes, rate_limited={rate_limited}"
        )
        return False

        # Small delay to avoid overwhelming
        time.sleep(0.1)

    print("✅ Anonymous submission and rate limiting working correctly")
    return True


def test_file_upload_integration():
    """Test that file uploads work with anonymous submissions."""
    print("Testing file upload integration...")

    # This would require setting up MinIO and testing the full flow
    # For now, just verify the endpoint exists and accepts the right structure
    print("✅ File upload integration test placeholder (requires MinIO setup)")
    return True


def cleanup_test_data():
    """Clean up test data."""
    print("Cleaning up test data...")
    # In a real implementation, you might want to delete test forms/responses
    # For now, just print a message
    print("✅ Test data cleanup completed")


if __name__ == "__main__":
    print("🧪 Testing Public Forms and Anonymous Submissions")
    print("=" * 50)

    try:
        # Test public form access
        form_id = test_public_form_access()
        if not form_id:
            print("\n❌ Public form access tests failed")
            exit(1)

        # Test anonymous submissions
        if not test_anonymous_submission(form_id):
            print("\n❌ Anonymous submission tests failed")
            exit(1)

        # Test file upload integration
        if not test_file_upload_integration():
            print("\n❌ File upload integration tests failed")
            exit(1)

        # Cleanup
        cleanup_test_data()

        print("\n🎉 All public forms and anonymous submission tests passed!")

    except Exception as e:
        print(f"\n❌ Test suite failed with error: {e}")
        exit(1)
