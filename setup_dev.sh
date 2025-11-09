#!/bin/bash
# Development setup script for SDIGdata

echo "🚀 Setting up SDIGdata Backend..."

# Check if Docker is running
if ! docker info >/dev/null 2>&1; then
  echo "❌ Docker is not running. Please start Docker first."
  exit 1
fi

# Copy environment file if it doesn't exist
if [ ! -f .env ]; then
  echo "📝 Creating .env file from template..."
  cp .env.example .env
  echo "✅ .env created. Edit it with your settings if needed."
else
  echo "✅ .env file already exists"
fi

# Start services
echo "🐳 Starting Docker services (PostgreSQL, MinIO, API)..."
docker-compose up -d

# Wait for database to be ready
echo "⏳ Waiting for PostgreSQL to be ready..."
sleep 5

# Check if services are running
if docker-compose ps | grep -q "Up"; then
  echo "✅ Services are running!"
  echo ""
  echo "📍 Access points:"
  echo "   API:          http://localhost:8000"
  echo "   API Docs:     http://localhost:8000/docs"
  echo "   MinIO Console: http://localhost:9001 (minio/miniopass)"
  echo ""
  echo "📝 Next steps:"
  echo "   1. Create your first admin user (see README.md)"
  echo "   2. Test the API with: curl http://localhost:8000"
  echo "   3. View logs with: docker-compose logs -f api"
  echo ""
else
  echo "❌ Some services failed to start. Check logs with: docker-compose logs"
  exit 1
fi
