import httpx

from app.core.config import get_settings

SERPAPI_ENDPOINT = "https://serpapi.com/search"
REQUEST_TIMEOUT_SECONDS = 8.0


async def _get(params: dict) -> dict:
    settings = get_settings()
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
        response = await client.get(
            SERPAPI_ENDPOINT,
            params={**params, "api_key": settings.serpapi_key},
        )
        response.raise_for_status()
        return response.json()


async def reverse_image_search(image_url: str) -> dict:
    return await _get({"engine": "google_lens", "url": image_url})


async def resolve_address(address: str) -> dict:
    return await _get({"engine": "google_maps", "q": address})


async def local_price_comparables(query: str, city: str) -> dict:
    return await _get(
        {"engine": "google_local", "q": query, "location": f"{city}, India"}
    )
