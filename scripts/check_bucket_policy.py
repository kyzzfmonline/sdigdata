#!/usr/bin/env python3
"""Check and optionally fix bucket permissions."""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.utils.spaces import get_s3_client
from app.core.config import get_settings
from botocore.exceptions import ClientError


def check_bucket_policy():
    """Check current bucket policy."""
    settings = get_settings()
    s3_client = get_s3_client()

    print(f"Checking bucket policy for: {settings.SPACES_BUCKET}")
    print()

    try:
        response = s3_client.get_bucket_policy(Bucket=settings.SPACES_BUCKET)
        policy = json.loads(response['Policy'])
        print("Current bucket policy:")
        print(json.dumps(policy, indent=2))
        print()
        return policy
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', '')
        if error_code == 'NoSuchBucketPolicy':
            print("⚠️  No bucket policy found")
            print()
            return None
        else:
            print(f"❌ Error: {e}")
            return None


def set_public_read_policy():
    """Set bucket policy to allow public read access."""
    settings = get_settings()
    s3_client = get_s3_client()

    # Policy that allows public read access
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "PublicReadGetObject",
                "Effect": "Allow",
                "Principal": "*",
                "Action": "s3:GetObject",
                "Resource": f"arn:aws:s3:::{settings.SPACES_BUCKET}/*"
            }
        ]
    }

    print(f"Setting public read policy on bucket: {settings.SPACES_BUCKET}")
    print()
    print("Policy:")
    print(json.dumps(policy, indent=2))
    print()

    confirm = input("Apply this policy? (yes/no): ")
    if confirm.lower() != 'yes':
        print("Cancelled.")
        return False

    try:
        s3_client.put_bucket_policy(
            Bucket=settings.SPACES_BUCKET,
            Policy=json.dumps(policy)
        )
        print()
        print("✅ Bucket policy applied successfully!")
        print(f"   All files in {settings.SPACES_BUCKET} are now publicly readable")
        return True
    except ClientError as e:
        print(f"❌ Error setting policy: {e}")
        return False


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(
        description='Check and manage bucket permissions'
    )
    parser.add_argument(
        '--set-public',
        action='store_true',
        help='Set bucket policy to allow public read access'
    )

    args = parser.parse_args()

    if args.set_public:
        set_public_read_policy()
    else:
        check_bucket_policy()
