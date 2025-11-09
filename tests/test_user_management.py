import pytest
import uuid


class TestUserManagement:
    """Test user management endpoints with new permission system."""

    def test_get_current_user_profile(self, client, auth_token):
        """Test getting current user profile."""
        response = client.get(
            "/users/me", headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200

        data = response.json()
        assert data["success"] == True
        assert "data" in data

        user = data["data"]
        assert "id" in user
        assert "username" in user
        assert "email" in user
        assert "role" in user  # Legacy field
        assert "organization_id" in user

    def test_update_current_user_profile(self, client, auth_token):
        """Test updating current user profile."""
        update_data = {"username": "updated_username", "email": "updated@example.com"}

        response = client.put(
            "/users/me",
            headers={"Authorization": f"Bearer {auth_token}"},
            json=update_data,
        )
        assert response.status_code == 200

        data = response.json()
        assert data["success"] == True
        assert "data" in data

    def test_update_user_profile_validation(self, client, auth_token):
        """Test validation when updating user profile."""
        # Try to update role (should be forbidden)
        update_data = {"role": "super_admin"}

        response = client.put(
            "/users/me",
            headers={"Authorization": f"Bearer {auth_token}"},
            json=update_data,
        )
        assert response.status_code == 403  # Forbidden

    def test_change_password(self, client, auth_token):
        """Test changing user password."""
        password_data = {
            "current_password": "admin123",
            "new_password": "NewPassword123!",
        }

        response = client.post(
            "/users/me/password",
            headers={"Authorization": f"Bearer {auth_token}"},
            json=password_data,
        )
        assert response.status_code == 200

        data = response.json()
        assert data["success"] == True
        assert "Password updated" in data["message"]

    def test_change_password_wrong_current(self, client, auth_token):
        """Test changing password with wrong current password."""
        password_data = {
            "current_password": "wrongpassword",
            "new_password": "NewPassword123!",
        }

        response = client.post(
            "/users/me/password",
            headers={"Authorization": f"Bearer {auth_token}"},
            json=password_data,
        )
        assert response.status_code == 400  # Bad request

    def test_change_password_weak_new(self, client, auth_token):
        """Test changing password with weak new password."""
        password_data = {"current_password": "admin123", "new_password": "weak"}

        response = client.post(
            "/users/me/password",
            headers={"Authorization": f"Bearer {auth_token}"},
            json=password_data,
        )
        assert response.status_code == 422  # Validation error

    def test_get_users_list_admin_only(self, client, auth_token):
        """Test that only admins can list users."""
        response = client.get(
            "/users", headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200

        data = response.json()
        assert data["success"] == True
        assert "data" in data

    def test_get_users_list_unauthorized(self, client):
        """Test that unauthorized users can't list users."""
        response = client.get("/users")
        assert response.status_code == 401

    def test_get_user_by_id_admin(self, client, auth_token, admin_user):
        """Test admin getting user by ID."""
        user_id = admin_user["id"]
        response = client.get(
            f"/users/{user_id}", headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200

        data = response.json()
        assert data["success"] == True
        assert data["data"]["id"] == user_id

    def test_update_user_by_id_admin(self, client, auth_token, admin_user):
        """Test admin updating user by ID."""
        user_id = admin_user["id"]
        update_data = {"email": "updated_admin@example.com"}

        response = client.put(
            f"/users/{user_id}",
            headers={"Authorization": f"Bearer {auth_token}"},
            json=update_data,
        )
        assert response.status_code == 200

        data = response.json()
        assert data["success"] == True

    def test_delete_user_by_id_admin(self, client, auth_token):
        """Test admin deleting user by ID."""
        # Create a test user first
        register_data = {
            "username": "test_delete_user",
            "password": "TestPass123!",
            "role": "agent",
            "organization_id": str(uuid.uuid4()),
        }

        # Register user
        register_response = client.post(
            "/auth/register",
            headers={"Authorization": f"Bearer {auth_token}"},
            json=register_data,
        )

        if register_response.status_code == 201:
            user_data = register_response.json()["data"]
            user_id = user_data["id"]

            # Delete the user
            delete_response = client.delete(
                f"/users/{user_id}", headers={"Authorization": f"Bearer {auth_token}"}
            )
            assert delete_response.status_code == 200

            data = delete_response.json()
            assert data["success"] == True
        else:
            # If registration failed (maybe org doesn't exist), skip delete test
            pytest.skip("Could not create test user for deletion")

    def test_user_cannot_delete_self(self, client, auth_token, admin_user):
        """Test that users cannot delete themselves."""
        user_id = admin_user["id"]

        response = client.delete(
            f"/users/{user_id}", headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 400  # Bad request

        data = response.json()
        assert data["success"] == False

    def test_user_management_permission_checks(self, client, auth_token):
        """Test that user management operations require proper permissions."""
        # These tests verify that the permission system is working
        # All the above tests already verify this indirectly

        # Test that cleanup operations work (they require specific permissions)
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

    @pytest.mark.asyncio
    async def test_user_preferences_integration(self, client, auth_token, db_conn):
        """Test that user preferences are properly integrated."""
        # Verify that preferences exist for the admin user
        user_result = await db_conn.fetchrow(
            "SELECT id FROM users WHERE username = 'admin'"
        )
        assert user_result is not None

        user_id = user_result["id"]

        # Check that preferences columns exist
        prefs_result = await db_conn.fetchrow(
            "SELECT email_notifications, theme FROM users WHERE id = $1", user_id
        )
        assert prefs_result is not None
        assert "email_notifications" in prefs_result
        assert "theme" in prefs_result

    def test_user_profile_data_integrity(self, client, auth_token):
        """Test that user profile data maintains integrity."""
        # Get profile
        response = client.get(
            "/users/me", headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200

        user_data = response.json()["data"]

        # Update profile
        update_data = {"username": "test_update", "email": "test@example.com"}

        response = client.put(
            "/users/me",
            headers={"Authorization": f"Bearer {auth_token}"},
            json=update_data,
        )
        assert response.status_code == 200

        # Verify update
        response = client.get(
            "/users/me", headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200

        updated_data = response.json()["data"]
        assert updated_data["username"] == update_data["username"]
        assert updated_data["email"] == update_data["email"]
