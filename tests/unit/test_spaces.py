"""
Unit tests for Spaces utility functions.
"""

from unittest.mock import MagicMock, patch

import pytest

from app.utils.spaces import ensure_bucket_exists, generate_presigned_url, get_s3_client


class TestSpacesUtils:
    """Test Spaces utility functions."""

    @patch("app.utils.spaces.boto3.client")
    @patch("app.core.config.get_settings")
    def test_get_s3_client(self, mock_get_settings, mock_boto3_client):
        """Test S3 client creation."""
        mock_settings = MagicMock()
        mock_settings.SPACES_ENDPOINT = "https://spaces.example.com"
        mock_settings.SPACES_KEY = "test_key"
        mock_settings.SPACES_SECRET = "test_secret"
        mock_settings.SPACES_REGION = "us-east-1"
        mock_get_settings.return_value = mock_settings

        mock_client = MagicMock()
        mock_boto3_client.return_value = mock_client

        result = get_s3_client()

        assert result == mock_client
        mock_boto3_client.assert_called_once_with(
            "s3",
            endpoint_url="https://spaces.example.com",
            aws_access_key_id="test_key",
            aws_secret_access_key="test_secret",
            region_name="us-east-1",
            config=mock_boto3_client.call_args[1]["config"],
        )

    @patch("app.utils.spaces.boto3.client")
    @patch("app.core.config.get_settings")
    @patch("app.utils.spaces.settings")
    def test_generate_presigned_url_docker_endpoint(
        self, mock_settings_global, mock_get_settings, mock_boto3_client
    ):
        """Test presigned URL generation with Docker endpoint."""
        mock_settings = MagicMock()
        mock_settings.SPACES_ENDPOINT = "https://host.docker.internal:9000"
        mock_settings.SPACES_KEY = "test_key"
        mock_settings.SPACES_SECRET = "test_secret"
        mock_settings.SPACES_REGION = "us-east-1"
        mock_settings.SPACES_BUCKET = "test-bucket"
        mock_get_settings.return_value = mock_settings
        mock_settings_global.SPACES_BUCKET = "test-bucket"

        mock_client = MagicMock()
        mock_client.generate_presigned_url.return_value = (
            "https://presigned-url.example.com"
        )
        mock_boto3_client.return_value = mock_client

        result = generate_presigned_url("test-file.jpg", "image/jpeg")

        # Should replace host.docker.internal with localhost for URL
        assert result["file_url"] == "https://localhost:9000/test-bucket/test-file.jpg"

    @patch("app.utils.spaces.boto3.client")
    @patch("app.core.config.get_settings")
    @patch("app.utils.spaces.settings")
    def test_generate_presigned_url(
        self, mock_settings_global, mock_get_settings, mock_boto3_client
    ):
        """Test presigned URL generation."""
        mock_settings = MagicMock()
        mock_settings.SPACES_ENDPOINT = (
            "https://test-bucket.us-east-1.digitaloceanspaces.com"
        )
        mock_settings.SPACES_KEY = "test_key"
        mock_settings.SPACES_SECRET = "test_secret"
        mock_settings.SPACES_REGION = "us-east-1"
        mock_settings.SPACES_BUCKET = "test-bucket"
        mock_get_settings.return_value = mock_settings
        mock_settings_global.SPACES_BUCKET = "test-bucket"
        mock_settings_global.SPACES_REGION = "us-east-1"
        mock_settings_global.SPACES_ENDPOINT = "https://host.docker.internal:9000"
        mock_settings_global.SPACES_ENDPOINT = (
            "https://test-bucket.us-east-1.digitaloceanspaces.com"
        )

        mock_client = MagicMock()
        mock_client.generate_presigned_url.return_value = (
            "https://presigned-url.example.com"
        )
        mock_boto3_client.return_value = mock_client

        result = generate_presigned_url("test-file.jpg", "image/jpeg", 1800)

        assert result["upload_url"] == "https://presigned-url.example.com"
        assert (
            result["file_url"]
            == "https://test-bucket.us-east-1.digitaloceanspaces.com/test-file.jpg"
        )

        # Verify generate_presigned_url was called correctly
        mock_client.generate_presigned_url.assert_called_once_with(
            "put_object",
            Params={
                "Bucket": "test-bucket",
                "Key": "test-file.jpg",
                "ContentType": "image/jpeg",
            },
            ExpiresIn=1800,
            HttpMethod="PUT",
        )

    @patch("app.utils.spaces.get_s3_client")
    @patch("app.core.config.get_settings")
    def test_ensure_bucket_exists_bucket_exists(
        self, mock_get_settings, mock_get_s3_client
    ):
        """Test ensuring bucket exists when bucket already exists."""
        mock_settings = MagicMock()
        mock_settings.SPACES_BUCKET = "test-bucket"
        mock_get_settings.return_value = mock_settings

        mock_client = MagicMock()
        # Simulate bucket exists (no exception)
        mock_client.head_bucket.return_value = None
        mock_get_s3_client.return_value = mock_client

        ensure_bucket_exists()

        mock_client.head_bucket.assert_called_once_with(Bucket="test-bucket")
        mock_client.create_bucket.assert_not_called()

    @patch("app.utils.spaces.get_s3_client")
    @patch("app.core.config.get_settings")
    def test_ensure_bucket_exists_bucket_not_exists(
        self, mock_get_settings, mock_get_s3_client
    ):
        """Test ensuring bucket exists when bucket doesn't exist."""
        mock_settings = MagicMock()
        mock_settings.SPACES_BUCKET = "test-bucket"
        mock_get_settings.return_value = mock_settings

        mock_client = MagicMock()
        # Simulate bucket doesn't exist
        from botocore.exceptions import ClientError

        error = ClientError({"Error": {"Code": "NoSuchBucket"}}, "HeadBucket")
        mock_client.head_bucket.side_effect = error
        mock_client.create_bucket.return_value = None
        mock_get_s3_client.return_value = mock_client

        ensure_bucket_exists()

        mock_client.head_bucket.assert_called_once_with(Bucket="test-bucket")
        mock_client.create_bucket.assert_called_once_with(Bucket="test-bucket")

    @patch("app.utils.spaces.get_s3_client")
    @patch("app.core.config.get_settings")
    def test_ensure_bucket_exists_other_error(
        self, mock_get_settings, mock_get_s3_client
    ):
        """Test ensuring bucket exists when other error occurs."""
        mock_settings = MagicMock()
        mock_settings.SPACES_BUCKET = "test-bucket"
        mock_get_settings.return_value = mock_settings

        mock_client = MagicMock()
        # Simulate other error
        from botocore.exceptions import ClientError

        error = ClientError({"Error": {"Code": "AccessDenied"}}, "HeadBucket")
        mock_client.head_bucket.side_effect = error
        mock_get_s3_client.return_value = mock_client

        with pytest.raises(ClientError):
            ensure_bucket_exists()

        mock_client.create_bucket.assert_not_called()
