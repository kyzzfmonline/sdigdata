#!/usr/bin/env python3
"""
Admin User Bootstrap Script

This script bootstraps the admin user with full super_admin permissions.
Run this after database migrations to ensure the admin user has all necessary permissions.

Usage:
    python bootstrap_admin.py
"""

import asyncio
import asyncpg
import os
import argon2


async def bootstrap_admin_users():
    """Bootstrap admin users."""

    # Use DATABASE_URL from env
    db_url = os.getenv(
        "DATABASE_URL", "postgresql://metroform:password@localhost:5432/metroform"
    )
    conn = await asyncpg.connect(db_url)

    try:
        print("🔍 Bootstrapping admin users...")

        # Check if organization exists
        org = await conn.fetchrow("SELECT id FROM organizations LIMIT 1")
        if not org:
            # Create default organization
            org_id = await conn.fetchval(
                "INSERT INTO organizations (name) VALUES ($1) RETURNING id",
                "SDIG Admin",
            )
            print(f"✅ Created organization: SDIG Admin (ID: {org_id})")
        else:
            org_id = org["id"]
            print(f"✅ Found organization (ID: {org_id})")

        # Password hasher
        ph = argon2.PasswordHasher()

        # Admin users to create
        admins = [("admin", "sage@2025"), ("sdigadmin", "sdig@2025")]

        for username, password in admins:
            # Check if user exists
            existing = await conn.fetchrow(
                "SELECT id FROM users WHERE username = $1", username
            )
            if existing:
                print(f"ℹ️  User {username} already exists")
                continue

            # Hash password
            hashed = ph.hash(password)

            # Create user
            user_id = await conn.fetchval(
                """
                INSERT INTO users (username, password_hash, role, organization_id)
                VALUES ($1, $2, $3, $4)
                RETURNING id
                """,
                username,
                hashed,
                "admin",
                org_id,
            )
            print(f"✅ Created admin user: {username} (ID: {user_id})")

        print("\n🎉 Admin users bootstrap complete!")
        return True

    except Exception as e:
        print(f"❌ Error during bootstrap: {e}")
        return False

    finally:
        await conn.close()


async def main():
    """Main bootstrap function."""
    print("🚀 SDIGdata Admin User Bootstrap")
    print("=" * 50)

    success = await bootstrap_admin_users()

    if success:
        print("\n✅ Bootstrap completed successfully!")
        print("The admin user now has full super_admin permissions.")
        print("You can now use the admin user to access all system features.")
    else:
        print("\n❌ Bootstrap failed!")
        print("Please check the error messages above and try again.")

    return success


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
