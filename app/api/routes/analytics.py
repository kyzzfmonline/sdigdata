"""Analytics and dashboard routes."""

from typing import Annotated
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_user, require_admin
from app.core.database import get_db
from app.services.analytics import (
    get_agent_performance,
    get_dashboard_stats,
    get_form_analytics,
    get_performance_metrics,
)

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/dashboard", response_model=dict)
async def get_dashboard(
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    period: str = Query("7d", description="Time period: 24h, 7d, 30d, 90d"),
):
    """
    Get dashboard analytics (admin only).

    **Query Parameters:**
    - period: Time period (24h, 7d, 30d, 90d) - default: 7d

    **Response:**
    ```json
    {
        "success": true,
        "data": {
            "stats": {
                "total_forms": 45,
                "total_responses": 1234,
                "total_agents": 12,
                "avg_completion_rate": 87.5,
                "active_forms": 23,
                "pending_reviews": 8,
                "completion_trend": 5.2,
                "response_rate": 92.3
            },
            "response_trend": [
                {
                    "date": "2024-11-01",
                    "responses": 45,
                    "target": 50
                }
            ],
            "top_forms": [
                {
                    "name": "Community Survey 2024",
                    "responses": 234,
                    "completion_rate": 89.2
                }
            ],
            "recent_activity": [
                {
                    "id": 1,
                    "type": "response",
                    "message": "New response submitted for Census 2025",
                    "time": "2 minutes ago",
                    "user": "agent.johnson",
                    "status": "success"
                }
            ],
            "performance_metrics": {
                "avg_response_time": 4.2,
                "form_completion_rate": 87.5,
                "user_satisfaction": 4.6,
                "data_quality_score": 94.2
            }
        }
    }
    ```
    """
    # Only admins can view dashboard
    if current_user["role"] != "admin":
        # Agents can only see their own performance
        data = await get_agent_performance(conn, current_user["id"])
        return {"success": True, "data": data}

    stats = await get_dashboard_stats(conn, period=period)

    return {"success": True, "data": stats}


@router.get("/forms/{form_id}", response_model=dict)
async def get_form_analytics_route(
    form_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    admin_user: Annotated[dict, Depends(require_admin)],
):
    """
    Get analytics for a specific form (admin only).

    **Response:**
    ```json
    {
        "success": true,
        "data": {
            "total_responses": 245,
            "completion_rate": 89,
            "avg_completion_time": 180,
            "response_trend": [
                {"date": "2025-01-01", "responses": 10}
            ],
            "field_completion_rates": {
                "field_1": 100,
                "field_2": 98
            },
            "top_agents": [
                {
                    "agent_id": "usr_456",
                    "agent_name": "John Agent",
                    "responses": 45
                }
            ]
        }
    }
    ```
    """
    analytics = await get_form_analytics(conn, form_id)

    return {"success": True, "data": analytics}


@router.get("/forms/{form_id}/detailed", response_model=dict)
async def get_detailed_form_analytics(
    form_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    admin_user: Annotated[dict, Depends(require_admin)],
):
    """
    Get detailed analytics for a specific form (admin only).

    **Response:**
    ```json
    {
        "success": true,
        "data": {
            "form_id": "form-123",
            "metrics": {
                "total_responses": 456,
                "completion_rate": 89.2,
                "avg_completion_time": 6.8,
                "drop_off_points": [...],
                "response_distribution": {...}
            },
            "demographics": {
                "age_groups": {...},
                "locations": {...},
                "devices": {...}
            }
        }
    }
    ```
    """
    analytics = await get_form_analytics(conn, form_id)

    return {"success": True, "data": analytics}


@router.get("/agents/{agent_id}", response_model=dict)
async def get_agent_performance_route(
    agent_id: UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """
    Get performance analytics for an agent.

    Admins can view any agent's performance.
    Agents can only view their own performance.

    **Response:**
    ```json
    {
        "success": true,
        "data": {
            "total_responses": 145,
            "forms_assigned": 5,
            "completion_rate": 92,
            "avg_responses_per_day": 12,
            "response_trend": [
                {"date": "2025-01-01", "responses": 10}
            ],
            "forms_breakdown": [
                {
                    "form_id": "frm_123",
                    "form_name": "Census 2025",
                    "responses": 45,
                    "target": 50,
                    "progress": 90
                }
            ]
        }
    }
    ```
    """
    # Agents can only view their own performance
    if current_user["role"] != "admin" and str(agent_id) != current_user["id"]:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own performance",
        )

    performance = await get_agent_performance(conn, current_user["id"])

    return {"success": True, "data": performance}


@router.get("/performance", response_model=dict)
async def get_performance(
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
    period: str = Query("30d", description="Time period: 24h, 7d, 30d, 90d"),
):
    """
    Get detailed performance metrics for advanced analytics (admin only).

    **Query Parameters:**
    - period: Time period (24h, 7d, 30d, 90d) - default: 30d

    **Response:**
    ```json
    {
        "success": true,
        "data": {
            "time_range": "30d",
            "metrics": {
                "response_times": {
                    "avg": 4.2,
                    "p50": 3.8,
                    "p95": 12.5,
                    "p99": 25.3
                },
                "completion_rates": {
                    "overall": 87.5,
                    "by_form_type": {...},
                    "by_department": {...}
                },
                "user_engagement": {
                    "avg_session_duration": 8.5,
                    "bounce_rate": 12.3,
                    "return_visitors": 68.4
                }
            },
            "trends": {
                "daily_responses": [...],
                "completion_trends": [...],
                "user_satisfaction": [...]
            }
        }
    }
    ```
    """
    # Only admins can view performance metrics
    if current_user["role"] != "admin":
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required"
        )

    metrics = await get_performance_metrics(conn, period=period)

    return {"success": True, "data": metrics}
