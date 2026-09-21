import pytest

from app.services import evidence, insights

SALE_LINK = "https://www.olx.in/en-in/item/for-sale-houses-apartments-3-bhk-house-in-agra-iid-1"


@pytest.mark.parametrize(
    "typed, expected",
    [
        ("9876543210", "9876543210"),
        ("+91 98765 43210", "9876543210"),
        ("098765-43210", "9876543210"),
        ("(91) 98765 43210", "9876543210"),
        ("1234567890", None),
        ("98765", None),
        ("98765432101", None),
        ("", None),
    ],
)
def test_normalize_phone(typed: str, expected: str | None) -> None:
    assert insights.normalize_phone(typed) == expected


# --- a pasted listing link ------------------------------------------------------------


def _page(
    title: str = "3BHK house for sale in Agra", price: int | None = 3_199_000, snippet: str = "3 BHK. ₹ 31,99,000."
) -> evidence.PageDetails:
    return evidence.PageDetails(price=price, snippet=snippet, title=title)


def test_a_link_that_is_a_sale_listing_is_reported_as_proven() -> None:
    found = insights.listing_link_insights(SALE_LINK, _page(), submitted_rent=15_000, city="Agra")

    assert [i.title for i in found] == ["This link is a sale listing"]
    assert found[0].tier == "proven"
    assert "₹31,99,000" in found[0].detail
    assert found[0].url == SALE_LINK


def test_a_link_showing_a_different_rent_is_reported_with_both_figures() -> None:
    link = "https://www.olx.in/item/for-rent-houses-apartments-2-bhk-in-agra-iid-2"
    found = insights.listing_link_insights(link, _page("2BHK flat for rent in Agra", 9_500, "₹ 9,500."), 15_000, "Agra")

    assert found[0].title == "The link shows a different rent"
    assert "₹9,500" in found[0].detail and "₹15,000" in found[0].detail


def test_a_link_for_another_city_is_reported() -> None:
    link = "https://www.olx.in/item/for-rent-houses-apartments-2-bhk-in-lucknow-iid-3"
    found = insights.listing_link_insights(link, _page("2BHK flat for rent in Lucknow", 15_000, ""), 15_000, "Agra")
    assert "The link is for another city" in [i.title for i in found]


def test_a_link_that_agrees_with_the_input_shows_what_the_page_says() -> None:
    link = "https://www.olx.in/item/for-rent-houses-apartments-2-bhk-in-agra-iid-4"
    found = insights.listing_link_insights(
        link, _page("2BHK flat for rent in Agra", 15_000, "2 BHK flat. ₹ 15,000."), 15_000, "Agra"
    )

    assert [i.title for i in found] == ["What the listing link says"]
    assert "2 BHK flat. ₹ 15,000." in found[0].detail


def test_an_unreadable_link_says_so_and_is_only_an_indicator() -> None:
    found = insights.listing_link_insights(SALE_LINK, None, 15_000, "Agra")
    assert found[0].title == "Couldn't read the listing link"
    assert found[0].tier == "indicator"


# --- a phone number -----------------------------------------------------------------------

PHONE = "9876543210"


def test_a_page_about_fraud_that_carries_the_number_is_an_indicator_with_its_link() -> None:
    results = [
        {
            "title": "Beware of rental scam",
            "snippet": "Caller +91 98765 43210 took a token amount and vanished.",
            "link": "https://forum.example/scam-1",
        }
    ]
    found = insights.phone_insights(results, PHONE, "Agra")

    assert found[0].title == "This number appears on a page about fraud"
    assert found[0].tier == "indicator"
    assert found[0].url == "https://forum.example/scam-1"
    assert PHONE not in found[0].detail
    assert "98765" not in found[0].detail  # however the page spaced the number
    assert "[this number] took a token" in found[0].detail
    assert "not proof" in found[0].detail


def test_a_listing_in_another_city_with_the_number_is_reported() -> None:
    results = [
        {
            "title": "2BHK Flat for Rent in Pune",
            "snippet": "Contact 9876543210 for visit.",
            "link": "https://www.somenewportal.com/property/2bhk-rent-pune-9912345",
        }
    ]
    found = insights.phone_insights(results, PHONE, "Agra")
    assert found[0].title == "This number is on a listing in Pune"


def test_a_result_that_does_not_contain_the_number_is_ignored() -> None:
    # A search engine can return near-matches; only pages that carry the number count.
    results = [{"title": "Rental scam warning", "snippet": "Call 9876543211 to pay the token.", "link": "https://forum.example/x"}]
    found = insights.phone_insights(results, PHONE, "Agra")
    assert [i.title for i in found] == ["Nothing found for this number"]


def test_a_listing_in_the_same_city_is_not_reported() -> None:
    results = [
        {
            "title": "2BHK Flat for Rent in Agra",
            "snippet": "Contact 9876543210.",
            "link": "https://www.somenewportal.com/property/2bhk-rent-agra-9912345",
        }
    ]
    assert [i.title for i in insights.phone_insights(results, PHONE, "Agra")] == ["Nothing found for this number"]


def test_phone_insights_are_capped() -> None:
    results = [
        {"title": "Scam alert", "snippet": f"Number {PHONE} is a scam #{n}", "link": f"https://forum.example/{n}"}
        for n in range(10)
    ]
    assert len(insights.phone_insights(results, PHONE, "Agra")) == insights.MAX_PHONE_INSIGHTS


# --- pincode ------------------------------------------------------------------------------


def test_a_pincode_that_differs_from_maps_is_reported_with_a_maps_link() -> None:
    place = {"title": "4, 12th Main Rd", "address": "HAL 2nd Stage, Bengaluru, Karnataka 560008, India", "place_id": "abc"}
    found = insights.pincode_insight(place, "560038")

    assert "560008" in found[0].detail and "560038" in found[0].detail
    assert found[0].url.endswith("place_id:abc")


def test_a_matching_missing_or_unstated_pincode_says_nothing() -> None:
    place = {"title": "x", "address": "Bengaluru, Karnataka 560008, India"}
    assert insights.pincode_insight(place, "560008") == []
    assert insights.pincode_insight({"title": "x", "address": "Bengaluru, India"}, "560008") == []
    assert insights.pincode_insight(place, None) == []
    assert insights.pincode_insight(None, "560008") == []
