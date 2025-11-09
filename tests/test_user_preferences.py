import pytest


class TestUserPreferences:
    """Test user preferences functionality."""

    def test_get_notification_preferences_unauthorized(self, client):
        """Test that unauthorized users can't access notification preferences."""
        response = client.get("/users/me/notifications")
        assert response.status_code == 401

    def test_get_theme_preferences_unauthorized(self, client):
        """Test that unauthorized users can't access theme preferences."""
        response = client.get("/users/me/preferences")
        assert response.status_code == 401

    def test_get_notification_preferences_authorized(self, client, auth_token):
        """Test getting notification preferences for authenticated user."""
        response = client.get(
            "/users/me/notifications", headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200

        data = response.json()
        assert data["success"] == True
        assert "data" in data

        prefs = data["data"]
        assert "email_notifications" in prefs
        assert "form_assignments" in prefs
        assert "responses" in prefs
        assert "system_updates" in prefs

        # All should be boolean
        assert isinstance(prefs["email_notifications"], bool)
        assert isinstance(prefs["form_assignments"], bool)
        assert isinstance(prefs["responses"], bool)
        assert isinstance(prefs["system_updates"], bool)

    def test_get_theme_preferences_authorized(self, client, auth_token):
        """Test getting theme preferences for authenticated user."""
        response = client.get(
            "/users/me/preferences", headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200

        data = response.json()
        assert data["success"] == True
        assert "data" in data

        prefs = data["data"]
        assert "theme" in prefs
        assert "compact_mode" in prefs

        # Theme should be one of the valid values
        assert prefs["theme"] in ["light", "dark", "system"]
        assert isinstance(prefs["compact_mode"], bool)

    def test_update_notification_preferences(self, client, auth_token):
        """Test updating notification preferences."""
        update_data = {
            "email_notifications": False,
            "form_assignments": True,
            "responses": False,
            "system_updates": True,
        }

        response = client.put(
            "/users/me/notifications",
            headers={"Authorization": f"Bearer {auth_token}"},
            json=update_data,
        )
        assert response.status_code == 200

        data = response.json()
        assert data["success"] == True
        assert "Preferences updated" in data["message"]

    def test_update_theme_preferences(self, client, auth_token):
        """Test updating theme preferences."""
        update_data = {"theme": "dark", "compact_mode": True}

        response = client.put(
            "/users/me/preferences",
            headers={"Authorization": f"Bearer {auth_token}"},
            json=update_data,
        )
        assert response.status_code == 200

        data = response.json()
        assert data["success"] == True
        assert "Preferences updated" in data["message"]

    def test_update_notification_preferences_partial(self, client, auth_token):
        """Test updating only some notification preferences."""
        update_data = {"email_notifications": False}

        response = client.put(
            "/users/me/notifications",
            headers={"Authorization": f"Bearer {auth_token}"},
            json=update_data,
        )
        assert response.status_code == 200

        data = response.json()
        assert data["success"] == True

    def test_update_theme_preferences_partial(self, client, auth_token):
        """Test updating only some theme preferences."""
        update_data = {"theme": "light"}

        response = client.put(
            "/users/me/preferences",
            headers={"Authorization": f"Bearer {auth_token}"},
            json=update_data,
        )
        assert response.status_code == 200

        data = response.json()
        assert data["success"] == True

    def test_update_notification_preferences_invalid_data(self, client, auth_token):
        """Test updating notification preferences with invalid data."""
        update_data = {"email_notifications": "not_a_boolean"}

        response = client.put(
            "/users/me/notifications",
            headers={"Authorization": f"Bearer {auth_token}"},
            json=update_data,
        )
        assert response.status_code == 422  # Validation error

    def test_update_theme_preferences_invalid_theme(self, client, auth_token):
        """Test updating theme preferences with invalid theme value."""
        update_data = {"theme": "invalid_theme"}

        response = client.put(
            "/users/me/preferences",
            headers={"Authorization": f"Bearer {auth_token}"},
            json=update_data,
        )
        assert response.status_code == 422  # Validation error

    def test_update_theme_preferences_invalid_compact_mode(self, client, auth_token):
        """Test updating theme preferences with invalid compact_mode value."""
        update_data = {"compact_mode": "not_a_boolean"}

        response = client.put(
            "/users/me/preferences",
            headers={"Authorization": f"Bearer {auth_token}"},
            json=update_data,
        )
        assert response.status_code == 422  # Validation error

    def test_preferences_persistence(self, client, auth_token):
        """Test that preferences are persisted correctly."""
        # Set specific preferences
        update_data = {
            "email_notifications": False,
            "theme": "dark",
            "compact_mode": True,
        }

        # Update notifications
        client.put(
            "/users/me/notifications",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={"email_notifications": update_data["email_notifications"]},
        )

        # Update theme
        client.put(
            "/users/me/preferences",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "theme": update_data["theme"],
                "compact_mode": update_data["compact_mode"],
            },
        )

        # Verify they were saved
        notif_response = client.get(
            "/users/me/notifications", headers={"Authorization": f"Bearer {auth_token}"}
        )
        theme_response = client.get(
            "/users/me/preferences", headers={"Authorization": f"Bearer {auth_token}"}
        )

        notif_data = notif_response.json()
        theme_data = theme_response.json()

        assert (
            notif_data["data"]["email_notifications"]
            == update_data["email_notifications"]
        )
        assert theme_data["data"]["theme"] == update_data["theme"]
        assert theme_data["data"]["compact_mode"] == update_data["compact_mode"]
