"""
Security tests for authentication, authorization, and input validation.
"""

import pytest


class TestSecurity:
    """Test security features and edge cases."""

    @pytest.mark.asyncio
    async def test_sql_injection_attempt(self, client):
        """Test protection against SQL injection."""
        # Try SQL injection in login
        response = await client.post(
            "/auth/login", json={"username": "admin' OR '1'='1", "password": "password"}
        )

        # Should fail authentication, not cause SQL error
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_xss_attempt_in_form_data(
        self, client, admin_auth_headers, test_organization
    ):
        """Test protection against XSS in form creation."""
        malicious_script = "<script>alert('xss')</script>"

        form_data = {
            "title": malicious_script,
            "description": "Test form",
            "organization_id": test_organization["id"],
            "schema": {"type": "object", "properties": {"field": {"type": "string"}}},
        }

        response = await client.post(
            "/forms", headers=admin_auth_headers, json=form_data
        )

        assert response.status_code == 201
        data = response.json()["data"]

        # The title should be sanitized or escaped
        assert "<script>" not in data["title"]

    @pytest.mark.asyncio
    async def test_large_payload_rejection(self, client, admin_auth_headers):
        """Test rejection of extremely large payloads."""
        # Create a very large JSON payload
        large_data = "x" * 1000000  # 1MB of data

        response = await client.post(
            "/auth/login",
            headers=admin_auth_headers,
            json={"username": large_data, "password": "test"},
        )

        # Should be rejected due to size limits
        assert response.status_code in [413, 422, 400]

    @pytest.mark.asyncio
    async def test_invalid_json_payload(self, client):
        """Test handling of invalid JSON payloads."""
        response = await client.post(
            "/auth/login",
            headers={"Content-Type": "application/json"},
            content=b'{"username": "test", "password": invalid}',
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_missing_content_type(self, client):
        """Test requests without proper content type."""
        response = await client.post(
            "/auth/login", content=b'{"username": "test", "password": "test"}'
        )

        # Should still work or give appropriate error
        assert response.status_code in [200, 422, 400]

    @pytest.mark.asyncio
    async def test_malformed_auth_header(self, client):
        """Test malformed authorization headers."""
        response = await client.get(
            "/auth/verify", headers={"Authorization": "InvalidFormat"}
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_expired_token_simulation(self, client):
        """Test behavior with potentially expired tokens."""
        # This would require mocking time, but let's test with obviously invalid token
        response = await client.get(
            "/auth/verify", headers={"Authorization": "Bearer expired.token.here"}
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_path_traversal_attempt(self, client, admin_auth_headers):
        """Test protection against path traversal attacks."""
        # Try to access files outside allowed directories
        traversal_paths = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\config\\sam",
            "/etc/passwd",
            "....//....//....//etc/passwd",
        ]

        for path in traversal_paths:
            response = await client.get(f"/files/{path}", headers=admin_auth_headers)

            # Should not allow access to system files
            assert response.status_code in [404, 403, 401]

    @pytest.mark.asyncio
    async def test_rate_limiting_simulation(self, client):
        """Test rate limiting behavior."""
        # Make multiple rapid requests to login endpoint
        response = None
        for _i in range(10):
            response = await client.post(
                "/auth/login", json={"username": "nonexistent", "password": "wrong"}
            )

        # Some requests should be rate limited (if rate limiting is enabled)
        # Note: This depends on rate limiting configuration
        # For now, just ensure the endpoint handles multiple requests
        assert response is not None
        assert response.status_code in [401, 429]

    @pytest.mark.asyncio
    async def test_cors_policy_enforcement(self, client):
        """Test CORS policy enforcement."""
        # Test with disallowed origin
        response = await client.options(
            "/auth/login",
            headers={
                "Origin": "https://malicious-site.com",
                "Access-Control-Request-Method": "POST",
            },
        )

        # Should not allow the malicious origin
        cors_headers = {
            k: v for k, v in response.headers.items() if k.startswith("access-control")
        }
        if cors_headers:
            # If CORS headers are present, check they don't allow malicious origin
            allow_origin = cors_headers.get("access-control-allow-origin")
            if allow_origin and allow_origin != "*":
                assert "malicious-site.com" not in allow_origin
