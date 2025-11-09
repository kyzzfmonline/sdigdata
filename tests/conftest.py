import pytest
from fastapi.testclient import TestClient
from app.main import app
import uuid
import asyncpg
import asyncio
from app.core.config import Settings, get_settings
from app.api.deps import get_db


@pytest.fixture(scope="session")
def test_settings():
    """Override settings for tests."""
    return Settings(
        DATABASE_URL="postgresql://metroform:password@localhost:5432/sdigdata",
        DATABASE_URL_YOYO="postgresql://metroform:password@localhost:5432/sdigdata",
        DATABASE_URL_APP="postgresql://metroform:password@localhost:5432/sdigdata",
        SECRET_KEY="test_secret",
        SPACES_ENDPOINT="http://localhost:9000",
        SPACES_REGION="us-east-1",
        SPACES_BUCKET="test-bucket",
        SPACES_KEY="minio",
        SPACES_SECRET="miniopass",
    )


@pytest.fixture(scope="session")
async def db_pool(test_settings):
    """
    An asyncpg connection pool to the test database.
    """
    pool = await asyncpg.create_pool(
        test_settings.DATABASE_URL_APP, min_size=1, max_size=10
    )
    yield pool
    await pool.close()


@pytest.fixture(scope="function")
async def db_conn(db_pool):
    """
    A single asyncpg connection from the pool for each test function.
    """
    conn = await db_pool.acquire()
    yield conn
    await db_pool.release(conn)


@pytest.fixture(scope="function")
async def client(test_settings, db_pool):
    """
    A TestClient instance for making requests to the application.
    """

    async def get_db_override():
        async with db_pool.acquire() as conn:
            yield conn

    def get_settings_override():
        return test_settings

    app.dependency_overrides[get_db] = get_db_override
    app.dependency_overrides[get_settings] = get_settings_override

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


@pytest.fixture(scope="module")
def test_organization_id():
    """
    A valid organization ID for testing purposes.
    """
    return str(uuid.uuid4())


@pytest.fixture(scope="session")
async def test_organization(db_pool):
    """
    Create an organization for testing.
    """
    from app.services import organizations

    async with db_pool.acquire() as conn:
        org = await organizations.create_organization(conn, name="Test Organization")
        return org


@pytest.fixture(scope="session")
async def admin_user(db_pool, test_organization):
    """
    Create an admin user for testing.
    """
    from app.core.security import hash_password
    from app.services import users

    password_hash = hash_password("admin123")

    async with db_pool.acquire() as conn:
        # Try to get existing user first
        existing_user = await conn.fetchrow(
            "SELECT id, username, role, organization_id, created_at FROM users WHERE username = $1",
            "admin",
        )

        if existing_user:
            return dict(existing_user)

        # Create new user if doesn't exist
        user = await users.create_user(
            conn,
            username="admin",
            password_hash=password_hash,
            role="admin",
            organization_id=test_organization["id"],
        )
        return user


@pytest.fixture(scope="function")
async def auth_token(client, admin_user):
    """
    Get an auth token for the admin user.
    """
    response = client.post(
        "/auth/login",
        json={"username": admin_user["username"], "password": "admin123"},
    )
    return response.json()["data"]["access_token"]


@pytest.fixture(scope="session")
async def agent_user(db_pool, test_organization):
    """
    Create an agent user for testing.
    """
    from app.core.security import hash_password
    from app.services import users

    async with db_pool.acquire() as conn:
        # Try to get existing user first
        existing_user = await conn.fetchrow(
            "SELECT id, username, role, organization_id, created_at FROM users WHERE username = $1",
            "agent",
        )

        if existing_user:
            return dict(existing_user)

        password_hash = hash_password("agent123")
        user = await users.create_user(
            conn,
            username="agent",
            password_hash=password_hash,
            role="agent",
            organization_id=test_organization["id"],
        )
        return user
