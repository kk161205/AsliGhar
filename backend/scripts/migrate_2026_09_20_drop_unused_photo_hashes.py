"""One-time migration: drop the `photo_hashes` table.

Pre-production cleanup (2026-09-20): the `PhotoHash` SQLAlchemy model was
scaffolded early on for a planned feature (crowd-sourced duplicate-photo
detection via perceptual hashing) but was never actually wired into any code
path — nothing ever inserted into it or queried it. Confirmed via grep across
the whole app before writing this. Dropping the empty, unused table rather
than shipping dead schema to production; re-add the model (and re-run an
equivalent migration) if that feature is actually built later.

Safe to re-run: checks the table exists before dropping.

Run from backend/: .venv/Scripts/python.exe -m scripts.migrate_2026_09_20_drop_unused_photo_hashes
"""

import asyncio

from sqlalchemy import text

from app.models.db import engine


async def main() -> None:
    async with engine.begin() as conn:
        result = await conn.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_name = 'photo_hashes'"
            )
        )
        if result.first() is None:
            print("photo_hashes already doesn't exist — nothing to do.")
            return

        row_count = await conn.execute(text("SELECT count(*) FROM photo_hashes"))
        count = row_count.scalar_one()
        if count > 0:
            print(f"Refusing to drop: photo_hashes has {count} row(s), not empty as expected.")
            return

        await conn.execute(text("DROP TABLE photo_hashes"))
        print("Dropped empty photo_hashes table.")


if __name__ == "__main__":
    asyncio.run(main())
