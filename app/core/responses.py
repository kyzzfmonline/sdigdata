"""Standardized API response utilities."""

from typing import Any

from fastapi import HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel


class APIResponse(BaseModel):
    """Standardized API response model."""

    success: bool
    data: Any | None = None
    message: str | None = None
    errors: dict[str, Any] | None = None


class PaginatedResponse(BaseModel):
    """Standardized paginated response model."""

    success: bool = True
    data: dict[str, Any]
    message: str | None = None


class ErrorResponse(BaseModel):
    """Standardized error response model."""

    success: bool = False
    message: str
    data: Any | None = None
    errors: dict[str, Any] | None = None


def success_response(data: Any = None, message: str | None = None) -> dict[str, Any]:
    """Create a successful API response."""
    return {"success": True, "data": data, "message": message}


def error_response(
    message: str,
    data: Any = None,
    errors: dict[str, Any] | None = None,
    status_code: int = status.HTTP_400_BAD_REQUEST,
) -> HTTPException:
    """Create an error response that raises an HTTPException."""
    raise HTTPException(
        status_code=status_code,
        detail={"success": False, "message": message, "data": data, "errors": errors},
    )


def error_response_dict(
    error_dict: dict[str, Any], status_code: int = status.HTTP_400_BAD_REQUEST
) -> JSONResponse:
    """Create an error response as a JSONResponse (for exception handlers)."""
    return JSONResponse(status_code=status_code, content=error_dict)


def paginated_response(
    items: list,
    page: int,
    limit: int,
    total: int,
    message: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Create a paginated response."""
    total_pages = (total + limit - 1) // limit  # Ceiling division

    return {
        "success": True,
        "data": {
            "data": items,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "total_pages": total_pages,
            },
            **kwargs,
        },
        "message": message,
    }


def validation_error_response(
    errors: dict[str, Any], message: str = "Validation failed"
) -> HTTPException:
    """Create a validation error response."""
    return error_response(
        message=message, errors=errors, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY
    )


def not_found_response(
    resource: str = "Resource", message: str | None = None
) -> HTTPException:
    """Create a not found error response."""
    return error_response(
        message=message or f"{resource} not found",
        status_code=status.HTTP_404_NOT_FOUND,
    )


def forbidden_response(message: str = "Access denied") -> HTTPException:
    """Create a forbidden error response."""
    return error_response(message=message, status_code=status.HTTP_403_FORBIDDEN)


def unauthorized_response(message: str = "Authentication required") -> HTTPException:
    """Create an unauthorized error response."""
    return error_response(message=message, status_code=status.HTTP_401_UNAUTHORIZED)
