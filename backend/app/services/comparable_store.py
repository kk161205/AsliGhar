"""Keeps rent comparables from past scans so a later scan of the same area has more to compare.

A live search often yields only two or three usable pages. Every page that
passed the comparable rules (see evidence.comparables) is stored, and later
scans of the same city and home size use recent ones alongside their own
search. Storage is best-effort: a database problem never fails a scan.
"""

import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.models.db import RentComparable, async_session
from app.services import cities
from app.services.evidence import Comparable

logger = logging.getLogger(__name__)

MAX_AGE_DAYS = 30
MAX_STORED_COMPARABLES = 15


def _key(city: str) -> str:
    return cities.canonical_city(city) or city.strip().lower()


async def load(city: str, bhk: str | None) -> list[Comparable]:
    """Recent comparables for this city and home size. Nothing when the size is unknown."""
    if bhk is None:
        return []
    cutoff = datetime.now(timezone.utc) - timedelta(days=MAX_AGE_DAYS)
    try:
        async with async_session() as session:
            result = await session.execute(
                select(RentComparable)
                .where(RentComparable.city == _key(city), RentComparable.bhk == bhk, RentComparable.seen_at >= cutoff)
                .order_by(RentComparable.seen_at.desc())
                .limit(MAX_STORED_COMPARABLES)
            )
            rows = result.scalars().all()
    except Exception as exc:
        logger.warning("Couldn't load stored comparables: %s", exc)
        return []
    return [Comparable(row.rent, row.title, row.url, row.snippet, earlier=True) for row in rows]


async def save(city: str, bhk: str | None, found: list[Comparable]) -> None:
    """Store comparables from this scan that aren't stored yet (by page link)."""
    new = {item.link: item for item in found if item.link}
    if bhk is None or not new:
        return
    try:
        async with async_session() as session:
            existing = await session.execute(select(RentComparable.url).where(RentComparable.url.in_(new)))
            known = set(existing.scalars().all())
            for link, item in new.items():
                if link in known:
                    continue
                session.add(
                    RentComparable(
                        id=uuid.uuid4().hex,
                        city=_key(city),
                        bhk=bhk,
                        rent=item.rent,
                        url=link,
                        title=item.title,
                        snippet=item.snippet,
                    )
                )
            await session.commit()
    except Exception as exc:
        logger.warning("Couldn't store comparables: %s", exc)
