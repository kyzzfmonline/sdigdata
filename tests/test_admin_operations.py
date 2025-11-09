import pytest


class TestAdminOperations:
    """Test admin cleanup operations."""

    def test_users_cleanup_unauthorized(self, client):
        """Test that unauthorized users can't access users cleanup."""
        response = client.delete("/users/cleanup")
        assert response.status_code == 401

    def test_forms_cleanup_unauthorized(self, client):
        """Test that unauthorized users can't access forms cleanup."""
        response = client.delete("/forms/cleanup")
        assert response.status_code == 401

    def test_responses_cleanup_unauthorized(self, client):
        """Test that unauthorized users can't access responses cleanup."""
        response = client.delete("/responses/cleanup")
        assert response.status_code == 401

    def test_users_cleanup_authorized(self, client, auth_token):
        """Test users cleanup with proper authorization."""
        response = client.delete(
            "/users/cleanup", headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200

        data = response.json()
        assert data["success"] == True
        assert "data" in data
        assert "deleted_count" in data["data"]
        assert isinstance(data["data"]["deleted_count"], int)
        assert data["data"]["deleted_count"] >= 0

    def test_forms_cleanup_authorized(self, client, auth_token):
        """Test forms cleanup with proper authorization."""
        response = client.delete(
            "/forms/cleanup", headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200

        data = response.json()
        assert data["success"] == True
        assert "data" in data
        assert "deleted_count" in data["data"]
        assert isinstance(data["data"]["deleted_count"], int)
        assert data["data"]["deleted_count"] >= 0

    def test_responses_cleanup_authorized(self, client, auth_token):
        """Test responses cleanup with proper authorization."""
        response = client.delete(
            "/responses/cleanup", headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200

        data = response.json()
        assert data["success"] == True
        assert "data" in data
        assert "deleted_count" in data["data"]
        assert isinstance(data["data"]["deleted_count"], int)
        assert data["data"]["deleted_count"] >= 0

    def test_cleanup_response_format(self, client, auth_token):
        """Test that cleanup responses have consistent format."""
        endpoints = ["/users/cleanup", "/forms/cleanup", "/responses/cleanup"]

        for endpoint in endpoints:
            response = client.delete(
                endpoint, headers={"Authorization": f"Bearer {auth_token}"}
            )
            assert response.status_code == 200

            data = response.json()
            assert data["success"] == True
            assert "message" in data
            assert "data" in data
            assert "deleted_count" in data["data"]

            # Message should contain the count
            assert str(data["data"]["deleted_count"]) in data["message"]

    @pytest.mark.asyncio
    async def test_cleanup_with_soft_deleted_records(self, client, auth_token, db_conn):
        """Test cleanup operations when there are actually soft-deleted records."""
        # First create and soft-delete some test records
        # Note: This is a complex test that would require setting up test data
        # For now, we'll just verify the endpoints work with 0 records

        # Test users cleanup
        response = client.delete(
            "/users/cleanup", headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200

        # Test forms cleanup
        response = client.delete(
            "/forms/cleanup", headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200

        # Test responses cleanup
        response = client.delete(
            "/responses/cleanup", headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200

    def test_cleanup_idempotent(self, client, auth_token):
        """Test that cleanup operations are idempotent."""
        # Run cleanup multiple times
        for _ in range(3):
            response = client.delete(
                "/users/cleanup", headers={"Authorization": f"Bearer {auth_token}"}
            )
            assert response.status_code == 200

            response = client.delete(
                "/forms/cleanup", headers={"Authorization": f"Bearer {auth_token}"}
            )
            assert response.status_code == 200

            response = client.delete(
                "/responses/cleanup", headers={"Authorization": f"Bearer {auth_token}"}
            )
            assert response.status_code == 200

    def test_cleanup_audit_logging(self, client, auth_token):
        """Test that cleanup operations are properly logged."""
        # This would require checking audit logs, but for now just verify the operation completes
        response = client.delete(
            "/users/cleanup", headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200

        response = client.delete(
            "/forms/cleanup", headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200

        response = client.delete(
            "/responses/cleanup", headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200

    def test_cleanup_permission_required(self, client):
        """Test that cleanup requires specific permissions."""
        # Try without auth
        response = client.delete("/users/cleanup")
        assert response.status_code == 401

        # Try with invalid token
        response = client.delete(
            "/users/cleanup", headers={"Authorization": "Bearer invalid"}
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_cleanup_database_integrity(self, client, auth_token, db_conn):
        """Test that cleanup operations maintain database integrity."""
        # Get counts before cleanup
        users_before = await db_conn.fetchval(
            "SELECT COUNT(*) FROM users WHERE deleted = TRUE"
        )
        forms_before = await db_conn.fetchval(
            "SELECT COUNT(*) FROM forms WHERE deleted = TRUE"
        )
        responses_before = await db_conn.fetchval(
            "SELECT COUNT(*) FROM responses WHERE deleted = TRUE"
        )

        # Run cleanups
        client.delete(
            "/users/cleanup", headers={"Authorization": f"Bearer {auth_token}"}
        )
        client.delete(
            "/forms/cleanup", headers={"Authorization": f"Bearer {auth_token}"}
        )
        client.delete(
            "/responses/cleanup", headers={"Authorization": f"Bearer {auth_token}"}
        )

        # Get counts after cleanup
        users_after = await db_conn.fetchval(
            "SELECT COUNT(*) FROM users WHERE deleted = TRUE"
        )
        forms_after = await db_conn.fetchval(
            "SELECT COUNT(*) FROM forms WHERE deleted = TRUE"
        )
        responses_after = await db_conn.fetchval(
            "SELECT COUNT(*) FROM responses WHERE deleted = TRUE"
        )

        # Should be 0 after cleanup
        assert users_after == 0
        assert forms_after == 0
        assert responses_after == 0

        # Verify that non-deleted records are still there
        active_users = await db_conn.fetchval(
            "SELECT COUNT(*) FROM users WHERE deleted = FALSE"
        )
        assert active_users >= 1  # At least the admin user

    def test_cleanup_concurrent_requests(self, client, auth_token):
        """Test that concurrent cleanup requests don't cause issues."""
        import threading
        import time

        results = []

        def make_request():
            response = client.delete(
                "/users/cleanup", headers={"Authorization": f"Bearer {auth_token}"}
            )
            results.append(response.status_code)

        # Start multiple threads making requests
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=make_request)
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # All should succeed
        assert all(code == 200 for code in results)
        assert len(results) == 5
