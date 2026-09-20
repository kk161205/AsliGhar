"""Extracts scored evidence out of raw SerpApi responses.

Field shapes here were confirmed against live SerpApi calls, not just the
documented contract, and differ from it in places: google_maps sometimes
returns `place_results`, sometimes a `local_results` list; google_local returns
agencies/complexes with no price data, so price comparables come from the
organic `google` engine instead.
"""

import logging
import re
import statistics

from app.models.schemas import ImageMatchEvidence, SignalResult
from app.services import scoring

logger = logging.getLogger(__name__)

CLASSIFIEDS_DOMAINS = {
    "olx.in",
    "quikr.com",
    "99acres.com",
    "magicbricks.com",
    "nobroker.in",
    "facebook.com",
    # Expanded 2026-09-20 — the original 6-domain list was reviewed against real
    # AI-summary output and found to silently miss reused photos on any of these
    # equally common Indian rental sites, undercutting the tool's headline signal.
    "housing.com",
    "sulekha.com",
    "commonfloor.com",
    "proptiger.com",
    "makaan.com",
    "nestaway.com",
    "squareyards.com",
}
PRICE_MISMATCH_TOLERANCE_PCT = 10  # a listed price is "different" beyond 10% of the submitted rent

MAJOR_INDIAN_CITIES = {
    "mumbai", "delhi", "new delhi", "bengaluru", "bangalore", "hyderabad",
    "chennai", "kolkata", "pune", "ahmedabad", "jaipur", "surat", "lucknow",
    "kanpur", "nagpur", "indore", "bhopal", "patna", "vadodara", "ghaziabad",
    "ludhiana", "agra", "nashik", "faridabad", "meerut", "rajkot", "varanasi",
    "srinagar", "amritsar", "chandigarh", "gurugram", "gurgaon", "noida",
    "kochi", "coimbatore", "visakhapatnam",
    # Expanded 2026-09-20 — a scam listing's contradicting match is just as
    # likely to be in a tier-2 city as a metro; this remains a hardcoded set
    # (not a geocoding lookup) so coverage is inherently partial, but a wider
    # list catches more real cases for the same cost.
    "thane", "navi mumbai", "thiruvananthapuram", "guwahati", "bhubaneswar",
    "dehradun", "raipur", "ranchi", "jodhpur", "madurai", "mysuru", "mysore",
    "nellore", "vijayawada", "aurangabad", "solapur", "hubli", "mangaluru",
    "mangalore", "tiruchirappalli", "salem", "warangal", "jamshedpur",
    "gwalior", "jabalpur", "allahabad", "prayagraj", "howrah", "bareilly",
    "moradabad",
}

# Substring match, not exact — Google's place categories are inconsistent
# ("Real estate rental agency" vs "real estate agency", "Condominium complex", etc).
RESIDENTIAL_CATEGORY_KEYWORDS = (
    "apartment", "residential", "real estate", "lodging", "guest house",
    "hostel", "condominium", "housing", "flat",
)

# Three independent patterns, not one: real snippets state a bare figure with no
# currency symbol at all, in a few different shapes — confirmed against live
# organic results ("27,000/Month", "18,000. Rent.", "Rs. 44,897").
RUPEE_PREFIXED_PATTERN = re.compile(r"(?:₹|rs\.?)\s?([\d,]{3,})", re.IGNORECASE)
MONTHLY_SUFFIXED_PATTERN = re.compile(r"([\d,]{3,})\s?/\s?month", re.IGNORECASE)
RENT_LABELED_PATTERN = re.compile(
    r"([\d,]{3,})\s?\.?\s?rent\b|\brent\.?\s?([\d,]{3,})", re.IGNORECASE
)
PER_SQFT_EXCLUSION_PATTERN = re.compile(r"per\s?sq|/\s?sq\s?ft|sqft", re.IGNORECASE)
# Sanity bounds reject likely misparses (phone numbers, pincodes, deposit
# amounts) rather than real monthly rent figures.
MIN_MONTHLY_RENT = 2_000
MAX_MONTHLY_RENT = 500_000
# Raised from 2 to 3 (2026-09-20): a median computed from just 2 noisy,
# regex-extracted snippet figures is a thin basis for up to 30/100 risk
# points. Real listings' price_deviation findings have shown 12-16 samples in
# practice, so 3 is a conservative floor, not a bar that starves the signal.
MIN_PRICE_SAMPLES = 3


def _mentions_other_city(text: str, submitted_city: str) -> str | None:
    lower = text.lower()
    submitted_lower = submitted_city.strip().lower()
    for city in MAJOR_INDIAN_CITIES:
        if city in lower and city != submitted_lower and city not in submitted_lower:
            return city.title()
    return None


def extract_image_reuse(
    lens_results: list, submitted_price: int, submitted_city: str
) -> tuple[SignalResult, list[ImageMatchEvidence]]:
    contradicting: list[ImageMatchEvidence] = []
    for photo_index, result in enumerate(lens_results):
        if isinstance(result, Exception):
            logger.warning("google_lens failed for photo %s: %s", photo_index, result)
            continue
        # For iconic/well-known photos (tested live with a Taj Mahal image), Lens
        # omits `visual_matches` entirely and returns an `ai_overview` block
        # instead — expected behavior, not a malformed response, hence the
        # defensive default rather than an assumption the key always exists.
        for match in result.get("visual_matches", []):
            domain = match.get("source", "").strip().lower()
            if domain not in CLASSIFIEDS_DOMAINS:
                continue
            title = match.get("title", "")
            listed_price = (match.get("price") or {}).get("extracted_value")
            listed_city = _mentions_other_city(title, submitted_city)
            price_mismatch = (
                listed_price is not None
                and submitted_price > 0
                and abs(listed_price - submitted_price) / submitted_price * 100
                > PRICE_MISMATCH_TOLERANCE_PCT
            )
            if not price_mismatch and listed_city is None:
                continue
            contradicting.append(
                ImageMatchEvidence(
                    photo_index=photo_index,
                    source_domain=domain,
                    source_url=match.get("link", ""),
                    source_title=title,
                    listed_price=listed_price,
                    submitted_price=submitted_price,
                    listed_city=listed_city,
                    submitted_city=submitted_city,
                )
            )

    score = scoring.image_reuse_score(len(contradicting))
    finding = (
        f"{len(contradicting)} of {len(lens_results)} photos found on other listings "
        "with a different price or city."
        if contradicting
        else "No photos found reused on other listings with a conflicting price or city."
    )
    return SignalResult(score=score, max=scoring.IMAGE_REUSE_MAX, finding=finding), contradicting


def _place_candidate(maps_result: dict) -> dict | None:
    place = maps_result.get("place_results")
    if place:
        return place
    local_results = maps_result.get("local_results")
    if local_results:
        return local_results[0]
    return None


def extract_address_validity(maps_result) -> SignalResult:
    if isinstance(maps_result, Exception):
        logger.warning("google_maps failed: %s", maps_result)
        return SignalResult(
            score=scoring.ADDRESS_AMBIGUOUS_SCORE,
            max=scoring.ADDRESS_VALIDITY_MAX,
            finding="Address lookup failed; could not verify it independently.",
        )

    place = _place_candidate(maps_result)
    if place is None:
        return SignalResult(
            score=scoring.ADDRESS_INVALID_SCORE,
            max=scoring.ADDRESS_VALIDITY_MAX,
            finding="The stated address does not resolve to any known location.",
        )

    category = place.get("type") or next(iter(place.get("types") or []), None)
    if category is None:
        # Common case for locality-level queries (confirmed live): place_results
        # resolves with title/address/gps_coordinates but no category at all.
        # That's a neutral "can't classify," not a red flag, so it scores above
        # a clean match but well below an actual category mismatch.
        location_label = place.get("title") or place.get("address") or "a known location"
        return SignalResult(
            score=scoring.ADDRESS_NO_CATEGORY_DATA_SCORE,
            max=scoring.ADDRESS_VALIDITY_MAX,
            finding=f'Address resolves to "{location_label}", but no category data was available to verify it further.',
        )

    if any(keyword in category.lower() for keyword in RESIDENTIAL_CATEGORY_KEYWORDS):
        return SignalResult(
            score=scoring.ADDRESS_VALID_SCORE,
            max=scoring.ADDRESS_VALIDITY_MAX,
            finding=f"Address resolves to a plausible residential category ({category}).",
        )

    return SignalResult(
        score=scoring.ADDRESS_AMBIGUOUS_SCORE,
        max=scoring.ADDRESS_VALIDITY_MAX,
        finding=f'Address resolves, but to a "{category}", not a residential building.',
    )


def _extract_monthly_prices(organic_results: list[dict]) -> list[int]:
    prices: list[int] = []
    for item in organic_results:
        text = f"{item.get('title', '')} {item.get('snippet', '')}"
        seen_spans: set[tuple[int, int]] = set()
        for pattern in (RUPEE_PREFIXED_PATTERN, MONTHLY_SUFFIXED_PATTERN, RENT_LABELED_PATTERN):
            for match in pattern.finditer(text):
                group_index = next(i for i, g in enumerate(match.groups(), 1) if g is not None)
                digits = match.group(group_index)
                span = match.span(group_index)
                if span in seen_spans:
                    continue
                window = text[max(0, match.start() - 15) : match.end() + 15]
                if PER_SQFT_EXCLUSION_PATTERN.search(window):
                    continue
                value = int(digits.replace(",", ""))
                if MIN_MONTHLY_RENT <= value <= MAX_MONTHLY_RENT:
                    prices.append(value)
                    seen_spans.add(span)
    return prices


def extract_price_deviation(organic_result, submitted_rent: int) -> SignalResult:
    if isinstance(organic_result, Exception):
        logger.warning("Price comparable search failed: %s", organic_result)
        return SignalResult(
            score=0,
            max=scoring.PRICE_DEVIATION_MAX,
            finding="Could not gather comparable price data for this locality.",
        )

    prices = _extract_monthly_prices(organic_result.get("organic_results", []))
    if len(prices) < MIN_PRICE_SAMPLES:
        return SignalResult(
            score=0,
            max=scoring.PRICE_DEVIATION_MAX,
            finding="Not enough comparable price data found for this locality to judge price deviation.",
        )

    median_rent = statistics.median(prices)
    score = scoring.price_deviation_score(submitted_rent, median_rent)
    deviation_pct = max(0.0, (median_rent - submitted_rent) / median_rent * 100)
    finding = (
        f"Rent is {deviation_pct:.0f}% below the estimated local median "
        f"(₹{median_rent:,.0f}) based on {len(prices)} comparable mentions."
        if score > 0
        else f"Rent is within a plausible range of the estimated local median (₹{median_rent:,.0f})."
    )
    return SignalResult(score=score, max=scoring.PRICE_DEVIATION_MAX, finding=finding)
