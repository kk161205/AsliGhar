"""Canonical Indian city names and the aliases people actually write.

A hardcoded list, not a geocoder, so coverage is inherently partial — but it
must at least agree with itself: "Bangalore" and "Bengaluru" are one city, and
"Mysore Road" is a street, not a claim about Mysuru.
"""

import re

_CANONICAL_TO_ALIASES: dict[str, tuple[str, ...]] = {
    "mumbai": ("bombay",),
    "navi mumbai": (),
    "thane": (),
    "delhi": ("new delhi",),
    "bengaluru": ("bangalore", "bengalooru", "blr"),
    "hyderabad": (),
    "chennai": ("madras",),
    "kolkata": ("calcutta",),
    "pune": ("poona",),
    "ahmedabad": (),
    "jaipur": (),
    "surat": (),
    "lucknow": (),
    "kanpur": (),
    "nagpur": (),
    "indore": (),
    "bhopal": (),
    "patna": (),
    "vadodara": ("baroda",),
    "ghaziabad": (),
    "ludhiana": (),
    "agra": (),
    "nashik": ("nasik",),
    "faridabad": (),
    "meerut": (),
    "rajkot": (),
    "varanasi": ("banaras", "benares"),
    "srinagar": (),
    "amritsar": (),
    "chandigarh": (),
    "gurugram": ("gurgaon",),
    "noida": (),
    "kochi": ("cochin",),
    "coimbatore": (),
    "visakhapatnam": ("vizag", "vishakhapatnam"),
    "thiruvananthapuram": ("trivandrum",),
    "guwahati": (),
    "bhubaneswar": (),
    "dehradun": (),
    "raipur": (),
    "ranchi": (),
    "jodhpur": (),
    "madurai": (),
    "mysuru": ("mysore",),
    "nellore": (),
    "vijayawada": (),
    "aurangabad": (),
    "solapur": (),
    "hubli": ("hubballi",),
    "mangaluru": ("mangalore",),
    "tiruchirappalli": ("trichy", "tiruchirapalli"),
    "salem": (),
    "warangal": (),
    "jamshedpur": (),
    "gwalior": (),
    "jabalpur": (),
    "prayagraj": ("allahabad",),
    "howrah": (),
    "bareilly": (),
    "moradabad": (),
}

_NAME_TO_CANONICAL = {
    name: canonical
    for canonical, aliases in _CANONICAL_TO_ALIASES.items()
    for name in (canonical, *aliases)
}

# A city name followed by one of these is part of a street or institution name
# ("Mysore Road", "Delhi Public School"), not a statement about where a place is.
_NON_CITY_FOLLOWERS = (
    "road", "rd", "highway", "hwy", "street", "main", "cross", "circle",
    "junction", "gate", "public",
)

# Longest names first so "navi mumbai" / "new delhi" win over "mumbai" / "delhi".
_MENTION_PATTERN = re.compile(
    r"(?<![a-z])("
    + "|".join(re.escape(name) for name in sorted(_NAME_TO_CANONICAL, key=len, reverse=True))
    + r")(?![a-z])(?:[\s.\-]+("
    + "|".join(_NON_CITY_FOLLOWERS)
    + r")(?![a-z]))?",
    re.IGNORECASE,
)


def cities_mentioned(text: str) -> set[str]:
    found: set[str] = set()
    for match in _MENTION_PATTERN.finditer(text or ""):
        if match.group(2):
            continue
        found.add(_NAME_TO_CANONICAL[match.group(1).lower()])
    return found


def canonical_city(text: str) -> str | None:
    """Canonical name for a user-typed city field.

    A known city or alias found in the text wins ("Bengaluru, Karnataka" ->
    "bengaluru"); otherwise the trimmed lowercase text itself, so a city we
    don't list still compares equal to itself.
    """
    mentioned = cities_mentioned(text)
    if mentioned:
        return sorted(mentioned)[0]
    cleaned = (text or "").strip().lower()
    return cleaned or None


def is_city_name(text: str) -> bool:
    """True when the whole text is just a city's name (or alias)."""
    return (text or "").strip().lower() in _NAME_TO_CANONICAL


def mentions_city(text: str, city: str) -> bool:
    """Whether the text places something in the given (user-typed) city.

    Works for cities we don't list too, by looking for the typed name itself.
    """
    canonical = canonical_city(city)
    if canonical is None:
        return False
    if canonical in cities_mentioned(text):
        return True
    if canonical in _CANONICAL_TO_ALIASES:
        return False
    return re.search(rf"(?<![a-z]){re.escape(canonical)}(?![a-z])", (text or "").lower()) is not None
