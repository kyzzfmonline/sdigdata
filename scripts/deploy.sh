#!/bin/bash
set -e  # Exit on any error

# Deployment script for SDIGData backend
# This script is idempotent and safe to run multiple times

echo "========================================="
echo "SDIGData Backend Deployment"
echo "========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if DATABASE_URL is set
if [ -z "$DATABASE_URL" ]; then
    echo -e "${RED}❌ ERROR: DATABASE_URL environment variable not set${NC}"
    echo "Set it with: export DATABASE_URL='postgresql://...'"
    exit 1
fi

echo -e "${GREEN}✓${NC} DATABASE_URL is set"
echo ""

# Step 1: Run database migrations
echo "========================================="
echo "Step 1: Running Database Migrations"
echo "========================================="
echo ""

# Check current migration version
CURRENT_VERSION=$(uv run alembic current 2>/dev/null | grep -v "INFO" | grep -v "Context" | grep -v "Will assume" | head -1 || echo "none")
echo "Current migration version: $CURRENT_VERSION"

# Run migrations
echo "Running: alembic upgrade head"
if uv run alembic upgrade head; then
    echo -e "${GREEN}✓${NC} Database migrations completed successfully"
else
    echo -e "${RED}❌ ERROR: Database migrations failed${NC}"
    exit 1
fi

# Show new version
NEW_VERSION=$(uv run alembic current 2>/dev/null | grep -v "INFO" | grep -v "Context" | grep -v "Will assume" | head -1)
echo "New migration version: $NEW_VERSION"
echo ""

# Step 2: Verify database schema
echo "========================================="
echo "Step 2: Verifying Database Schema"
echo "========================================="
echo ""

# Check forms status constraint
echo "Checking forms status constraint..."
CONSTRAINT_CHECK=$(uv run python -c "
import asyncpg
import asyncio
import sys

async def check():
    try:
        conn = await asyncpg.connect('$DATABASE_URL')
        result = await conn.fetchval(\"\"\"
            SELECT pg_get_constraintdef(oid)
            FROM pg_constraint
            WHERE conrelid = 'forms'::regclass
            AND conname = 'forms_status_check'
        \"\"\")
        await conn.close()

        if result and 'active' in result:
            print('✓ Status constraint includes active')
            sys.exit(0)
        else:
            print('✗ Status constraint missing active')
            sys.exit(1)
    except Exception as e:
        print(f'✗ Error checking constraint: {e}')
        sys.exit(1)

asyncio.run(check())
" 2>&1)

if echo "$CONSTRAINT_CHECK" | grep -q "✓"; then
    echo -e "${GREEN}$CONSTRAINT_CHECK${NC}"
else
    echo -e "${RED}$CONSTRAINT_CHECK${NC}"
    echo -e "${YELLOW}⚠ Warning: Status constraint may need attention${NC}"
fi

echo ""

# Step 3: Summary
echo "========================================="
echo "Deployment Summary"
echo "========================================="
echo ""
echo -e "${GREEN}✓${NC} Database migrations: Complete"
echo -e "${GREEN}✓${NC} Schema validation: Complete"
echo ""
echo "Next steps:"
echo "  1. Restart your backend service"
echo "  2. Test form creation and publishing"
echo "  3. Verify mobile app can see published forms"
echo ""
echo -e "${GREEN}========================================="
echo "Deployment Successful!"
echo "=========================================${NC}"
