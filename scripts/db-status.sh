#!/bin/bash
# Check database migration status

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

echo "📊 Database Migration Status"
echo "Environment: $ENVIRONMENT"
echo "Database: $(echo $DATABASE_URL | sed 's/:\/\/.*@/:\/\/[REDACTED]@/')"
echo ""

# Run alembic current
cd "$PROJECT_ROOT"
echo "Current revision:"
alembic current

echo ""
echo "Migration history:"
alembic history | head -20
