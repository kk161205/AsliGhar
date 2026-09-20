import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from app.core.config import get_settings
from app.models.db import Scan, async_session
from app.models.schemas import (
    ImageMatchEvidence,
    ScanResponse,
    ScanSignals,
    ScanSummary,
    SearchTrace,
    TraceQuery,
    UnderstoodInput,
)
from app.services import (
    evidence,
    groq_client,
    image_host,
    input_review,
    query_builder,
    scoring,
    serpapi_client,
)

logger = logging.getLogger(__name__)

SCAN_ID_LENGTH = 10
RECENT_SCANS_LIMIT = 20


def _discard_unretrieved(lens_results: list, saved_paths: list) -> list:
    """Replace the Lens result of any photo nobody downloaded with a failure.

    Lens reports "no matches" identically whether it found none or never saw
    the image, so a result for a photo that wasn't actually fetched must not
    be read as "checked and clean".
    """
    checked = []
    for result, path in zip(lens_results, saved_paths):
        if not isinstance(result, Exception) and not image_host.was_fetched(path.name):
            logger.warning("Image search never requested photo %s; ignoring its result", path.name)
            result = image_host.PhotoNotRetrieved(path.name)
        checked.append(result)
    return checked


async def _review(
    address: str, city: str, description: str | None
) -> input_review.NormalizedInput | None:
    if not get_settings().supervisor_enabled:
        return None
    return await input_review.review_input(address, city, description)


async def run_scan(
    photos: list[tuple[bytes, str]],
    address: str,
    city: str,
    rent: int,
    bhk: str | None,
    description: str | None,
    user_id: str,
    override_reason: str | None = None,
) -> ScanResponse:
    image_host.cleanup_expired(get_settings().image_ttl_minutes)
    saved_paths = [image_host.save_upload(content, suffix) for content, suffix in photos]
    image_urls = [_public_image_url(path.name) for path in saved_paths]

    # Photo searches are slow and need nothing from the reviewer, so they start
    # first and run while the address is being read.
    lens_tasks = [asyncio.ensure_future(serpapi_client.reverse_image_search(url)) for url in image_urls]

    reviewed = await _review(address, city, description)
    # A stated BHK wins; otherwise only one written in the description is used —
    # never guessed.
    stated_bhk = bhk or input_review.extract_bhk(description or "")
    locality = reviewed.locality if reviewed else None
    price_query = query_builder.price_query(stated_bhk, locality, city)
    logger.info("Searching: price_query=%r reviewer_used=%s", price_query, reviewed is not None)

    # The address check always searches the address exactly as submitted: a
    # rewritten query could make a made-up address resolve.
    results = await asyncio.gather(
        *lens_tasks,
        serpapi_client.resolve_address(address),
        serpapi_client.organic_price_search(price_query, city),
        return_exceptions=True,
    )
    lens_results, maps_result, price_result = results[: len(image_urls)], results[-2], results[-1]
    lens_results = _discard_unretrieved(lens_results, saved_paths)
    trace = SearchTrace(
        reviewer_used=reviewed is not None,
        understood=UnderstoodInput(
            address_city=reviewed.address_city if reviewed else None,
            locality=locality,
            landmark=reviewed.landmark if reviewed else None,
            pincode=reviewed.pincode if reviewed else None,
            bhk=stated_bhk,
        ),
        queries=[
            TraceQuery(check="address", query=address),
            TraceQuery(check="price", query=price_query),
        ],
    )

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
                override_reason=override_reason,
                trace_json=trace.model_dump(),
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
        override_reason=override_reason,
        search_trace=trace,
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
        override_reason=row.override_reason,
        search_trace=SearchTrace.model_validate(row.trace_json) if row.trace_json else None,
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
