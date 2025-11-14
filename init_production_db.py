#!/usr/bin/env python3
import asyncio
import os

import asyncpg


async def init_db():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("DATABASE_URL not set")
        return

    conn = await asyncpg.connect(db_url)
    try:
        # Read and execute the init script
        with open("init_db_extensions.sql") as f:
            sql = f.read()
        await conn.execute(sql)
        print("✅ Database extensions initialized")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(init_db())
