#!/bin/bash
# Switch to local environment (for running outside Docker)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "🔄 Switching to LOCAL environment..."

# Copy local env file
cp "$PROJECT_ROOT/.env.local" "$PROJECT_ROOT/.env"

echo "✅ Local environment activated"
echo ""
echo "Current configuration:"
grep "^DATABASE_URL=" "$PROJECT_ROOT/.env" || echo "DATABASE_URL not found"
grep "^ENVIRONMENT=" "$PROJECT_ROOT/.env" || echo "ENVIRONMENT not found"
echo ""
echo "ℹ️  This configuration is for running the app directly on your host machine"
echo "ℹ️  (not in Docker). Make sure PostgreSQL and MinIO are running locally."
