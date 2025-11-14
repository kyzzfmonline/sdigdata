"""API metrics and monitoring routes."""

import time
from typing import Annotated

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, status

try:
    import psutil

    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
import os

from app.api.deps import require_admin
from app.core.database import get_db
from app.core.logging_config import get_logger
from app.core.responses import success_response

router = APIRouter(prefix="/metrics", tags=["Metrics & Monitoring"])
logger = get_logger(__name__)


@router.get("/api-usage", response_model=dict)
async def get_api_usage_metrics(
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(require_admin)],
    days: int = 7,
):
    """
    Get API usage statistics (admin only).

    **Query Parameters:**
    - days: Number of days to look back (default: 7)

    **Response:**
    ```json
    {
        "success": true,
        "data": {
            "period_days": 7,
            "total_requests": 15420,
            "requests_by_endpoint": {
                "/auth/login": 1250,
                "/responses": 8900,
                "/forms": 2340
            },
            "requests_by_method": {
                "GET": 12000,
                "POST": 3200,
                "PUT": 180,
                "DELETE": 40
            },
            "requests_by_hour": [
                {"hour": "2025-01-01T10:00:00Z", "count": 450},
                {"hour": "2025-01-01T11:00:00Z", "count": 520}
            ],
            "top_users": [
                {"user_id": "usr_123", "username": "agent1", "requests": 1250},
                {"user_id": "usr_456", "username": "agent2", "requests": 980}
            ]
        }
    }
    ```
    """
    # For now, return mock data since we don't have request logging implemented
    # In a real implementation, this would query from request logs table
    mock_data = {
        "period_days": days,
        "total_requests": 15420,
        "requests_by_endpoint": {
            "/auth/login": 1250,
            "/responses": 8900,
            "/forms": 2340,
            "/analytics/dashboard": 456,
            "/files/presign": 780,
            "/notifications": 234,
        },
        "requests_by_method": {"GET": 12000, "POST": 3200, "PUT": 180, "DELETE": 40},
        "requests_by_hour": [
            {
                "hour": f"2025-01-{day:02d}T{hour:02d}:00:00Z",
                "count": 400 + (day * 10) + (hour * 5),
            }
            for day in range(1, min(days + 1, 8))
            for hour in range(8, 18)
        ][:50],  # Limit to 50 entries
        "top_users": [
            {"user_id": "usr_123", "username": "agent1", "requests": 1250},
            {"user_id": "usr_456", "username": "agent2", "requests": 980},
            {"user_id": "usr_789", "username": "admin", "requests": 756},
            {"user_id": "usr_012", "username": "agent3", "requests": 623},
        ],
    }

    return success_response(data=mock_data)


@router.get("/performance", response_model=dict)
async def get_performance_metrics(
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(require_admin)],
):
    """
    Get API performance metrics (admin only).

    **Response:**
    ```json
    {
        "success": true,
        "data": {
            "response_times": {
                "avg_ms": 245,
                "p50_ms": 180,
                "p95_ms": 890,
                "p99_ms": 2100
            },
            "error_rates": {
                "total_errors": 45,
                "error_rate_percent": 0.29,
                "errors_by_status": {
                    "400": 12,
                    "401": 8,
                    "403": 5,
                    "404": 15,
                    "500": 5
                }
            },
            "throughput": {
                "requests_per_second": 12.5,
                "requests_per_minute": 750
            },
            "database_performance": {
                "avg_query_time_ms": 45,
                "slow_queries_count": 3,
                "connection_pool_usage": 0.75
            }
        }
    }
    ```
    """
    # Mock performance data
    mock_data = {
        "response_times": {"avg_ms": 245, "p50_ms": 180, "p95_ms": 890, "p99_ms": 2100},
        "error_rates": {
            "total_errors": 45,
            "error_rate_percent": 0.29,
            "errors_by_status": {"400": 12, "401": 8, "403": 5, "404": 15, "500": 5},
        },
        "throughput": {"requests_per_second": 12.5, "requests_per_minute": 750},
        "database_performance": {
            "avg_query_time_ms": 45,
            "slow_queries_count": 3,
            "connection_pool_usage": 0.75,
        },
    }

    return success_response(data=mock_data)


@router.get("/rate-limits", response_model=dict)
async def get_rate_limit_status(
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(require_admin)],
):
    """
    Get current rate limiting status (admin only).

    **Response:**
    ```json
    {
        "success": true,
        "data": {
            "login_attempts": {
                "blocked_ips": ["192.168.1.100", "10.0.0.50"],
                "blocked_users": ["suspicious_user"],
                "total_blocks_last_hour": 15
            },
            "anonymous_submissions": {
                "blocked_ips": ["203.0.113.1"],
                "total_blocks_last_hour": 3
            },
            "global_limits": {
                "requests_per_minute": 1000,
                "current_usage_percent": 75.5
            }
        }
    }
    ```
    """
    # Mock rate limit data
    mock_data = {
        "login_attempts": {
            "blocked_ips": ["192.168.1.100", "10.0.0.50"],
            "blocked_users": ["suspicious_user"],
            "total_blocks_last_hour": 15,
        },
        "anonymous_submissions": {
            "blocked_ips": ["203.0.113.1"],
            "total_blocks_last_hour": 3,
        },
        "global_limits": {"requests_per_minute": 1000, "current_usage_percent": 75.5},
    }

    return success_response(data=mock_data)


@router.get("/system-health", response_model=dict)
async def get_system_health(
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(require_admin)],
):
    """
    Get detailed system health metrics (admin only).

    **Response:**
    ```json
    {
        "success": true,
        "data": {
            "server": {
                "cpu_percent": 45.2,
                "memory_percent": 67.8,
                "disk_usage_percent": 23.4,
                "uptime_seconds": 345600
            },
            "database": {
                "connections_active": 12,
                "connections_idle": 8,
                "connections_total": 20,
                "cache_hit_ratio": 0.94
            },
            "storage": {
                "used_gb": 45.2,
                "total_gb": 100.0,
                "usage_percent": 45.2,
                "files_count": 12580
            },
            "application": {
                "version": "1.0.0",
                "environment": "production",
                "active_users_last_hour": 45,
                "total_forms": 125,
                "total_responses": 15420
            }
        }
    }
    ```
    """
    try:
        # Get system metrics
        if PSUTIL_AVAILABLE:
            server_metrics = {
                "cpu_percent": psutil.cpu_percent(interval=1),
                "memory_percent": psutil.virtual_memory().percent,
                "disk_usage_percent": psutil.disk_usage("/").percent,
                "uptime_seconds": int(time.time() - psutil.boot_time()),
            }
        else:
            server_metrics = {
                "cpu_percent": 0.0,
                "memory_percent": 0.0,
                "disk_usage_percent": 0.0,
                "uptime_seconds": 0,
            }

        # Get database metrics
        db_stats = await conn.fetchrow("""
            SELECT
                count(*) as active_connections
            FROM pg_stat_activity
            WHERE state = 'active'
        """)

        # Get application metrics
        app_stats = await conn.fetchrow("""
            SELECT
                (SELECT COUNT(*) FROM forms WHERE deleted = FALSE) as total_forms,
                (SELECT COUNT(*) FROM responses WHERE deleted = FALSE) as total_responses,
                (SELECT COUNT(*) FROM users WHERE deleted = FALSE) as total_users
        """)

        # Mock some additional metrics
        system_data = {
            "server": server_metrics,
            "database": {
                "connections_active": db_stats["active_connections"] or 0,
                "connections_idle": 8,  # Mock
                "connections_total": 20,  # Mock
                "cache_hit_ratio": 0.94,  # Mock
            },
            "storage": {
                "used_gb": 45.2,  # Mock
                "total_gb": 100.0,  # Mock
                "usage_percent": 45.2,  # Mock
                "files_count": 12580,  # Mock
            },
            "application": {
                "version": "1.0.0",
                "environment": os.getenv("ENVIRONMENT", "development"),
                "active_users_last_hour": 45,  # Mock
                "total_forms": app_stats["total_forms"] or 0,
                "total_responses": app_stats["total_responses"] or 0,
                "total_users": app_stats["total_users"] or 0,
            },
        }

        return success_response(data=system_data)

    except Exception as e:
        logger.error(f"Error getting system health: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve system health metrics",
        )


@router.get("/logs", response_model=dict)
async def get_application_logs(
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(require_admin)],
    level: str = "ERROR",
    limit: int = 50,
    hours: int = 24,
):
    """
    Get recent application logs (admin only).

    **Query Parameters:**
    - level: Log level to filter (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    - limit: Maximum number of logs to return (default: 50)
    - hours: Hours to look back (default: 24)

    **Response:**
    ```json
    {
        "success": true,
        "data": {
            "logs": [
                {
                    "timestamp": "2025-01-01T10:30:00Z",
                    "level": "ERROR",
                    "message": "Database connection failed",
                    "module": "app.core.database",
                    "user_id": null
                }
            ],
            "total_count": 5,
            "filtered_count": 5
        }
    }
    ```
    """
    # Mock log data since we don't have a logs table
    mock_logs = [
        {
            "timestamp": "2025-01-01T10:30:00Z",
            "level": level,
            "message": f"Sample {level.lower()} message",
            "module": "app.api.routes.metrics",
            "user_id": None,
        }
        for _ in range(min(limit, 10))
    ]

    return success_response(
        data={
            "logs": mock_logs,
            "total_count": len(mock_logs),
            "filtered_count": len(mock_logs),
        }
    )
