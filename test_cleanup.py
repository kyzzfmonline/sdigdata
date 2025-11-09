#!/usr/bin/env python3
"""
Test script for admin cleanup endpoints.
"""

import json
import urllib.request
import urllib.error

BASE_URL = "http://localhost:8000"


def test_cleanup_endpoints():
    """Test the admin cleanup endpoints."""

    print("Testing Admin Cleanup Endpoints")
    print("=" * 40)

    # First, login as admin to get token
    login_data = {"username": "admin", "password": "admin123"}

    try:
        req = urllib.request.Request(
            f"{BASE_URL}/auth/login",
            data=json.dumps(login_data).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urllib.request.urlopen(req) as response:
            login_response = json.loads(response.read().decode("utf-8"))
            token = login_response["data"]["access_token"]
            print("✅ Admin login successful")

    except Exception as e:
        print(f"❌ Admin login failed: {e}")
        return

    # Test headers with bearer token
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # Test cleanup endpoints
    endpoints = [
        ("DELETE", "/users/cleanup", "Users cleanup"),
        ("DELETE", "/forms/cleanup", "Forms cleanup"),
        ("DELETE", "/responses/cleanup", "Responses cleanup"),
    ]

    for method, endpoint, description in endpoints:
        print(f"\n🔍 Testing: {method} {endpoint} - {description}")

        try:
            req = urllib.request.Request(
                f"{BASE_URL}{endpoint}", headers=headers, method=method
            )

            with urllib.request.urlopen(req) as response:
                status_code = response.getcode()
                response_data = json.loads(response.read().decode("utf-8"))
                print(f"   Status: {status_code}")
                print(f"   Response: {response_data}")
                print("   ✅ Success")

        except urllib.error.HTTPError as e:
            print(f"   Status: {e.code}")
            print(f"   ❌ Failed: {e.read().decode('utf-8')[:200]}")
        except Exception as e:
            print(f"   ❌ Error: {str(e)}")


if __name__ == "__main__":
    test_cleanup_endpoints()
