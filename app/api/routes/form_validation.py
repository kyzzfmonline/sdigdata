"""Form validation API routes."""

from typing import Annotated, Any
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.api.deps import get_current_user, get_db, require_admin
from app.core.responses import success_response
from app.services.validation import (
    create_validation_rule,
    delete_validation_rule,
    get_validation_rules,
    update_validation_rule,
    validate_form_data,
)

router = APIRouter(prefix="/forms/{form_id}/validation-rules", tags=["Form Validation"])


class ValidationRuleCreate(BaseModel):
    """Validation rule creation request."""

    field_id: str
    rule_type: str
    rule_config: dict[str, Any]
    error_message: str
    severity: str = "error"


class ValidationRuleUpdate(BaseModel):
    """Validation rule update request."""

    rule_config: dict[str, Any] | None = None
    error_message: str | None = None
    severity: str | None = None
    is_active: bool | None = None


class ValidateFormRequest(BaseModel):
    """Form validation request."""

    form_data: dict[str, Any]
    partial: bool = False


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_rule(
    form_id: UUID,
    request: ValidationRuleCreate,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict[str, Any], Depends(require_admin)],
) -> dict[str, Any]:
    """
    Create a validation rule for a form field (admin only).

    **Supported rule types:**
    - regex: Validate against a regular expression
    - cross_field: Validate against another field
    - range: Validate numeric range
    - length: Validate string length
    - custom: Custom validation logic
    - async: Asynchronous validation (e.g., database check)
    """
    rule = await create_validation_rule(
        conn,
        form_id=form_id,
        field_id=request.field_id,
        rule_type=request.rule_type,
        rule_config=request.rule_config,
        error_message=request.error_message,
        severity=request.severity,
    )

    if not rule:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create validation rule",
        )

    return success_response(data=rule, message="Validation rule created successfully")


@router.get("", response_model=dict)
async def list_rules(
    form_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
    field_id: str | None = None,
    is_active: bool | None = None,
) -> dict[str, Any]:
    """
    Get all validation rules for a form.

    **Query Parameters:**
    - field_id: Filter by field
    - is_active: Filter by active status
    """
    rules = await get_validation_rules(
        conn, form_id, field_id=field_id, is_active=is_active
    )
    return success_response(data=rules)


@router.put("/{rule_id}", response_model=dict)
async def update_rule(
    form_id: UUID,
    rule_id: UUID,
    request: ValidationRuleUpdate,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict[str, Any], Depends(require_admin)],
) -> dict[str, Any]:
    """Update a validation rule (admin only)."""
    rule = await update_validation_rule(
        conn,
        rule_id=rule_id,
        rule_config=request.rule_config,
        error_message=request.error_message,
        severity=request.severity,
        is_active=request.is_active,
    )

    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Validation rule not found",
        )

    return success_response(data=rule, message="Validation rule updated successfully")


@router.delete("/{rule_id}", response_model=dict)
async def delete_rule(
    form_id: UUID,
    rule_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict[str, Any], Depends(require_admin)],
) -> dict[str, Any]:
    """Delete a validation rule (admin only)."""
    success = await delete_validation_rule(conn, rule_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Validation rule not found",
        )
    return success_response(message="Validation rule deleted successfully")


@router.post("/validate", response_model=dict)
async def validate(
    form_id: UUID,
    request: ValidateFormRequest,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> dict[str, Any]:
    """
    Validate form data against all validation rules.

    **Request Body:**
    - form_data: The form data to validate
    - partial: If true, only validate provided fields (for incremental validation)

    **Response:**
    - is_valid: Overall validation status
    - errors: Critical validation errors (prevent submission)
    - warnings: Non-critical issues (allow submission with confirmation)
    - info: Informational messages
    """
    result = await validate_form_data(
        conn, form_id, request.form_data, partial=request.partial
    )

    return success_response(data=result)
