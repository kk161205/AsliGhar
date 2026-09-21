from datetime import date

import pytest

from app.services import evidence, insights, listing_text, scoring

OLX_SALE = "https://www.olx.in/en-in/item/for-sale-houses-apartments-3-bhk-house-in-agra-iid-1855312754"
UNKNOWN_SITE_LISTING = "https://www.somenewportal.com/property/3bhk-house-for-sale-pune-8801234"


def _match(title: str, link: str, **extra) -> dict:
    return {"title": title, "link": link, "source": "Some Site", **extra}


def _photos(*per_photo: list[dict]) -> list[dict]:
    return [{"exact_matches": matches} for matches in per_photo]


def _reuse(lens_results, city="Bengaluru", **kwargs):
    return evidence.extract_image_reuse(lens_results, submitted_price=15_000, submitted_city=city, **kwargs)


# --- the same house recognised by more than one identifier ---------------------------------


def test_two_of_your_photos_on_one_page_confirm_it_as_the_same_house_on_any_site() -> None:
    page = _match("3BHK House for Sale in Pune", UNKNOWN_SITE_LISTING)
    signal, matches = _reuse(_photos([page], [page]))

    assert len(matches) == 1
    assert matches[0].photo_indexes == [0, 1]
    assert matches[0].matched_by == ["photo 1", "photo 2"]
    assert matches[0].tier == "proven"
    assert signal.basis == "proven"


def test_one_photo_on_an_unknown_site_stays_an_indicator() -> None:
    signal, matches = _reuse(_photos([_match("3BHK House for Sale in Pune", UNKNOWN_SITE_LISTING)]))

    assert matches[0].tier == "indicator"
    assert matches[0].matched_by == ["photo 1"]
    assert signal.score == scoring.IMAGE_REUSE_INDICATOR_PER_PHOTO


def test_a_photo_plus_the_phone_or_the_wording_on_the_same_page_confirms_it() -> None:
    lens = _photos([_match("3BHK House for Sale in Pune", UNKNOWN_SITE_LISTING)])
    key = evidence.page_key(UNKNOWN_SITE_LISTING)

    _, matches = _reuse(lens, also_identified={key: ["phone number"]})

    assert matches[0].tier == "proven"
    assert matches[0].matched_by == ["photo 1", "phone number"]


def test_a_page_hit_by_two_photos_is_one_contradicted_page_but_two_photos_score() -> None:
    page = _match("3BHK House for Sale in Pune", UNKNOWN_SITE_LISTING)
    signal, _ = _reuse(_photos([page], [page], []))
    assert signal.score == scoring.image_reuse_score(2)


def test_the_listing_the_user_pasted_is_not_reported_against_itself() -> None:
    lens = _photos([_match("3BHK House for Sale in Agra", OLX_SALE)])
    signal, matches = _reuse(lens, city="Agra", own_listing_url=OLX_SALE)

    assert matches == []
    assert signal.score == 0


def test_a_geo_code_in_a_category_url_is_not_a_listing_id() -> None:
    # Real OLX category URLs carry "_g5318137"; a partial-run match on it once made them look like listings.
    assert not evidence.looks_like_listing_page(
        "Buy, Sell & Rent Duplex House in Chandan Nagar", "https://www.olx.in/chandan-nagar_g5318137/properties_c3/q-duplex-house"
    )
    assert not evidence.looks_like_listing_page(
        "3BHK duplex house for sale in Agra", "https://www.olx.in/rohta_g5339499/for-sale-houses-apartments_c1725/q-agra"
    )


def test_pages_that_only_list_many_homes_are_still_not_identity_evidence() -> None:
    lens = _photos([_match("330 Flats & Apartments for Rent in Dhaulpur - OLX India", "https://www.olx.in/dhaulpur_g4059117/for-rent-houses-apartments_c1723")])
    signal, matches = _reuse(lens)
    assert matches == []
    assert signal.score == 0


# --- stock photos, recognised by exact domain ------------------------------------------------


def test_a_photo_on_a_stock_photo_site_is_reported_as_not_a_specific_home() -> None:
    lens = _photos([_match("Modern house exterior - Shutterstock", "https://www.shutterstock.com/image-photo/modern-house-1234567")])
    signal, matches = _reuse(lens)

    assert matches[0].source_domain == "shutterstock.com"
    assert matches[0].tier == "proven"
    assert matches[0].reasons == ["shutterstock.com is a stock-photo site, so this is not a photo of one particular home."]
    assert signal.score == scoring.image_reuse_score(1)


@pytest.mark.parametrize("link", ["https://notshutterstock.com/x", "https://shutterstock.com.evil.example/x", "https://example.com/shutterstock.com"])
def test_a_look_alike_host_is_not_a_stock_site(link: str) -> None:
    _, matches = _reuse(_photos([_match("A house", link)]))
    assert all(m.source_domain != "shutterstock.com" for m in matches)


# --- identifiers taken from the description ----------------------------------------------------


def test_mobile_numbers_are_read_from_the_description_in_any_common_format() -> None:
    text = "Call 98765 43210 or +91-91234-56789. Landline 0522 2345678. Also 98765 43210 again."
    assert listing_text.phones_in(text) == ["9876543210", "9123456789"]
    assert listing_text.phones_in("No number here, plot 12345") == []
    assert listing_text.phones_in(None) == []


def test_the_longest_plain_sentence_becomes_the_search_phrase() -> None:
    text = (
        "Call 9876543210. Spacious three bedroom semi furnished duplex house near the Gwalior road bypass with parking and a garden. "
        "Nice home."
    )
    assert listing_text.distinctive_phrase(text) == "Spacious three bedroom semi furnished duplex house near the Gwalior road bypass with parking"


def test_a_short_description_or_one_with_only_phone_lines_gives_no_phrase() -> None:
    assert listing_text.distinctive_phrase("2 BHK for rent. Call now.") is None
    assert listing_text.distinctive_phrase("Contact us on 98765 43210 for a visit to the flat today please") is None
    assert listing_text.distinctive_phrase(None) is None


# --- pages found through the description's wording -----------------------------------------------

PHRASE = "Spacious three bedroom semi furnished duplex house near the Gwalior road bypass"


def test_a_result_sharing_only_some_of_the_words_is_not_a_hit() -> None:
    # Real: Google's phrase search returned category pages that merely share words with the phrase.
    results = [
        {"title": "628 Furnished Flats for Sale in Saraswati Nagar", "snippet": "Spacious three bedroom semi furnished flats near the bypass. Buy now.", "link": "https://a.example/1"}
    ]
    assert insights.text_hits(results, PHRASE) == []


def test_only_results_that_show_the_wording_count_as_hits() -> None:
    results = [
        {"title": "House", "snippet": "Spacious three bedroom semi furnished duplex house near the Gwalior road bypass, Agra", "link": "https://a.example/1"},
        {"title": "Other house", "snippet": "Two bedroom flat with lift", "link": "https://a.example/2"},
    ]
    assert [h["link"] for h in insights.text_hits(results, PHRASE)] == ["https://a.example/1"]


def test_the_same_wording_on_a_listing_in_another_city_is_reported() -> None:
    hits = [{"title": "3BHK House for Rent in Pune", "snippet": PHRASE, "link": "https://www.somenewportal.com/property/3bhk-house-rent-pune-8801234"}]
    found = insights.description_reuse_insights(hits, "Agra", None)

    assert found[0].title == "This description is on a listing in Pune"
    assert found[0].tier == "indicator"


def test_the_same_wording_on_a_known_sites_sale_listing_is_proven() -> None:
    hits = [{"title": "3BHK house for sale in Agra", "snippet": PHRASE, "link": OLX_SALE}]
    found = insights.description_reuse_insights(hits, "Agra", None)

    assert found[0].title == "This description is on a sale listing"
    assert found[0].tier == "proven"


def test_wording_on_a_matching_listing_or_the_users_own_link_or_a_non_listing_is_not_reported() -> None:
    matching = {"title": "3BHK House for Rent in Agra", "snippet": PHRASE, "link": "https://www.somenewportal.com/property/3bhk-rent-agra-8801234"}
    blog = {"title": "My holiday in Pune", "snippet": PHRASE, "link": "https://blog.example/post-1"}
    own = {"title": "3BHK house for sale in Agra", "snippet": PHRASE, "link": OLX_SALE}

    assert insights.description_reuse_insights([matching, blog], "Agra", None) == []
    assert insights.description_reuse_insights([own], "Agra", OLX_SALE) == []


# --- how old the photo is ---------------------------------------------------------------------------

TODAY = date(2026, 9, 21)


def test_the_oldest_dated_page_is_reported_when_it_is_well_before_now() -> None:
    lens = _photos(
        [
            _match("Flat for rent - 2023", "https://a.example/1", date="Mar 4, 2023"),
            _match("Flat for rent - 2025", "https://a.example/2", date="Feb 10, 2025"),
            _match("Undated", "https://a.example/3"),
        ]
    )
    found = insights.photo_age_insight(lens, None, today=TODAY)

    assert found[0].title == "This photo was online long before now"
    assert "04 Mar 2023" in found[0].detail
    assert found[0].url == "https://a.example/1"
    assert found[0].tier == "indicator"


def test_a_recent_or_undated_or_own_page_gives_no_age_insight() -> None:
    recent = _photos([_match("New", "https://a.example/1", date="Sep 1, 2026")])
    undated = _photos([_match("Old", "https://a.example/2")])
    unparseable = _photos([_match("Old", "https://a.example/3", date="3 days ago")])
    own = _photos([_match("Own", OLX_SALE, date="Jan 1, 2020")])

    assert insights.photo_age_insight(recent, None, today=TODAY) == []
    assert insights.photo_age_insight(undated, None, today=TODAY) == []
    assert insights.photo_age_insight(unparseable, None, today=TODAY) == []
    assert insights.photo_age_insight(own, OLX_SALE, today=TODAY) == []
    assert insights.photo_age_insight([TimeoutError("x")], None, today=TODAY) == []
