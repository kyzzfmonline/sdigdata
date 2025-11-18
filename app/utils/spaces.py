"""DigitalOcean Spaces / MinIO file storage utilities."""

from typing import Any

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError
from fastapi import HTTPException

from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)


def get_s3_client() -> Any:
    """Create and return an S3 client configured for Spaces/MinIO."""
    from app.core.config import get_settings

    current_settings = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=current_settings.SPACES_ENDPOINT,
        aws_access_key_id=current_settings.SPACES_KEY,
        aws_secret_access_key=current_settings.SPACES_SECRET,
        region_name=current_settings.SPACES_REGION,
        config=Config(signature_version="s3v4"),
    )


def generate_presigned_url(
    filename: str, content_type: str, expires_in: int = 3600, read_expires_in: int = 86400
) -> dict:
    """
    Generate presigned URLs for file upload and download.

    Args:
        filename: Name of the file to upload
        content_type: MIME type of the file
        expires_in: Upload URL expiration time in seconds (default: 1 hour)
        read_expires_in: Read URL expiration time in seconds (default: 24 hours)

    Returns:
        Dictionary with 'upload_url' and 'file_url' (both presigned)
    """
    from app.core.config import get_settings

    current_settings = get_settings()

    # For local development, use localhost endpoint for presigned URLs
    # but keep the S3 client configured for Docker networking
    endpoint_for_url = current_settings.SPACES_ENDPOINT
    if "host.docker.internal" in current_settings.SPACES_ENDPOINT:
        endpoint_for_url = current_settings.SPACES_ENDPOINT.replace(
            "host.docker.internal", "localhost"
        )

    # Create a temporary client with the URL-friendly endpoint
    temp_client = boto3.client(
        "s3",
        endpoint_url=endpoint_for_url,
        aws_access_key_id=current_settings.SPACES_KEY,
        aws_secret_access_key=current_settings.SPACES_SECRET,
        region_name=current_settings.SPACES_REGION,
        config=Config(signature_version="s3v4"),
    )

    # Generate upload URL (for PUT requests)
    # Note: We no longer use ACL=public-read for security
    # Instead, we generate presigned read URLs
    upload_url = temp_client.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": settings.SPACES_BUCKET,
            "Key": filename,
            "ContentType": content_type,
        },
        ExpiresIn=expires_in,
        HttpMethod="PUT",
    )

    # Generate read URL (for GET requests) - valid for 24 hours by default
    # This allows secure, temporary access without making files public
    file_url = temp_client.generate_presigned_url(
        "get_object",
        Params={
            "Bucket": settings.SPACES_BUCKET,
            "Key": filename,
        },
        ExpiresIn=read_expires_in,
        HttpMethod="GET",
    )

    return {"upload_url": upload_url, "file_url": file_url}


def ensure_bucket_exists() -> None:
    """Ensure the configured bucket exists and has public read policy (useful for MinIO setup)."""
    import json

    from app.core.config import get_settings

    current_settings = get_settings()

    s3_client = get_s3_client()

    bucket_created = False
    try:
        s3_client.head_bucket(Bucket=current_settings.SPACES_BUCKET)
        logger.info(f"Bucket exists: {current_settings.SPACES_BUCKET}")
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")

        if error_code == "404" or error_code == "NoSuchBucket":
            # Bucket doesn't exist, create it
            try:
                s3_client.create_bucket(Bucket=current_settings.SPACES_BUCKET)
                logger.info(f"Created bucket: {current_settings.SPACES_BUCKET}")
                print(f"Created bucket: {current_settings.SPACES_BUCKET}")
                bucket_created = True
            except ClientError as create_error:
                logger.error(
                    f"Failed to create bucket {current_settings.SPACES_BUCKET}: {create_error}"
                )
                raise
        elif error_code == "403":
            logger.error(f"Access denied to bucket {current_settings.SPACES_BUCKET}")
            raise HTTPException(
                status_code=500, detail="Storage configuration error: Access denied"
            )
        else:
            logger.error(f"Error checking bucket {current_settings.SPACES_BUCKET}: {e}")
            raise
    except Exception as e:
        logger.error(
            f"Unexpected error with bucket {current_settings.SPACES_BUCKET}: {e}",
            exc_info=True,
        )
        raise

    # Set public read policy for the bucket
    try:
        # Define a public read policy
        bucket_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"AWS": "*"},
                    "Action": ["s3:GetObject"],
                    "Resource": [f"arn:aws:s3:::{current_settings.SPACES_BUCKET}/*"],
                }
            ],
        }

        s3_client.put_bucket_policy(
            Bucket=current_settings.SPACES_BUCKET, Policy=json.dumps(bucket_policy)
        )

        if bucket_created:
            logger.info(
                f"Set public read policy on bucket: {current_settings.SPACES_BUCKET}"
            )
            print(f"Set public read policy on bucket: {current_settings.SPACES_BUCKET}")
        else:
            logger.info(
                f"Updated public read policy on bucket: {current_settings.SPACES_BUCKET}"
            )
    except ClientError as e:
        logger.warning(f"Could not set bucket policy: {e}")
        # Don't fail if we can't set the policy - it might already be set or not supported
