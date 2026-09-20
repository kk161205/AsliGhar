"""Reads a home size ("2BHK", "1RK", "Studio") out of free text by pattern.

Pattern-only on purpose: text either states a size or it doesn't, and nothing
here can invent one.
"""

import re

_PATTERNS = (
    (re.compile(r"(?<!\d)(\d)\s*-?\s*bhk", re.IGNORECASE), lambda m: f"{m.group(1)}BHK"),
    (re.compile(r"(?<!\d)(\d)\s*-?\s*bed\s?rooms?", re.IGNORECASE), lambda m: f"{m.group(1)}BHK"),
    (re.compile(r"\b1\s*-?\s*rk\b", re.IGNORECASE), lambda m: "1RK"),
    (re.compile(r"\bstudio\b", re.IGNORECASE), lambda m: "Studio"),
)


def mentioned(text: str) -> set[str]:
    """Every home size the text states."""
    found: set[str] = set()
    for pattern, render in _PATTERNS:
        found.update(render(match) for match in pattern.finditer(text or ""))
    return found


def extract_bhk(text: str) -> str | None:
    """The first home size (in pattern order) the text states, or None."""
    for pattern, render in _PATTERNS:
        match = pattern.search(text or "")
        if match:
            return render(match)
    return None
