IMAGE_REUSE_MAX = 40
IMAGE_REUSE_PER_MATCH = 10

PRICE_DEVIATION_MAX = 30
# Without a home size the comparison mixes 1BHKs with 4BHKs, so the price check
# is a weaker signal and counts for two-thirds as much.
PRICE_DEVIATION_UNKNOWN_BHK_MAX = 20
PRICE_DEVIATION_TOLERANCE_PCT = 15
PRICE_DEVIATION_FLOOR_PCT = 50

ADDRESS_VALID_SCORE = 0
ADDRESS_NO_CATEGORY_DATA_SCORE = 8
ADDRESS_AMBIGUOUS_SCORE = 15
ADDRESS_INVALID_SCORE = 30
ADDRESS_VALIDITY_MAX = 30

RISK_BANDS: tuple[tuple[int, str], ...] = (
    (24, "Low"),
    (49, "Moderate"),
    (74, "High"),
    (100, "Severe"),
)


def band_for_score(score: int) -> str:
    for ceiling, band in RISK_BANDS:
        if score <= ceiling:
            return band
    return "Severe"


def image_reuse_score(contradicting_match_count: int) -> int:
    return min(contradicting_match_count * IMAGE_REUSE_PER_MATCH, IMAGE_REUSE_MAX)


def price_deviation_max(bhk_known: bool) -> int:
    return PRICE_DEVIATION_MAX if bhk_known else PRICE_DEVIATION_UNKNOWN_BHK_MAX


def price_deviation_score(
    submitted_rent: int, median_rent: float, max_score: int = PRICE_DEVIATION_MAX
) -> int:
    if median_rent <= 0:
        return 0
    deviation_pct = max(0.0, (median_rent - submitted_rent) / median_rent * 100)
    if deviation_pct <= PRICE_DEVIATION_TOLERANCE_PCT:
        return 0
    scaled = (deviation_pct - PRICE_DEVIATION_TOLERANCE_PCT) / (
        PRICE_DEVIATION_FLOOR_PCT - PRICE_DEVIATION_TOLERANCE_PCT
    )
    return round(min(max(scaled, 0.0), 1.0) * max_score)
