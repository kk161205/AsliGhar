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
from collections.abc import Sequence
from typing import Literal, NamedTuple
from urllib.parse import urlparse

from app.models.schemas import ImageMatchEvidence, SignalResult, SignalSource, Tier
from app.services import bhk as bhk_reader
from app.services import cities, scoring
from app.services.money import inr

logger = logging.getLogger(__name__)

# The URL shape of a page that is ONE listing, per site. Exact-image matches
# also include search and category pages ("330 Flats & Apartments for Rent in
# Dhaulpur") that show the photo as one thumbnail among many; those prove
# nothing about a specific listing. Only shapes seen in real results are
# listed — a site is trusted once its listing URLs have been observed. The
# shape alone isn't enough (OLX also sells phones; Facebook posts can be about
# anything), so a page must also read as property — see _classify_page.
LISTING_PAGE_PATHS = {
    "olx.in": re.compile(r"/item/"),
    "magicbricks.com": re.compile(r"/propertyDetails/", re.IGNORECASE),
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

# A listing page's own price, as Google's result for it quotes it ("₹ 31,99,000").
# Not range-checked: a sale price is far above any monthly rent.
LISTING_PRICE_PATTERN = re.compile(r"(?:₹|rs\.?)\s?([\d,]{4,})", re.IGNORECASE)
MAX_PAGE_SNIPPET_CHARS = 200


class PageDetails(NamedTuple):
    price: int | None
    snippet: str | None
    title: str = ""


def page_key(link: str) -> str:
    """Identifies a listing across the URL variants a site serves it under."""
    parsed = urlparse(link)
    host = (parsed.hostname or "").lower().removeprefix("www.")
    listing_id = re.search(r"iid-\d+", parsed.path)
    if listing_id:
        return f"{host}/{listing_id.group(0)}"
    return host + re.sub(r"^/[a-z]{2}-[a-z]{2}/", "/", parsed.path)


def page_details(organic_results: list[dict], link: str) -> PageDetails | None:
    """What Google shows for this exact page, found among search results for its URL."""
    key = page_key(link)
    for item in organic_results:
        if page_key(item.get("link", "")) != key:
            continue
        snippet = (item.get("snippet") or "").strip()
        figures = {
            int(digits.replace(",", ""))
            for digits in LISTING_PRICE_PATTERN.findall(f"{item.get('title', '')} {snippet}")
        }
        return PageDetails(
            price=next(iter(figures)) if len(figures) == 1 else None,
            snippet=snippet[:MAX_PAGE_SNIPPET_CHARS] or None,
            title=item.get("title", ""),
        )
    return None


def listing_site(link: str) -> str | None:
    """The site a link is a single listing page of, or None.

    Taken from the link, not Lens's `source`, which is only a display name.
    """
    parsed = urlparse(link)
    host = (parsed.hostname or "").lower()
    for domain, path_pattern in LISTING_PAGE_PATHS.items():
        if (host == domain or host.endswith(f".{domain}")) and path_pattern.search(parsed.path):
            return domain
    return None


_PROPERTY_WORDS = re.compile(
    r"\b(bhk|flats?|houses?|villas?|apartments?|bungalows?|studio|rooms?|pg|kothi|floor|independent|penthouse|duplex)\b"
)
_LISTING_INTENT = re.compile(r"\b(sale|resale|buy|rent|rental|lease|to let)\b")
# Titles/URLs of search and category pages rather than one listing: a leading
# count ("330 Flats..."), "Page 2", a plural property noun followed by "in"/"near"/
# "for", or search parameters in the URL.
_AGGREGATE_TITLE = re.compile(
    r"^\s*\d[\d,+]*\s|\bpage \d+\b|\b(?:properties|flats|houses|apartments|villas|rooms|homes|bungalows)\b.*\b(?:in|near|for)\b",
    re.IGNORECASE,
)
# A run of 6+ digits not glued to a letter (so a geo code like "_g4059117" isn't
# one), or a long hex id.
_LISTING_ID = re.compile(r"(?<![A-Za-z0-9])\d{6,}|[0-9a-f]{16,}", re.IGNORECASE)
_AGGREGATE_QUERY = re.compile(r"filter=|searchparam|[?&]q=|/search", re.IGNORECASE)


def looks_like_listing_page(title: str, link: str) -> bool:
    """Whether a page's own title/URL reads like ONE property listing.

    Used for sites whose listing URL shapes haven't been observed, so a match
    here is an indicator, not proof.
    """
    parsed = urlparse(link)
    location = f"{parsed.path}?{parsed.query}"
    # One listing has its own ID in the URL; category pages on the same sites
    # ("...-for-rent-in-khar-mumbai-pppfr") don't. Confirmed against real
    # Magicbricks and 99acres results.
    if not _LISTING_ID.search(location) or _AGGREGATE_QUERY.search(location):
        return False
    if _AGGREGATE_TITLE.search(title):
        return False
    words = re.sub(r"[^a-z0-9]+", " ", page_text(title, link).lower())
    return bool(_PROPERTY_WORDS.search(words) and _LISTING_INTENT.search(words))


def _classify_page(title: str, link: str) -> tuple[str, Tier] | None:
    """(site, tier) if the page is a property listing: proven for sites whose listing URLs are known.

    Both routes require the page to read as property, so a phone ad on a
    classifieds site or a mortgage post on social media is never a listing.
    """
    known = listing_site(link)
    if known and _PROPERTY_WORDS.search(re.sub(r"[^a-z0-9]+", " ", page_text(title, link).lower())):
        return known, "proven"
    if looks_like_listing_page(title, link):
        host = (urlparse(link).hostname or "").lower().removeprefix("www.")
        return host, "indicator"
    return None


def page_text(title: str, link: str) -> str:
    return f"{title} {urlparse(link).path}"


def listing_type(title: str, link: str) -> ListingType | None:
    """Whether a page's own title/URL says it is a sale or a rental listing.

    None when it says neither, or both.
    """
    words = re.sub(r"[^a-z0-9]+", " ", page_text(title, link).lower())
    is_sale, is_rent = bool(_SALE_WORDS.search(words)), bool(_RENT_WORDS.search(words))
    if is_sale == is_rent:
        return None
    return "sale" if is_sale else "rent"


def other_city(text: str, submitted_city: str) -> str | None:
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
    match: dict, submitted_price: int, submitted_city: str, page: PageDetails | None
) -> tuple[list[str], int | None, str | None, ListingType | None]:
    """What the page itself says that conflicts with the submitted listing."""
    title, link = match.get("title", ""), match.get("link", "")
    listed_price = (match.get("price") or {}).get("extracted_value") or (page.price if page else None)
    kind = listing_type(title, link)
    reasons: list[str] = []
    if kind == "sale":
        shown = f" It shows {inr(listed_price)}." if listed_price else ""
        reasons.append(f"It is a listing for sale, but you submitted a rental.{shown}")
    elif (
        listed_price is not None
        and submitted_price > 0
        and abs(listed_price - submitted_price) / submitted_price * 100 > PRICE_MISMATCH_TOLERANCE_PCT
    ):
        reasons.append(f"It shows {inr(listed_price)} a month, but you submitted {inr(submitted_price)}.")
    listed_city = other_city(page_text(title, link), submitted_city)
    if listed_city:
        reasons.append(f"Its title or address places it in {listed_city}, but you submitted {submitted_city}.")
    return reasons, listed_price, listed_city, kind


STOCK_PHOTO_DOMAINS = {
    "shutterstock.com",
    "alamy.com",
    "istockphoto.com",
    "gettyimages.com",
    "gettyimages.in",
    "freepik.com",
    "unsplash.com",
    "pexels.com",
    "pixabay.com",
    "dreamstime.com",
    "depositphotos.com",
    "123rf.com",
    "stock.adobe.com",
    "vecteezy.com",
    "rawpixel.com",
}


def _stock_site(link: str) -> str | None:
    """The stock-photo site a link points to, or None. Exact host match, no guessing."""
    host = (urlparse(link).hostname or "").lower()
    for domain in STOCK_PHOTO_DOMAINS:
        if host == domain or host.endswith(f".{domain}"):
            return domain
    return None


class _Candidate:
    """One page that carries at least one of the submitted photos."""

    def __init__(self, match: dict, domain: str, base_tier: Tier) -> None:
        self.match = match
        self.domain = domain
        self.base_tier = base_tier
        self.photo_indexes: set[int] = set()


def _collect_candidates(
    lens_results: list, own_listing_url: str | None
) -> tuple[dict[str, _Candidate], dict[int, dict]]:
    """Pages carrying the photos (one entry per page across all photos) and stock-photo hits per photo.

    A page is one entry however many photos matched it and however many URL
    variants the site serves it under.
    """
    candidates: dict[str, _Candidate] = {}
    by_title: dict[tuple[str, str], str] = {}
    stock: dict[int, dict] = {}
    own_key = page_key(own_listing_url) if own_listing_url else None
    for photo_index, result in enumerate(lens_results):
        if isinstance(result, Exception):
            logger.warning("google_lens failed for photo %s: %s", photo_index, result)
            continue
        # Only pages carrying the same image count — Lens's look-alike matches
        # (other houses that merely resemble the photo) are never requested.
        exact_matches = result.get("exact_matches", [])
        for match in exact_matches:
            link = match.get("link", "")
            stock_site = _stock_site(link)
            if stock_site:
                stock.setdefault(photo_index, {**match, "domain": stock_site})
                continue
            classified = _classify_page(match.get("title", ""), link)
            if classified is None:
                continue
            domain, tier = classified
            key = page_key(link)
            if key == own_key:
                continue
            key = by_title.setdefault((domain, match.get("title", "").strip().lower()), key)
            candidate = candidates.setdefault(key, _Candidate(match, domain, tier))
            candidate.photo_indexes.add(photo_index)
        logger.info("google_lens photo %s: %s exact matches", photo_index, len(exact_matches))
    return candidates, stock


def extract_image_reuse(
    lens_results: list,
    submitted_price: int,
    submitted_city: str,
    pages: dict[str, PageDetails] | None = None,
    *,
    also_identified: dict[str, list[str]] | None = None,
    own_listing_url: str | None = None,
) -> tuple[SignalResult, list[ImageMatchEvidence]]:
    """Find other listings of this house and report where they contradict the submission.

    A page is the same house's listing when independent identifiers agree: two
    of the submitted photos, or a photo plus the phone number or the description
    text (`also_identified`: page key -> what else pointed at it). A single
    photo on a page whose URL shape is known to be one listing also counts;
    a single photo on any other listing-looking page is an indicator only.
    Stock-photo sites are recognised by their exact domain.
    """
    pages = pages or {}
    also_identified = also_identified or {}
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

    candidates, stock = _collect_candidates(lens_results, own_listing_url)
    contradicting: list[ImageMatchEvidence] = []
    consistent = 0
    for key, candidate in candidates.items():
        match = candidate.match
        link = match.get("link", "")
        page = pages.get(link)
        reasons, listed_price, listed_city, kind = _contradictions(match, submitted_price, submitted_city, page)
        if not reasons:
            consistent += 1
            continue
        matched_by = [f"photo {index + 1}" for index in sorted(candidate.photo_indexes)] + also_identified.get(key, [])
        tier: Tier = "proven" if candidate.base_tier == "proven" or len(matched_by) >= 2 else "indicator"
        contradicting.append(
            ImageMatchEvidence(
                photo_index=min(candidate.photo_indexes),
                photo_indexes=sorted(candidate.photo_indexes),
                source_domain=candidate.domain,
                source_url=link,
                source_title=match.get("title", ""),
                listed_price=listed_price,
                submitted_price=submitted_price,
                listed_city=listed_city,
                submitted_city=submitted_city,
                reasons=reasons,
                listing_type=kind,
                source_snippet=page.snippet if page else None,
                tier=tier,
                matched_by=matched_by,
            )
        )
    for photo_index, match in stock.items():
        contradicting.append(
            ImageMatchEvidence(
                photo_index=photo_index,
                photo_indexes=[photo_index],
                source_domain=match["domain"],
                source_url=match.get("link", ""),
                source_title=match.get("title", ""),
                submitted_price=submitted_price,
                submitted_city=submitted_city,
                reasons=[f"{match['domain']} is a stock-photo site, so this is not a photo of one particular home."],
                tier="proven",
                matched_by=[f"photo {photo_index + 1}"],
            )
        )

    checked = len(lens_results) - failed_photos
    contradicted = {index for item in contradicting for index in item.photo_indexes}
    proven_photos = {index for item in contradicting if item.tier == "proven" for index in item.photo_indexes}
    # Per photo, not per page: the same stolen photo on five pages is one photo.
    score = scoring.image_reuse_score(len(proven_photos), len(contradicted - proven_photos))
    finding = (
        f"{len(contradicted)} of {checked} photos appear on other listings or sites "
        "in a way that contradicts this one."
        if contradicting
        else "The photos weren't found on any other listing that contradicts this one."
    )
    if consistent:
        finding += f" {consistent} other listing(s) show the same photo without contradicting it."
    if failed_photos:
        finding += f" {failed_photos} photo(s) couldn't be checked."
    return (
        SignalResult(
            score=score,
            max=scoring.IMAGE_REUSE_MAX,
            finding=finding,
            basis="proven" if proven_photos else "indicator",
        ),
        contradicting,
    )


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


def maps_link(place: dict) -> str | None:
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
        url=maps_link(place),
        detail=f"Google Maps: {full_address}" if full_address else "Google Maps result",
    )
    found_with_city = " Found by adding your city to the search." if city_added else ""

    resolved_city = other_city(full_address, submitted_city)
    if resolved_city:
        return SignalResult(
            score=scoring.ADDRESS_WRONG_CITY_SCORE,
            max=scoring.ADDRESS_VALIDITY_MAX,
            finding=f'Address resolves to "{title}" in {resolved_city}, not {submitted_city}.{found_with_city}',
            sources=[source],
        )

    category = place.get("type") or next(iter(place.get("types") or []), None)
    if category is None:
        # Common for locality-level queries (confirmed live): Maps resolves the
        # place with title/address/gps but no category. Absence of a category is
        # not evidence against the address, so it isn't scored as one.
        located = f" ({full_address})" if full_address else ""
        return SignalResult(
            score=scoring.ADDRESS_VALID_SCORE,
            max=scoring.ADDRESS_VALIDITY_MAX,
            finding=(
                f'Google Maps found "{title}"{located}. That confirms the place exists, '
                f"not what kind of building it is.{found_with_city}"
            ),
            sources=[source],
        )

    if any(keyword in category.lower() for keyword in RESIDENTIAL_CATEGORY_KEYWORDS):
        return SignalResult(
            score=scoring.ADDRESS_VALID_SCORE,
            max=scoring.ADDRESS_VALIDITY_MAX,
            finding=f"Address resolves to a plausible residential category ({category}).{found_with_city}",
            sources=[source],
        )

    return SignalResult(
        score=scoring.ADDRESS_AMBIGUOUS_SCORE,
        max=scoring.ADDRESS_VALIDITY_MAX,
        finding=f'Address resolves, but to a "{category}", not a residential building.{found_with_city}',
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
    earlier: bool = False  # kept from a previous scan rather than found just now


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
            detail=(
                f"{inr(item.rent)} a month — “{(item.snippet or item.title)[:MAX_SNIPPET_CHARS]}”"
                f"{' (from an earlier search)' if item.earlier else ''}"
            ),
        )
        for item in comparables
    ]


def extract_price_deviation(
    organic_result,
    submitted_rent: int,
    *,
    city: str,
    bhk: str | None,
    stored: Sequence[Comparable] = (),
) -> SignalResult:
    """`stored`: comparables kept from earlier scans of the same area, used alongside today's search."""
    max_score = scoring.price_deviation_max(bhk_known=bhk is not None)
    search_failed = isinstance(organic_result, Exception)
    if search_failed:
        logger.warning("Price comparable search failed: %s", organic_result)
    fresh = [] if search_failed else comparables(organic_result.get("organic_results", []), city, bhk)
    fresh_links = {item.link for item in fresh}
    found = [*fresh, *(item for item in stored if item.link not in fresh_links)]
    if len(found) < MIN_PRICE_SAMPLES:
        if search_failed:
            return SignalResult(
                score=0,
                max=max_score,
                status="unavailable",
                finding="Couldn't gather comparable rents — the price search didn't respond.",
            )
        home = f"a {bhk}" if bhk else "a home"
        return SignalResult(
            score=0,
            max=max_score,
            status="unavailable",
            finding=(
                f"Found {len(found)} page(s) quoting a rent for {home} in {city}; "
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
            f"Rent is {deviation_pct:.0f}% below the median ({inr(round(median_rent))}) of "
            f"{len(found)} pages that quote a rent."
        )
    elif above_pct > NOTABLY_ABOVE_MEDIAN_PCT:
        finding = (
            f"Rent is {above_pct:.0f}% above the median ({inr(round(median_rent))}) of "
            f"{len(found)} pages that quote a rent. Only rents below the median add to the risk score."
        )
    else:
        finding = (
            f"Rent is within a plausible range of the median ({inr(round(median_rent))}) of "
            f"{len(found)} pages that quote a rent."
        )
    if bhk is None:
        finding += " No home size was given, so this compares across all sizes and counts for less."
    return SignalResult(score=score, max=max_score, finding=finding, sources=_sources(found))
