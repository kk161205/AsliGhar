from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, computed_field

RiskBand = Literal["Low", "Moderate", "High", "Severe"]
# "unavailable" means the check couldn't run (a search failed, or too little
# data to judge) — distinct from "ok with a score of 0", which means it ran
# and found nothing worrying. Stored scans from before this field existed
# parse as "ok".
SignalStatus = Literal["ok", "unavailable"]


class SignalResult(BaseModel):
    score: int
    max: int
    finding: str
    status: SignalStatus = "ok"


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


class ScanResponse(BaseModel):
    scan_id: str
    risk_score: int = Field(ge=0, le=100)
    risk_band: RiskBand
    signals: ScanSignals
    evidence: list[ImageMatchEvidence]
    ai_summary: Optional[str] = None
    created_at: datetime

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
