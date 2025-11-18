#!/usr/bin/env python3
"""
Make specific files or all files in DigitalOcean Spaces publicly accessible.

Usage:
    # Make a specific file public
    python scripts/make_file_public.py uploads/80954a0f-2905-4d24-9b27-bf71e08c6354.jpeg

    # Make all files in a prefix public
    python scripts/make_file_public.py --prefix uploads/

    # Make all files in the bucket public
    python scripts/make_file_public.py --all
"""

import sys
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.utils.spaces import get_s3_client
from app.core.config import get_settings
from botocore.exceptions import ClientError


def make_file_public(file_key: str):
    """Make a specific file public."""
    settings = get_settings()
    s3_client = get_s3_client()

    try:
        s3_client.put_object_acl(
            Bucket=settings.SPACES_BUCKET,
            Key=file_key,
            ACL="public-read"
        )
        print(f"✅ Made public: {file_key}")
        print(f"   URL: https://{settings.SPACES_BUCKET}.{settings.SPACES_REGION}.digitaloceanspaces.com/{file_key}")
        return True
    except ClientError as e:
        print(f"❌ Error making {file_key} public: {e}")
        return False


def make_prefix_public(prefix: str):
    """Make all files with a prefix public."""
    settings = get_settings()
    s3_client = get_s3_client()

    print(f"Fetching files with prefix: {prefix}")

    try:
        # List all objects with the prefix
        paginator = s3_client.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=settings.SPACES_BUCKET, Prefix=prefix)

        count = 0
        success = 0

        for page in pages:
            for obj in page.get('Contents', []):
                count += 1
                if make_file_public(obj['Key']):
                    success += 1

        print(f"\n✅ Made {success}/{count} files public")
        return True

    except ClientError as e:
        print(f"❌ Error listing files: {e}")
        return False


def make_all_public():
    """Make all files in the bucket public."""
    settings = get_settings()
    s3_client = get_s3_client()

    print(f"⚠️  WARNING: This will make ALL files in bucket '{settings.SPACES_BUCKET}' public!")
    confirm = input("Type 'yes' to confirm: ")

    if confirm.lower() != 'yes':
        print("Cancelled.")
        return False

    return make_prefix_public("")


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(
        description='Make files in DigitalOcean Spaces publicly accessible'
    )
    parser.add_argument(
        'file_key',
        nargs='?',
        help='Specific file key to make public (e.g., uploads/file.jpg)'
    )
    parser.add_argument(
        '--prefix',
        help='Make all files with this prefix public (e.g., uploads/)'
    )
    parser.add_argument(
        '--all',
        action='store_true',
        help='Make ALL files in the bucket public (use with caution!)'
    )

    args = parser.parse_args()

    if args.all:
        make_all_public()
    elif args.prefix:
        make_prefix_public(args.prefix)
    elif args.file_key:
        make_file_public(args.file_key)
    else:
        parser.print_help()
        sys.exit(1)
