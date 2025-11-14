"""Conditional logic service for dynamic form behavior."""

import json
from typing import Any
from uuid import UUID

import asyncpg


async def create_conditional_rule(
    conn: asyncpg.Connection,
    form_id: UUID,
    rule_name: str,
    rule_type: str,
    conditions: list[dict[str, Any]],
    actions: list[dict[str, Any]],
    created_by: UUID,
    priority: int = 0,
) -> dict[str, Any] | None:
    """Create a conditional rule for a form."""
    result = await conn.fetchrow(
        """
        INSERT INTO conditional_rules (
            form_id, rule_name, rule_type, conditions, actions, priority, created_by
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        RETURNING id, form_id, rule_name, rule_type, conditions, actions, priority,
                  is_active, created_at, updated_at, created_by
        """,
        str(form_id),
        rule_name,
        rule_type,
        json.dumps(conditions),
        json.dumps(actions),
        priority,
        str(created_by),
    )
    if result:
        result_dict = dict(result)
        result_dict["conditions"] = (
            json.loads(result_dict["conditions"])
            if isinstance(result_dict["conditions"], str)
            else result_dict["conditions"]
        )
        result_dict["actions"] = (
            json.loads(result_dict["actions"])
            if isinstance(result_dict["actions"], str)
            else result_dict["actions"]
        )
        return result_dict
    return None


async def get_conditional_rules(
    conn: asyncpg.Connection,
    form_id: UUID,
    rule_type: str | None = None,
    is_active: bool | None = None,
) -> list[dict[str, Any]]:
    """Get all conditional rules for a form."""
    query = """
        SELECT id, form_id, rule_name, rule_type, conditions, actions, priority,
               is_active, created_at, updated_at, created_by
        FROM conditional_rules
        WHERE form_id = $1
    """
    params: list[Any] = [str(form_id)]

    if rule_type:
        query += f" AND rule_type = ${len(params) + 1}"
        params.append(rule_type)

    if is_active is not None:
        query += f" AND is_active = ${len(params) + 1}"
        params.append(is_active)

    query += " ORDER BY priority ASC, created_at ASC"

    results = await conn.fetch(query, *params)
    output = []
    for result in results:
        result_dict = dict(result)
        result_dict["conditions"] = (
            json.loads(result_dict["conditions"])
            if isinstance(result_dict["conditions"], str)
            else result_dict["conditions"]
        )
        result_dict["actions"] = (
            json.loads(result_dict["actions"])
            if isinstance(result_dict["actions"], str)
            else result_dict["actions"]
        )
        output.append(result_dict)
    return output


async def get_conditional_rule_by_id(
    conn: asyncpg.Connection, rule_id: UUID
) -> dict[str, Any] | None:
    """Get a conditional rule by ID."""
    result = await conn.fetchrow(
        """
        SELECT id, form_id, rule_name, rule_type, conditions, actions, priority,
               is_active, created_at, updated_at, created_by
        FROM conditional_rules
        WHERE id = $1
        """,
        str(rule_id),
    )
    if result:
        result_dict = dict(result)
        result_dict["conditions"] = (
            json.loads(result_dict["conditions"])
            if isinstance(result_dict["conditions"], str)
            else result_dict["conditions"]
        )
        result_dict["actions"] = (
            json.loads(result_dict["actions"])
            if isinstance(result_dict["actions"], str)
            else result_dict["actions"]
        )
        return result_dict
    return None


async def update_conditional_rule(
    conn: asyncpg.Connection,
    rule_id: UUID,
    rule_name: str | None = None,
    conditions: list[dict[str, Any]] | None = None,
    actions: list[dict[str, Any]] | None = None,
    priority: int | None = None,
    is_active: bool | None = None,
) -> dict[str, Any] | None:
    """Update a conditional rule."""
    updates: list[str] = []
    params: list[Any] = []

    if rule_name is not None:
        updates.append(f"rule_name = ${len(params) + 1}")
        params.append(rule_name)

    if conditions is not None:
        updates.append(f"conditions = ${len(params) + 1}")
        params.append(json.dumps(conditions))

    if actions is not None:
        updates.append(f"actions = ${len(params) + 1}")
        params.append(json.dumps(actions))

    if priority is not None:
        updates.append(f"priority = ${len(params) + 1}")
        params.append(priority)

    if is_active is not None:
        updates.append(f"is_active = ${len(params) + 1}")
        params.append(is_active)

    if not updates:
        return await get_conditional_rule_by_id(conn, rule_id)

    updates.append("updated_at = CURRENT_TIMESTAMP")
    params.append(str(rule_id))

    query = f"""
        UPDATE conditional_rules
        SET {", ".join(updates)}
        WHERE id = ${len(params)}
        RETURNING id, form_id, rule_name, rule_type, conditions, actions, priority,
                  is_active, created_at, updated_at, created_by
    """

    result = await conn.fetchrow(query, *params)
    if result:
        result_dict = dict(result)
        result_dict["conditions"] = (
            json.loads(result_dict["conditions"])
            if isinstance(result_dict["conditions"], str)
            else result_dict["conditions"]
        )
        result_dict["actions"] = (
            json.loads(result_dict["actions"])
            if isinstance(result_dict["actions"], str)
            else result_dict["actions"]
        )
        return result_dict
    return None


async def delete_conditional_rule(conn: asyncpg.Connection, rule_id: UUID) -> bool:
    """Delete a conditional rule."""
    result = await conn.execute(
        "DELETE FROM conditional_rules WHERE id = $1",
        str(rule_id),
    )
    return int(result.split()[-1]) > 0


def evaluate_condition(
    condition: dict[str, Any], form_data: dict[str, Any]
) -> bool:
    """Evaluate a single condition against form data."""
    field_id = condition.get("field_id")
    operator = condition.get("operator")
    expected_value = condition.get("value")

    if not field_id or not operator:
        return False

    actual_value = form_data.get(field_id)

    # Handle different operators
    if operator == "equals":
        return actual_value == expected_value
    elif operator == "not_equals":
        return actual_value != expected_value
    elif operator == "greater_than":
        try:
            return float(actual_value) > float(expected_value)
        except (ValueError, TypeError):
            return False
    elif operator == "less_than":
        try:
            return float(actual_value) < float(expected_value)
        except (ValueError, TypeError):
            return False
    elif operator == "greater_than_or_equal":
        try:
            return float(actual_value) >= float(expected_value)
        except (ValueError, TypeError):
            return False
    elif operator == "less_than_or_equal":
        try:
            return float(actual_value) <= float(expected_value)
        except (ValueError, TypeError):
            return False
    elif operator == "contains":
        return expected_value in str(actual_value) if actual_value else False
    elif operator == "not_contains":
        return expected_value not in str(actual_value) if actual_value else True
    elif operator == "in":
        return actual_value in expected_value if isinstance(expected_value, list) else False
    elif operator == "not_in":
        return actual_value not in expected_value if isinstance(expected_value, list) else True
    elif operator == "is_empty":
        return not actual_value or actual_value == "" or actual_value == []
    elif operator == "is_not_empty":
        return bool(actual_value and actual_value != "" and actual_value != [])
    elif operator == "matches_regex":
        import re
        try:
            return bool(re.match(expected_value, str(actual_value)))
        except (re.error, TypeError):
            return False

    return False


async def evaluate_rules(
    conn: asyncpg.Connection, form_id: UUID, form_data: dict[str, Any]
) -> dict[str, Any]:
    """Evaluate all conditional rules for a form against form data."""
    rules = await get_conditional_rules(conn, form_id, is_active=True)

    visible_fields: set[str] = set()
    hidden_fields: set[str] = set()
    required_fields: set[str] = set()
    optional_fields: set[str] = set()
    calculated_values: dict[str, Any] = {}
    errors: dict[str, str] = {}

    # Sort by priority
    rules.sort(key=lambda r: r.get("priority", 0))

    for rule in rules:
        conditions = rule.get("conditions", [])
        actions = rule.get("actions", [])

        # Evaluate all conditions (AND logic)
        all_conditions_met = all(
            evaluate_condition(cond, form_data) for cond in conditions
        )

        if all_conditions_met:
            # Execute actions
            for action in actions:
                action_type = action.get("type")
                target_field_id = action.get("target_field_id")

                if action_type == "show_field" and target_field_id:
                    visible_fields.add(target_field_id)
                    hidden_fields.discard(target_field_id)
                elif action_type == "hide_field" and target_field_id:
                    hidden_fields.add(target_field_id)
                    visible_fields.discard(target_field_id)
                elif action_type == "set_required" and target_field_id:
                    required_fields.add(target_field_id)
                    optional_fields.discard(target_field_id)
                elif action_type == "set_optional" and target_field_id:
                    optional_fields.add(target_field_id)
                    required_fields.discard(target_field_id)
                elif action_type == "set_value" and target_field_id:
                    calculated_values[target_field_id] = action.get("value")
                elif action_type == "show_error" and target_field_id:
                    errors[target_field_id] = action.get("message", "Error")

    return {
        "visible_fields": list(visible_fields),
        "hidden_fields": list(hidden_fields),
        "required_fields": list(required_fields),
        "optional_fields": list(optional_fields),
        "calculated_values": calculated_values,
        "errors": errors,
    }
