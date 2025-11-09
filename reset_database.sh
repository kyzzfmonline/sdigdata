#!/bin/bash
set -e

echo "=== Database Reset Script ==="
echo "This will destroy all existing data and recreate the database fresh"
echo ""

# Stop all containers
echo "1. Stopping containers..."
docker-compose down

# Remove database volume
echo "2. Removing database volume..."
docker volume rm sdigdata_postgres_data 2>/dev/null || echo "Volume doesn't exist or already removed"

# Start database container
echo "3. Starting database container..."
docker-compose up -d db

# Wait for database to be ready
echo "4. Waiting for database to be ready..."
for i in {1..30}; do
    if docker-compose exec -T db pg_isready -U metroform -d sdigdata > /dev/null 2>&1; then
        echo "   Database is ready!"
        break
    fi
    echo "   Waiting... ($i/30)"
    sleep 2
done

# Initialize extensions
echo "5. Initializing PostgreSQL extensions..."
docker-compose exec -T db psql -U metroform -d sdigdata < init_db_extensions.sql

# Start API container
echo "6. Starting API container..."

# Kill any process using port 8000
pkill -f "uvicorn\|python.*main.py" || true
sleep 2

docker-compose up -d api

# Wait for API to be ready
echo "7. Waiting for API container to be ready..."
sleep 10

# Apply migrations using Alembic
echo "8. Applying migrations using Alembic..."
docker-compose exec api uv run alembic upgrade head

# Show tables
echo ""
echo "9. Database tables:"
docker-compose exec -T db psql -U metroform -d sdigdata -c "\dt"

echo ""
echo "=== Database reset complete! ==="
echo "All migrations have been applied fresh."
echo ""
echo "Next steps:"
echo "- Bootstrap admin user: curl -X POST http://localhost:8000/auth/bootstrap -H 'Content-Type: application/json' -d '{\"username\":\"admin\",\"password\":\"admin123\"}'"
