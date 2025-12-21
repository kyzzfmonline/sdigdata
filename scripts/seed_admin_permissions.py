"""Seed admin user with all required RBAC permissions.

This script is idempotent - it can be run multiple times safely.
"""

import asyncio
import sys

import asyncpg

# Add parent directory to path
sys.path.insert(0, "/root/workspace/sdigdata")

from app.core.config import get_settings
from app.core.security import hash_password


# All permissions that the frontend expects (colon notation)
ALL_PERMISSIONS = [
    # Forms permissions
    ('forms:create', 'forms', 'create', 'Create new forms'),
    ('forms:read', 'forms', 'read', 'View forms'),
    ('forms:edit', 'forms', 'edit', 'Edit existing forms'),
    ('forms:update', 'forms', 'update', 'Update forms'),
    ('forms:delete', 'forms', 'delete', 'Delete forms'),
    ('forms:publish', 'forms', 'publish', 'Publish forms'),
    ('forms:assign', 'forms', 'assign', 'Assign forms to users'),
    ('forms:admin', 'forms', 'admin', 'Full administrative access to forms'),

    # Responses permissions
    ('responses:read', 'responses', 'read', 'View form responses'),
    ('responses:create', 'responses', 'create', 'Create responses'),
    ('responses:update', 'responses', 'update', 'Update responses'),
    ('responses:delete', 'responses', 'delete', 'Delete responses'),
    ('responses:export', 'responses', 'export', 'Export response data'),

    # Users permissions
    ('users:read', 'users', 'read', 'View users'),
    ('users:create', 'users', 'create', 'Create new users'),
    ('users:update', 'users', 'update', 'Update users'),
    ('users:delete', 'users', 'delete', 'Delete users'),
    ('users:admin', 'users', 'admin', 'Full administrative access to users'),
    ('users:manage_roles', 'users', 'manage_roles', 'Manage user roles'),

    # Analytics permissions
    ('analytics:view', 'analytics', 'view', 'View analytics and reports'),
    ('analytics:export', 'analytics', 'export', 'Export analytics data'),

    # System permissions
    ('system:admin', 'system', 'admin', 'System administrator access'),
    ('system:cleanup', 'system', 'cleanup', 'Run cleanup operations'),
    ('system:audit', 'system', 'audit', 'View audit logs'),

    # Roles & Permissions management
    ('roles:admin', 'roles', 'admin', 'Manage roles'),
    ('permissions:admin', 'permissions', 'admin', 'Manage permissions'),

    # Organizations permissions
    ('organizations:create', 'organizations', 'create', 'Create new organizations'),
    ('organizations:read', 'organizations', 'read', 'View organization information'),
    ('organizations:update', 'organizations', 'update', 'Update organization information'),
    ('organizations:delete', 'organizations', 'delete', 'Delete organizations'),

    # Reputation permissions
    ('reputation:view', 'reputation', 'view', 'View user reputation and leaderboards'),
    ('reputation:manage', 'reputation', 'manage', 'Manage user reputation scores'),

    # Elections permissions
    ('elections:create', 'elections', 'create', 'Create new elections'),
    ('elections:read', 'elections', 'read', 'View elections'),
    ('elections:update', 'elections', 'update', 'Update elections'),
    ('elections:delete', 'elections', 'delete', 'Delete elections'),
    ('elections:manage', 'elections', 'manage', 'Manage election settings'),
    ('elections:publish', 'elections', 'publish', 'Publish elections'),

    # Election Analytics permissions
    ('election_analytics:view', 'election_analytics', 'view', 'View election results'),
    ('election_analytics:export', 'election_analytics', 'export', 'Export election data'),
    ('election_analytics:finalize', 'election_analytics', 'finalize', 'Finalize election results'),

    # Collation permissions
    ('collation:read', 'collation', 'read', 'View collation data and dashboards'),
    ('collation:create', 'collation', 'create', 'Create result sheets and incidents'),
    ('collation:update', 'collation', 'update', 'Update collation data'),
    ('collation:delete', 'collation', 'delete', 'Delete collation data'),
    ('collation:verify', 'collation', 'verify', 'Verify result sheets'),
    ('collation:approve', 'collation', 'approve', 'Approve verified result sheets'),
    ('collation:manage', 'collation', 'manage', 'Manage collation settings and officers'),
    ('collation:assign', 'collation', 'assign', 'Assign officers to polling stations'),

    # Voting permissions
    ('voting:vote', 'voting', 'vote', 'Cast votes in elections'),
    ('voting:verify', 'voting', 'verify', 'Verify voter eligibility'),

    # Translations permissions
    ('translations:submit', 'translations', 'submit', 'Submit new translations'),
    ('translations:review', 'translations', 'review', 'Review translations'),
    ('translations:moderate', 'translations', 'moderate', 'Moderate translation reviews'),
    ('translations:import', 'translations', 'import', 'Bulk import translations'),
    ('translations:export', 'translations', 'export', 'Export validated translations'),
]


async def seed_admin_permissions():
    """Seed admin user with complete RBAC permissions.

    This function is idempotent - safe to run multiple times.
    """
    settings = get_settings()
    conn = await asyncpg.connect(dsn=settings.DATABASE_URL)

    print("=" * 60)
    print("SEEDING ADMIN USER WITH RBAC PERMISSIONS")
    print("=" * 60)

    try:
        # 1. Get or create organization
        org_id = await conn.fetchval("""
            SELECT id FROM organizations WHERE name = 'Default Organization'
        """)

        if not org_id:
            org_id = await conn.fetchval("""
                INSERT INTO organizations (name, primary_color)
                VALUES ('Default Organization', '#0066CC')
                RETURNING id
            """)
            print(f"\n✓ Created organization ID: {org_id}")
        else:
            print(f"\n✓ Organization already exists: {org_id}")

        # 2. Get or create admin user (DO NOT overwrite existing password)
        admin_id = await conn.fetchval("""
            SELECT id FROM users WHERE username = 'admin'
        """)

        if not admin_id:
            password_hash = hash_password("admin123")
            admin_id = await conn.fetchval("""
                INSERT INTO users (username, password_hash, role, organization_id, email)
                VALUES ('admin', $1, 'admin', $2, 'admin@metroform.local')
                RETURNING id
            """, password_hash, str(org_id))
            print(f"✓ Created admin user ID: {admin_id}")
            print(f"✓ Admin credentials: username='admin', password='admin123'")
        else:
            print(f"✓ Admin user already exists: {admin_id}")
            print(f"✓ Existing password preserved (not overwritten)")

        # 3. Get or create admin role
        admin_role_id = await conn.fetchval("""
            SELECT id FROM roles WHERE name = 'admin'
        """)

        if not admin_role_id:
            admin_role_id = await conn.fetchval("""
                INSERT INTO roles (name, description, level)
                VALUES ('admin', 'Full administrative access', 100)
                RETURNING id
            """)
            print(f"✓ Created admin role: {admin_role_id}")
        else:
            print(f"✓ Admin role exists: {admin_role_id}")

        # 4. Create all permissions (idempotent - check before insert)
        print(f"\n✓ Ensuring all {len(ALL_PERMISSIONS)} permissions exist...")

        created_count = 0
        skipped_count = 0
        for name, resource, action, description in ALL_PERMISSIONS:
            # Check if permission exists by name OR by (resource, action)
            exists = await conn.fetchval("""
                SELECT id FROM permissions
                WHERE name = $1 OR (resource = $2 AND action = $3)
            """, name, resource, action)

            if exists:
                skipped_count += 1
                continue

            # Safe to insert - no conflicts
            try:
                await conn.execute("""
                    INSERT INTO permissions (name, resource, action, description)
                    VALUES ($1, $2, $3, $4)
                """, name, resource, action, description)
                created_count += 1
            except Exception as e:
                # Skip if any constraint violation
                skipped_count += 1

        print(f"✓ Created {created_count} new permissions")
        print(f"✓ Skipped {skipped_count} (already exist)")

        # 5. Get all permission IDs
        all_perms = await conn.fetch("SELECT id, name FROM permissions")
        print(f"✓ Total permissions in database: {len(all_perms)}")

        # 6. Assign ALL permissions to admin role (idempotent)
        print(f"\n✓ Assigning all permissions to admin role...")

        assigned_count = 0
        for perm in all_perms:
            result = await conn.execute("""
                INSERT INTO role_permissions (role_id, permission_id)
                VALUES ($1, $2)
                ON CONFLICT DO NOTHING
            """, admin_role_id, perm['id'])

            if "INSERT 0 1" in result:
                assigned_count += 1

        print(f"✓ Assigned {assigned_count} new permissions to admin role")
        print(f"✓ Skipped {len(all_perms) - assigned_count} (already assigned)")

        # 7. Assign admin role to admin user (idempotent)
        await conn.execute("""
            INSERT INTO user_roles (user_id, role_id)
            VALUES ($1, $2)
            ON CONFLICT DO NOTHING
        """, admin_id, admin_role_id)
        print(f"✓ Admin role assigned to admin user")

        # 8. Verify final state
        final_count = await conn.fetchval("""
            SELECT COUNT(DISTINCT p.id)
            FROM user_roles ur
            JOIN role_permissions rp ON ur.role_id = rp.role_id
            JOIN permissions p ON rp.permission_id = p.id
            WHERE ur.user_id = $1
        """, admin_id)

        total_perms = await conn.fetchval("SELECT COUNT(*) FROM permissions")

        print("\n" + "=" * 60)
        print(f"SEEDING COMPLETE")
        print("=" * 60)

        if final_count == total_perms:
            print(f"✅ Admin has ALL {total_perms} permissions")
        else:
            print(f"⚠️  Admin has {final_count}/{total_perms} permissions")

        print(f"\n📋 Login credentials:")
        print(f"   Username: admin")
        print(f"   Password: admin123")
        print("=" * 60)

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(seed_admin_permissions())
