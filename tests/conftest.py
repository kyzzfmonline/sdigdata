"""
Pytest configuration and fixtures for SDIGdata backend tests.

This module provides:
- Test database setup and teardown
- FastAPI test client
- Authentication fixtures
- Test data fixtures
- Utility functions for testing
"""

import os
import tempfile
from pathlib import Path
from typing import Any
from uuid import UUID

import asyncpg
import pytest
from httpx import AsyncClient

from app.core.config import Settings
from app.core.database import close_db_pool, init_db_pool
from app.core.security import hash_password
from app.main import app
from app.services.forms import create_form
from app.services.organizations import create_organization
from app.services.responses import create_response
from app.services.users import create_user


# Test settings override
@pytest.fixture(scope="session", autouse=True)
def setup_test_env():
    """Set up test environment variables."""
    # Use test environment variables
    test_env = {
        "ENVIRONMENT": "test",
        "DATABASE_URL": "postgresql://metroform:password@localhost:5432/sdigdata",
        "SECRET_KEY": "test_secret_key_for_testing_only",
        "JWT_ALGORITHM": "HS256",
        "ACCESS_TOKEN_EXPIRE_MINUTES": 60,
        "SPACES_ENDPOINT": "http://127.0.0.1:9000",
        "SPACES_REGION": "us-east-1",
        "SPACES_BUCKET": "sdigdata-test",
        "SPACES_KEY": "minio",
        "SPACES_SECRET": "miniopass",
        "CORS_ORIGINS": "*",
        "SMTP_SERVER": "localhost",
        "SMTP_PORT": "1025",  # MailHog port
        "FROM_EMAIL": "test@example.com",
        "FROM_NAME": "Test SDIGdata",
    }

    # Store old values and set test values
    old_values = {}
    for key, value in test_env.items():
        old_values[key] = os.environ.get(key)
        os.environ[key] = str(value)

    # Force reload settings with test environment
    from app.core.config import settings

    # Update settings attributes with test values
    settings.DATABASE_URL = test_env["DATABASE_URL"]
    settings.SECRET_KEY = test_env["SECRET_KEY"]
    settings.SPACES_ENDPOINT = test_env["SPACES_ENDPOINT"]
    settings.SPACES_REGION = test_env["SPACES_REGION"]
    settings.SPACES_BUCKET = test_env["SPACES_BUCKET"]
    settings.SPACES_KEY = test_env["SPACES_KEY"]
    settings.SPACES_SECRET = test_env["SPACES_SECRET"]
    settings.CORS_ORIGINS = test_env["CORS_ORIGINS"]
    settings.SMTP_SERVER = test_env["SMTP_SERVER"]
    settings.SMTP_PORT = int(test_env["SMTP_PORT"])
    settings.FROM_EMAIL = test_env["FROM_EMAIL"]
    settings.FROM_NAME = test_env["FROM_NAME"]
    settings.ENVIRONMENT = test_env["ENVIRONMENT"]

    yield

    # Restore old values
    for key, old_value in old_values.items():
        if old_value is not None:
            os.environ[key] = old_value
        else:
            os.environ.pop(key, None)


@pytest.fixture(scope="session")
def test_settings():
    """Get test settings from updated settings object."""
    from app.core.config import settings

    return settings


@pytest.fixture(scope="session")
async def test_db_pool(test_settings: Settings):
    """Create and manage test database connection pool."""
    # Initialize test database pool (this also sets the global _pool)
    await init_db_pool(test_settings)

    # Run database migrations for tests
    from app.core.database import _pool

    if _pool:
        async with _pool.acquire() as conn:
            # Create test schema if needed
            await conn.execute("""
                CREATE SCHEMA IF NOT EXISTS test;
            """)

    yield _pool

    # Cleanup
    await close_db_pool()


@pytest.fixture(scope="function")
async def db_connection(test_settings):
    """Provide a database connection for each test."""

    # Create a direct connection for each test
    conn = await asyncpg.connect(dsn=test_settings.DATABASE_URL)

    # Start a transaction manually
    await conn.execute("BEGIN")

    try:
        yield conn
    finally:
        # Rollback any changes
        try:
            await conn.execute("ROLLBACK")
        except Exception:
            pass  # Connection might be closed
        await conn.close()


@pytest.fixture(scope="function")
def client(test_db_pool):
    """FastAPI test client."""
    from fastapi.testclient import TestClient

    return TestClient(app)


@pytest.fixture(scope="function")
async def async_client(test_db_pool):
    """FastAPI async test client."""
    from httpx import ASGITransport

    from app.main import app

    # Create async client for testing
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as async_client:
        yield async_client


@pytest.fixture(scope="function")
async def auth_headers(async_client, test_user: dict[str, Any]) -> dict[str, str]:
    """Authentication headers for test user."""
    # Login to get token
    login_response = await async_client.post(
        "/auth/login",
        json={"username": test_user["username"], "password": test_user["password"]},
    )

    assert login_response.status_code == 200
    token_data = login_response.json()
    token = token_data["data"]["access_token"]

    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="function")
async def admin_auth_headers(
    async_client, admin_user: dict[str, Any], event_loop
) -> dict[str, str]:
    """Authentication headers for admin user."""
    # Login to get token
    login_response = await async_client.post(
        "/auth/login",
        json={"username": admin_user["username"], "password": admin_user["password"]},
    )

    assert login_response.status_code == 200
    token_data = login_response.json()
    token = token_data["data"]["access_token"]

    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="function")
async def test_user(db_connection) -> dict[str, Any]:
    """Create a test user for testing."""
    # First create an organization
    org_result = await create_organization(
        db_connection, name="Test Organization", logo_url=None, primary_color=None
    )
    org_id = org_result["id"]

    # Hash password
    password_hash = hash_password("testpass123")

    # Create user
    user_result = await create_user(
        db_connection,
        username="testuser",
        password_hash=password_hash,
        role="agent",
        organization_id=org_id,
    )

    # Assign RBAC role to user
    await db_connection.execute(
        """
        INSERT INTO user_roles (user_id, role_id, is_active)
        SELECT $1, r.id, TRUE
        FROM roles r
        WHERE r.name = 'agent'
        ON CONFLICT (user_id, role_id) DO NOTHING
        """,
        str(user_result["id"]),
    )

    user_data = {
        "id": user_result["id"],
        "username": "testuser",
        "password": "testpass123",  # Plain password for login
        "role": "agent",
        "organization_id": org_id,
    }

    return user_data


@pytest.fixture(scope="function")
async def admin_user(db_connection) -> dict[str, Any]:
    """Create an admin user for testing."""
    # First create an organization
    org_result = await create_organization(
        db_connection, name="Admin Organization", logo_url=None, primary_color=None
    )
    org_id = org_result["id"]

    # Hash password
    password_hash = hash_password("admin123")

    # Create admin user
    user_result = await create_user(
        db_connection,
        username="admin",
        password_hash=password_hash,
        role="admin",
        organization_id=org_id,
    )

    # Assign RBAC role to admin user
    await db_connection.execute(
        """
        INSERT INTO user_roles (user_id, role_id, is_active)
        SELECT $1, r.id, TRUE
        FROM roles r
        WHERE r.name = 'admin'
        ON CONFLICT (user_id, role_id) DO NOTHING
        """,
        str(user_result["id"]),
    )

    user_data = {
        "id": user_result["id"],
        "username": "admin",
        "password": "admin123",  # Plain password for login
        "role": "admin",
        "organization_id": org_id,
    }

    return user_data


@pytest.fixture(scope="function")
async def test_organization(db_connection) -> dict[str, Any]:
    """Create a test organization."""
    org_result = await create_organization(
        db_connection, name="Test Organization", logo_url=None, primary_color=None
    )

    return org_result


@pytest.fixture(scope="function")
async def test_form(
    db_connection, test_organization: dict[str, Any], admin_user: dict[str, Any]
) -> dict[str, Any]:
    """Create a test form."""
    form_result = await create_form(
        db_connection,
        title="Test Form",
        organization_id=test_organization["id"],
        schema={
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"},
                "location": {"type": "string"},
            },
            "required": ["name"],
        },
        created_by=admin_user["id"],
        status="draft",
        description="Form for testing",
    )

    return form_result


@pytest.fixture(scope="function")
def temp_file():
    """Create a temporary file for testing uploads."""
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        f.write(b"Test file content for upload testing")
        temp_path = f.name

    yield temp_path

    # Cleanup
    Path(temp_path).unlink(missing_ok=True)


# Utility functions for tests
async def create_test_response(
    db_connection, form_id: str, user_id: str, data: dict[str, Any]
) -> dict[str, Any]:
    """Helper function to create a test response."""
    response_result = await create_response(
        db_connection,
        form_id=UUID(form_id),
        submitted_by=UUID(user_id) if user_id else None,
        data=data,
    )

    if response_result is None:
        raise ValueError("Failed to create test response")

    return response_result
