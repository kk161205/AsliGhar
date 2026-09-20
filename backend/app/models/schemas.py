from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, computed_field

RiskBand = Literal["Low", "Moderate", "High", "Severe"]
# "unavailable" means the check couldn't run (a search failed, or too little
# data to judge) — distinct from "ok with a score of 0", which means it ran
# and found nothing worrying. Stored scans from before this field existed
# parse as "ok".
SignalStatus = Literal["ok", "unavailable"]


class SignalSource(BaseModel):
    """One concrete thing a signal's finding rests on, with a link where there is one."""

    title: str
    url: Optional[str] = None
    detail: str


class SignalResult(BaseModel):
    score: int
    max: int
    finding: str
    status: SignalStatus = "ok"
    sources: list[SignalSource] = []


class ScanSignals(BaseModel):
    image_reuse: SignalResult
    price_deviation: SignalResult
    address_validity: SignalResult


class ImageMatchEvidence(BaseModel):
    type: Literal["image_match"] = "image_match"
    photo_index: int
    source_domain: str
    source_url: str
    source_title: str
    listed_price: Optional[int] = None
    submitted_price: int
    listed_city: Optional[str] = None
    submitted_city: str
    # Why this exact copy of the photo contradicts the submitted listing —
    # each reason is read straight from the page's own title, URL or price.
    reasons: list[str] = []
    listing_type: Optional[Literal["sale", "rent"]] = None
    # The page's own description as Google shows it (title, size, price), so the
    # listing can be judged without opening it.
    source_snippet: Optional[str] = None


class UnderstoodInput(BaseModel):
    """What the input reviewer (and the BHK pattern) read out of the submission."""

    address_city: Optional[str] = None
    locality: Optional[str] = None
    landmark: Optional[str] = None
    pincode: Optional[str] = None
    bhk: Optional[str] = None


class TraceQuery(BaseModel):
    check: Literal["address", "price"]
    query: str


class SearchTrace(BaseModel):
    """How a scan searched, kept so a result can be explained afterwards."""

    reviewer_used: bool
    understood: UnderstoodInput
    queries: list[TraceQuery]


class PrecheckRequest(BaseModel):
    rent: int


class ScanResponse(BaseModel):
    scan_id: str
    risk_score: int = Field(ge=0, le=100)
    risk_band: RiskBand
    signals: ScanSignals
    evidence: list[ImageMatchEvidence]
    ai_summary: Optional[str] = None
    created_at: datetime
    # The user's stated reason for an unusual rent. Shown alongside the result,
    # never an input to the score or the summary.
    override_reason: Optional[str] = None
    search_trace: Optional[SearchTrace] = None

    @computed_field  # derived, so it's right for stored scans too, not just new ones
    @property
    def partial(self) -> bool:
        checks = (self.signals.image_reuse, self.signals.price_deviation, self.signals.address_validity)
        return any(check.status == "unavailable" for check in checks)


class ScanSummary(BaseModel):
    scan_id: str
    address: str
    city: str
    risk_score: int = Field(ge=0, le=100)
    risk_band: RiskBand
    created_at: datetime
