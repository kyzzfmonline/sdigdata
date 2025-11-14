#!/usr/bin/env python3
"""
Ensure Admin User Has All Permissions

This script ensures the default admin user has all permissions in the system.
It can work in two modes:
1. Via super_admin role (recommended)
2. Direct permission assignment (alternative)

Usage:
    python ensure_admin_permissions.py [--direct]
"""

import asyncio

import asyncpg

from app.core.config import Settings


async def ensure_admin_has_all_permissions():
    """Ensure the admin user has all permissions via super_admin role."""

    settings = Settings(
        DATABASE_URL="postgresql://metroform:password@localhost:5432/sdigdata",
        DATABASE_URL_YOYO="postgresql://metroform:password@localhost:5432/sdigdata",
        DATABASE_URL_APP="postgresql://metroform:password@localhost:5432/sdigdata",
        SECRET_KEY="bootstrap_secret_key",
        SPACES_ENDPOINT="http://localhost:9000",
        SPACES_REGION="us-east-1",
        SPACES_BUCKET="test-bucket",
        SPACES_KEY="minio",
        SPACES_SECRET="miniopass",
    )
    conn = await asyncpg.connect(settings.DATABASE_URL_APP)

    try:
        # Get admin user
        admin_user = await conn.fetchrow(
            "SELECT id, username FROM users WHERE username = $1", "admin"
        )

        if not admin_user:
            print("❌ Admin user not found! Please create the admin user first.")
            return False

        print(f"✅ Found admin user: {admin_user['username']} (ID: {admin_user['id']})")

        # Use super_admin role assignment (recommended)
        print("\n🔧 Using super_admin role assignment...")

        # Get super_admin role
        super_admin_role = await conn.fetchrow(
            "SELECT id, name FROM roles WHERE name = $1", "super_admin"
        )

        if not super_admin_role:
            print("❌ Super admin role not found! Please run database migrations.")
            return False

        # Check if admin already has super_admin role
        existing_role = await conn.fetchrow(
            """
            SELECT ur.id FROM user_roles ur
            WHERE ur.user_id = $1 AND ur.role_id = $2 AND ur.is_active = true
            """,
            admin_user["id"],
            super_admin_role["id"],
        )

        if existing_role:
            print("ℹ️  Admin user already has super_admin role")
        else:
            # Remove any existing roles first
            await conn.execute(
                "DELETE FROM user_roles WHERE user_id = $1", admin_user["id"]
            )

            # Assign super_admin role
            await conn.execute(
                """
                INSERT INTO user_roles (user_id, role_id, assigned_by, is_active)
                VALUES ($1, $2, $1, true)
                """,
                admin_user["id"],
                super_admin_role["id"],
            )
            print("✅ Assigned super_admin role to admin user")

        # Verify final state
        print("\n🔍 Verifying final permissions...")

        # Check permissions via roles
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
        perm_by_resource = {}
        for perm in user_perms:
            resource = perm["resource"]
            if resource not in perm_by_resource:
                perm_by_resource[resource] = []
            perm_by_resource[resource].append(perm["action"])

        print(f"\\n🎉 Admin user has {len(user_perms)} permissions:")
        for resource, actions in sorted(perm_by_resource.items()):
            actions_str = ", ".join(sorted(actions))
            print(f"   {resource}: {actions_str}")

        # Verify all permissions are assigned
        total_system_perms = await conn.fetchval("SELECT COUNT(*) FROM permissions")
        admin_perm_count = len(user_perms)

        if admin_perm_count == total_system_perms:
            print(
                f"\\n✅ SUCCESS: Admin has ALL {total_system_perms} permissions in the system!"
            )
            return True
        else:
            print(
                f"\\n❌ ERROR: Admin has {admin_perm_count} permissions, but system has {total_system_perms}"
            )
            return False

    except Exception as e:
        print(f"❌ Error during permission assignment: {e}")
        return False

    finally:
        await conn.close()


async def main():
    """Main function."""
    print("🚀 SDIGdata Admin Permission Assignment")
    print("=" * 50)
    print("✅ Using role-based assignment (recommended)")

    success = await ensure_admin_has_all_permissions()

    if success:
        print("\\n🎉 Admin user permission assignment completed successfully!")
        print(
            "The admin user now has the super_admin role with all system permissions."
        )
    else:
        print("\\n❌ Permission assignment failed!")
        print("Please check the error messages above and try again.")

    return success


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
