#!/bin/bash
# Verify database schema and migrations
# This script uses a scalable approach that doesn't require manually maintaining column lists

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Load environment variables
if [ -f "$PROJECT_ROOT/.env" ]; then
    export $(grep -v '^#' "$PROJECT_ROOT/.env" | xargs)
fi

# Check if DATABASE_URL is set
if [ -z "$DATABASE_URL" ]; then
    echo "❌ ERROR: DATABASE_URL is not set"
    echo "ℹ️  Run one of: ./scripts/use-dev.sh, ./scripts/use-prod.sh, or ./scripts/use-local.sh"
    exit 1
fi

echo "🔍 Verifying Database Schema"
echo "Environment: $ENVIRONMENT"
echo "Database: $(echo $DATABASE_URL | sed 's/:\/\/.*@/:\/\/[REDACTED]@/')"
echo ""

# Run Python verification script
python3 << 'PYTHON_SCRIPT'
import psycopg2
import os
import sys

def test_query(cur, description, query, expected_columns=None):
    """Test a query to ensure all columns exist."""
    try:
        cur.execute(query)
        if expected_columns:
            # Verify column names match
            actual_cols = [desc[0] for desc in cur.description]
            missing = [col for col in expected_columns if col not in actual_cols]
            if missing:
                print(f"  ❌ Missing columns: {', '.join(missing)}")
                return False
        print(f"  ✅ {description}")
        return True
    except Exception as e:
        print(f"  ❌ {description}")
        print(f"     Error: {str(e)}")
        return False

try:
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))

    with conn.cursor() as cur:
        print("=" * 70)
        print("MIGRATION STATUS")
        print("=" * 70)

        # Check if alembic_version table exists
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'alembic_version'
            )
        """)

        if not cur.fetchone()[0]:
            print("❌ Alembic version table not found!")
            print("   Run: ./scripts/db-migrate.sh")
            sys.exit(1)

        # Get current migration version
        cur.execute("SELECT version_num FROM alembic_version")
        version = cur.fetchone()
        if version:
            print(f"✅ Current revision: {version[0]}")
        else:
            print("❌ No migrations applied!")
            sys.exit(1)

        print()
        print("=" * 70)
        print("SCHEMA VALIDATION")
        print("=" * 70)
        print("Testing critical queries from the codebase...")
        print()

        all_good = True

        # Test core tables exist
        print("📋 Core Tables:")
        core_tables = ['users', 'organizations', 'forms', 'form_assignments', 'responses', 'notifications']
        cur.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_type = 'BASE TABLE'
        """)
        existing_tables = [row[0] for row in cur.fetchall()]

        for table in core_tables:
            if table in existing_tables:
                print(f"  ✅ {table} table exists")
            else:
                print(f"  ❌ {table} table missing")
                all_good = False

        print()
        print("🔍 Query Tests:")

        # Test queries that are actually used in the code
        # These will fail if columns are missing

        # Test 1: User queries
        all_good &= test_query(
            cur,
            "User list query (with email, last_login, status, deleted)",
            "SELECT id, username, email, role, status, organization_id, created_at, last_login, deleted FROM users LIMIT 0"
        )

        all_good &= test_query(
            cur,
            "User preferences query (notifications, theme, compact_mode)",
            "SELECT email_notifications, theme, compact_mode, form_assignments, responses, system_updates FROM users LIMIT 0"
        )

        # Test 2: Form queries
        all_good &= test_query(
            cur,
            "Form query (with updated_at, published_at, deleted)",
            "SELECT id, title, status, updated_at, published_at, deleted FROM forms LIMIT 0"
        )

        # Test 3: Response queries
        all_good &= test_query(
            cur,
            "Response query (with status, submission_type, deleted)",
            "SELECT id, form_id, status, submission_type, deleted FROM responses LIMIT 0"
        )

        # Test 4: Form assignment queries
        all_good &= test_query(
            cur,
            "Form assignment query (with assigned_by, due_date, target_responses)",
            "SELECT id, form_id, agent_id, assigned_by, due_date, target_responses, status FROM form_assignments LIMIT 0"
        )

        # Test 5: Check indexes exist for performance
        print()
        print("⚡ Performance Indexes:")

        critical_indexes = [
            ('idx_users_deleted', 'users'),
            ('idx_forms_deleted', 'forms'),
            ('idx_responses_deleted', 'responses'),
            ('idx_users_email', 'users'),
            ('idx_responses_form_id', 'responses'),
        ]

        cur.execute("""
            SELECT indexname, tablename
            FROM pg_indexes
            WHERE schemaname = 'public'
        """)
        existing_indexes = {row[0]: row[1] for row in cur.fetchall()}

        indexes_ok = True
        for idx_name, table_name in critical_indexes:
            if idx_name in existing_indexes:
                print(f"  ✅ {idx_name}")
            else:
                print(f"  ⚠️  {idx_name} missing (non-critical)")
                # Don't fail on missing indexes, just warn

        print()
        print("=" * 70)
        print("SUMMARY")
        print("=" * 70)

        if all_good:
            print("✅ Database schema validation PASSED")
            print("   All critical columns and tables are present.")
            print("   The application should run without schema errors.")
            sys.exit(0)
        else:
            print("❌ Database schema validation FAILED")
            print("   Some required columns or tables are missing.")
            print("   Run: ./scripts/db-migrate.sh")
            sys.exit(1)

except psycopg2.OperationalError as e:
    print(f"\n❌ Cannot connect to database: {e}")
    print("\nTroubleshooting:")
    print("  - Check DATABASE_URL is correct")
    print("  - Ensure database server is running")
    print("  - Verify network connectivity")
    sys.exit(1)
except Exception as e:
    print(f"\n❌ Unexpected error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
finally:
    if 'conn' in locals():
        conn.close()
PYTHON_SCRIPT
