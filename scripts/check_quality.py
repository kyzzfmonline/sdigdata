#!/usr/bin/env python3
"""
Code Quality Enforcement Script
Runs all quality checks and fixes automatically.
"""

import subprocess
import sys
import os
from pathlib import Path


def run_command(command, description, fix=False):
    """Run a command and return success status."""
    print(f"\n🔍 Running: {description}")
    print(f"   Command: {command}")
    print("-" * 60)

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            cwd="/root/workspace/sdigdata",
        )

        if result.returncode == 0:
            status = "✅ FIXED" if fix else "✅ PASSED"
            print(status)
            if result.stdout.strip():
                print("   Output:")
                for line in result.stdout.strip().split("\n"):
                    print(f"   {line}")
        else:
            print("❌ FAILED")
            if result.stderr.strip():
                print("   Error Output:")
                for line in result.stderr.strip().split("\n"):
                    print(f"   {line}")
            if result.stdout.strip():
                print("   Standard Output:")
                for line in result.stdout.strip().split("\n"):
                    print(f"   {line}")

        return result.returncode == 0

    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        return False


def main():
    """Run all quality checks."""
    print("🛡️  SDIGdata Code Quality Enforcement")
    print("=" * 60)

    # Check if we're in the right directory
    if not Path("/root/workspace/sdigdata").exists():
        print("❌ Error: Not in correct directory. Expected /root/workspace/sdigdata")
        return 1

    quality_checks = [
        # Formatting and linting
        ("ruff check app/ tests/ --fix", "Ruff linting and auto-fixes", True),
        ("ruff format app/ tests/", "Ruff code formatting", True),
        ("python -m mypy app/ --ignore-missing-imports", "MyPy type checking", False),
        # Security checks
        (
            "python -m bandit -r app/ -c pyproject.toml",
            "Bandit security scanning",
            False,
        ),
        ("python -m safety check", "Dependency security check", False),
        # Tests
        ("python -m pytest tests/unit/ -v --tb=short", "Unit tests", False),
        (
            "python -m pytest tests/integration/ -v --tb=short",
            "Integration tests",
            False,
        ),
    ]

    results = []
    total_passed = 0
    total_failed = 0

    for command, description, is_fix in quality_checks:
        success = run_command(command, description, is_fix)
        results.append((description, success))

        if success:
            total_passed += 1
        else:
            total_failed += 1

    # Summary
    print("\n" + "=" * 60)
    print("📊 QUALITY CHECK SUMMARY")
    print("=" * 60)

    print(f"Total Checks: {len(results)}")
    print(f"Passed: {total_passed}")
    print(f"Failed: {total_failed}")

    if results:
        print("\nDetailed Results:")
        for description, success in results:
            status = "✅ PASS" if success else "❌ FAIL"
            print(f"   {status} - {description}")

    # Final result
    print("\n" + "=" * 60)
    if total_failed == 0:
        print("🎉 ALL QUALITY CHECKS PASSED!")
        print("✅ Code is ready for production")
        return 0
    else:
        print(f"⚠️  {total_failed} quality check(s) failed")
        print("❌ Please fix the issues before committing")
        print("\n💡 Quick fixes:")
        print("   - Run 'python scripts/check_quality.py' to see detailed errors")
        print("   - Run 'ruff check app/ tests/ --fix' to auto-fix linting issues")
        print("   - Run 'ruff format app/ tests/' to format code")
        return 1


if __name__ == "__main__":
    sys.exit(main())
