"""One-time migration: add `users.full_name` and `users.city`.

Same reasoning as migrate_2026_09_19_add_auth.py — `Base.metadata.create_all`
only creates missing tables, never alters an existing table's columns, and
`users` already exists live with real rows in it (from before this signup
form asked for a name/city). Safe to re-run: checks each column first.

Run from backend/: .venv/Scripts/python.exe -m scripts.migrate_2026_09_20_add_user_profile
"""

import asyncio

from sqlalchemy import text

from app.models.db import engine

NEW_COLUMNS = ["full_name", "city"]


async def main() -> None:
    async with engine.begin() as conn:
        existing = await conn.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'users' AND column_name = ANY(:cols)"
            ),
            {"cols": NEW_COLUMNS},
        )
        already_present = {row[0] for row in existing}

        for column in NEW_COLUMNS:
            if column in already_present:
                print(f"users.{column} already exists — skipping.")
                continue
            await conn.execute(text(f"ALTER TABLE users ADD COLUMN {column} VARCHAR"))
            print(f"Added users.{column}.")


if __name__ == "__main__":
    asyncio.run(main())
