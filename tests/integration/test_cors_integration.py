#!/usr/bin/env python3
"""
Test CORS configuration for local development.
"""

import requests


def test_cors():
    """Test CORS configuration."""
    base_url = "http://localhost:8000"

    print("🔍 Testing CORS configuration...")

    # Test the CORS test endpoint
    try:
        response = requests.get(f"{base_url}/cors-test")
        if response.status_code == 200:
            data = response.json()
            print("✅ CORS test endpoint accessible")
            print(f"   Environment: {data['data']['environment']}")
            print(f"   Allowed origins: {data['data']['allowed_origins']}")
        else:
            print(f"❌ CORS test endpoint failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ CORS test endpoint error: {e}")
        return False

    # Test preflight request
    try:
        response = requests.options(
            f"{base_url}/auth/login",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Authorization,Content-Type",
            },
        )
        if response.status_code == 200:
            print("✅ Preflight request successful")
            cors_headers = {
                k: v
                for k, v in response.headers.items()
                if k.startswith("access-control")
            }
            for header, value in cors_headers.items():
                print(f"   {header}: {value}")
        else:
            print(f"❌ Preflight request failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Preflight request error: {e}")
        return False

    # Test actual API request with auth
    try:
        login_response = requests.post(
            f"{base_url}/auth/login", json={"username": "admin", "password": "admin123"}
        )
        if login_response.status_code == 200:
            print("✅ Authentication request successful")
            # Check if CORS headers are present
            cors_headers = {
                k: v
                for k, v in login_response.headers.items()
                if k.startswith("access-control")
            }
            if cors_headers:
                print("✅ CORS headers present in response")
            else:
                print(
                    "⚠️  No CORS headers in response (might be expected for simple requests)"
                )
        else:
            print(f"❌ Authentication request failed: {login_response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Authentication request error: {e}")
        return False

    print("\n🎉 CORS configuration appears to be working correctly!")
    print("\n📋 Frontend development tips:")
    print("   • Make sure your frontend is running on an allowed port")
    print("   • Include credentials: true in your fetch requests")
    print("   • The API allows all origins in development mode")
    print("   • Check browser dev tools for any remaining CORS errors")

    return True


if __name__ == "__main__":
    test_cors()
