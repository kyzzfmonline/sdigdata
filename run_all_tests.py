#!/usr/bin/env python3
"""
Comprehensive test runner for SDIGdata backend.
Runs all test suites and provides detailed reporting.
"""

import os
import subprocess
import sys
from pathlib import Path


def run_command(command, description):
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
            print("✅ PASSED")
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
    """Run all test suites."""
    print("🚀 SDIGdata Backend - Comprehensive Test Suite")
    print("=" * 60)
    print("Testing all components: Authentication, Permissions, User Management,")
    print("Preferences, Admin Operations, and Core Functionality")
    print("=" * 60)

    # Test suites to run
    test_suites = [
        ("tests/unit/", "Unit Tests"),
        ("tests/integration/", "Integration Tests"),
        ("tests/security/", "Security Tests"),
    ]

    results = []
    total_passed = 0
    total_failed = 0

    # Check if we're in the right directory
    if not Path("/root/workspace/sdigdata").exists():
        print("❌ Error: Not in correct directory. Expected /root/workspace/sdigdata")
        return 1

    # Check if virtual environment is activated
    if not os.environ.get("VIRTUAL_ENV"):
        print("⚠️  Warning: Virtual environment not activated")

    # Run each test suite
    for test_path, description in test_suites:
        if not Path(f"/root/workspace/sdigdata/{test_path}").exists():
            print(f"⚠️  Skipping {test_path} - directory not found")
            continue

        success = run_command(
            f"python -m pytest {test_path} -v --tb=short",
            f"{description} ({test_path})",
        )

        results.append((test_path, description, success))

        if success:
            total_passed += 1
        else:
            total_failed += 1

    # Run legacy comprehensive API test if it exists
    if Path("/root/workspace/sdigdata/test_api_comprehensive.py").exists():
        success = run_command(
            "python test_api_comprehensive.py",
            "Legacy Comprehensive API Test",
        )
        results.append(("test_api_comprehensive.py", "Legacy API Test", success))

        if success:
            total_passed += 1
        else:
            total_failed += 1

    # Summary
    print("\n" + "=" * 60)
    print("📊 TEST SUMMARY")
    print("=" * 60)

    print(f"Total Test Suites: {len(results)}")
    print(f"Passed: {total_passed}")
    print(f"Failed: {total_failed}")

    if results:
        print("\nDetailed Results:")
        for test_file, description, success in results:
            status = "✅ PASS" if success else "❌ FAIL"
            print(f"   {status} - {description} ({test_file})")

    # Coverage check (if pytest-cov is available)
    print("\n🔍 Checking test coverage...")
    try:
        coverage_success = run_command(
            "python -m pytest --cov=app --cov-report=term-missing --cov-report=html:htmlcov tests/",
            "Test Coverage Analysis",
        )
        if coverage_success:
            print("✅ Coverage analysis completed")
            print("📊 HTML coverage report generated in htmlcov/")
        else:
            print("⚠️  Coverage analysis failed (pytest-cov may not be installed)")
    except:
        print("⚠️  Coverage analysis not available")

    # Final result
    print("\n" + "=" * 60)
    if total_failed == 0:
        print("🎉 ALL TESTS PASSED!")
        print("✅ Backend is ready for production")
        return 0
    else:
        print(f"⚠️  {total_failed} test suite(s) failed")
        print("❌ Please fix failing tests before deployment")
        return 1


if __name__ == "__main__":
    sys.exit(main())
