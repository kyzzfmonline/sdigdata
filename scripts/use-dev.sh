#!/bin/bash
# Switch to development environment

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "🔄 Switching to DEVELOPMENT environment..."

# Copy dev env file
cp "$PROJECT_ROOT/.env.dev" "$PROJECT_ROOT/.env"

echo "✅ Development environment activated"
echo ""
echo "Current configuration:"
grep "^DATABASE_URL=" "$PROJECT_ROOT/.env" || echo "DATABASE_URL not found"
grep "^ENVIRONMENT=" "$PROJECT_ROOT/.env" || echo "ENVIRONMENT not found"
echo ""
echo "ℹ️  Changes will take effect on next app restart"
echo "ℹ️  For Docker: docker-compose restart"
echo "ℹ️  For local: restart your dev server"
