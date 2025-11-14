#!/usr/bin/env bash
# Quality Check Script - Run before commits and in CI/CD

set -e

echo "🛡️  SDIGdata Quality Enforcement"
echo "================================="

# Check if we're in the right directory
if [ ! -f "pyproject.toml" ]; then
    echo "❌ Error: Not in project root directory"
    exit 1
fi

echo "📦 Installing quality tools..."
pip install -e ".[dev]" --quiet

echo "🔍 Running quality checks..."

# Format code
echo "📝 Formatting code..."
ruff format app/ tests/
ruff check app/ tests/ --fix

# Type checking
echo "🔍 Type checking..."
python -m mypy app/ --ignore-missing-imports

# Security scanning
echo "🔒 Security scanning..."
python -m bandit -r app/ -c pyproject.toml

# Dependency security
echo "📦 Checking dependencies..."
python -m safety check

# Run tests
echo "🧪 Running tests..."
python -m pytest tests/unit/ -v --tb=short
python -m pytest tests/integration/ -v --tb=short

echo "✅ All quality checks passed!"
echo ""
echo "💡 Tips:"
echo "  - Run 'pre-commit install' to enable automatic checks on commit"
echo "  - Use 'scripts/check_quality.py' for detailed reports"
echo "  - See docs/CODING_STANDARDS.md for guidelines"