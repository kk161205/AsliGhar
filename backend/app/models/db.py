import sys
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.pool import NullPool

from app.core.config import get_settings

settings = get_settings()

# A connection opened under one asyncio event loop crashes if reused under a
# different one (asyncpg raises "Event loop is closed"). pytest hits this
# directly — each TestClient(app) spins up its own loop — so tests keep
# NullPool, paying a fresh connection per query. The running server has a
# single long-lived loop for its whole process, so it's safe to actually
# pool, avoiding a repeat TCP+TLS handshake (~450ms to Neon, measured live)
# on every request.
#
# No pool_pre_ping: measured live, it adds a full extra round trip to Neon
# per request (~150-200ms one-way from here) to validate a connection that's
# almost always fine — recycling every 5 minutes already keeps connections
# well under Neon's own idle-close timeout, which was the actual failure
# pre_ping would have been guarding against.
_under_pytest = "pytest" in sys.modules
_pool_kwargs = (
    {"poolclass": NullPool} if _under_pytest else {"pool_recycle": 300, "pool_size": 5, "max_overflow": 5}
)

engine = create_async_engine(
    settings.database_url,
    echo=False,
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
    **_pool_kwargs,
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
    # Nullable: scans stored before the input review existed have neither
    # (see scripts/migrate_2026_09_21_add_scan_trace.py).
    override_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    trace_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    insights_json: Mapped[list | None] = mapped_column(JSON, nullable=True)


class RentComparable(Base):
    """A page that quoted a rent, kept so later scans of the same area have more to compare."""

    __tablename__ = "rent_comparables"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    city: Mapped[str] = mapped_column(String, index=True)
    bhk: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    rent: Mapped[int] = mapped_column(Integer)
    url: Mapped[str] = mapped_column(String, unique=True)
    title: Mapped[str] = mapped_column(String)
    snippet: Mapped[str] = mapped_column(String)
    seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
