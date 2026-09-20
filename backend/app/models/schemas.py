from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

RiskBand = Literal["Low", "Moderate", "High", "Severe"]


class SignalResult(BaseModel):
    score: int
    max: int
    finding: str


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


class ScanSummary(BaseModel):
    scan_id: str
    address: str
    city: str
    risk_score: int = Field(ge=0, le=100)
    risk_band: RiskBand
    created_at: datetime
