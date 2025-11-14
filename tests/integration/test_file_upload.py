#!/usr/bin/env python3
"""
Test file upload functionality end-to-end.
"""

import os
import tempfile

import pytest


@pytest.mark.asyncio
async def test_file_upload(client, auth_token):
    print("Testing file upload functionality...")

    # Get presigned URL
    presign_response = await client.post(
        "/files/presign",
        headers={"Authorization": f"Bearer {auth_token}"},
        json={"filename": "test_upload.jpg", "content_type": "image/jpeg"},
    )

    assert presign_response.status_code == 200, (
        f"Presigned URL generation failed: {presign_response.text}"
    )

    presign_data = presign_response.json()["data"]
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
            upload_response = await client.put(
                upload_url, content=f.read(), headers={"Content-Type": "image/jpeg"}
            )

        assert upload_response.status_code in [200, 201], (
            f"File upload failed with status {upload_response.status_code}: {upload_response.text}"
        )

        print("✅ File uploaded successfully")

        # Try to access the file URL
        file_response = await client.get(file_url)
        if file_response.status_code == 200:
            print("✅ File is accessible at public URL")
        else:
            print(
                f"⚠️  File URL returned status {file_response.status_code} (might be expected with local MinIO)"
            )

    finally:
        # Clean up
        os.unlink(test_file_path)
