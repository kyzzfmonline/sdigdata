"""
Async database connection using asyncpg (NO ORM).

asyncpg is the fastest PostgreSQL driver for Python:
- 3x faster than psycopg
- Built-in connection pooling
- Full async/await support
- Type-safe
- Production-ready
"""

import asyncpg
from typing import AsyncGenerator
from contextlib import asynccontextmanager

from app.core.config import Settings, get_settings


# Global connection pool
_pool: asyncpg.Pool | None = None


async def init_db_pool(settings: Settings):
    """
    Initialize database connection pool on startup.

    Call this in the FastAPI lifespan event.
    """
    global _pool
    _pool = await asyncpg.create_pool(
        dsn=settings.DATABASE_URL,
        min_size=10,  # Minimum number of connections in pool
        max_size=50,  # Maximum number of connections in pool
        max_queries=50000,  # Maximum queries per connection before recycling
        max_inactive_connection_lifetime=300,  # Close idle connections after 5 minutes
        timeout=30,  # Connection timeout in seconds
        command_timeout=60,  # Query timeout in seconds
    )
    print(f"✅ Database pool initialized: {_pool.get_size()} / {_pool.get_max_size()} connections")


async def close_db_pool():
    """
    Close database connection pool on shutdown.

    Call this in the FastAPI lifespan event.
    """
    global _pool
    if _pool:
        await _pool.close()
        print("✅ Database pool closed")


@asynccontextmanager
async def get_db_connection():
    """
    Get a database connection from the pool.

    Usage:
        async with get_db_connection() as conn:
            result = await conn.fetchrow("SELECT * FROM users WHERE id = $1", user_id)
    """
    if not _pool:
        raise RuntimeError("Database pool not initialized. Call init_db_pool() first.")

    async with _pool.acquire() as connection:
        yield connection


async def get_db() -> AsyncGenerator[asyncpg.Connection, None]:
    """
    FastAPI dependency for database connections.

    Usage in routes:
        @router.get("/users")
        async def get_users(conn: asyncpg.Connection = Depends(get_db)):
            users = await conn.fetch("SELECT * FROM users")
            return users
    """
    if not _pool:
        raise RuntimeError("Database pool not initialized. Call init_db_pool() first.")

    async with _pool.acquire() as connection:
        try:
            yield connection
        finally:
            # Connection is automatically returned to the pool
            pass


# Helper functions to convert asyncpg.Record to dict
def record_to_dict(record: asyncpg.Record | None) -> dict | None:
    """Convert asyncpg Record to dictionary."""
    if record is None:
        return None
    return dict(record)


def records_to_list(records: list[asyncpg.Record]) -> list[dict]:
    """Convert list of asyncpg Records to list of dictionaries."""
    return [dict(record) for record in records]
