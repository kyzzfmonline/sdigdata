#!/usr/bin/env python3
"""
Detailed CORS testing for all endpoints.
"""

import requests
import json

BASE_URL = "http://localhost:8000"

def test_endpoint_cors(endpoint, method="GET", data=None, headers=None, description=""):
    """Test CORS for a specific endpoint."""
    print(f"\n🔍 Testing {description}: {method} {endpoint}")
    
    try:
        # Test preflight OPTIONS request
        options_headers = {
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": method,
            "Access-Control-Request-Headers": "Authorization,Content-Type",
        }
        
        options_response = requests.options(f"{BASE_URL}{endpoint}", headers=options_headers)
        
        if options_response.status_code == 200:
            print("  ✅ Preflight OPTIONS successful")
            cors_headers = {k: v for k, v in options_response.headers.items() if k.startswith("access-control")}
            for header, value in cors_headers.items():
                print(f"     {header}: {value}")
        else:
            print(f"  ❌ Preflight OPTIONS failed: {options_response.status_code}")
            return False
            
        # Test actual request
        request_headers = {
            "Origin": "http://localhost:3000",
            **(headers or {})
        }
        
        if method == "GET":
            response = requests.get(f"{BASE_URL}{endpoint}", headers=request_headers)
        elif method == "POST":
            response = requests.post(f"{BASE_URL}{endpoint}", json=data, headers=request_headers)
        else:
            print(f"  ⚠️  Skipping actual {method} request test")
            return True
            
        print(f"  ✅ Actual {method} request: {response.status_code}")
        
        # Check for CORS headers in response
        cors_headers = {k: v for k, v in response.headers.items() if k.startswith("access-control")}
        if cors_headers:
            print("  ✅ CORS headers present in response")
        else:
            print("  ⚠️  No CORS headers in response (may be expected for simple requests)")
            
        return True
        
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False

def main():
    """Run comprehensive CORS tests."""
    print("🚀 Starting detailed CORS tests...")
    
    endpoints_to_test = [
        ("/health", "GET", None, None, "Health check"),
        ("/cors-test", "GET", None, None, "CORS test endpoint"),
        ("/auth/login", "POST", {"username": "admin", "password": "admin123"}, None, "Authentication"),
        ("/responses", "GET", None, {"Authorization": "Bearer invalid"}, "Protected responses endpoint"),
        ("/forms", "GET", None, {"Authorization": "Bearer invalid"}, "Protected forms endpoint"),
        ("/public/forms/12345678-1234-1234-1234-123456789012", "GET", None, None, "Public form access"),
    ]
    
    failed_tests = 0
    
    for endpoint, method, data, headers, description in endpoints_to_test:
        if not test_endpoint_cors(endpoint, method, data, headers, description):
            failed_tests += 1
    
    print(f"\n{'='*50}")
    if failed_tests == 0:
        print("🎉 All CORS tests passed!")
        print("\n📋 If you're still getting CORS errors in your frontend:")
        print("   1. Make sure your frontend is running on http://localhost:3000 (or update the Origin header)")
        print("   2. Include credentials: true in your fetch requests")
        print("   3. Check that you're using the correct headers")
        print("   4. Try clearing browser cache and cookies")
        print("   5. Check browser dev tools Network tab for exact error details")
    else:
        print(f"❌ {failed_tests} CORS tests failed")
        print("\n🔧 Troubleshooting steps:")
        print("   1. Check that the backend is running on http://localhost:8000")
        print("   2. Verify the ENVIRONMENT variable is set to 'development'")
        print("   3. Check server logs for any CORS-related errors")
        print("   4. Ensure no other middleware is interfering with CORS")

if __name__ == "__main__":
    main()
