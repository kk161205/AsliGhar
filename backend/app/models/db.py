from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.pool import NullPool

from app.core.config import get_settings

settings = get_settings()
engine = create_async_engine(
    settings.database_url,
    echo=False,
    # NullPool: don't let SQLAlchemy hold its own long-lived connection pool
    # on top of Neon's pooled connection string, which already pools via
    # PgBouncer. Double-pooling here caused a real failure — a connection
    # opened under one asyncio event loop got reused under a different one
    # (e.g. multiple TestClient instances in one pytest run, each of which
    # spins up its own event loop) and asyncpg raised "Event loop is
    # closed" on teardown. NullPool makes every checkout a fresh connection
    # instead, which is the pattern Neon itself recommends against a pooled
    # connection string.
    poolclass=NullPool,
    connect_args={
        # required for asyncpg against Neon's pooled connection string
        # (PgBouncer in transaction mode) — without this, asyncpg's
        # prepared-statement cache causes "prepared statement already
        # exists" errors under connection reuse. Harmless against a direct
        # (non-pooled) connection string too.
        "statement_cache_size": 0,
        # Neon requires TLS. asyncpg doesn't understand the libpq-style
        # `sslmode`/`channel_binding` query params Neon's dashboard puts in
        # its connection string — passing them through the URL raises a
        # TypeError, confirmed live. DATABASE_URL should be given without
        # those params; SSL is handled here instead.
        "ssl": "require",
    },
)
async_session: async_sessionmaker[AsyncSession] = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String)
    # Nullable: added 2026-09-20, after users.email/password_hash already had
    # rows in the live DB (see scripts/migrate_2026_09_20_add_user_profile.py).
    # Every new signup always sets both — see auth_service.create_user().
    full_name: Mapped[str | None] = mapped_column(String, nullable=True)
    city: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class Scan(Base):
    __tablename__ = "scans"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    # Nullable: the two scans already in the live DB predate auth and have no
    # owner. Every new scan is created through the now-protected POST /scan,
    # so this is always set going forward — see scan_service.run_scan().
    user_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("users.id"), nullable=True, index=True
    )
    # timezone=True: the app always works in timezone-aware UTC datetimes
    # (scan_service.py uses datetime.now(timezone.utc)) — a naive column
    # rejects those with "can't subtract offset-naive and offset-aware
    # datetimes" on Postgres, confirmed live. SQLite silently tolerated the
    # mismatch, which is why this didn't surface before the Neon migration.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    address: Mapped[str] = mapped_column(String)
    city: Mapped[str] = mapped_column(String)
    rent: Mapped[int] = mapped_column(Integer)
    risk_score: Mapped[int] = mapped_column(Integer)
    risk_band: Mapped[str] = mapped_column(String)
    signals_json: Mapped[dict] = mapped_column(JSON)
    evidence_json: Mapped[list] = mapped_column(JSON)
    ai_summary: Mapped[str | None] = mapped_column(String, nullable=True)


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
