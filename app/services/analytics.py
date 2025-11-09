"""Analytics service functions."""

from typing import Optional
from uuid import UUID
from datetime import datetime, timedelta
import asyncpg


async def get_dashboard_stats(conn: asyncpg.Connection, period: str = "7d") -> dict:
    """
    Get dashboard statistics.

    Args:
        period: Time period (24h, 7d, 30d, 90d)
    """
    # Calculate date range based on period
    period_days = {
        "24h": 1,
        "7d": 7,
        "30d": 30,
        "90d": 90,
    }
    days = period_days.get(period, 7)
    start_date = datetime.now() - timedelta(days=days)

    # Total forms
    total_forms = await conn.fetchval(
        "SELECT COUNT(*) FROM forms WHERE deleted = FALSE"
    )

    # Active forms (published)
    active_forms = await conn.fetchval(
        "SELECT COUNT(*) FROM forms WHERE status = 'published' AND deleted = FALSE"
    )

    # Forms created in period
    period_forms = await conn.fetchval(
        "SELECT COUNT(*) FROM forms WHERE created_at >= $1 AND deleted = FALSE",
        start_date,
    )

    # Total responses
    total_responses = await conn.fetchval(
        "SELECT COUNT(*) FROM responses WHERE deleted = FALSE"
    )

    # Responses in period
    period_responses = await conn.fetchval(
        "SELECT COUNT(*) FROM responses WHERE submitted_at >= $1 AND deleted = FALSE",
        start_date,
    )

    # Total agents
    total_agents = await conn.fetchval(
        "SELECT COUNT(*) FROM users WHERE role = 'agent' AND deleted = FALSE"
    )

    # Calculate completion rate (responses with all required fields)
    completion_data = await conn.fetchrow(
        """
        SELECT
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE status = 'complete') as complete
        FROM responses
        WHERE deleted = FALSE
        """
    )
    avg_completion_rate = 0
    if completion_data and completion_data["total"] > 0:
        avg_completion_rate = int(
            (completion_data["complete"] / completion_data["total"]) * 100
        )

    # Pending reviews (incomplete responses)
    pending_reviews = await conn.fetchval(
        "SELECT COUNT(*) FROM responses WHERE status = 'incomplete' AND deleted = FALSE"
    )

    # Response rate (responses vs form assignments targets)
    response_rate_data = await conn.fetchrow(
        """
        SELECT
            COALESCE(SUM(fa.target_responses), 0) as total_targets,
            COUNT(r.id) as total_responses
        FROM form_assignments fa
        LEFT JOIN responses r ON fa.form_id = r.form_id AND r.deleted = FALSE
        """
    )
    response_rate = 0
    if response_rate_data and response_rate_data["total_targets"] > 0:
        response_rate = int(
            (
                response_rate_data["total_responses"]
                / response_rate_data["total_targets"]
            )
            * 100
        )

    # Completion trend (compare current period vs previous period)
    prev_start_date = start_date - timedelta(days=days)
    prev_completion_data = await conn.fetchrow(
        """
        SELECT
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE status = 'complete') as complete
        FROM responses
        WHERE submitted_at >= $1 AND submitted_at < $2 AND deleted = FALSE
        """,
        prev_start_date,
        start_date,
    )
    prev_completion_rate = 0
    if prev_completion_data and prev_completion_data["total"] > 0:
        prev_completion_rate = (
            prev_completion_data["complete"] / prev_completion_data["total"]
        ) * 100

    completion_trend = 0
    if prev_completion_rate > 0:
        completion_trend = (
            (avg_completion_rate - prev_completion_rate) / prev_completion_rate
        ) * 100

    # Get response trend (daily counts with targets)
    response_trend_rows = await conn.fetch(
        """
        SELECT
            DATE(submitted_at) as date,
            COUNT(*) as responses,
            COALESCE(SUM(fa.target_responses), 0) as target
        FROM responses r
        LEFT JOIN form_assignments fa ON r.form_id = fa.form_id
        WHERE r.submitted_at >= $1 AND r.deleted = FALSE
        GROUP BY DATE(submitted_at)
        ORDER BY date ASC
        """,
        start_date,
    )
    response_trend = [
        {
            "date": str(row["date"]),
            "responses": row["responses"],
            "target": row["target"],
        }
        for row in response_trend_rows
    ]

    # Get top forms
    top_forms_rows = await conn.fetch(
        """
        SELECT
            f.id as form_id,
            f.title as name,
            COUNT(r.id) as responses,
            COUNT(r.id) FILTER (WHERE r.status = 'complete') * 100.0 / NULLIF(COUNT(r.id), 0) as completion_rate
        FROM forms f
        LEFT JOIN responses r ON f.id = r.form_id AND r.deleted = FALSE
        WHERE f.deleted = FALSE
        GROUP BY f.id, f.title
        ORDER BY responses DESC
        LIMIT 5
        """
    )
    top_forms = [
        {
            "form_id": str(row["form_id"]),
            "name": row["name"],
            "responses": row["responses"],
            "completion_rate": int(row["completion_rate"])
            if row["completion_rate"]
            else 0,
        }
        for row in top_forms_rows
    ]

    # Get recent activity
    recent_activity_rows = await conn.fetch(
        """
        SELECT
            r.id,
            'response' as type,
            'New response submitted for ' || f.title as message,
            u.username as user,
            r.submitted_at as timestamp,
            'success' as status,
            EXTRACT(EPOCH FROM (NOW() - r.submitted_at))/60 as minutes_ago
        FROM responses r
        JOIN forms f ON r.form_id = f.id
        JOIN users u ON r.submitted_by = u.id
        WHERE r.deleted = FALSE
        ORDER BY r.submitted_at DESC
        LIMIT 10
        """
    )
    recent_activity = [
        {
            "id": int(row["id"]) if row["id"] else None,
            "type": row["type"],
            "message": row["message"],
            "time": f"{int(row['minutes_ago'])} minutes ago"
            if row["minutes_ago"] < 60
            else f"{int(row['minutes_ago'] / 60)} hours ago",
            "user": row["user"],
            "status": row["status"],
        }
        for row in recent_activity_rows
    ]

    # Performance metrics (placeholder values - would need actual system monitoring)
    performance_metrics = {
        "avg_response_time": 4.2,
        "form_completion_rate": avg_completion_rate,
        "user_satisfaction": 4.6,  # Placeholder
        "data_quality_score": 94.2,  # Placeholder
    }

    return {
        "stats": {
            "total_forms": total_forms,
            "total_responses": total_responses,
            "total_agents": total_agents,
            "avg_completion_rate": avg_completion_rate,
            "active_forms": active_forms,
            "pending_reviews": pending_reviews,
            "completion_trend": round(completion_trend, 1),
            "response_rate": response_rate,
        },
        "response_trend": response_trend,
        "top_forms": top_forms,
        "recent_activity": recent_activity,
        "performance_metrics": performance_metrics,
    }


async def get_form_analytics(conn: asyncpg.Connection, form_id: UUID) -> dict:
    """Get analytics for a specific form."""
    # Total responses
    total_responses = await conn.fetchval(
        "SELECT COUNT(*) FROM responses WHERE form_id = $1 AND deleted = FALSE",
        str(form_id),
    )

    # Completion rate
    completion_data = await conn.fetchrow(
        """
        SELECT
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE status = 'complete') as complete
        FROM responses
        WHERE form_id = $1 AND deleted = FALSE
        """,
        str(form_id),
    )
    completion_rate = 0
    if completion_data and completion_data["total"] > 0:
        completion_rate = int(
            (completion_data["complete"] / completion_data["total"]) * 100
        )

    # Average completion time (placeholder - would need actual timing data)
    avg_completion_time = 6.8

    # Drop-off points (placeholder - would need step-by-step completion tracking)
    drop_off_points = [
        {"step": 3, "drop_off_rate": 15.2},
        {"step": 7, "drop_off_rate": 8.7},
    ]

    # Response distribution
    response_distribution = {
        "daily": [],  # Would need daily aggregation
        "weekly": [],  # Would need weekly aggregation
        "monthly": [],  # Would need monthly aggregation
    }

    # Get response trend (last 30 days) for daily distribution
    response_trend_rows = await conn.fetch(
        """
        SELECT
            DATE(submitted_at) as date,
            COUNT(*) as responses
        FROM responses
        WHERE form_id = $1 AND submitted_at >= NOW() - INTERVAL '30 days' AND deleted = FALSE
        GROUP BY DATE(submitted_at)
        ORDER BY date ASC
        """,
        str(form_id),
    )
    response_distribution["daily"] = [
        {"date": str(row["date"]), "responses": row["responses"]}
        for row in response_trend_rows
    ]

    # Demographics (placeholder - would need actual demographic data collection)
    demographics = {
        "age_groups": {"18-24": 25, "25-34": 35, "35-44": 20, "45-54": 12, "55+": 8},
        "locations": {
            "district_a": 120,
            "district_b": 98,
            "district_c": 76,
            "district_d": 54,
        },
        "devices": {"mobile": 68, "desktop": 32},
    }

    # Top agents
    top_agents_rows = await conn.fetch(
        """
        SELECT
            u.id as agent_id,
            u.username as agent_name,
            COUNT(r.id) as responses
        FROM responses r
        JOIN users u ON r.submitted_by = u.id
        WHERE r.form_id = $1 AND r.deleted = FALSE
        GROUP BY u.id, u.username
        ORDER BY responses DESC
        LIMIT 5
        """,
        str(form_id),
    )
    top_agents = [
        {
            "agent_id": str(row["agent_id"]),
            "agent_name": row["agent_name"],
            "responses": row["responses"],
        }
        for row in top_agents_rows
    ]

    return {
        "form_id": str(form_id),
        "metrics": {
            "total_responses": total_responses,
            "completion_rate": completion_rate,
            "avg_completion_time": avg_completion_time,
            "drop_off_points": drop_off_points,
            "response_distribution": response_distribution,
        },
        "demographics": demographics,
        "top_agents": top_agents,  # Keep for backward compatibility
    }


async def get_agent_performance(conn: asyncpg.Connection, agent_id: UUID) -> dict:
    """Get performance analytics for an agent."""
    # Total responses
    total_responses = await conn.fetchval(
        "SELECT COUNT(*) FROM responses WHERE submitted_by = $1 AND deleted = FALSE",
        str(agent_id),
    )

    # Forms assigned
    forms_assigned = await conn.fetchval(
        "SELECT COUNT(*) FROM form_assignments WHERE agent_id = $1", str(agent_id)
    )

    # Completion rate
    completion_data = await conn.fetchrow(
        """
        SELECT
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE status = 'complete') as complete
        FROM responses
        WHERE submitted_by = $1 AND deleted = FALSE
        """,
        str(agent_id),
    )
    completion_rate = 0
    if completion_data and completion_data["total"] > 0:
        completion_rate = int(
            (completion_data["complete"] / completion_data["total"]) * 100
        )

    # Response trend (last 30 days)
    response_trend_rows = await conn.fetch(
        """
        SELECT
            DATE(submitted_at) as date,
            COUNT(*) as responses
        FROM responses
        WHERE submitted_by = $1 AND submitted_at >= NOW() - INTERVAL '30 days' AND deleted = FALSE
        GROUP BY DATE(submitted_at)
        ORDER BY date ASC
        """,
        str(agent_id),
    )
    response_trend = [
        {"date": str(row["date"]), "responses": row["responses"]}
        for row in response_trend_rows
    ]

    # Forms breakdown
    forms_breakdown_rows = await conn.fetch(
        """
        SELECT
            f.id as form_id,
            f.title as form_name,
            COUNT(r.id) as responses,
            fa.target_responses as target,
            CASE
                WHEN fa.target_responses > 0
                THEN (COUNT(r.id) * 100.0 / fa.target_responses)
                ELSE 0
            END as progress
        FROM form_assignments fa
        JOIN forms f ON fa.form_id = f.id
        LEFT JOIN responses r ON f.id = r.form_id AND r.submitted_by = $1 AND r.deleted = FALSE
        WHERE fa.agent_id = $2
        GROUP BY f.id, f.title, fa.target_responses
        ORDER BY responses DESC
        """,
        str(agent_id),
        str(agent_id),
    )
    forms_breakdown = [
        {
            "form_id": str(row["form_id"]),
            "form_name": row["form_name"],
            "responses": row["responses"],
            "target": row["target"] if row["target"] else 0,
            "progress": int(row["progress"]) if row["progress"] else 0,
        }
        for row in forms_breakdown_rows
    ]

    # Calculate avg responses per day (last 30 days)
    avg_responses_per_day = 0
    if response_trend:
        total_days = len(response_trend)
        total_resp = sum(day["responses"] for day in response_trend)
        avg_responses_per_day = total_resp // total_days if total_days > 0 else 0

    return {
        "total_responses": total_responses,
        "forms_assigned": forms_assigned,
        "completion_rate": completion_rate,
        "avg_responses_per_day": avg_responses_per_day,
        "response_trend": response_trend,
        "forms_breakdown": forms_breakdown,
    }


async def get_performance_metrics(
    conn: asyncpg.Connection, period: str = "30d"
) -> dict:
    """Get detailed performance metrics for advanced analytics."""
    # Calculate date range
    period_days = {
        "24h": 1,
        "7d": 7,
        "30d": 30,
        "90d": 90,
    }
    days = period_days.get(period, 30)
    start_date = datetime.now() - timedelta(days=days)

    # Response times (placeholder - would need actual timing data)
    response_times = {"avg": 4.2, "p50": 3.8, "p95": 12.5, "p99": 25.3}

    # Completion rates
    completion_data = await conn.fetchrow(
        """
        SELECT
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE status = 'complete') as complete
        FROM responses
        WHERE submitted_at >= $1 AND deleted = FALSE
        """,
        start_date,
    )

    overall_completion = 0
    if completion_data and completion_data["total"] > 0:
        overall_completion = int(
            (completion_data["complete"] / completion_data["total"]) * 100
        )

    # Completion rates by form type (simplified - assuming all are "survey")
    completion_by_type = {
        "survey": overall_completion,
        "registration": max(overall_completion - 5, 0),
        "feedback": min(overall_completion + 3, 100),
    }

    # Completion rates by department (simplified - using organization names)
    dept_completion = await conn.fetch(
        """
        SELECT
            o.name as department,
            COUNT(r.id) as total,
            COUNT(r.id) FILTER (WHERE r.status = 'complete') as complete
        FROM organizations o
        LEFT JOIN forms f ON o.id = f.organization_id
        LEFT JOIN responses r ON f.id = r.form_id AND r.submitted_at >= $1 AND r.deleted = FALSE
        GROUP BY o.id, o.name
        """,
        start_date,
    )

    completion_by_dept = {}
    for row in dept_completion:
        if row["total"] > 0:
            rate = int((row["complete"] / row["total"]) * 100)
            completion_by_dept[row["department"]] = rate
        else:
            completion_by_dept[row["department"]] = 0

    # User engagement (placeholder metrics)
    user_engagement = {
        "avg_session_duration": 8.5,
        "bounce_rate": 12.3,
        "return_visitors": 68.4,
    }

    # Trends data
    daily_responses = await conn.fetch(
        """
        SELECT
            DATE(submitted_at) as date,
            COUNT(*) as responses
        FROM responses
        WHERE submitted_at >= $1 AND deleted = FALSE
        GROUP BY DATE(submitted_at)
        ORDER BY date ASC
        """,
        start_date,
    )

    completion_trends = await conn.fetch(
        """
        SELECT
            DATE(submitted_at) as date,
            COUNT(*) FILTER (WHERE status = 'complete') * 100.0 / NULLIF(COUNT(*), 0) as rate
        FROM responses
        WHERE submitted_at >= $1 AND deleted = FALSE
        GROUP BY DATE(submitted_at)
        ORDER BY date ASC
        """,
        start_date,
    )

    # User satisfaction (placeholder)
    user_satisfaction_trend = [
        {
            "date": str((datetime.now() - timedelta(days=i)).date()),
            "score": 4.2 + (i % 3 - 1) * 0.3,
        }
        for i in range(min(days, 30))
    ]

    return {
        "time_range": period,
        "metrics": {
            "response_times": response_times,
            "completion_rates": {
                "overall": overall_completion,
                "by_form_type": completion_by_type,
                "by_department": completion_by_dept,
            },
            "user_engagement": user_engagement,
        },
        "trends": {
            "daily_responses": [
                {"date": str(row["date"]), "responses": row["responses"]}
                for row in daily_responses
            ],
            "completion_trends": [
                {
                    "date": str(row["date"]),
                    "rate": round(float(row["rate"]), 1) if row["rate"] else 0,
                }
                for row in completion_trends
            ],
            "user_satisfaction": user_satisfaction_trend,
        },
    }
