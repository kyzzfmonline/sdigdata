#!/bin/bash
# Show current environment configuration

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "📋 Current Environment Configuration"
echo "=================================="
echo ""

if [ ! -f "$PROJECT_ROOT/.env" ]; then
    echo "❌ No .env file found"
    echo "ℹ️  Run one of: ./scripts/use-dev.sh, ./scripts/use-prod.sh, or ./scripts/use-local.sh"
    exit 1
fi

# Show safe environment variables (redact sensitive values)
echo "Environment Variables:"
echo ""

while IFS= read -r line; do
    # Skip comments and empty lines
    if [[ $line =~ ^[[:space:]]*# ]] || [[ -z $line ]]; then
        continue
    fi

    # Redact sensitive values
    if [[ $line =~ ^(DATABASE_URL|SECRET_KEY|SPACES_KEY|SPACES_SECRET)= ]]; then
        echo "$line" | sed 's/=.*/=[REDACTED]/'
    else
        echo "$line"
    fi
done < "$PROJECT_ROOT/.env"

echo ""
echo "=================================="
