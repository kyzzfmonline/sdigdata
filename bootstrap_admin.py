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
from app.core.config import Settings


async def bootstrap_admin_user():
    """Bootstrap the admin user with super_admin role and all permissions."""

    settings = Settings(
        DATABASE_URL="postgresql://metroform:password@localhost:5432/metroform",
        DATABASE_URL_YOYO="postgresql://metroform:password@localhost:5432/metroform",
        DATABASE_URL_APP="postgresql://metroform:password@localhost:5432/metroform",
        SECRET_KEY="bootstrap_secret_key",
        SPACES_ENDPOINT="http://localhost:9000",
        SPACES_REGION="us-east-1",
        SPACES_BUCKET="test-bucket",
        SPACES_KEY="minio",
        SPACES_SECRET="miniopass",
    )
    conn = await asyncpg.connect(settings.DATABASE_URL_APP)

    try:
        print("🔍 Checking admin user setup...")

        # Get admin user
        admin_user = await conn.fetchrow(
            "SELECT id, username FROM users WHERE username = $1", "admin"
        )

        if not admin_user:
            print("❌ Admin user not found! Please create the admin user first.")
            return False

        print(f"✅ Found admin user: {admin_user['username']} (ID: {admin_user['id']})")

        # Get super_admin role
        super_admin_role = await conn.fetchrow(
            "SELECT id, name, level FROM roles WHERE name = $1", "super_admin"
        )

        if not super_admin_role:
            print("❌ Super admin role not found! Please run database migrations.")
            return False

        print(f"✅ Found super_admin role (level: {super_admin_role['level']})")

        # Check if admin already has super_admin role
        existing_role = await conn.fetchrow(
            """
            SELECT ur.id, ur.assigned_at
            FROM user_roles ur
            WHERE ur.user_id = $1 AND ur.role_id = $2 AND ur.is_active = true
            """,
            admin_user["id"],
            super_admin_role["id"],
        )

        if existing_role:
            print("ℹ️  Admin user already has super_admin role")
        else:
            # Assign super_admin role to admin user
            await conn.execute(
                """
                INSERT INTO user_roles (user_id, role_id, assigned_by, is_active)
                VALUES ($1, $2, $1, true)
                """,
                admin_user["id"],
                super_admin_role["id"],
            )
            print("✅ Assigned super_admin role to admin user")

        # Verify permissions
        user_perms = await conn.fetch(
            """
            SELECT DISTINCT p.name, p.resource, p.action
            FROM user_roles ur
            JOIN role_permissions rp ON ur.role_id = rp.role_id
            JOIN permissions p ON rp.permission_id = p.id
            WHERE ur.user_id = $1 AND ur.is_active = true
            ORDER BY p.resource, p.action
            """,
            admin_user["id"],
        )

        # Group permissions by resource
        perm_summary = {}
        for perm in user_perms:
            resource = perm["resource"]
            if resource not in perm_summary:
                perm_summary[resource] = []
            perm_summary[resource].append(perm["action"])

        print("\n🎉 Admin user bootstrap complete!")
        print(f"   • Roles: 1 (super_admin)")
        print(f"   • Total permissions: {len(user_perms)}")
        print("   • Permission breakdown:")
        for resource, actions in sorted(perm_summary.items()):
            actions_str = ", ".join(sorted(actions))
            print(f"     - {resource}: {actions_str}")

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

    success = await bootstrap_admin_user()

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
