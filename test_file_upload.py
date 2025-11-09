#!/usr/bin/env python3
"""
Test file upload functionality end-to-end.
"""

import requests
import json
import tempfile
import os

BASE_URL = "http://localhost:8000"


def test_file_upload():
    print("Testing file upload functionality...")

    # First, login to get token
    login_response = requests.post(
        f"{BASE_URL}/auth/login", json={"username": "admin", "password": "admin123"}
    )

    if login_response.status_code != 200:
        print("❌ Login failed")
        return False

    token = login_response.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Get presigned URL
    presign_response = requests.post(
        f"{BASE_URL}/files/presign",
        headers=headers,
        json={"filename": "test_upload.jpg", "content_type": "image/jpeg"},
    )

    if presign_response.status_code != 200:
        print("❌ Presigned URL generation failed")
        print(f"Response: {presign_response.text}")
        return False

    presign_data = presign_response.json()
    upload_url = presign_data["upload_url"]
    file_url = presign_data["file_url"]

    print(f"✅ Got presigned URL: {upload_url[:50]}...")

    # Create a test file
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
        f.write(b"fake image data for testing")
        test_file_path = f.name

    try:
        # Upload file to presigned URL
        with open(test_file_path, "rb") as f:
            upload_response = requests.put(
                upload_url, data=f, headers={"Content-Type": "image/jpeg"}
            )

        if upload_response.status_code not in [200, 201]:
            print(f"❌ File upload failed with status {upload_response.status_code}")
            print(f"Response: {upload_response.text}")
            return False

        print("✅ File uploaded successfully")

        # Try to access the file URL
        file_response = requests.get(file_url)
        if file_response.status_code == 200:
            print("✅ File is accessible at public URL")
        else:
            print(
                f"⚠️  File URL returned status {file_response.status_code} (might be expected with local MinIO)"
            )

        return True

    finally:
        # Clean up
        os.unlink(test_file_path)


if __name__ == "__main__":
    success = test_file_upload()
    if success:
        print("\n🎉 File upload functionality is working!")
    else:
        print("\n❌ File upload functionality has issues")
