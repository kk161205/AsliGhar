import logging
import time

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

SERPAPI_ENDPOINT = "https://serpapi.com/search"
SERPAPI_ACCOUNT_ENDPOINT = "https://serpapi.com/account"
REQUEST_TIMEOUT_SECONDS = 8.0
MAX_RETRIES = 1

_cache: dict[tuple, tuple[float, dict]] = {}


async def verify_key() -> bool:
    """Confirm SERPAPI_KEY is valid via the account endpoint (does not spend search quota)."""
    settings = get_settings()
    if not settings.serpapi_key:
        logger.error("SerpApi verification failed: SERPAPI_KEY is not set")
        return False
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
            response = await client.get(
                SERPAPI_ACCOUNT_ENDPOINT, params={"api_key": settings.serpapi_key}
            )
        data = response.json()
        if response.status_code != 200 or "error" in data:
            logger.error("SerpApi verification failed: %s", data.get("error", response.status_code))
            return False
        logger.info(
            "SerpApi key verified (plan=%s, searches_left=%s)",
            data.get("plan_name"),
            data.get("total_searches_left"),
        )
        return True
    except httpx.HTTPError as exc:
        logger.error("SerpApi verification failed: %s", exc)
        return False


async def _get(
    engine: str,
    params: dict,
    timeout_seconds: float = REQUEST_TIMEOUT_SECONDS,
    cache_ttl_seconds: float | None = None,
) -> dict:
    settings = get_settings()
    ttl = settings.scan_cache_ttl_seconds if cache_ttl_seconds is None else cache_ttl_seconds
    cache_key = (engine, tuple(sorted(params.items())))
    cached = _cache.get(cache_key)
    if cached and time.monotonic() - cached[0] < ttl:
        logger.info("SerpApi cache hit: engine=%s", engine)
        return cached[1]

    request_params = {**params, "engine": engine, "api_key": settings.serpapi_key}
    last_exc: httpx.TimeoutException | None = None
    for attempt in range(1, MAX_RETRIES + 2):
        try:
            async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                response = await client.get(SERPAPI_ENDPOINT, params=request_params)
            response.raise_for_status()
            data = response.json()
            _cache[cache_key] = (time.monotonic(), data)
            logger.info("SerpApi call succeeded: engine=%s attempt=%s", engine, attempt)
            return data
        except httpx.TimeoutException as exc:
            last_exc = exc
            logger.warning("SerpApi call timed out: engine=%s attempt=%s", engine, attempt)
        except httpx.HTTPStatusError as exc:
            logger.error(
                "SerpApi call failed: engine=%s status=%s", engine, exc.response.status_code
            )
            raise

    logger.error("SerpApi call failed after %s attempts: engine=%s", MAX_RETRIES + 1, engine)
    assert last_exc is not None
    raise last_exc


async def reverse_image_search(image_url: str) -> dict:
    # google_lens runs noticeably slower than the other engines in practice
    # (confirmed live: ~9s typical, vs ~4s for maps/local/organic), so it gets
    # its own, wider timeout rather than sharing REQUEST_TIMEOUT_SECONDS.
    settings = get_settings()
    # exact_matches: pages carrying this same image. The default (visual_matches)
    # returns look-alikes — other houses that merely resemble the photo.
    return await _get(
        "google_lens",
        {"url": image_url, "type": "exact_matches"},
        timeout_seconds=settings.serpapi_lens_timeout_seconds,
    )


async def resolve_address(address: str) -> dict:
    return await _get("google_maps", {"q": address})


async def organic_price_search(query: str, city: str) -> dict:
    """Primary source for price comparables, not a fallback: google_local returns
    agencies/complexes with no price data at all (confirmed against live data),
    so real ₹ figures come from organic snippets instead."""
    return await _get(
        "google",
        {"q": query, "location": f"{city}, India"},
        cache_ttl_seconds=get_settings().price_cache_ttl_seconds,
    )


async def search_page(url: str) -> dict:
    """Google's own entry for a page, found by searching its URL.

    Direct requests to listing sites are blocked, but the search result for a
    listing carries its title, size and price (confirmed live for OLX).
    """
    return await _get("google", {"q": url}, cache_ttl_seconds=get_settings().price_cache_ttl_seconds)


async def search_phone(phone: str) -> dict:
    """Pages that carry this exact number (an exact-phrase search)."""
    return await _get(
        "google", {"q": f'"{phone}"', "gl": "in"}, cache_ttl_seconds=get_settings().price_cache_ttl_seconds
    )
