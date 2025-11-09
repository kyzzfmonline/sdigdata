#!/bin/bash
# Verification script for SDIGdata backend

echo "🔍 SDIGdata Backend - Setup Verification"
echo "========================================"
echo ""

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check counter
checks_passed=0
checks_failed=0

check() {
  if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓${NC} $1"
    ((checks_passed++))
  else
    echo -e "${RED}✗${NC} $1"
    ((checks_failed++))
  fi
}

# Check project structure
echo "📁 Project Structure:"
[ -f "pyproject.toml" ]
check "pyproject.toml exists"
[ -f "Dockerfile" ]
check "Dockerfile exists"
[ -f "docker-compose.yml" ]
check "docker-compose.yml exists"
[ -f ".env.example" ]
check ".env.example exists"
[ -d "app" ]
check "app/ directory exists"
[ -d "alembic" ]
check "alembic/ directory exists"
echo ""

# Check core modules
echo "🧩 Core Modules:"
[ -f "app/main.py" ]
check "app/main.py exists"
[ -f "app/core/config.py" ]
check "app/core/config.py exists"
[ -f "app/core/database.py" ]
check "app/core/database.py exists"
[ -f "app/core/security.py" ]
check "app/core/security.py exists"
echo ""

# Check API routes
echo "🛣️  API Routes:"
[ -f "app/api/routes/auth.py" ]
check "Auth routes exist"
[ -f "app/api/routes/organizations.py" ]
check "Organization routes exist"
[ -f "app/api/routes/forms.py" ]
check "Form routes exist"
[ -f "app/api/routes/responses.py" ]
check "Response routes exist"
[ -f "app/api/routes/files.py" ]
check "File routes exist"
echo ""

# Check services
echo "🔧 Service Layer:"
[ -f "app/services/users.py" ]
check "User service exists"
[ -f "app/services/organizations.py" ]
check "Organization service exists"
[ -f "app/services/forms.py" ]
check "Form service exists"
[ -f "app/services/responses.py" ]
check "Response service exists"
echo ""

# Check utilities
echo "🛠️  Utilities:"
[ -f "app/utils/spaces.py" ]
check "Spaces utility exists"
[ -f "app/utils/csv_export.py" ]
check "CSV export utility exists"
echo ""

# Check migrations
echo "📊 Migrations:"
[ -f "alembic.ini" ]
check "Alembic config exists"
[ -d "alembic/versions" ]
check "Alembic versions directory exists"
echo ""

# Check documentation
echo "📚 Documentation:"
[ -f "README.md" ]
check "README.md exists"
[ -f "QUICKSTART.md" ]
check "QUICKSTART.md exists"
[ -f "PROJECT_SUMMARY.md" ]
check "PROJECT_SUMMARY.md exists"
echo ""

# Check Python syntax
echo "🐍 Python Syntax Check:"
if command -v python3 &>/dev/null; then
  python3 -m py_compile app/main.py 2>/dev/null
  check "app/main.py syntax valid"
  python3 -m py_compile app/core/config.py 2>/dev/null
  check "config.py syntax valid"
  python3 -m py_compile app/core/database.py 2>/dev/null
  check "database.py syntax valid"
else
  echo -e "${YELLOW}⚠${NC} Python3 not found, skipping syntax check"
fi
echo ""

# Summary
echo "========================================"
echo "📊 Summary:"
echo -e "${GREEN}Passed:${NC} $checks_passed"
echo -e "${RED}Failed:${NC} $checks_failed"
echo ""

if [ $checks_failed -eq 0 ]; then
  echo -e "${GREEN}✅ All checks passed! Your SDIGdata backend is ready.${NC}"
  echo ""
  echo "Next steps:"
  echo "  1. Run: ./setup_dev.sh"
  echo "  2. Visit: http://localhost:8000/docs"
  echo "  3. Create your first admin user (see README.md)"
  exit 0
else
  echo -e "${RED}❌ Some checks failed. Please review the output above.${NC}"
  exit 1
fi
