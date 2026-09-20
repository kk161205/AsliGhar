"""One-time migration: add the `users` table and `scans.user_id` column.

`Base.metadata.create_all` (called at startup, app/models/db.py:init_db)
creates missing *tables* but never alters an *existing* table's columns —
`scans` already exists in the live Neon DB, so the new `user_id` column on
the Scan model needs an explicit ALTER TABLE. This script does exactly that,
and only that: the `users` table itself is created by the normal
create_all() path, since it's new.

Safe to re-run: checks for the column before altering.

Run from backend/: .venv/Scripts/python.exe -m scripts.migrate_2026_09_19_add_auth
"""

import asyncio

from sqlalchemy import text

from app.models.db import Base, engine


async def main() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        result = await conn.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'scans' AND column_name = 'user_id'"
            )
        )
        if result.first() is not None:
            print("scans.user_id already exists — nothing to do.")
            return

        await conn.execute(
            text("ALTER TABLE scans ADD COLUMN user_id VARCHAR REFERENCES users(id)")
        )
        await conn.execute(text("CREATE INDEX ix_scans_user_id ON scans (user_id)"))
        print("Added scans.user_id column and index.")


if __name__ == "__main__":
    asyncio.run(main())
