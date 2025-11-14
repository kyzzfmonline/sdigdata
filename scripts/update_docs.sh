#!/bin/bash
# Update API Documentation
#
# This script generates comprehensive API documentation by reading the OpenAPI
# schema from the running FastAPI application.
#
# Usage:
#   ./scripts/update_docs.sh              # Use default URL (localhost:8000)
#   ./scripts/update_docs.sh production   # Use production URL (if configured)

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Configuration
API_URL="${API_URL:-http://localhost:8000}"
OUTPUT_FILE="API_DOCUMENTATION.md"

echo -e "${BLUE}📚 SDIGdata API Documentation Generator${NC}"
echo "=========================================="
echo ""

# Check if API is running
echo -e "${BLUE}🔍 Checking if API is running at ${API_URL}...${NC}"
if curl -s -f "${API_URL}/health" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ API is running${NC}"
else
    echo -e "${RED}❌ API is not running at ${API_URL}${NC}"
    echo ""
    echo "Please start the API first:"
    echo "  uvicorn app.main:app --reload"
    exit 1
fi

echo ""

# Generate documentation
echo -e "${BLUE}📝 Generating API documentation...${NC}"
python3 scripts/generate_api_docs.py --url "${API_URL}" --output "${OUTPUT_FILE}"

echo ""
echo -e "${GREEN}✅ Documentation updated successfully!${NC}"
echo ""
echo "📄 File: ${OUTPUT_FILE}"
echo "🔗 View online: ${API_URL}/docs (Swagger UI)"
echo "🔗 View online: ${API_URL}/redoc (ReDoc)"
echo ""
echo "💡 Tip: Run this script after adding new endpoints to keep docs up to date"
