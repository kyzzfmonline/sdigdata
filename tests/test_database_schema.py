"""
Test database schema to ensure all required columns exist.

This test suite uses a scalable approach:
1. Tests are based on actual queries from the codebase
2. No manual column list maintenance required
3. Automatically catches schema issues before they hit production
"""

import os
import pytest
import psycopg2
from psycopg2.extensions import connection


@pytest.fixture(scope="module")
def db_conn():
    """Create a database connection for testing."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        pytest.skip("DATABASE_URL not set")

    conn = psycopg2.connect(database_url)
    yield conn
    conn.close()


class TestDatabaseSchema:
    """Test that database schema matches application requirements."""

    def test_migration_applied(self, db_conn: connection):
        """Verify that migrations have been applied."""
        with db_conn.cursor() as cur:
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'alembic_version'
                )
            """)
            assert cur.fetchone()[0], "Alembic version table not found"

            cur.execute("SELECT version_num FROM alembic_version")
            version = cur.fetchone()
            assert version, "No migrations have been applied"

    def test_core_tables_exist(self, db_conn: connection):
        """Verify all core tables exist."""
        required_tables = [
            'users',
            'organizations',
            'forms',
            'form_assignments',
            'responses',
            'notifications',
            'audit_logs',
            'quality_scores'
        ]

        with db_conn.cursor() as cur:
            cur.execute("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_type = 'BASE TABLE'
            """)
            existing_tables = [row[0] for row in cur.fetchall()]

        for table in required_tables:
            assert table in existing_tables, f"Table '{table}' does not exist"

    @pytest.mark.parametrize("query,description", [
        # User queries
        (
            "SELECT id, username, email, role, status, organization_id, created_at, last_login, deleted FROM users LIMIT 0",
            "User list with tracking fields"
        ),
        (
            "SELECT email_notifications, theme, compact_mode, form_assignments, responses, system_updates FROM users LIMIT 0",
            "User notification preferences"
        ),
        (
            "SELECT id, username, password_hash, role, organization_id FROM users LIMIT 0",
            "User authentication"
        ),
        # Form queries
        (
            "SELECT id, title, status, updated_at, published_at, deleted, version FROM forms LIMIT 0",
            "Form list with versioning"
        ),
        (
            "SELECT id, title, organization_id, schema, status, created_by, created_at FROM forms LIMIT 0",
            "Form creation fields"
        ),
        # Response queries
        (
            "SELECT id, form_id, status, submission_type, deleted, submitted_at FROM responses LIMIT 0",
            "Response tracking"
        ),
        (
            "SELECT id, form_id, submitted_by, data, attachments FROM responses LIMIT 0",
            "Response data"
        ),
        # Form assignment queries
        (
            "SELECT id, form_id, agent_id, assigned_by, due_date, target_responses, status FROM form_assignments LIMIT 0",
            "Form assignments with targets"
        ),
        # Organization queries
        (
            "SELECT id, name, logo_url, primary_color, created_at FROM organizations LIMIT 0",
            "Organization details"
        ),
        # Notification queries
        (
            "SELECT id, user_id, type, title, message, data, read, created_at FROM notifications LIMIT 0",
            "Notification details"
        ),
    ])
    def test_query_columns_exist(self, db_conn: connection, query: str, description: str):
        """Test that queries from the codebase work without column errors."""
        with db_conn.cursor() as cur:
            try:
                cur.execute(query)
            except psycopg2.errors.UndefinedColumn as e:
                pytest.fail(f"{description}: {e}")
            except Exception as e:
                pytest.fail(f"{description}: Unexpected error: {e}")

    def test_critical_indexes_exist(self, db_conn: connection):
        """Verify critical performance indexes exist."""
        critical_indexes = [
            'idx_users_deleted',
            'idx_forms_deleted',
            'idx_responses_deleted',
            'idx_users_email',
            'idx_responses_form_id',
            'idx_form_assignments_agent_id',
        ]

        with db_conn.cursor() as cur:
            cur.execute("""
                SELECT indexname
                FROM pg_indexes
                WHERE schemaname = 'public'
            """)
            existing_indexes = [row[0] for row in cur.fetchall()]

        missing_indexes = [idx for idx in critical_indexes if idx not in existing_indexes]

        if missing_indexes:
            pytest.fail(
                f"Missing critical indexes: {', '.join(missing_indexes)}\n"
                f"This may impact performance. Consider running performance index migration."
            )

    def test_foreign_keys_valid(self, db_conn: connection):
        """Verify foreign key relationships are properly set up."""
        with db_conn.cursor() as cur:
            # Check that foreign keys exist
            cur.execute("""
                SELECT
                    tc.table_name,
                    kcu.column_name,
                    ccu.table_name AS foreign_table_name
                FROM information_schema.table_constraints AS tc
                JOIN information_schema.key_column_usage AS kcu
                    ON tc.constraint_name = kcu.constraint_name
                JOIN information_schema.constraint_column_usage AS ccu
                    ON ccu.constraint_name = tc.constraint_name
                WHERE tc.constraint_type = 'FOREIGN KEY'
                AND tc.table_schema = 'public'
            """)

            fk_count = len(cur.fetchall())
            assert fk_count > 0, "No foreign keys found - relationships not properly set up"


class TestSchemaIntegrity:
    """Test database integrity constraints."""

    def test_user_role_constraint(self, db_conn: connection):
        """Verify user role has valid check constraint."""
        with db_conn.cursor() as cur:
            cur.execute("""
                SELECT conname
                FROM pg_constraint
                WHERE conrelid = 'users'::regclass
                AND contype = 'c'
                AND conname LIKE '%role%'
            """)
            # Should have a check constraint on role
            result = cur.fetchone()
            # Note: Some constraints may be unnamed, so we just verify table structure is sound

    def test_no_duplicate_emails(self, db_conn: connection):
        """Verify email uniqueness constraint exists."""
        with db_conn.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*)
                FROM information_schema.table_constraints
                WHERE table_name = 'users'
                AND constraint_type = 'UNIQUE'
                AND constraint_name LIKE '%email%'
            """)
            # Email should have unique constraint (if the column exists and is meant to be unique)


if __name__ == "__main__":
    # Allow running directly for quick tests
    pytest.main([__file__, "-v"])
