"""Fix permission names to use colons instead of dots."""

import asyncio
import sys

import asyncpg

# Add parent directory to path
sys.path.insert(0, "/root/workspace/sdigdata")

from app.core.config import get_settings


async def fix_permission_names():
    """Update all permission names to use colons instead of dots."""
    settings = get_settings()
    conn = await asyncpg.connect(dsn=settings.DATABASE_URL)

    print("=" * 60)
    print("FIXING PERMISSION NAMES TO USE COLONS")
    print("=" * 60)

    # Get all permissions with dots in the name
    perms_with_dots = await conn.fetch("""
        SELECT id, name, resource, action
        FROM permissions
        WHERE name LIKE '%.%'
        ORDER BY name
    """)

    print(f"\nFound {len(perms_with_dots)} permissions with dots")
    print()

    if len(perms_with_dots) == 0:
        print("✅ All permissions already use colons!")
        await conn.close()
        return

    print("Updating permissions:")
    print("-" * 60)

    updated_count = 0
    for perm in perms_with_dots:
        old_name = perm['name']
        new_name = old_name.replace('.', ':')

        # Update the permission name
        await conn.execute("""
            UPDATE permissions
            SET name = $1
            WHERE id = $2
        """, new_name, perm['id'])

        print(f"  {old_name:<40} → {new_name}")
        updated_count += 1

    print("-" * 60)
    print(f"\n✅ Updated {updated_count} permissions to use colons")

    # Verify
    remaining_dots = await conn.fetchval("""
        SELECT COUNT(*) FROM permissions WHERE name LIKE '%.%'
    """)

    total_colons = await conn.fetchval("""
        SELECT COUNT(*) FROM permissions WHERE name LIKE '%:%'
    """)

    total_perms = await conn.fetchval("SELECT COUNT(*) FROM permissions")

    print("\n" + "=" * 60)
    print("VERIFICATION")
    print("=" * 60)
    print(f"Total permissions: {total_perms}")
    print(f"Using colons (:): {total_colons}")
    print(f"Using dots (.): {remaining_dots}")
    print()

    if remaining_dots == 0 and total_colons == total_perms:
        print("✅ ALL PERMISSIONS NOW USE COLONS!")
    else:
        print(f"⚠️  {remaining_dots} permissions still use dots")

    print("=" * 60)

    await conn.close()


if __name__ == "__main__":
    asyncio.run(fix_permission_names())
