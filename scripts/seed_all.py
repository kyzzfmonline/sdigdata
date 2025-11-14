"""Master seed script - Seeds everything needed for local development."""

import asyncio
import sys

# Add parent directory to path
sys.path.insert(0, "/root/workspace/sdigdata")


async def run_all_seeds():
    """Run all seed scripts in order."""
    print("\n" + "=" * 70)
    print(" " * 20 + "METROFORM - MASTER SEED SCRIPT")
    print("=" * 70)

    # Import after adding to path
    from scripts.seed_admin_permissions import seed_admin_permissions
    from scripts.seed_form_templates import seed_templates

    # 1. Seed admin user and permissions
    print("\n[1/2] Seeding admin user and RBAC permissions...")
    print("-" * 70)
    await seed_admin_permissions()

    # 2. Seed form templates
    print("\n[2/2] Seeding form templates...")
    print("-" * 70)
    await seed_templates()

    # Final summary
    print("\n" + "=" * 70)
    print(" " * 25 + "SEEDING COMPLETE!")
    print("=" * 70)
    print("\n✅ Admin user created with full RBAC permissions")
    print("✅ 5 form templates seeded")
    print("\nQuick Start:")
    print("  1. Start API: docker-compose up -d")
    print("  2. Login: username='admin', password='admin123'")
    print("  3. API Docs: http://localhost:8000/docs")
    print("\n" + "=" * 70 + "\n")


if __name__ == "__main__":
    asyncio.run(run_all_seeds())
