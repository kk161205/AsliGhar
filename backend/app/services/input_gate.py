"""Refuses impossible inputs before any paid search is spent.

Only *absolute* implausibility is checked here (typos, wrong units): a rent far
below the local median is the core fraud signal, not an input error, so it is
never blocked. Odd or unresolvable addresses aren't blocked either — that is
what the address check scores.
"""

from typing import Literal

from pydantic import BaseModel

from app.services.evidence import MAX_MONTHLY_RENT, MIN_MONTHLY_RENT

# Outside these no real monthly rent exists — refuse outright, no override.
HARD_MIN_RENT = 500
HARD_MAX_RENT = 5_000_000
# Outside the price extractor's own sanity range (still possible: a single room
# in a family home, a luxury penthouse) — allowed only with a stated reason.
TYPICAL_MIN_RENT = MIN_MONTHLY_RENT
TYPICAL_MAX_RENT = MAX_MONTHLY_RENT
MIN_OVERRIDE_REASON_CHARS = 10
MAX_OVERRIDE_REASON_CHARS = 300


class GateIssue(BaseModel):
    code: Literal["rent_impossible", "rent_unusually_low", "rent_unusually_high"]
    field: Literal["rent"]
    message: str


class GateResult(BaseModel):
    status: Literal["ok", "needs_confirmation", "rejected"]
    issues: list[GateIssue] = []


def _inr(amount: int) -> str:
    # Indian digit grouping: 12,34,567 (last three digits, then pairs).
    digits = str(amount)
    if len(digits) <= 3:
        return f"₹{digits}"
    head, tail = digits[:-3], digits[-3:]
    pairs = []
    while len(head) > 2:
        pairs.insert(0, head[-2:])
        head = head[:-2]
    pairs.insert(0, head)
    return "₹" + ",".join([*pairs, tail])


def evaluate(rent: int) -> GateResult:
    if rent < HARD_MIN_RENT or rent > HARD_MAX_RENT:
        return GateResult(
            status="rejected",
            issues=[
                GateIssue(
                    code="rent_impossible",
                    field="rent",
                    message=(
                        f"{_inr(rent)} a month isn't a possible rent. "
                        f"Enter the monthly rent between {_inr(HARD_MIN_RENT)} and {_inr(HARD_MAX_RENT)}."
                    ),
                )
            ],
        )
    if rent < TYPICAL_MIN_RENT:
        return GateResult(
            status="needs_confirmation",
            issues=[
                GateIssue(
                    code="rent_unusually_low",
                    field="rent",
                    message=f"{_inr(rent)} a month is unusually low for a rental.",
                )
            ],
        )
    if rent > TYPICAL_MAX_RENT:
        return GateResult(
            status="needs_confirmation",
            issues=[
                GateIssue(
                    code="rent_unusually_high",
                    field="rent",
                    message=f"{_inr(rent)} a month is unusually high for a rental.",
                )
            ],
        )
    return GateResult(status="ok")
