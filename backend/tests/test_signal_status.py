from datetime import datetime, timezone

import httpx

from app.models.schemas import ScanResponse, ScanSignals, SignalResult
from app.services import evidence


def _lens(title: str, price: int | None = None, source: str = "OLX") -> list[dict]:
    match = {"title": title, "link": "https://www.olx.in/item/x", "source": source}
    if price is not None:
        match["price"] = {"extracted_value": price}
    return [{"exact_matches": [match]}]


# --- a failed check must not read as a clean one -------------------------------


def test_every_lens_call_failing_is_unavailable_not_clean() -> None:
    signal, matches = evidence.extract_image_reuse(
        [httpx.TimeoutException("t")] * 3, submitted_price=15000, submitted_city="Bengaluru"
    )
    assert signal.status == "unavailable"
    assert signal.score == 0
    assert matches == []
    assert "weren't found" not in signal.finding


def test_some_lens_calls_failing_stays_ok_but_says_so() -> None:
    signal, _ = evidence.extract_image_reuse(
        [{"exact_matches": []}, httpx.TimeoutException("t")],
        submitted_price=15000,
        submitted_city="Bengaluru",
    )
    assert signal.status == "ok"
    assert "1 photo(s) couldn't be checked" in signal.finding


def test_address_lookup_failure_is_unavailable_and_scores_nothing() -> None:
    signal = evidence.extract_address_validity(httpx.TimeoutException("t"), "Bengaluru", city_added=False)
    assert signal.status == "unavailable"
    assert signal.score == 0


def test_price_lookup_failure_and_thin_data_are_both_unavailable() -> None:
    failed = evidence.extract_price_deviation(httpx.TimeoutException("t"), submitted_rent=9000, city="Bengaluru", bhk="2BHK")
    thin = evidence.extract_price_deviation({"organic_results": []}, submitted_rent=9000, city="Bengaluru", bhk="2BHK")
    assert failed.status == thin.status == "unavailable"
    assert failed.score == thin.score == 0


def test_a_completed_check_is_ok_even_with_a_zero_score() -> None:
    signal, _ = evidence.extract_image_reuse(
        [{"exact_matches": []}], submitted_price=15000, submitted_city="Bengaluru"
    )
    assert signal.status == "ok"
    assert signal.score == 0


# --- city matching ---------------------------------------------------------------


def test_spelling_variant_of_the_submitted_city_is_not_a_contradiction() -> None:
    signal, matches = evidence.extract_image_reuse(
        _lens("2BHK flat for rent Bangalore", price=15000),
        submitted_price=15000,
        submitted_city="Bengaluru",
    )
    assert matches == []
    assert signal.score == 0


def test_a_street_named_after_another_city_is_not_a_contradiction() -> None:
    signal, matches = evidence.extract_image_reuse(
        _lens("1BHK on Mysore Road, Bengaluru", price=15000),
        submitted_price=15000,
        submitted_city="Bengaluru",
    )
    assert matches == []
    assert signal.score == 0


def test_a_genuinely_different_city_is_still_flagged() -> None:
    _, matches = evidence.extract_image_reuse(
        _lens("2BHK flat for rent in Pune", price=15000),
        submitted_price=15000,
        submitted_city="Bengaluru",
    )
    assert len(matches) == 1
    assert matches[0].listed_city == "Pune"


def test_finding_counts_photos_not_matches() -> None:
    two_matches_one_photo = [
        {
            "exact_matches": [
                {"title": "Flat in Pune", "link": "https://www.olx.in/item/1", "source": "OLX"},
                {"title": "Flat in Mumbai", "link": "https://www.olx.in/item/2", "source": "OLX"},
            ]
        },
        {"exact_matches": []},
    ]
    signal, matches = evidence.extract_image_reuse(
        two_matches_one_photo, submitted_price=15000, submitted_city="Bengaluru"
    )
    assert len(matches) == 2
    assert signal.finding.startswith("1 of 2 photos")


# --- the response says when it's partial -----------------------------------------


def _response(**statuses: str) -> ScanResponse:
    def signal(name: str) -> SignalResult:
        return SignalResult(score=0, max=10, finding="x", status=statuses.get(name, "ok"))

    return ScanResponse(
        scan_id="abc",
        risk_score=0,
        risk_band="Low",
        signals=ScanSignals(
            image_reuse=signal("image_reuse"),
            price_deviation=signal("price_deviation"),
            address_validity=signal("address_validity"),
        ),
        evidence=[],
        created_at=datetime.now(timezone.utc),
    )


def test_response_is_partial_only_when_a_check_was_unavailable() -> None:
    assert _response().partial is False
    assert _response(price_deviation="unavailable").partial is True
    assert _response(price_deviation="unavailable").model_dump()["partial"] is True


def test_scans_stored_before_status_existed_parse_as_ok() -> None:
    legacy = {"score": 8, "max": 30, "finding": "Address resolves."}
    assert SignalResult.model_validate(legacy).status == "ok"
