"""File upload routes."""

from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
import uuid

from app.utils.spaces import generate_presigned_url, ensure_bucket_exists
from app.api.deps import get_current_user

router = APIRouter(prefix="/files", tags=["Files"])


class PresignRequest(BaseModel):
    """Presigned URL request."""

    filename: str
    content_type: str


class PresignResponse(BaseModel):
    """Presigned URL response."""

    upload_url: str
    file_url: str


@router.post("/presign", response_model=PresignResponse)
async def get_presigned_url(
    request: PresignRequest, current_user: Annotated[dict, Depends(get_current_user)]
):
    """
    Get a presigned URL for file upload.

    **Request Body:**
    ```json
    {
        "filename": "household_photo.jpg",
        "content_type": "image/jpeg"
    }
    ```

    **Response:**
    ```json
    {
        "upload_url": "https://minio:9000/metroform-dev/uploads/abc123.jpg?signature=...",
        "file_url": "https://minio:9000/metroform-dev/uploads/abc123.jpg"
    }
    ```

    **Usage:**
    1. Call this endpoint to get upload_url and file_url
    2. Upload file to upload_url using PUT request with the file content
    3. Save file_url in your form response's attachments field
    """
    # Generate unique filename
    file_extension = request.filename.split(".")[-1] if "." in request.filename else ""
    unique_filename = (
        f"uploads/{uuid.uuid4()}.{file_extension}"
        if file_extension
        else f"uploads/{uuid.uuid4()}"
    )

    try:
        # Ensure bucket exists before generating presigned URL
        ensure_bucket_exists()

        result = generate_presigned_url(
            filename=unique_filename, content_type=request.content_type
        )
        return PresignResponse(**result)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate presigned URL: {str(e)}",
        )
