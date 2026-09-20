import pytest

from app.services import input_gate, money


@pytest.mark.parametrize("rent", [499, 0, -5, 5_000_001, 99_999_999])
def test_impossible_rents_are_rejected_outright(rent: int) -> None:
    result = input_gate.evaluate(rent)
    assert result.status == "rejected"
    assert result.issues[0].code == "rent_impossible"


@pytest.mark.parametrize("rent", [500, 1_999])
def test_unusually_low_rents_need_confirmation(rent: int) -> None:
    result = input_gate.evaluate(rent)
    assert result.status == "needs_confirmation"
    assert result.issues[0].code == "rent_unusually_low"


@pytest.mark.parametrize("rent", [500_001, 5_000_000])
def test_unusually_high_rents_need_confirmation(rent: int) -> None:
    result = input_gate.evaluate(rent)
    assert result.status == "needs_confirmation"
    assert result.issues[0].code == "rent_unusually_high"


@pytest.mark.parametrize("rent", [2_000, 4_000, 15_000, 27_000, 500_000])
def test_ordinary_rents_pass_including_ones_far_below_market(rent: int) -> None:
    # A rent well under the local median is the fraud signal itself and must
    # never be blocked here — only absolute implausibility is.
    assert input_gate.evaluate(rent).status == "ok"


def test_amounts_are_shown_with_indian_digit_grouping() -> None:
    assert money.inr(999) == "₹999"
    assert money.inr(15000) == "₹15,000"
    assert money.inr(500000) == "₹5,00,000"
    assert money.inr(5000000) == "₹50,00,000"
    assert money.inr(12345678) == "₹1,23,45,678"


def test_the_typical_range_matches_the_price_extractors_own_bounds() -> None:
    from app.services import evidence

    assert input_gate.TYPICAL_MIN_RENT == evidence.MIN_MONTHLY_RENT
    assert input_gate.TYPICAL_MAX_RENT == evidence.MAX_MONTHLY_RENT
