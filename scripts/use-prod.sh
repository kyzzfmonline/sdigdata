#!/bin/bash
# Switch to production environment

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "🔄 Switching to PRODUCTION environment..."
echo ""
echo "⚠️  WARNING: You are about to switch to PRODUCTION environment!"
echo "⚠️  This will connect to the live production database."
echo ""
read -p "Are you sure you want to continue? (yes/no): " -r
echo ""

if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
    echo "❌ Cancelled"
    exit 1
fi

# Copy prod env file
cp "$PROJECT_ROOT/.env.prod" "$PROJECT_ROOT/.env"

echo "✅ Production environment activated"
echo ""
echo "Current configuration:"
grep "^DATABASE_URL=" "$PROJECT_ROOT/.env" | sed 's/:.*/:[REDACTED]/' || echo "DATABASE_URL not found"
grep "^ENVIRONMENT=" "$PROJECT_ROOT/.env" || echo "ENVIRONMENT not found"
echo ""
echo "ℹ️  Changes will take effect on next app restart"
echo "ℹ️  For Docker: docker-compose restart"
echo "ℹ️  For local: restart your dev server"
