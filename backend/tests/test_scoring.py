from app.services import scoring


def test_band_for_score_boundaries() -> None:
    assert scoring.band_for_score(0) == "Low"
    assert scoring.band_for_score(24) == "Low"
    assert scoring.band_for_score(25) == "Moderate"
    assert scoring.band_for_score(49) == "Moderate"
    assert scoring.band_for_score(50) == "High"
    assert scoring.band_for_score(74) == "High"
    assert scoring.band_for_score(75) == "Severe"
    assert scoring.band_for_score(100) == "Severe"


def test_image_reuse_score_caps_at_max() -> None:
    assert scoring.image_reuse_score(0) == 0
    assert scoring.image_reuse_score(1) == 10
    assert scoring.image_reuse_score(10) == scoring.IMAGE_REUSE_MAX


def test_price_deviation_score_within_tolerance_is_zero() -> None:
    assert scoring.price_deviation_score(submitted_rent=9000, median_rent=10000) == 0


def test_price_deviation_score_scales_below_tolerance() -> None:
    score = scoring.price_deviation_score(submitted_rent=5000, median_rent=10000)
    assert 0 < score <= scoring.PRICE_DEVIATION_MAX


def test_price_deviation_score_floors_at_max() -> None:
    score = scoring.price_deviation_score(submitted_rent=1000, median_rent=10000)
    assert score == scoring.PRICE_DEVIATION_MAX


def test_price_deviation_score_zero_median_is_safe() -> None:
    assert scoring.price_deviation_score(submitted_rent=9000, median_rent=0) == 0
