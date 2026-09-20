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
    bhk as bhk_reader,
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


async def _resolve_address(
    address: str, city: str, queries_used: list[str]
) -> tuple[dict, bool]:
    """Look the address up exactly as submitted; only if that finds nothing, retry with the city added.

    Adding the submitted city is not rewriting the claim, but it is only
    accepted when Maps answers with something more specific than the city
    itself (see evidence.resolved_place). Returns the result and whether the
    city had to be added.
    """
    queries_used.append(address)
    first = await serpapi_client.resolve_address(address)
    if evidence.resolved_place(first, city) is not None:
        return first, False
    with_city = f"{address}, {city}"
    queries_used.append(with_city)
    return await serpapi_client.resolve_address(with_city), True


async def _search_prices(
    bhk: str | None, locality: str | None, city: str, queries_used: list[str]
) -> dict:
    """Search for comparable rents at locality level; widen to the city if that finds too few.

    At most one extra search, and only when the first result has fewer usable
    comparables than the price check needs.
    """
    query = query_builder.price_query(bhk, locality, city)
    queries_used.append(query)
    result = await serpapi_client.organic_price_search(query, city)
    if locality is None or len(evidence.comparables(result.get("organic_results", []), city, bhk)) >= evidence.MIN_PRICE_SAMPLES:
        return result

    wider_query = query_builder.price_query(bhk, None, city)
    queries_used.append(wider_query)
    try:
        wider = await serpapi_client.organic_price_search(wider_query, city)
    except Exception as exc:
        logger.warning("Wider price search failed, using the locality results alone: %s", exc)
        return result
    seen_links: set[str] = set()
    merged = []
    for item in [*result.get("organic_results", []), *wider.get("organic_results", [])]:
        if item.get("link") not in seen_links:
            seen_links.add(item.get("link"))
            merged.append(item)
    return {"organic_results": merged}


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
    stated_bhk = bhk_reader.extract_bhk(bhk or "") or bhk_reader.extract_bhk(description or "")
    locality = reviewed.locality if reviewed else None
    logger.info("Searching: locality=%r bhk=%r reviewer_used=%s", locality, stated_bhk, reviewed is not None)

    # The address check always starts from the address exactly as submitted: a
    # rewritten query could make a made-up address resolve.
    address_queries: list[str] = []
    price_queries: list[str] = []
    results = await asyncio.gather(
        *lens_tasks,
        _resolve_address(address, city, address_queries),
        _search_prices(stated_bhk, locality, city, price_queries),
        return_exceptions=True,
    )
    lens_results, maps_outcome, price_result = results[: len(image_urls)], results[-2], results[-1]
    maps_result, city_added = maps_outcome if not isinstance(maps_outcome, Exception) else (maps_outcome, False)
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
            *(TraceQuery(check="address", query=query) for query in address_queries),
            *(TraceQuery(check="price", query=query) for query in price_queries),
        ],
    )

    image_reuse_signal, image_evidence = evidence.extract_image_reuse(lens_results, rent, city)
    address_signal = evidence.extract_address_validity(maps_result, city, city_added=city_added)
    price_signal = evidence.extract_price_deviation(price_result, rent, city=city, bhk=stated_bhk)

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
        {
            "submitted_listing": {"monthly_rent": rent, "city": city, "home_size": stated_bhk},
            "signals": signals.model_dump(),
            "evidence": evidence_payload,
        },
        ensure_ascii=False,
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
