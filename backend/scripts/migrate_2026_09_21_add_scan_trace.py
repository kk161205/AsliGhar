"""One-time migration: add `scans.override_reason` and `scans.trace_json`.

`Base.metadata.create_all` only creates missing tables, never alters an
existing table's columns, and `scans` already exists live with rows in it.
Safe to re-run: checks each column first.

Run from backend/: .venv/Scripts/python.exe -m scripts.migrate_2026_09_21_add_scan_trace
"""

import asyncio

from sqlalchemy import text

from app.models.db import engine

NEW_COLUMNS = {"override_reason": "VARCHAR", "trace_json": "JSON"}


async def main() -> None:
    async with engine.begin() as conn:
        existing = await conn.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'scans' AND column_name = ANY(:cols)"
            ),
            {"cols": list(NEW_COLUMNS)},
        )
        already_present = {row[0] for row in existing}

        for column, column_type in NEW_COLUMNS.items():
            if column in already_present:
                print(f"scans.{column} already exists — skipping.")
                continue
            await conn.execute(text(f"ALTER TABLE scans ADD COLUMN {column} {column_type}"))
            print(f"Added scans.{column}.")


if __name__ == "__main__":
    asyncio.run(main())
