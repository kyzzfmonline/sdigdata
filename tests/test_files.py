"""
Tests for file upload routes.
"""

import pytest
from unittest.mock import patch


def test_get_presigned_url(client, auth_token):
    """
    Test getting a presigned URL for file upload.
    """
    with patch("app.api.routes.files.generate_presigned_url") as mock_generate_url:
        mock_generate_url.return_value = {
            "upload_url": "https://example.com/upload",
            "file_url": "https://example.com/file",
        }

        response = client.post(
            "/files/presign",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={"filename": "test.jpg", "content_type": "image/jpeg"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "upload_url" in data
        assert "file_url" in data
        mock_generate_url.assert_called_once()


def test_get_presigned_url_unauthorized(client):
    """
    Test that getting a presigned URL requires authentication.
    """
    response = client.post(
        "/files/presign",
        json={"filename": "test.jpg", "content_type": "image/jpeg"},
    )
    assert response.status_code == 403
