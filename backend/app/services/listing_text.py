"""Flags scam-typical phrasing in a listing description, quoting the exact words.

Pattern-based on purpose: every flag carries the sentence fragment that
triggered it, so nothing here can be invented, and text pasted into the
description can't steer it. Each flag is an indicator — phrasing that is common
in rental scams and worth a second look, never proof on its own.
"""

import re
from typing import NamedTuple

from app.models.schemas import Insight

MAX_FLAGS = 4
MAX_QUOTE_CHARS = 120
_MILITARY = r"(?:army|crpf|cisf|bsf|itbp|ssb|air ?force|navy)"


class _Rule(NamedTuple):
    title: str
    why: str
    pattern: re.Pattern


def _rule(title: str, why: str, pattern: str) -> _Rule:
    return _Rule(title, why, re.compile(pattern, re.IGNORECASE))


_RULES = (
    _rule(
        "Asks for money before you see the home",
        "Genuine landlords rarely take payment before a visit.",
        r"(?:advance|token|booking|deposit|payment|amount|money)\b[^.\n]{0,50}\bbefore\b[^.\n]{0,25}"
        r"\b(?:visit|visiting|seeing|viewing|inspect\w*)|without\s+(?:a\s+)?(?:visit|visiting|seeing|viewing)",
    ),
    _rule(
        "Keys to be sent rather than handed over",
        "A landlord who cannot meet you or show the home is a common scam pattern.",
        r"\bkeys?\b[^.\n]{0,40}\b(?:courier|posted|mailed|shipped|sent by)\b",
    ),
    _rule(
        "Owner unavailable to meet",
        "Used to explain why you cannot visit. Some owners really are away, so confirm with a video call.",
        r"\b(?:out of (?:station|town|country|india)|abroad|overseas|outside india|nri)\b",
    ),
    _rule(
        "Claims a defence posting",
        "A defence or government posting is a common pretext in rental scams; it can also be true, so verify it separately.",
        rf"\b{_MILITARY}\s+(?:officer|personnel|jawan|man|posting|transfer(?:red)?)\b"
        rf"|\b(?:transferred|posted|posting)\b[^.\n]{{0,40}}\b{_MILITARY}\b"
        rf"|\b{_MILITARY}\b[^.\n]{{0,40}}\b(?:transferred|posted)\b",
    ),
    _rule(
        "Wants to avoid phone calls",
        "Scammers often keep contact to messages so they can't be questioned live.",
        r"\bwhats\s?app\s+only\b|\bonly\s+(?:on\s+)?whats\s?app\b|\bno\s+calls?\b|\bmessage\s+only\b",
    ),
    _rule(
        "Pressure to act quickly",
        "Urgency discourages the checks a renter should make.",
        r"\b(?:urgent(?:ly)?|hurry|last\s+(?:unit|flat|one)|limited\s+time|today\s+only|first\s+come\s+first\s+served)\b",
    ),
    _rule(
        "Unusual payment method",
        "Rent and deposits are not normally paid by gift card, crypto or wire transfer.",
        r"\b(?:gift\s?card|crypto\w*|bitcoin|western\s+union|wire\s+transfer)\b",
    ),
)


def red_flags(description: str | None) -> list[Insight]:
    """Indicator insights for scam-typical phrases in the description, each quoting it."""
    if not description:
        return []
    insights: list[Insight] = []
    for rule in _RULES:
        match = rule.pattern.search(description)
        if match is None:
            continue
        quote = " ".join(match.group(0).split())[:MAX_QUOTE_CHARS]
        insights.append(
            Insight(
                kind="description",
                tier="indicator",
                title=rule.title,
                detail=f"The description says “{quote}”. {rule.why} Not proof on its own.",
            )
        )
        if len(insights) == MAX_FLAGS:
            break
    return insights
