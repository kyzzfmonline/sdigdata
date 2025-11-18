#!/usr/bin/env python3
"""
Configure CORS settings for DigitalOcean Spaces bucket.

This script sets up CORS to allow file uploads from the admin frontend
at https://sdigdata.com using presigned URLs with PUT requests.

NOTE: MinIO (local development) may not support CORS configuration via API.
      For local development, CORS is typically bypassed for localhost origins.
      This script is primarily for production DigitalOcean Spaces configuration.

USAGE:
    # For production (requires production .env with DigitalOcean Spaces credentials):
    python scripts/configure_spaces_cors.py

    # Check current CORS:
    python scripts/configure_spaces_cors.py --get
"""

import sys
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import get_settings
from app.utils.spaces import get_s3_client
from botocore.exceptions import ClientError


def configure_cors():
    """Configure CORS settings for the Spaces bucket."""
    settings = get_settings()
    s3_client = get_s3_client()

    # CORS configuration XML
    # This allows:
    # - Origins: https://sdigdata.com (production) and http://localhost:3000 (development)
    # - Methods: GET (for reading), PUT (for uploading with presigned URLs)
    # - Headers: * (allows Content-Type and other headers)
    # - Exposed Headers: ETag (useful for file integrity checks)
    cors_configuration = {
        'CORSRules': [
            {
                'AllowedOrigins': [
                    'https://sdigdata.com',
                    'http://localhost:3000',
                    'http://localhost:3001',
                ],
                'AllowedMethods': ['GET', 'PUT', 'HEAD'],
                'AllowedHeaders': ['*'],
                'ExposeHeaders': ['ETag', 'Content-Length'],
                'MaxAgeSeconds': 3600
            }
        ]
    }

    try:
        print(f"Configuring CORS for bucket: {settings.SPACES_BUCKET}")
        print(f"Endpoint: {settings.SPACES_ENDPOINT}")
        print(f"Region: {settings.SPACES_REGION}")
        print()

        # Check if using MinIO (local)
        if 'localhost' in settings.SPACES_ENDPOINT or '127.0.0.1' in settings.SPACES_ENDPOINT:
            print("⚠️  Warning: Detected local MinIO endpoint.")
            print("   MinIO may not support CORS configuration via API.")
            print("   For local development, CORS is typically bypassed for localhost.")
            print()
            print("   If you need CORS for local testing:")
            print("   1. Check MinIO console at http://localhost:9001")
            print("   2. Or use 'mc' (MinIO Client) to configure CORS")
            print()
            print("   For production DigitalOcean Spaces:")
            print("   - Update .env with production SPACES_* credentials")
            print("   - Run this script again")
            print()
            return

        # Apply CORS configuration
        s3_client.put_bucket_cors(
            Bucket=settings.SPACES_BUCKET,
            CORSConfiguration=cors_configuration
        )

        print("✅ CORS configuration applied successfully!")
        print()
        print("Configuration details:")
        print(f"  - Allowed Origins: https://sdigdata.com, http://localhost:3000, http://localhost:3001")
        print(f"  - Allowed Methods: GET, PUT, HEAD")
        print(f"  - Allowed Headers: * (all)")
        print(f"  - Exposed Headers: ETag, Content-Length")
        print(f"  - Max Age: 3600 seconds")
        print()

        # Verify the configuration
        response = s3_client.get_bucket_cors(Bucket=settings.SPACES_BUCKET)
        print("✅ Verified CORS configuration:")
        for idx, rule in enumerate(response['CORSRules'], 1):
            print(f"  Rule {idx}:")
            print(f"    Origins: {', '.join(rule.get('AllowedOrigins', []))}")
            print(f"    Methods: {', '.join(rule.get('AllowedMethods', []))}")
            print(f"    Headers: {', '.join(rule.get('AllowedHeaders', []))}")
            print(f"    Exposed: {', '.join(rule.get('ExposeHeaders', []))}")
            print(f"    Max Age: {rule.get('MaxAgeSeconds', 0)} seconds")
        print()

    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', '')
        error_msg = e.response.get('Error', {}).get('Message', '')

        if error_code == 'NoSuchBucket':
            print(f"❌ Error: Bucket '{settings.SPACES_BUCKET}' does not exist.")
            print("   Create the bucket first or check your configuration.")
        elif error_code == 'AccessDenied':
            print(f"❌ Error: Access denied to bucket '{settings.SPACES_BUCKET}'.")
            print("   Check your Spaces credentials (SPACES_KEY and SPACES_SECRET).")
        else:
            print(f"❌ Error configuring CORS: {error_code}")
            print(f"   Message: {error_msg}")

        sys.exit(1)

    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)


def get_current_cors():
    """Display current CORS configuration."""
    settings = get_settings()
    s3_client = get_s3_client()

    try:
        response = s3_client.get_bucket_cors(Bucket=settings.SPACES_BUCKET)
        print(f"Current CORS configuration for bucket: {settings.SPACES_BUCKET}")
        print()

        for idx, rule in enumerate(response['CORSRules'], 1):
            print(f"Rule {idx}:")
            print(f"  Allowed Origins: {', '.join(rule.get('AllowedOrigins', []))}")
            print(f"  Allowed Methods: {', '.join(rule.get('AllowedMethods', []))}")
            print(f"  Allowed Headers: {', '.join(rule.get('AllowedHeaders', []))}")
            print(f"  Exposed Headers: {', '.join(rule.get('ExposeHeaders', []))}")
            print(f"  Max Age: {rule.get('MaxAgeSeconds', 0)} seconds")
            print()

    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', '')

        if error_code == 'NoSuchCORSConfiguration':
            print(f"No CORS configuration found for bucket: {settings.SPACES_BUCKET}")
            print("Run this script without arguments to configure CORS.")
        else:
            print(f"Error retrieving CORS configuration: {e}")

        sys.exit(1)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(
        description='Configure CORS for DigitalOcean Spaces bucket'
    )
    parser.add_argument(
        '--get',
        action='store_true',
        help='Get current CORS configuration instead of setting it'
    )

    args = parser.parse_args()

    if args.get:
        get_current_cors()
    else:
        configure_cors()
