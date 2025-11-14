"""Form validation service."""

import json
import re
from typing import Any
from uuid import UUID

import asyncpg


async def create_validation_rule(
    conn: asyncpg.Connection,
    form_id: UUID,
    field_id: str,
    rule_type: str,
    rule_config: dict[str, Any],
    error_message: str,
    severity: str = "error",
) -> dict[str, Any] | None:
    """Create a validation rule for a form field."""
    result = await conn.fetchrow(
        """
        INSERT INTO validation_rules (
            form_id, field_id, rule_type, rule_config, error_message, severity
        )
        VALUES ($1, $2, $3, $4, $5, $6)
        RETURNING id, form_id, field_id, rule_type, rule_config, error_message,
                  severity, is_active, created_at, updated_at
        """,
        str(form_id),
        field_id,
        rule_type,
        json.dumps(rule_config),
        error_message,
        severity,
    )
    if result:
        result_dict = dict(result)
        result_dict["rule_config"] = (
            json.loads(result_dict["rule_config"])
            if isinstance(result_dict["rule_config"], str)
            else result_dict["rule_config"]
        )
        return result_dict
    return None


async def get_validation_rules(
    conn: asyncpg.Connection,
    form_id: UUID,
    field_id: str | None = None,
    is_active: bool | None = None,
) -> list[dict[str, Any]]:
    """Get validation rules for a form."""
    query = """
        SELECT id, form_id, field_id, rule_type, rule_config, error_message,
               severity, is_active, created_at, updated_at
        FROM validation_rules
        WHERE form_id = $1
    """
    params: list[Any] = [str(form_id)]

    if field_id:
        query += f" AND field_id = ${len(params) + 1}"
        params.append(field_id)

    if is_active is not None:
        query += f" AND is_active = ${len(params) + 1}"
        params.append(is_active)

    query += " ORDER BY created_at ASC"

    results = await conn.fetch(query, *params)
    output = []
    for result in results:
        result_dict = dict(result)
        result_dict["rule_config"] = (
            json.loads(result_dict["rule_config"])
            if isinstance(result_dict["rule_config"], str)
            else result_dict["rule_config"]
        )
        output.append(result_dict)
    return output


async def update_validation_rule(
    conn: asyncpg.Connection,
    rule_id: UUID,
    rule_config: dict[str, Any] | None = None,
    error_message: str | None = None,
    severity: str | None = None,
    is_active: bool | None = None,
) -> dict[str, Any] | None:
    """Update a validation rule."""
    updates: list[str] = []
    params: list[Any] = []

    if rule_config is not None:
        updates.append(f"rule_config = ${len(params) + 1}")
        params.append(json.dumps(rule_config))

    if error_message is not None:
        updates.append(f"error_message = ${len(params) + 1}")
        params.append(error_message)

    if severity is not None:
        updates.append(f"severity = ${len(params) + 1}")
        params.append(severity)

    if is_active is not None:
        updates.append(f"is_active = ${len(params) + 1}")
        params.append(is_active)

    if not updates:
        return None

    updates.append("updated_at = CURRENT_TIMESTAMP")
    params.append(str(rule_id))

    query = f"""
        UPDATE validation_rules
        SET {", ".join(updates)}
        WHERE id = ${len(params)}
        RETURNING id, form_id, field_id, rule_type, rule_config, error_message,
                  severity, is_active, created_at, updated_at
    """

    result = await conn.fetchrow(query, *params)
    if result:
        result_dict = dict(result)
        result_dict["rule_config"] = (
            json.loads(result_dict["rule_config"])
            if isinstance(result_dict["rule_config"], str)
            else result_dict["rule_config"]
        )
        return result_dict
    return None


async def delete_validation_rule(conn: asyncpg.Connection, rule_id: UUID) -> bool:
    """Delete a validation rule."""
    result = await conn.execute(
        "DELETE FROM validation_rules WHERE id = $1",
        str(rule_id),
    )
    return int(result.split()[-1]) > 0


def validate_regex(value: Any, pattern: str, flags: str = "") -> bool:
    """Validate value against a regex pattern."""
    try:
        regex_flags = 0
        if "i" in flags.lower():
            regex_flags |= re.IGNORECASE
        if "m" in flags.lower():
            regex_flags |= re.MULTILINE
        return bool(re.match(pattern, str(value), regex_flags))
    except (re.error, TypeError):
        return False


def validate_cross_field(
    value: Any, form_data: dict[str, Any], compare_field: str, operator: str
) -> bool:
    """Validate value against another field."""
    compare_value = form_data.get(compare_field)

    if operator == "equals":
        return value == compare_value
    elif operator == "not_equals":
        return value != compare_value
    elif operator == "greater_than":
        try:
            return float(value) > float(compare_value)
        except (ValueError, TypeError):
            return False
    elif operator == "less_than":
        try:
            return float(value) < float(compare_value)
        except (ValueError, TypeError):
            return False
    elif operator == "greater_than_or_equal":
        try:
            return float(value) >= float(compare_value)
        except (ValueError, TypeError):
            return False
    elif operator == "less_than_or_equal":
        try:
            return float(value) <= float(compare_value)
        except (ValueError, TypeError):
            return False

    return False


def validate_range(value: Any, min_val: float | None, max_val: float | None) -> bool:
    """Validate value is within a range."""
    try:
        num_value = float(value)
        if min_val is not None and num_value < min_val:
            return False
        if max_val is not None and num_value > max_val:
            return False
        return True
    except (ValueError, TypeError):
        return False


def validate_length(
    value: Any, min_length: int | None, max_length: int | None
) -> bool:
    """Validate string length."""
    try:
        str_value = str(value)
        length = len(str_value)
        if min_length is not None and length < min_length:
            return False
        if max_length is not None and length > max_length:
            return False
        return True
    except (ValueError, TypeError):
        return False


async def validate_form_data(
    conn: asyncpg.Connection,
    form_id: UUID,
    form_data: dict[str, Any],
    partial: bool = False,
) -> dict[str, Any]:
    """Validate form data against all validation rules."""
    rules = await get_validation_rules(conn, form_id, is_active=True)

    errors: dict[str, dict[str, str]] = {}
    warnings: dict[str, dict[str, str]] = {}
    infos: dict[str, dict[str, str]] = {}

    for rule in rules:
        field_id = rule["field_id"]
        rule_type = rule["rule_type"]
        rule_config = rule["rule_config"]
        error_message = rule["error_message"]
        severity = rule["severity"]

        # Skip validation for fields not in partial data
        if partial and field_id not in form_data:
            continue

        value = form_data.get(field_id)

        is_valid = True

        if rule_type == "regex":
            pattern = rule_config.get("pattern", "")
            flags = rule_config.get("flags", "")
            is_valid = validate_regex(value, pattern, flags)

        elif rule_type == "cross_field":
            compare_field = rule_config.get("compare_field")
            operator = rule_config.get("operator")
            if compare_field and operator:
                is_valid = validate_cross_field(value, form_data, compare_field, operator)

        elif rule_type == "range":
            min_val = rule_config.get("min")
            max_val = rule_config.get("max")
            is_valid = validate_range(value, min_val, max_val)

        elif rule_type == "length":
            min_length = rule_config.get("min_length")
            max_length = rule_config.get("max_length")
            is_valid = validate_length(value, min_length, max_length)

        # Add to appropriate severity dict if validation failed
        if not is_valid:
            validation_error = {
                "field_id": field_id,
                "severity": severity,
                "message": error_message,
            }

            if severity == "error":
                errors[field_id] = validation_error
            elif severity == "warning":
                warnings[field_id] = validation_error
            elif severity == "info":
                infos[field_id] = validation_error

    is_valid_overall = len(errors) == 0

    return {
        "is_valid": is_valid_overall,
        "errors": errors,
        "warnings": warnings,
        "info": infos,
    }
