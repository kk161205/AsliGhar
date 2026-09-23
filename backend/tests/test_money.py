from app.services.money import inr


def test_small_amounts_have_no_separators() -> None:
    assert inr(0) == "₹0"
    assert inr(500) == "₹500"


def test_thousands_group_in_pairs() -> None:
    assert inr(1500) == "₹1,500"
    assert inr(12345) == "₹12,345"
    assert inr(1234567) == "₹12,34,567"


def test_a_negative_amount_keeps_the_sign_before_the_symbol() -> None:
    assert inr(-500) == "-₹500"
    assert inr(-1234567) == "-₹12,34,567"
