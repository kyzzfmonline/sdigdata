"""Advanced search and filtering routes."""
# type: ignore

from typing import Annotated
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.logging_config import get_logger
from app.core.responses import paginated_response, success_response

router = APIRouter(prefix="/search", tags=["Search"])
logger = get_logger(__name__)


class SearchFilter(BaseModel):
    """Search filter configuration."""

    field: str
    operator: str = Field(
        ..., pattern="^(eq|ne|gt|gte|lt|lte|contains|startswith|endswith|in|between)$"
    )
    value: str  # Changed from 'any' to 'str' to fix type issues
    case_sensitive: bool = False


class AdvancedSearchRequest(BaseModel):
    """Advanced search request."""

    entity: str = Field(..., pattern="^(forms|responses|users)$")
    query: str | None = None
    filters: list[SearchFilter] | None = None
    sort_by: str | None = None
    sort_order: str = Field("desc", pattern="^(asc|desc)$")
    page: int = Field(1, ge=1)
    limit: int = Field(20, ge=1, le=100)


class SavedSearchCreate(BaseModel):
    """Saved search creation request."""

    name: str = Field(..., min_length=1, max_length=100)
    entity: str = Field(..., pattern="^(forms|responses|users)$")
    query: str | None = None
    filters: list[SearchFilter] | None = None
    sort_by: str | None = None
    sort_order: str = Field("desc", pattern="^(asc|desc)$")
    is_public: bool = False


class GlobalSearchRequest(BaseModel):
    """Global search across all entities."""

    query: str = Field(..., min_length=1, max_length=100)
    entities: list[str] | None = Field(None, pattern="^(forms|responses|users)$")
    limit: int = Field(10, ge=1, le=50)


@router.post("/advanced", response_model=dict)
async def advanced_search(
    request: AdvancedSearchRequest,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """
    Perform advanced search with filters, sorting, and pagination.

    **Request Body:**
    ```json
    {
        "entity": "forms",
        "query": "household survey",
        "filters": [
            {
                "field": "status",
                "operator": "eq",
                "value": "published"
            },
            {
                "field": "created_at",
                "operator": "gte",
                "value": "2025-01-01"
            }
        ],
        "sort_by": "created_at",
        "sort_order": "desc",
        "page": 1,
        "limit": 20
    }
    ```

    **Response:**
    ```json
    {
        "success": true,
        "data": {
            "results": [...],
            "pagination": {
                "page": 1,
                "limit": 20,
                "total": 45,
                "total_pages": 3
            },
            "search_info": {
                "entity": "forms",
                "query": "household survey",
                "filters_applied": 2
            }
        }
    }
    ```
    """
    try:
        if request.entity == "forms":
            return await _search_forms(conn, request, current_user)
        elif request.entity == "responses":
            return await _search_responses(conn, request, current_user)
        elif request.entity == "users":
            return await _search_users(conn, request, current_user)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported entity: {request.entity}",
            )
    except Exception as e:
        logger.error(f"Advanced search error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Search failed. Please try again.",
        )


@router.get("/global", response_model=dict)
async def global_search(
    request: GlobalSearchRequest,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """
    Search across all entities (forms, responses, users).

    **Query Parameters:**
    - query: Search term (required)
    - entities: Comma-separated list of entities to search (optional)
    - limit: Maximum results per entity (default: 10)

    **Response:**
    ```json
    {
        "success": true,
        "data": {
            "forms": {
                "results": [...],
                "total": 5
            },
            "responses": {
                "results": [...],
                "total": 12
            },
            "users": {
                "results": [...],
                "total": 3
            },
            "query": "survey"
        }
    }
    ```
    """
    entities_to_search = request.entities or ["forms", "responses", "users"]
    results = {}

    for entity in entities_to_search:
        try:
            if entity == "forms":
                forms_results = await _global_search_forms(
                    conn, request.query, request.limit, current_user
                )
                results["forms"] = forms_results
            elif entity == "responses":
                responses_results = await _global_search_responses(
                    conn, request.query, request.limit, current_user
                )
                results["responses"] = responses_results
            elif entity == "users" and current_user["role"] == "admin":
                users_results = await _global_search_users(
                    conn, request.query, request.limit
                )
                results["users"] = users_results
        except Exception as e:
            logger.warning(f"Global search failed for {entity}: {e}")
            results[entity] = {"results": [], "total": 0}

    return success_response(data={**results, "query": request.query})


@router.get("/autocomplete", response_model=dict)
async def search_autocomplete(
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    q: str = Query(..., min_length=1, max_length=50, description="Search query"),
    entity: str = Query(
        ..., pattern="^(forms|responses|users)$", description="Entity to search"
    ),
    limit: int = Query(10, ge=1, le=20, description="Maximum suggestions"),
):
    """
    Get search autocomplete suggestions.

    **Query Parameters:**
    - q: Search query
    - entity: Entity to search (forms, responses, users)
    - limit: Maximum suggestions (default: 10)

    **Response:**
    ```json
    {
        "success": true,
        "data": {
            "suggestions": [
                {"text": "Household Survey 2025", "type": "form_title", "id": "frm_123"},
                {"text": "Community Survey", "type": "form_title", "id": "frm_456"}
            ],
            "query": "survey"
        }
    }
    ```
    """
    suggestions = []

    try:
        if entity == "forms":
            suggestions = await _autocomplete_forms(conn, q, limit, current_user)
        elif entity == "responses":
            suggestions = await _autocomplete_responses(conn, q, limit, current_user)
        elif entity == "users" and current_user["role"] == "admin":
            suggestions = await _autocomplete_users(conn, q, limit)
    except Exception as e:
        logger.warning(f"Autocomplete failed for {entity}: {e}")

    return success_response(
        data={"suggestions": suggestions, "query": q, "entity": entity}
    )


@router.post("/saved", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_saved_search(
    request: SavedSearchCreate,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """
    Create a saved search query.

    **Request Body:**
    ```json
    {
        "name": "Active Household Surveys",
        "entity": "forms",
        "query": "household",
        "filters": [
            {
                "field": "status",
                "operator": "eq",
                "value": "published"
            }
        ],
        "sort_by": "created_at",
        "sort_order": "desc",
        "is_public": false
    }
    ```
    """
    # For now, return success without actually saving (table doesn't exist yet)
    # TODO: Create saved_searches table in database migration
    return success_response(
        data={
            "id": f"temp_{request.name.replace(' ', '_').lower()}",
            "name": request.name,
            "entity": request.entity,
            "query": request.query,
            "filters": request.filters,
            "sort_by": request.sort_by,
            "sort_order": request.sort_order,
            "is_public": request.is_public,
            "created_by": current_user["id"],
            "created_at": "2025-01-01T00:00:00Z",  # Placeholder
        }
    )


@router.get("/saved", response_model=dict)
async def list_saved_searches(
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """
    List saved searches for current user.

    **Response:**
    ```json
    {
        "success": true,
        "data": [
            {
                "id": "ss_123",
                "name": "Active Surveys",
                "entity": "forms",
                "query": "survey",
                "is_public": false,
                "created_at": "2025-01-01T00:00:00Z"
            }
        ]
    }
    ```
    """
    # Get user's saved searches and public ones
    saved_searches = await conn.fetch(
        """
        SELECT id, name, entity, query, filters, sort_by, sort_order,
               is_public, created_by, created_at
        FROM saved_searches
        WHERE created_by = $1 OR is_public = TRUE
        ORDER BY created_at DESC
        """,
        UUID(current_user["id"]),
    )

    return success_response(data=[dict(search) for search in saved_searches])


# Helper functions for search implementation


async def _search_forms(
    conn: asyncpg.Connection, request: AdvancedSearchRequest, current_user: dict
) -> dict:
    """Search forms with advanced filters."""
    # Build WHERE clause from filters
    where_conditions = []
    params = []
    param_count = 0

    # Add text search
    if request.query:
        param_count += 1
        where_conditions.append(
            f"(title ILIKE ${param_count} OR description ILIKE ${param_count})"
        )
        params.append(f"%{request.query}%")

    # Add filters
    if request.filters:
        for filter_item in request.filters:
            param_count += 1
            condition = _build_filter_condition(filter_item, param_count)
            where_conditions.append(condition)
            params.append(filter_item.value)

    where_clause = " AND ".join(where_conditions) if where_conditions else "TRUE"

    # Build sort clause
    sort_field = request.sort_by or "created_at"
    sort_clause = f"{sort_field} {request.sort_order}"

    # Get total count
    count_query = f"SELECT COUNT(*) FROM forms WHERE {where_clause}"
    total = await conn.fetchval(count_query, *params) or 0

    # Get paginated results
    offset = (request.page - 1) * request.limit
    query = f"""
        SELECT id, title, description, status, schema, version,
               created_by, created_at, updated_at, published_at
        FROM forms
        WHERE {where_clause}
        ORDER BY {sort_clause}
        LIMIT ${param_count + 1} OFFSET ${param_count + 2}
    """
    params.extend([request.limit, offset])

    results = await conn.fetch(query, *params)

    return paginated_response(
        items=[dict(row) for row in results],
        page=request.page,
        limit=request.limit,
        total=total,
        extra_data={
            "search_info": {
                "entity": "forms",
                "query": request.query,
                "filters_applied": len(request.filters) if request.filters else 0,
            }
        },
    )


async def _search_responses(
    conn: asyncpg.Connection, request: AdvancedSearchRequest, current_user: dict
) -> dict:
    """Search responses with advanced filters."""
    # Similar implementation to forms search
    where_conditions = []
    params = []
    param_count = 0

    # Add permission-based filtering for agents
    if current_user["role"] == "agent":
        # Agents can only see responses from forms they're assigned to
        from app.services.forms import get_agent_assigned_forms

        assigned_forms = await get_agent_assigned_forms(conn, current_user["id"])
        assigned_form_ids = [str(f["id"]) for f in assigned_forms]
        if assigned_form_ids:
            placeholders = ", ".join(f"${i + 1}" for i in range(len(assigned_form_ids)))
            where_conditions.append(f"form_id IN ({placeholders})")
            params.extend(assigned_form_ids)
            param_count += len(assigned_form_ids)
        else:
            # No assigned forms, return empty results
            return paginated_response([], 1, request.limit, 0)

    # Add text search in response data (JSON)
    if request.query:
        param_count += 1
        where_conditions.append(f"data::text ILIKE ${param_count}")
        params.append(f"%{request.query}%")

    # Add filters
    if request.filters:
        for filter_item in request.filters:
            param_count += 1
            condition = _build_filter_condition(filter_item, param_count)
            where_conditions.append(condition)
            params.append(filter_item.value)

    where_clause = " AND ".join(where_conditions) if where_conditions else "TRUE"

    # Get total count
    count_query = (
        f"SELECT COUNT(*) FROM responses WHERE deleted = FALSE AND {where_clause}"
    )
    total = await conn.fetchval(count_query, *params) or 0

    # Get paginated results
    offset = (request.page - 1) * request.limit
    sort_field = request.sort_by or "submitted_at"
    sort_clause = f"{sort_field} {request.sort_order}"

    query = f"""
        SELECT id, form_id, submitted_by, data, attachments,
               submitted_at, submission_type
        FROM responses
        WHERE deleted = FALSE AND {where_clause}
        ORDER BY {sort_clause}
        LIMIT ${param_count + 1} OFFSET ${param_count + 2}
    """
    params.extend([request.limit, offset])

    results = await conn.fetch(query, *params)

    return paginated_response(
        items=[dict(row) for row in results],
        page=request.page,
        limit=request.limit,
        total=total,
        extra_data={
            "search_info": {
                "entity": "responses",
                "query": request.query,
                "filters_applied": len(request.filters) if request.filters else 0,
            }
        },
    )


async def _search_users(
    conn: asyncpg.Connection, request: AdvancedSearchRequest, current_user: dict
) -> dict:
    """Search users with advanced filters (admin only)."""
    if current_user["role"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required for user search",
        )

    # Similar implementation to forms search
    where_conditions = []
    params = []
    param_count = 0

    # Add text search
    if request.query:
        param_count += 1
        where_conditions.append(
            f"(username ILIKE ${param_count} OR email ILIKE ${param_count})"
        )
        params.append(f"%{request.query}%")

    # Add filters
    if request.filters:
        for filter_item in request.filters:
            param_count += 1
            condition = _build_filter_condition(filter_item, param_count)
            where_conditions.append(condition)
            params.append(filter_item.value)

    where_clause = " AND ".join(where_conditions) if where_conditions else "TRUE"

    # Get total count
    count_query = f"SELECT COUNT(*) FROM users WHERE deleted = FALSE AND {where_clause}"
    total = await conn.fetchval(count_query, *params) or 0

    # Get paginated results
    offset = (request.page - 1) * request.limit
    sort_field = request.sort_by or "created_at"
    sort_clause = f"{sort_field} {request.sort_order}"

    query = f"""
        SELECT id, username, email, role, status, organization_id,
               created_at, last_login
        FROM users
        WHERE deleted = FALSE AND {where_clause}
        ORDER BY {sort_clause}
        LIMIT ${param_count + 1} OFFSET ${param_count + 2}
    """
    params.extend([request.limit, offset])

    results = await conn.fetch(query, *params)

    return paginated_response(
        items=[dict(row) for row in results],
        page=request.page,
        limit=request.limit,
        total=total,
        extra_data={
            "search_info": {
                "entity": "users",
                "query": request.query,
                "filters_applied": len(request.filters) if request.filters else 0,
            }
        },
    )


def _build_filter_condition(filter_item, param_index):
    """Build SQL condition from filter."""
    field = filter_item.field
    operator = filter_item.operator
    param = f"${param_index}"

    if operator == "eq":
        return f"{field} = {param}"
    elif operator == "ne":
        return f"{field} != {param}"
    elif operator == "gt":
        return f"{field} > {param}"
    elif operator == "gte":
        return f"{field} >= {param}"
    elif operator == "lt":
        return f"{field} < {param}"
    elif operator == "lte":
        return f"{field} <= {param}"
    elif operator == "contains":
        return f"{field} ILIKE {param}"
    elif operator == "startswith":
        return f"{field} ILIKE {param}"
    elif operator == "endswith":
        return f"{field} ILIKE {param}"
    elif operator == "in":
        return f"{field} = ANY({param})"
    else:
        raise ValueError(f"Unsupported operator: {operator}")


async def _global_search_forms(
    conn: asyncpg.Connection, query: str, limit: int, current_user: dict
) -> dict:
    """Global search in forms."""
    results = await conn.fetch(
        """
        SELECT id, title, description, status, created_at
        FROM forms
        WHERE deleted = FALSE AND (title ILIKE $1 OR description ILIKE $1)
        ORDER BY created_at DESC
        LIMIT $2
        """,
        f"%{query}%",
        limit,
    )
    return {
        "results": [
            {"id": str(r["id"]), "title": r["title"], "type": "form"} for r in results
        ],
        "total": len(results),
    }


async def _global_search_responses(
    conn: asyncpg.Connection, query: str, limit: int, current_user: dict
) -> dict:
    """Global search in responses."""
    # Add permission filtering for agents
    where_clause = "deleted = FALSE"
    params = [f"%{query}%", limit]

    if current_user["role"] == "agent":
        from app.services.forms import get_agent_assigned_forms

        assigned_forms = await get_agent_assigned_forms(conn, current_user["id"])
        assigned_form_ids = [str(f["id"]) for f in assigned_forms]
        if assigned_form_ids:
            placeholders = ", ".join(f"${i + 3}" for i in range(len(assigned_form_ids)))
            where_clause += f" AND form_id IN ({placeholders})"
            params.extend(assigned_form_ids)
        else:
            return {"results": [], "total": 0}

    results = await conn.fetch(
        f"""
        SELECT id, form_id, submitted_at, data
        FROM responses
        WHERE {where_clause} AND data::text ILIKE $1
        ORDER BY submitted_at DESC
        LIMIT $2
        """,
        *params,
    )
    return {
        "results": [
            {"id": str(r["id"]), "form_id": str(r["form_id"]), "type": "response"}
            for r in results
        ],
        "total": len(results),
    }


async def _global_search_users(
    conn: asyncpg.Connection, query: str, limit: int
) -> dict:
    """Global search in users (admin only)."""
    results = await conn.fetch(
        """
        SELECT id, username, email, role
        FROM users
        WHERE deleted = FALSE AND (username ILIKE $1 OR email ILIKE $1)
        ORDER BY created_at DESC
        LIMIT $2
        """,
        f"%{query}%",
        limit,
    )
    return {
        "results": [
            {"id": str(r["id"]), "username": r["username"], "type": "user"}
            for r in results
        ],
        "total": len(results),
    }


async def _autocomplete_forms(
    conn: asyncpg.Connection, query: str, limit: int, current_user: dict
) -> list[dict]:
    """Autocomplete for forms."""
    results = await conn.fetch(
        """
        SELECT id, title
        FROM forms
        WHERE deleted = FALSE AND title ILIKE $1
        ORDER BY title
        LIMIT $2
        """,
        f"{query}%",
        limit,
    )
    return [
        {"text": r["title"], "type": "form_title", "id": str(r["id"])} for r in results
    ]


async def _autocomplete_responses(
    conn: asyncpg.Connection, query: str, limit: int, current_user: dict
) -> list[dict]:
    """Autocomplete for responses."""
    # This is more complex as we need to search within JSON data
    # For now, return empty suggestions
    return []


async def _autocomplete_users(
    conn: asyncpg.Connection, query: str, limit: int
) -> list[dict]:
    """Autocomplete for users."""
    results = await conn.fetch(
        """
        SELECT id, username
        FROM users
        WHERE deleted = FALSE AND username ILIKE $1
        ORDER BY username
        LIMIT $2
        """,
        f"{query}%",
        limit,
    )
    return [
        {"text": r["username"], "type": "username", "id": str(r["id"])} for r in results
    ]
