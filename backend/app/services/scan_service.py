import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from app.core.config import get_settings
from app.models.db import Scan, async_session
from app.models.schemas import ImageMatchEvidence, ScanResponse, ScanSignals, ScanSummary
from app.services import evidence, groq_client, image_host, scoring, serpapi_client

logger = logging.getLogger(__name__)

SCAN_ID_LENGTH = 10
RECENT_SCANS_LIMIT = 20


def _price_query(bhk: str | None, city: str) -> str:
    # "price" biases the organic engine toward snippets that actually quote a
    # rupee figure — confirmed against live data.
    return " ".join(filter(None, [bhk, "rent", city, "price"]))


async def run_scan(
    photos: list[tuple[bytes, str]],
    address: str,
    city: str,
    rent: int,
    bhk: str | None,
    description: str | None,
    user_id: str,
) -> ScanResponse:
    image_host.cleanup_expired(get_settings().image_ttl_minutes)
    saved_paths = [image_host.save_upload(content, suffix) for content, suffix in photos]
    image_urls = [_public_image_url(path.name) for path in saved_paths]

    lens_calls = [serpapi_client.reverse_image_search(url) for url in image_urls]
    tasks = [
        *lens_calls,
        serpapi_client.resolve_address(address),
        serpapi_client.organic_price_search(_price_query(bhk, city), city),
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    lens_results, maps_result, price_result = results[: len(image_urls)], results[-2], results[-1]

    image_reuse_signal, image_evidence = evidence.extract_image_reuse(lens_results, rent, city)
    address_signal = evidence.extract_address_validity(maps_result)
    price_signal = evidence.extract_price_deviation(price_result, rent)

    risk_score = image_reuse_signal.score + address_signal.score + price_signal.score
    risk_band = scoring.band_for_score(risk_score)
    signals = ScanSignals(
        image_reuse=image_reuse_signal,
        price_deviation=price_signal,
        address_validity=address_signal,
    )

    evidence_payload = [item.model_dump() for item in image_evidence]
    # ensure_ascii=False: with the default True, non-ASCII characters (₹) get
    # escaped to the literal 6-character text "₹" in the prompt, which
    # the model then has to decode back into a glyph itself when writing
    # prose — unreliably, confirmed live (two of three real summaries
    # silently wrote £ instead of ₹). Sending the actual character removes
    # that failure mode entirely.
    evidence_json = json.dumps(
        {"signals": signals.model_dump(), "evidence": evidence_payload}, ensure_ascii=False
    )
    ai_summary = await groq_client.summarize_evidence(
        evidence_json=evidence_json,
        risk_score=risk_score,
        risk_band=risk_band,
        listing_description=description,
    )

    scan_id = uuid.uuid4().hex[:SCAN_ID_LENGTH]
    created_at = datetime.now(timezone.utc)

    async with async_session() as session:
        session.add(
            Scan(
                id=scan_id,
                created_at=created_at,
                user_id=user_id,
                address=address,
                city=city,
                rent=rent,
                risk_score=risk_score,
                risk_band=risk_band,
                signals_json=signals.model_dump(),
                evidence_json=evidence_payload,
                ai_summary=ai_summary,
            )
        )
        await session.commit()

    logger.info(
        "Scan %s completed: user=%s score=%s band=%s", scan_id, user_id, risk_score, risk_band
    )
    return ScanResponse(
        scan_id=scan_id,
        risk_score=risk_score,
        risk_band=risk_band,
        signals=signals,
        evidence=image_evidence,
        ai_summary=ai_summary,
        created_at=created_at,
    )


async def get_scan(scan_id: str) -> ScanResponse | None:
    async with async_session() as session:
        row = await session.get(Scan, scan_id)
    if row is None:
        return None
    return ScanResponse(
        scan_id=row.id,
        risk_score=row.risk_score,
        risk_band=row.risk_band,
        signals=ScanSignals.model_validate(row.signals_json),
        evidence=[ImageMatchEvidence.model_validate(item) for item in row.evidence_json],
        ai_summary=row.ai_summary,
        created_at=row.created_at,
    )


async def list_recent_scans(user_id: str, limit: int = RECENT_SCANS_LIMIT) -> list[ScanSummary]:
    async with async_session() as session:
        result = await session.execute(
            select(Scan)
            .where(Scan.user_id == user_id)
            .order_by(Scan.created_at.desc())
            .limit(limit)
        )
        rows = result.scalars().all()
    return [
        ScanSummary(
            scan_id=row.id,
            address=row.address,
            city=row.city,
            risk_score=row.risk_score,
            risk_band=row.risk_band,
            created_at=row.created_at,
        )
        for row in rows
    ]


def _public_image_url(filename: str) -> str:
    return f"{get_settings().public_base_url}/static/scans/{filename}"
