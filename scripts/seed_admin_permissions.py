"""Seed admin user with all required RBAC permissions."""

import asyncio
import sys

import asyncpg
from argon2 import PasswordHasher

# Add parent directory to path
sys.path.insert(0, "/root/workspace/sdigdata")

from app.core.config import get_settings


async def seed_admin_permissions():
    """Seed admin user with complete RBAC permissions."""
    settings = get_settings()
    conn = await asyncpg.connect(dsn=settings.DATABASE_URL)

    print("=" * 60)
    print("SEEDING ADMIN USER WITH RBAC PERMISSIONS")
    print("=" * 60)

    # 1. Create organization if not exists
    org_id = await conn.fetchval("""
        INSERT INTO organizations (name, primary_color)
        VALUES ('Default Organization', '#0066CC')
        ON CONFLICT DO NOTHING
        RETURNING id
    """)

    if not org_id:
        org_id = await conn.fetchval("SELECT id FROM organizations LIMIT 1")

    print(f"\n✓ Organization ID: {org_id}")

    # 2. Create admin user if not exists
    ph = PasswordHasher()
    password_hash = ph.hash("admin123")

    admin_id = await conn.fetchval("""
        INSERT INTO users (username, password_hash, role, organization_id, email)
        VALUES ('admin', $1, 'admin', $2, 'admin@metroform.local')
        ON CONFLICT (username) DO UPDATE
        SET password_hash = EXCLUDED.password_hash
        RETURNING id
    """, password_hash, str(org_id))

    print(f"✓ Admin user ID: {admin_id}")
    print(f"✓ Admin credentials: username='admin', password='admin123'")

    # 3. Get or create admin role
    admin_role_id = await conn.fetchval("""
        SELECT id FROM roles WHERE name = 'admin'
    """)

    if not admin_role_id:
        print("\n⚠ Admin role not found - creating it...")
        admin_role_id = await conn.fetchval("""
            INSERT INTO roles (name, description)
            VALUES ('admin', 'Full administrative access')
            RETURNING id
        """)
        print(f"✓ Created admin role: {admin_role_id}")
    else:
        print(f"\n✓ Admin role exists: {admin_role_id}")

    # 4. Get ALL existing permissions from the database
    # This makes the seeder idempotent - it will assign whatever permissions exist
    print(f"\n✓ Fetching all existing permissions from database...")

    all_permissions = await conn.fetch("""
        SELECT id, name, resource, action, description
        FROM permissions
        ORDER BY resource, action
    """)

    print(f"✓ Found {len(all_permissions)} permissions in database")

    # Also define minimum required permissions to create if they don't exist
    minimum_required_permissions = [
        # Forms permissions (8)
        ('forms:create', 'forms', 'create', 'Create new forms'),
        ('forms:read', 'forms', 'read', 'View forms'),
        ('forms:edit', 'forms', 'edit', 'Edit existing forms'),
        ('forms:update', 'forms', 'update', 'Update forms'),
        ('forms:delete', 'forms', 'delete', 'Delete forms'),
        ('forms:publish', 'forms', 'publish', 'Publish forms'),
        ('forms:assign', 'forms', 'assign', 'Assign forms to users'),
        ('forms:admin', 'forms', 'admin', 'Full administrative access to forms'),

        # Responses permissions (5)
        ('responses:read', 'responses', 'read', 'View form responses'),
        ('responses:export', 'responses', 'export', 'Export response data'),
        ('responses:delete', 'responses', 'delete', 'Delete responses'),
        ('responses:create', 'responses', 'create', 'Create responses'),
        ('responses:update', 'responses', 'update', 'Update responses'),

        # Users permissions (6)
        ('users:create', 'users', 'create', 'Create new users'),
        ('users:delete', 'users', 'delete', 'Delete users'),
        ('users:admin', 'users', 'admin', 'Full administrative access to users'),
        ('users:read', 'users', 'read', 'View users'),
        ('users:update', 'users', 'update', 'Update users'),
        ('users:manage_roles', 'users', 'manage_roles', 'Manage user roles'),

        # Analytics permissions (2)
        ('analytics:view', 'analytics', 'view', 'View analytics and reports'),
        ('analytics:export', 'analytics', 'export', 'Export analytics data'),

        # System permissions (3)
        ('system:admin', 'system', 'admin', 'System administrator access'),
        ('system:cleanup', 'system', 'cleanup', 'Run cleanup operations'),
        ('system:audit', 'system', 'audit', 'View audit logs'),

        # Roles & Permissions management (2)
        ('roles:admin', 'roles', 'admin', 'Manage roles'),
        ('permissions:admin', 'permissions', 'admin', 'Manage permissions'),

        # Organizations permissions (4)
        ('organizations:create', 'organizations', 'create', 'Create new organizations'),
        ('organizations:read', 'organizations', 'read', 'View organization information'),
        ('organizations:update', 'organizations', 'update', 'Update organization information'),
        ('organizations:delete', 'organizations', 'delete', 'Delete organizations'),

        # Reputation permissions (2)
        ('reputation:view', 'reputation', 'view', 'View user reputation and leaderboards'),
        ('reputation:manage', 'reputation', 'manage', 'Manage user reputation scores'),
    ]

    # 5. Create any minimum required permissions that don't exist
    print(f"\n✓ Ensuring minimum required permissions exist...")

    created_count = 0
    for name, resource, action, description in minimum_required_permissions:
        # Check if permission exists
        perm_id = await conn.fetchval("""
            SELECT id FROM permissions
            WHERE resource = $1 AND action = $2
        """, resource, action)

        if not perm_id:
            # Create permission
            perm_id = await conn.fetchval("""
                INSERT INTO permissions (name, resource, action, description)
                VALUES ($1, $2, $3, $4)
                RETURNING id
            """, name, resource, action, description)
            print(f"  ✓ Created: {resource}:{action}")
            created_count += 1

    if created_count > 0:
        print(f"\n✓ Created {created_count} new permissions")
        # Re-fetch all permissions after creating new ones
        all_permissions = await conn.fetch("""
            SELECT id, name, resource, action, description
            FROM permissions
            ORDER BY resource, action
        """)
        print(f"✓ Total permissions now: {len(all_permissions)}")
    else:
        print(f"✓ All minimum required permissions already exist")

    # 6. Assign ALL existing permissions to admin role (idempotent)
    print(f"\n✓ Assigning ALL {len(all_permissions)} permissions to admin role...")

    assigned_count = 0
    skipped_count = 0
    for perm in all_permissions:
        result = await conn.execute("""
            INSERT INTO role_permissions (role_id, permission_id)
            VALUES ($1, $2)
            ON CONFLICT DO NOTHING
        """, admin_role_id, perm['id'])

        # Check row count: "INSERT 0 1" = 1 row inserted, "INSERT 0 0" = 0 rows (conflict)
        rows_inserted = int(result.split()[-1])
        if rows_inserted > 0:
            assigned_count += 1
        else:
            skipped_count += 1

    print(f"✓ Assigned {assigned_count} new permissions to admin role")
    print(f"✓ Skipped {skipped_count} permissions (already assigned)")

    # 7. Assign admin role to admin user
    user_role_result = await conn.execute("""
        INSERT INTO user_roles (user_id, role_id)
        VALUES ($1, $2)
        ON CONFLICT DO NOTHING
    """, admin_id, admin_role_id)

    if "INSERT" in user_role_result:
        print(f"\n✓ Assigned admin role to admin user")
    else:
        print(f"\n✓ Admin user already has admin role")

    # 8. Verify final permissions
    final_perms = await conn.fetch("""
        SELECT DISTINCT p.resource || ':' || p.action as permission, p.id
        FROM user_roles ur
        JOIN role_permissions rp ON ur.role_id = rp.role_id
        JOIN permissions p ON rp.permission_id = p.id
        WHERE ur.user_id = $1
        ORDER BY permission
    """, admin_id)

    print("\n" + "=" * 60)
    print(f"ADMIN USER FINAL PERMISSIONS ({len(final_perms)} total)")
    print("=" * 60)

    # Group by resource
    by_resource = {}
    for perm in final_perms:
        resource, action = perm['permission'].split(':')
        if resource not in by_resource:
            by_resource[resource] = []
        by_resource[resource].append(action)

    for resource in sorted(by_resource.keys()):
        actions = ', '.join(sorted(by_resource[resource]))
        print(f"  {resource}: {actions}")

    # Get total permissions in system
    total_system_perms = await conn.fetchval("SELECT COUNT(*) FROM permissions")

    print("\n" + "=" * 60)
    if len(final_perms) == total_system_perms:
        print(f"✅ ADMIN HAS ALL {total_system_perms} PERMISSIONS IN SYSTEM!")
        print("✅ ADMIN USER READY WITH FULL ACCESS!")
    else:
        missing_count = total_system_perms - len(final_perms)
        print(f"⚠️  Admin has {len(final_perms)}/{total_system_perms} permissions")
        print(f"⚠️  Missing {missing_count} permissions")

    print("=" * 60)

    await conn.close()


if __name__ == "__main__":
    asyncio.run(seed_admin_permissions())
