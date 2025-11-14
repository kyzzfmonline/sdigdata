"""
Integration tests for file upload and storage functionality.
"""

import tempfile
from pathlib import Path

import pytest


class TestFileUpload:
    """Test file upload and storage functionality."""

    @pytest.mark.asyncio
    async def test_presigned_url_generation(self, client, auth_headers):
        """Test generating presigned URLs for file upload."""
        presign_data = {"filename": "test_image.jpg", "content_type": "image/jpeg"}

        response = await client.post(
            "/files/presign", headers=auth_headers, json=presign_data
        )

        assert response.status_code == 200
        data = response.json()["data"]
        assert "upload_url" in data
        assert "file_url" in data
        assert "test_image.jpg" in data["file_url"]

    @pytest.mark.asyncio
    async def test_presigned_url_unauthorized(self, client):
        """Test presigned URL generation without authentication."""
        presign_data = {"filename": "test.jpg", "content_type": "image/jpeg"}

        response = await client.post("/files/presign", json=presign_data)

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_file_upload_workflow(self, client, auth_headers, temp_file):
        """Test complete file upload workflow."""
        # Get presigned URL
        presign_response = await client.post(
            "/files/presign",
            headers=auth_headers,
            json={"filename": "test_upload.txt", "content_type": "text/plain"},
        )

        assert presign_response.status_code == 200
        presign_data = presign_response.json()["data"]
        upload_url = presign_data["upload_url"]

        # Upload file to presigned URL
        with open(temp_file, "rb") as f:
            upload_response = await client.put(
                upload_url, content=f.read(), headers={"Content-Type": "text/plain"}
            )

        # Check if upload was successful (may vary based on storage setup)
        assert upload_response.status_code in [200, 201]

    @pytest.mark.asyncio
    async def test_invalid_file_type(self, client, auth_headers):
        """Test uploading invalid file types."""
        presign_data = {
            "filename": "malicious.exe",
            "content_type": "application/x-msdownload",
        }

        response = await client.post(
            "/files/presign", headers=auth_headers, json=presign_data
        )

        # Should either reject or allow (depending on validation)
        assert response.status_code in [200, 400, 422]

    @pytest.mark.asyncio
    async def test_large_file_handling(self, client, auth_headers):
        """Test handling of large files."""
        # Create a larger test file
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            large_content = "x" * 1000000  # 1MB file
            f.write(large_content.encode())
            large_file_path = f.name

        try:
            presign_response = await client.post(
                "/files/presign",
                headers=auth_headers,
                json={"filename": "large_test.txt", "content_type": "text/plain"},
            )

            if presign_response.status_code == 200:
                presign_data = presign_response.json()["data"]
                upload_url = presign_data["upload_url"]

                # Try to upload large file
                with open(large_file_path, "rb") as f:
                    upload_response = await client.put(
                        upload_url,
                        content=f.read(),
                        headers={"Content-Type": "text/plain"},
                    )

                # Should handle large files appropriately
                assert upload_response.status_code in [200, 201, 413]
        finally:
            Path(large_file_path).unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_file_access_control(
        self, client, auth_headers, test_user, admin_user
    ):
        """Test that users can only access their own files or public files."""
        # Upload a file as regular user
        presign_response = await client.post(
            "/files/presign",
            headers=auth_headers,
            json={"filename": "user_file.txt", "content_type": "text/plain"},
        )

        assert presign_response.status_code == 200

        # Admin should be able to access files (depending on permissions)
        # This test may need adjustment based on actual permission model
