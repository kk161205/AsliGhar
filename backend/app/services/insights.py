"""Context that doesn't change the score: what a pasted listing link says, where a phone number
appears, and whether the address's pincode matches Maps.

Every insight is tied to a page or place we can link to, and carries a tier:
"proven" when it is the linked page's own words, "indicator" when it is an
inference (for instance that a search result mentions the number).
"""

import re

from app.models.schemas import Insight
from app.services import evidence
from app.services.money import inr

PHONE_PATTERN = re.compile(r"^[6-9]\d{9}$")
_COUNTRY_PREFIX = re.compile(r"^(?:\+?91|0)(?=\d{10}$)")
MAX_PHONE_INSIGHTS = 3
MAX_QUOTE_CHARS = 160
_FRAUD_WORDS = re.compile(r"\b(scam|scammer|fraud|fraudster|cheat|cheated|cheating|beware|fake)\b", re.IGNORECASE)
_PINCODE = re.compile(r"\b\d{6}\b")


def normalize_phone(text: str) -> str | None:
    """A 10-digit Indian mobile number from what the user typed, or None."""
    digits = re.sub(r"[\s\-().]", "", text or "")
    digits = _COUNTRY_PREFIX.sub("", digits)
    return digits if PHONE_PATTERN.match(digits) else None


def _quote(text: str) -> str:
    return " ".join(text.split())[:MAX_QUOTE_CHARS]


def _without_number(text: str, phone: str) -> str:
    """The text with the phone number (however it is spaced or prefixed) replaced by a placeholder."""
    digits = r"[\s\-().]*".join(phone)
    return re.sub(rf"(?:\+?91[\s\-]*|0)?{digits}", "[this number]", text)


def listing_link_insights(
    url: str, page: evidence.PageDetails | None, submitted_rent: int, city: str
) -> list[Insight]:
    """What the page the user pasted says, compared with what they typed."""
    if page is None:
        return [
            Insight(
                kind="listing_link",
                tier="indicator",
                title="Couldn't read the listing link",
                detail="Google has no entry for this page, so nothing was checked from it.",
                url=url,
            )
        ]

    found: list[tuple[str, str]] = []
    kind = evidence.listing_type(page.title, url)
    if kind == "sale":
        shown = f" It shows {inr(page.price)}." if page.price else ""
        found.append(("This link is a sale listing", f"You entered a rent, but the page is for sale.{shown}"))
    elif (
        page.price is not None
        and kind == "rent"
        and abs(page.price - submitted_rent) / submitted_rent * 100 > evidence.PRICE_MISMATCH_TOLERANCE_PCT
    ):
        found.append(("The link shows a different rent", f"The page shows {inr(page.price)}, but you entered {inr(submitted_rent)}."))
    linked_city = evidence.other_city(evidence.page_text(page.title, url), city)
    if linked_city:
        found.append(("The link is for another city", f"The page's title or address places it in {linked_city}, but you entered {city}."))

    insights = [
        Insight(kind="listing_link", tier="proven", title=title, detail=detail, url=url)
        for title, detail in found
    ]
    if not insights and page.snippet:
        insights.append(
            Insight(
                kind="listing_link",
                tier="proven",
                title="What the listing link says",
                detail=f"Nothing on the page contradicts what you entered. It reads: “{_quote(page.snippet)}”.",
                url=url,
            )
        )
    return insights


def phone_insights(organic_results: list[dict], phone: str, city: str) -> list[Insight]:
    """Pages that mention this number as a listing in another city or in connection with fraud.

    A page counts only if the number itself appears in its title or snippet;
    a search engine can return near-matches that mention nothing of the sort.
    """
    number = re.compile(rf"(?<!\d)(?:\+?91|0)?{phone}(?!\d)")
    found: list[Insight] = []
    for item in organic_results:
        title, snippet, link = item.get("title", ""), item.get("snippet", ""), item.get("link", "")
        if not number.search(re.sub(r"[\s\-().]", "", f"{title} {snippet}")):
            continue
        text = f"{title} {snippet}"
        if _FRAUD_WORDS.search(text):
            found.append(
                Insight(
                    kind="phone",
                    tier="indicator",
                    title="This number appears on a page about fraud",
                    detail=(
                        f"A page mentioning the number reads: “{_quote(_without_number(snippet or title, phone))}”. "
                        "A mention is not proof the number is involved, so read the page."
                    ),
                    url=link,
                )
            )
        elif evidence.looks_like_listing_page(title, link):
            other_city = evidence.other_city(evidence.page_text(title, link), city)
            if other_city:
                found.append(
                    Insight(
                        kind="phone",
                        tier="indicator",
                        title=f"This number is on a listing in {other_city}",
                        detail=f"A listing page for {other_city} carries this number: “{_quote(_without_number(title, phone))}”. You entered {city}.",
                        url=link,
                    )
                )
        if len(found) == MAX_PHONE_INSIGHTS:
            break
    if not found:
        return [
            Insight(
                kind="phone",
                tier="indicator",
                title="Nothing found for this number",
                detail="A search for the number found no fraud reports or listings in other cities.",
            )
        ]
    return found


def pincode_insight(place: dict | None, stated_pincode: str | None) -> list[Insight]:
    """A mismatch between the pincode in the address and the one Maps gives that place."""
    if place is None or not stated_pincode:
        return []
    maps_pincodes = set(_PINCODE.findall(place.get("address") or ""))
    if not maps_pincodes or stated_pincode in maps_pincodes:
        return []
    return [
        Insight(
            kind="address",
            tier="indicator",
            title="Pincode doesn't match Google Maps",
            detail=(
                f'Google Maps places "{place.get("title", "this address")}" in pincode '
                f"{', '.join(sorted(maps_pincodes))}, but the address says {stated_pincode}."
            ),
            url=evidence.maps_link(place),
        )
    ]
