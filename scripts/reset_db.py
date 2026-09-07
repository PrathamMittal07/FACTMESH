"""Reset the FactMesh database — drops all data, re-runs init.sql."""

import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

import asyncpg


async def reset_db():
    conn = await asyncpg.connect(
        user="factmesh",
        password="factmesh",
        database="factmesh",
        host="localhost",
        port=5432,
    )

    print("Dropping all tables...")
    await conn.execute("DROP TABLE IF EXISTS relationships CASCADE")
    await conn.execute("DROP TABLE IF EXISTS extraction_issues CASCADE")
    await conn.execute("DROP TABLE IF EXISTS facts CASCADE")
    await conn.execute("DROP TABLE IF EXISTS documents CASCADE")

    print("Re-running init.sql...")
    init_sql_path = Path(__file__).parent.parent / "backend" / "app" / "db" / "init.sql"
    init_sql = init_sql_path.read_text(encoding="utf-8")
    
    # Remove BOM if present
    if init_sql.startswith("\ufeff"):
        init_sql = init_sql[1:]

    await conn.execute(init_sql)

    print("Database reset complete!")
    await conn.close()


if __name__ == "__main__":
    asyncio.run(reset_db())
