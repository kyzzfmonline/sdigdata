#!/usr/bin/env python3
import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()


async def check_db():
    db_url = os.getenv(
        "DATABASE_URL_APP", "postgresql://metroform:password@localhost:5432/metroform"
    )
    conn = await asyncpg.connect(db_url)
    result = await conn.fetch(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
    )
    tables = [r["table_name"] for r in result]
    print("Tables:", tables)
    if "notifications" in tables:
        print("✅ notifications table exists")
        # Check if there are any records
        count = await conn.fetchval("SELECT COUNT(*) FROM notifications")
        print(f"Notifications count: {count}")
    else:
        print("❌ notifications table missing")
    await conn.close()


if __name__ == "__main__":
    asyncio.run(check_db())
