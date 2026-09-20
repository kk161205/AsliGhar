"""Turns raw SerpApi responses into scored signals, each with the proof behind it.

Field shapes here were confirmed against live SerpApi calls, not just the
documented contract, and differ from it in places: Lens's `source` is a display
name ("OLX", "Facebook"), not a domain, so sites are recognised from each
match's link; google_maps sometimes returns `place_results`, sometimes a
`local_results` list; google_local returns agencies/complexes with no price
data, so price comparables come from the organic `google` engine instead.

Nothing is reported as evidence unless it can be stated as a fact about a
specific page or place: a photo match needs the page's own title, URL or price
to contradict the submitted listing, and a price comparison lists the listings
it was computed from.
"""

import logging
import re
import statistics
from typing import Literal, NamedTuple
from urllib.parse import urlparse

from app.models.schemas import ImageMatchEvidence, SignalResult, SignalSource
from app.services import bhk as bhk_reader
from app.services import cities, scoring

logger = logging.getLogger(__name__)

# The URL shape of a page that is ONE listing, per site. Exact-image matches
# also include search and category pages ("330 Flats & Apartments for Rent in
# Dhaulpur") that show the photo as one thumbnail among many; those prove
# nothing about a specific listing. Only shapes seen in real results are
# listed — a site is trusted once its listing URLs have been observed.
LISTING_PAGE_PATHS = {
    "olx.in": re.compile(r"/item/"),
    "magicbricks.com": re.compile(r"/propertyDetails/", re.IGNORECASE),
    "facebook.com": re.compile(r"/marketplace/item/|/posts/"),
}
PRICE_MISMATCH_TOLERANCE_PCT = 10  # a listed rent is "different" beyond 10% of the submitted rent

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
# How far around a figure to look for "per sqft": a price-per-area phrase can
# run for a whole clause ("price per sqft to rent a 3 BHK in Agra is Rs. 44,897").
PER_SQFT_LOOKBEHIND_CHARS = 40
PER_SQFT_LOOKAHEAD_CHARS = 15
# A figure introduced by one of these is a bound or a range end, not a rent
# ("Flats for rent under ₹10000", "from ₹8,000").
PRICE_QUALIFIER_PATTERN = re.compile(
    r"(?:under|below|upto|up to|from|starting|starts|above|over|between|max|min|budget)\W{0,3}$", re.IGNORECASE
)
PRICE_QUALIFIER_LOOKBEHIND_CHARS = 14
_SALE_WORDS = re.compile(r"\b(sale|resale|buy)\b")
_RENT_WORDS = re.compile(r"\b(rent|rentals?|lease|to let)\b")
# Sanity bounds reject likely misparses (phone numbers, pincodes, deposit
# amounts) rather than real monthly rent figures.
MIN_MONTHLY_RENT = 2_000
MAX_MONTHLY_RENT = 500_000
# A median from fewer than 3 comparable listings is too thin a basis for up to
# 30/100 risk points.
MIN_PRICE_SAMPLES = 3
# A rent this far over the median is worth saying so, even though only cheap
# rents add to the risk score.
NOTABLY_ABOVE_MEDIAN_PCT = 50
MAX_SNIPPET_CHARS = 160

ListingType = Literal["sale", "rent"]


def _listing_site(link: str) -> str | None:
    """The site a link is a single listing page of, or None.

    Taken from the link, not Lens's `source`, which is only a display name.
    """
    parsed = urlparse(link)
    host = (parsed.hostname or "").lower()
    for domain, path_pattern in LISTING_PAGE_PATHS.items():
        if (host == domain or host.endswith(f".{domain}")) and path_pattern.search(parsed.path):
            return domain
    return None


def _page_text(title: str, link: str) -> str:
    return f"{title} {urlparse(link).path}"


def listing_type(title: str, link: str) -> ListingType | None:
    """Whether a page's own title/URL says it is a sale or a rental listing.

    None when it says neither, or both.
    """
    words = re.sub(r"[^a-z0-9]+", " ", _page_text(title, link).lower())
    is_sale, is_rent = bool(_SALE_WORDS.search(words)), bool(_RENT_WORDS.search(words))
    if is_sale == is_rent:
        return None
    return "sale" if is_sale else "rent"


def _other_city(text: str, submitted_city: str) -> str | None:
    """A city the text names that isn't the submitted one, or None.

    Text that also names the submitted city, or a spelling variant of it
    ("Bangalore" vs "Bengaluru"), isn't a contradiction; nor is a street or
    institution that merely contains a city's name ("Mysore Road").
    """
    mentioned = cities.cities_mentioned(text)
    if not mentioned or cities.canonical_city(submitted_city) in mentioned:
        return None
    return sorted(mentioned)[0].title()


def _contradictions(
    match: dict, submitted_price: int, submitted_city: str
) -> tuple[list[str], int | None, str | None, ListingType | None]:
    """What the page itself says that conflicts with the submitted listing."""
    title, link = match.get("title", ""), match.get("link", "")
    listed_price = (match.get("price") or {}).get("extracted_value")
    kind = listing_type(title, link)
    reasons: list[str] = []
    if kind == "sale":
        shown = f" It shows ₹{listed_price:,}." if listed_price else ""
        reasons.append(f"It is a listing for sale, but you submitted a rental.{shown}")
    elif (
        listed_price is not None
        and submitted_price > 0
        and abs(listed_price - submitted_price) / submitted_price * 100 > PRICE_MISMATCH_TOLERANCE_PCT
    ):
        reasons.append(f"It shows ₹{listed_price:,} a month, but you submitted ₹{submitted_price:,}.")
    other_city = _other_city(_page_text(title, link), submitted_city)
    if other_city:
        reasons.append(f"Its title or address places it in {other_city}, but you submitted {submitted_city}.")
    return reasons, listed_price, other_city, kind


def extract_image_reuse(
    lens_results: list, submitted_price: int, submitted_city: str
) -> tuple[SignalResult, list[ImageMatchEvidence]]:
    failed_photos = sum(isinstance(result, Exception) for result in lens_results)
    if lens_results and failed_photos == len(lens_results):
        logger.warning("google_lens failed for all %s photos", failed_photos)
        return (
            SignalResult(
                score=0,
                max=scoring.IMAGE_REUSE_MAX,
                status="unavailable",
                finding="Couldn't check the photos for reuse — the image search didn't return a usable result.",
            ),
            [],
        )

    contradicting: list[ImageMatchEvidence] = []
    consistent = 0
    for photo_index, result in enumerate(lens_results):
        if isinstance(result, Exception):
            logger.warning("google_lens failed for photo %s: %s", photo_index, result)
            continue
        # Only pages carrying the same image count — Lens's look-alike matches
        # (other houses that merely resemble the photo) are never requested.
        exact_matches = result.get("exact_matches", [])
        seen_listings: set[tuple[str, str]] = set()
        listing_pages = 0
        for match in exact_matches:
            link = match.get("link", "")
            domain = _listing_site(link)
            # The same listing is served under several URLs (language prefixes).
            listing_key = (domain or "", match.get("title", "").strip().lower())
            if domain is None or listing_key in seen_listings:
                continue
            seen_listings.add(listing_key)
            listing_pages += 1
            reasons, listed_price, listed_city, kind = _contradictions(match, submitted_price, submitted_city)
            if not reasons:
                consistent += 1
                continue
            contradicting.append(
                ImageMatchEvidence(
                    photo_index=photo_index,
                    source_domain=domain,
                    source_url=link,
                    source_title=match.get("title", ""),
                    listed_price=listed_price,
                    submitted_price=submitted_price,
                    listed_city=listed_city,
                    submitted_city=submitted_city,
                    reasons=reasons,
                    listing_type=kind,
                )
            )
        logger.info(
            "google_lens photo %s: %s exact matches, %s of them single listing pages",
            photo_index,
            len(exact_matches),
            listing_pages,
        )

    checked = len(lens_results) - failed_photos
    photos_with_matches = len({item.photo_index for item in contradicting})
    # Per photo, not per page: the same stolen photo on five pages is one photo.
    score = scoring.image_reuse_score(photos_with_matches)
    finding = (
        f"{photos_with_matches} of {checked} photos appear on other property listings "
        "that contradict this one."
        if contradicting
        else "The photos weren't found on any other property listing that contradicts this one."
    )
    if consistent:
        finding += f" {consistent} other property listing(s) show the same photo without contradicting it."
    if failed_photos:
        finding += f" {failed_photos} photo(s) couldn't be checked."
    return SignalResult(score=score, max=scoring.IMAGE_REUSE_MAX, finding=finding), contradicting


def _place_candidate(maps_result: dict) -> dict | None:
    place = maps_result.get("place_results")
    if place:
        return place
    local_results = maps_result.get("local_results")
    if local_results:
        return local_results[0]
    return None


def resolved_place(maps_result, submitted_city: str) -> dict | None:
    """The place Maps found for an address, if it is more than just the city.

    A query like "<gibberish>, Bengaluru" makes Maps answer with Bengaluru
    itself (confirmed live). That is not the address resolving, so it is not
    accepted.
    """
    if isinstance(maps_result, Exception):
        return None
    place = _place_candidate(maps_result)
    if place is None:
        return None
    title = (place.get("title") or "").strip()
    if cities.is_city_name(title) or title.lower() == (cities.canonical_city(submitted_city) or ""):
        return None
    return place


def _maps_link(place: dict) -> str | None:
    place_id = place.get("place_id")
    return f"https://www.google.com/maps/place/?q=place_id:{place_id}" if place_id else None


def extract_address_validity(maps_result, submitted_city: str, *, city_added: bool) -> SignalResult:
    """`city_added`: the address alone found nothing, so the city was added to the search."""
    if isinstance(maps_result, Exception):
        logger.warning("google_maps failed: %s", maps_result)
        return SignalResult(
            score=0,
            max=scoring.ADDRESS_VALIDITY_MAX,
            status="unavailable",
            finding="Couldn't look up the address — the maps search didn't respond.",
        )

    place = resolved_place(maps_result, submitted_city)
    if place is None:
        suffix = ", even with the city added" if city_added else ""
        return SignalResult(
            score=scoring.ADDRESS_INVALID_SCORE,
            max=scoring.ADDRESS_VALIDITY_MAX,
            finding=f"The stated address does not resolve to any known location{suffix}.",
        )

    title = place.get("title") or "a known location"
    full_address = place.get("address") or ""
    source = SignalSource(
        title=title,
        url=_maps_link(place),
        detail=f"Google Maps: {full_address}" if full_address else "Google Maps result",
    )
    only_with_city = " Only found once the city was added to the search." if city_added else ""

    other_city = _other_city(full_address, submitted_city)
    if other_city:
        return SignalResult(
            score=scoring.ADDRESS_WRONG_CITY_SCORE,
            max=scoring.ADDRESS_VALIDITY_MAX,
            finding=f'Address resolves to "{title}" in {other_city}, not {submitted_city}.{only_with_city}',
            sources=[source],
        )

    category = place.get("type") or next(iter(place.get("types") or []), None)
    if category is None:
        # Common case for locality-level queries (confirmed live): place_results
        # resolves with title/address/gps_coordinates but no category at all.
        # That's a neutral "can't classify," not a red flag, so it scores above
        # a clean match but well below an actual category mismatch.
        return SignalResult(
            score=scoring.ADDRESS_NO_CATEGORY_DATA_SCORE,
            max=scoring.ADDRESS_VALIDITY_MAX,
            finding=(
                f'Address resolves to "{title}", but no category data was available to verify it further.'
                f"{only_with_city}"
            ),
            sources=[source],
        )

    if any(keyword in category.lower() for keyword in RESIDENTIAL_CATEGORY_KEYWORDS):
        return SignalResult(
            score=scoring.ADDRESS_VALID_SCORE,
            max=scoring.ADDRESS_VALIDITY_MAX,
            finding=f"Address resolves to a plausible residential category ({category}).{only_with_city}",
            sources=[source],
        )

    return SignalResult(
        score=scoring.ADDRESS_AMBIGUOUS_SCORE,
        max=scoring.ADDRESS_VALIDITY_MAX,
        finding=f'Address resolves, but to a "{category}", not a residential building.{only_with_city}',
        sources=[source],
    )


def _figures_in(text: str) -> tuple[set[int], bool]:
    """Rent-like figures in the text, and whether a price bound/range was seen."""
    figures: set[int] = set()
    has_bound = False
    seen_spans: set[tuple[int, int]] = set()
    for pattern in (RUPEE_PREFIXED_PATTERN, MONTHLY_SUFFIXED_PATTERN, RENT_LABELED_PATTERN):
        for match in pattern.finditer(text):
            group_index = next(i for i, g in enumerate(match.groups(), 1) if g is not None)
            span = match.span(group_index)
            if span in seen_spans:
                continue
            before = text[max(0, match.start() - PRICE_QUALIFIER_LOOKBEHIND_CHARS) : match.start()]
            if PRICE_QUALIFIER_PATTERN.search(before):
                has_bound = True
                continue
            window = text[max(0, match.start() - PER_SQFT_LOOKBEHIND_CHARS) : match.end() + PER_SQFT_LOOKAHEAD_CHARS]
            if PER_SQFT_EXCLUSION_PATTERN.search(window):
                continue
            value = int(match.group(group_index).replace(",", ""))
            if MIN_MONTHLY_RENT <= value <= MAX_MONTHLY_RENT:
                figures.add(value)
                seen_spans.add(span)
    return figures, has_bound


class Comparable(NamedTuple):
    rent: int
    title: str
    link: str
    snippet: str


def comparables(organic_results: list[dict], city: str, bhk: str | None) -> list[Comparable]:
    """Search results that state one monthly rent for a rental in this city.

    Each must name the city, not be a sale listing, state exactly one figure
    and no price bound or range (a snippet quoting several can't be attributed to one home) and — when the
    home size is known — state exactly that size.
    """
    found: list[Comparable] = []
    for item in organic_results:
        title, snippet, link = item.get("title", ""), item.get("snippet", ""), item.get("link", "")
        text = f"{title} {snippet}"
        if not cities.mentions_city(f"{text} {urlparse(link).path}", city):
            continue
        if listing_type(title, link) == "sale":
            continue
        if bhk and bhk_reader.mentioned(text) != {bhk}:
            continue
        figures, has_bound = _figures_in(text)
        if len(figures) != 1 or has_bound:
            continue
        found.append(Comparable(next(iter(figures)), title, link, snippet))
    return found


def _sources(comparables: list[Comparable]) -> list[SignalSource]:
    return [
        SignalSource(
            title=item.title,
            url=item.link or None,
            detail=f"₹{item.rent:,} a month — “{(item.snippet or item.title)[:MAX_SNIPPET_CHARS]}”",
        )
        for item in comparables
    ]


def extract_price_deviation(
    organic_result, submitted_rent: int, *, city: str, bhk: str | None
) -> SignalResult:
    max_score = scoring.price_deviation_max(bhk_known=bhk is not None)
    if isinstance(organic_result, Exception):
        logger.warning("Price comparable search failed: %s", organic_result)
        return SignalResult(
            score=0,
            max=max_score,
            status="unavailable",
            finding="Couldn't gather comparable rents — the price search didn't respond.",
        )

    found = comparables(organic_result.get("organic_results", []), city, bhk)
    if len(found) < MIN_PRICE_SAMPLES:
        home = f"a {bhk}" if bhk else "a home"
        return SignalResult(
            score=0,
            max=max_score,
            status="unavailable",
            finding=(
                f"Found {len(found)} listing(s) stating a rent for {home} in {city}; "
                f"at least {MIN_PRICE_SAMPLES} are needed to judge the price."
            ),
            sources=_sources(found),
        )

    median_rent = statistics.median(item.rent for item in found)
    score = scoring.price_deviation_score(submitted_rent, median_rent, max_score)
    deviation_pct = max(0.0, (median_rent - submitted_rent) / median_rent * 100)
    above_pct = (submitted_rent - median_rent) / median_rent * 100
    if score > 0:
        finding = (
            f"Rent is {deviation_pct:.0f}% below the median (₹{median_rent:,.0f}) of "
            f"{len(found)} listings that state a rent."
        )
    elif above_pct > NOTABLY_ABOVE_MEDIAN_PCT:
        finding = (
            f"Rent is {above_pct:.0f}% above the median (₹{median_rent:,.0f}) of "
            f"{len(found)} listings that state a rent. Only rents below the median add to the risk score."
        )
    else:
        finding = (
            f"Rent is within a plausible range of the median (₹{median_rent:,.0f}) of "
            f"{len(found)} listings that state a rent."
        )
    if bhk is None:
        finding += " No home size was given, so this compares across all sizes and counts for less."
    return SignalResult(score=score, max=max_score, finding=finding, sources=_sources(found))
