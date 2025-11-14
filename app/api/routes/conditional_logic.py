"""Conditional logic API routes."""

from typing import Annotated, Any
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.api.deps import get_current_user, get_db, require_admin
from app.core.responses import not_found_response, success_response
from app.services.conditional_logic import (
    create_conditional_rule,
    delete_conditional_rule,
    evaluate_rules,
    get_conditional_rule_by_id,
    get_conditional_rules,
    update_conditional_rule,
)

router = APIRouter(prefix="/forms/{form_id}/conditional-rules", tags=["Conditional Logic"])


class ConditionalRuleCreate(BaseModel):
    """Conditional rule creation request."""

    rule_name: str
    rule_type: str
    conditions: list[dict[str, Any]]
    actions: list[dict[str, Any]]
    priority: int = 0


class ConditionalRuleUpdate(BaseModel):
    """Conditional rule update request."""

    rule_name: str | None = None
    conditions: list[dict[str, Any]] | None = None
    actions: list[dict[str, Any]] | None = None
    priority: int | None = None
    is_active: bool | None = None


class EvaluateRulesRequest(BaseModel):
    """Request to evaluate conditional rules."""

    form_data: dict[str, Any]


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_rule(
    form_id: UUID,
    request: ConditionalRuleCreate,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict[str, Any], Depends(require_admin)],
) -> dict[str, Any]:
    """
    Create a conditional rule for a form (admin only).

    Conditional rules enable dynamic form behavior based on user responses.
    """
    rule = await create_conditional_rule(
        conn,
        form_id=form_id,
        rule_name=request.rule_name,
        rule_type=request.rule_type,
        conditions=request.conditions,
        actions=request.actions,
        created_by=current_user["id"],
        priority=request.priority,
    )

    if not rule:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create conditional rule",
        )

    return success_response(data=rule, message="Conditional rule created successfully")


@router.get("", response_model=dict)
async def list_rules(
    form_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
    rule_type: str | None = None,
    is_active: bool | None = None,
) -> dict[str, Any]:
    """
    Get all conditional rules for a form.

    **Query Parameters:**
    - rule_type: Filter by rule type (show_hide, calculate, validate, set_value)
    - is_active: Filter by active status
    """
    rules = await get_conditional_rules(
        conn, form_id, rule_type=rule_type, is_active=is_active
    )
    return success_response(data=rules)


@router.get("/{rule_id}", response_model=dict)
async def get_rule(
    form_id: UUID,
    rule_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> dict[str, Any]:
    """Get a specific conditional rule by ID."""
    rule = await get_conditional_rule_by_id(conn, rule_id)
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conditional rule not found",
        )
    return success_response(data=rule)


@router.put("/{rule_id}", response_model=dict)
async def update_rule(
    form_id: UUID,
    rule_id: UUID,
    request: ConditionalRuleUpdate,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict[str, Any], Depends(require_admin)],
) -> dict[str, Any]:
    """Update a conditional rule (admin only)."""
    rule = await update_conditional_rule(
        conn,
        rule_id=rule_id,
        rule_name=request.rule_name,
        conditions=request.conditions,
        actions=request.actions,
        priority=request.priority,
        is_active=request.is_active,
    )

    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conditional rule not found",
        )

    return success_response(data=rule, message="Conditional rule updated successfully")


@router.delete("/{rule_id}", response_model=dict)
async def delete_rule(
    form_id: UUID,
    rule_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict[str, Any], Depends(require_admin)],
) -> dict[str, Any]:
    """Delete a conditional rule (admin only)."""
    success = await delete_conditional_rule(conn, rule_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conditional rule not found",
        )
    return success_response(message="Conditional rule deleted successfully")


@router.post("/evaluate", response_model=dict)
async def evaluate(
    form_id: UUID,
    request: EvaluateRulesRequest,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> dict[str, Any]:
    """
    Evaluate conditional rules against form data.

    This endpoint is used for client-side validation to determine
    which fields should be visible, required, etc.
    """
    result = await evaluate_rules(conn, form_id, request.form_data)
    return success_response(data=result)
