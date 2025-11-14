"""Form versioning service."""

import json
from typing import Any
from uuid import UUID

import asyncpg


async def create_version(
    conn: asyncpg.Connection,
    form_id: UUID,
    version_number: int,
    form_schema: dict[str, Any],
    title: str,
    created_by: UUID,
    description: str | None = None,
    change_summary: str | None = None,
    status: str = "draft",
) -> dict[str, Any] | None:
    """Create a new form version."""
    result = await conn.fetchrow(
        """
        INSERT INTO form_versions (
            form_id, version_number, form_schema, title, description,
            change_summary, status, created_by
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        RETURNING id, form_id, version_number, form_schema, title, description,
                  change_summary, status, created_by, created_at, published_at
        """,
        str(form_id),
        version_number,
        json.dumps(form_schema),
        title,
        description,
        change_summary,
        status,
        str(created_by),
    )
    if result:
        result_dict = dict(result)
        result_dict["form_schema"] = (
            json.loads(result_dict["form_schema"])
            if isinstance(result_dict["form_schema"], str)
            else result_dict["form_schema"]
        )
        return result_dict
    return None


async def get_form_versions(
    conn: asyncpg.Connection, form_id: UUID
) -> list[dict[str, Any]]:
    """Get all versions of a form."""
    results = await conn.fetch(
        """
        SELECT id, form_id, version_number, title, description,
               change_summary, status, created_by, created_at, published_at,
               (SELECT jsonb_array_length(form_schema->'fields')) as field_count
        FROM form_versions
        WHERE form_id = $1
        ORDER BY version_number DESC
        """,
        str(form_id),
    )
    return [dict(row) for row in results]


async def get_version_by_number(
    conn: asyncpg.Connection, form_id: UUID, version_number: int
) -> dict[str, Any] | None:
    """Get a specific version of a form."""
    result = await conn.fetchrow(
        """
        SELECT id, form_id, version_number, form_schema, title, description,
               change_summary, status, created_by, created_at, published_at
        FROM form_versions
        WHERE form_id = $1 AND version_number = $2
        """,
        str(form_id),
        version_number,
    )
    if result:
        result_dict = dict(result)
        result_dict["form_schema"] = (
            json.loads(result_dict["form_schema"])
            if isinstance(result_dict["form_schema"], str)
            else result_dict["form_schema"]
        )
        return result_dict
    return None


async def get_latest_version_number(
    conn: asyncpg.Connection, form_id: UUID
) -> int:
    """Get the latest version number for a form."""
    result = await conn.fetchval(
        """
        SELECT MAX(version_number)
        FROM form_versions
        WHERE form_id = $1
        """,
        str(form_id),
    )
    return result or 0


async def log_form_change(
    conn: asyncpg.Connection,
    form_id: UUID,
    version_number: int,
    change_type: str,
    change_details: dict[str, Any],
    changed_by: UUID,
) -> dict[str, Any] | None:
    """Log a form change."""
    result = await conn.fetchrow(
        """
        INSERT INTO form_change_log (
            form_id, version_number, change_type, change_details, changed_by
        )
        VALUES ($1, $2, $3, $4, $5)
        RETURNING id, form_id, version_number, change_type, change_details,
                  changed_by, changed_at
        """,
        str(form_id),
        version_number,
        change_type,
        json.dumps(change_details),
        str(changed_by),
    )
    if result:
        result_dict = dict(result)
        result_dict["change_details"] = (
            json.loads(result_dict["change_details"])
            if isinstance(result_dict["change_details"], str)
            else result_dict["change_details"]
        )
        return result_dict
    return None


async def get_change_log(
    conn: asyncpg.Connection,
    form_id: UUID,
    start_version: int | None = None,
    end_version: int | None = None,
    change_type: str | None = None,
    changed_by: UUID | None = None,
) -> list[dict[str, Any]]:
    """Get change log for a form."""
    query = """
        SELECT id, form_id, version_number, change_type, change_details,
               changed_by, changed_at
        FROM form_change_log
        WHERE form_id = $1
    """
    params: list[Any] = [str(form_id)]

    if start_version is not None:
        query += f" AND version_number >= ${len(params) + 1}"
        params.append(start_version)

    if end_version is not None:
        query += f" AND version_number <= ${len(params) + 1}"
        params.append(end_version)

    if change_type:
        query += f" AND change_type = ${len(params) + 1}"
        params.append(change_type)

    if changed_by:
        query += f" AND changed_by = ${len(params) + 1}"
        params.append(str(changed_by))

    query += " ORDER BY changed_at DESC"

    results = await conn.fetch(query, *params)
    output = []
    for result in results:
        result_dict = dict(result)
        result_dict["change_details"] = (
            json.loads(result_dict["change_details"])
            if isinstance(result_dict["change_details"], str)
            else result_dict["change_details"]
        )
        output.append(result_dict)
    return output


def compare_versions(
    version_a: dict[str, Any], version_b: dict[str, Any]
) -> dict[str, Any]:
    """Compare two form versions and return differences."""
    schema_a = version_a.get("form_schema", {})
    schema_b = version_b.get("form_schema", {})

    fields_a = {f["id"]: f for f in schema_a.get("fields", [])}
    fields_b = {f["id"]: f for f in schema_b.get("fields", [])}

    # Find added, removed, and modified fields
    fields_added = []
    for field_id, field in fields_b.items():
        if field_id not in fields_a:
            fields_added.append(field)

    fields_removed = []
    for field_id, field in fields_a.items():
        if field_id not in fields_b:
            fields_removed.append(field)

    fields_modified = []
    for field_id in set(fields_a.keys()) & set(fields_b.keys()):
        if fields_a[field_id] != fields_b[field_id]:
            changes = {}
            for key in set(fields_a[field_id].keys()) | set(fields_b[field_id].keys()):
                old_val = fields_a[field_id].get(key)
                new_val = fields_b[field_id].get(key)
                if old_val != new_val:
                    changes[key] = {"old": old_val, "new": new_val}
            if changes:
                fields_modified.append({
                    "field_id": field_id,
                    "changes": changes,
                })

    # Compare branding
    branding_a = schema_a.get("branding", {})
    branding_b = schema_b.get("branding", {})
    branding_changes = {}
    for key in set(branding_a.keys()) | set(branding_b.keys()):
        old_val = branding_a.get(key)
        new_val = branding_b.get(key)
        if old_val != new_val:
            branding_changes[key] = {"old": old_val, "new": new_val}

    return {
        "version_a": version_a.get("version_number"),
        "version_b": version_b.get("version_number"),
        "differences": {
            "fields_added": fields_added,
            "fields_removed": fields_removed,
            "fields_modified": fields_modified,
            "branding_changes": branding_changes,
        },
    }


async def auto_create_version_on_publish(
    conn: asyncpg.Connection,
    form_id: UUID,
    form_schema: dict[str, Any],
    title: str,
    created_by: UUID,
    description: str | None = None,
) -> dict[str, Any] | None:
    """Automatically create a new version when a form is published."""
    # Get the latest version number
    latest_version = await get_latest_version_number(conn, form_id)
    new_version = latest_version + 1

    # Create the version
    version = await create_version(
        conn,
        form_id=form_id,
        version_number=new_version,
        form_schema=form_schema,
        title=title,
        description=description,
        change_summary="Auto-created on publish",
        status="published",
        created_by=created_by,
    )

    if version:
        # Update published_at
        await conn.execute(
            """
            UPDATE form_versions
            SET published_at = CURRENT_TIMESTAMP
            WHERE id = $1
            """,
            str(version["id"]),
        )

    return version
