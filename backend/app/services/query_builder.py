"""Builds the search queries from fixed templates.

Deterministic on purpose: the LLM reviewer only fills in *fields*; it never
writes a search string, so the same input always produces the same query.
"""


def price_query(bhk: str | None, locality: str | None, city: str) -> str:
    # "price" biases the organic engine toward snippets that actually quote a
    # rupee figure — confirmed against live data. A locality narrows the
    # comparables to the place being rented, not the whole city.
    return " ".join(filter(None, [bhk, "rent", locality, city, "price"]))
