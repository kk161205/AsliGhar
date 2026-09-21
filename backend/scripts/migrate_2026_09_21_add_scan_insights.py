"""One-time migration: add `scans.insights_json`.

`Base.metadata.create_all` only creates missing tables, never alters an
existing table's columns. Safe to re-run: checks the column first.

Run from backend/: .venv/Scripts/python.exe -m scripts.migrate_2026_09_21_add_scan_insights
"""

import asyncio

from sqlalchemy import text

from app.models.db import engine


async def main() -> None:
    async with engine.begin() as conn:
        existing = await conn.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'scans' AND column_name = 'insights_json'"
            )
        )
        if existing.first() is not None:
            print("scans.insights_json already exists — skipping.")
            return
        await conn.execute(text("ALTER TABLE scans ADD COLUMN insights_json JSON"))
        print("Added scans.insights_json.")


if __name__ == "__main__":
    asyncio.run(main())
