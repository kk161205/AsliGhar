import httpx
import pytest

from app.services import evidence, scoring

# Fixtures mirror real response shapes captured from live SerpApi calls: Lens's
# `source` is a display name ("OLX"), never a domain, and exact matches carry
# only a title and a link.

OLX_SALE_URL = "https://www.olx.in/en-in/item/for-sale-houses-apartments-c1725-3-bhk-house-villa-800-sq-ft-in-agra-cantonment-agra-iid-1855312754"
OLX_SALE_TITLE = "3BHK semi furnished semi duplex house for sale in rohta Gwalior Road"


def _lens(*matches: dict) -> list[dict]:
    return [{"exact_matches": list(matches)}]


def _match(title: str, link: str, price: int | None = None) -> dict:
    match = {"title": title, "link": link, "source": "OLX"}
    if price is not None:
        match["price"] = {"extracted_value": price}
    return match


def _image_reuse(lens_results: list, price: int = 150_000, city: str = "Agra"):
    return evidence.extract_image_reuse(lens_results, submitted_price=price, submitted_city=city)


# --- image reuse: only provable contradictions become evidence -----------------


def test_the_same_photo_on_a_for_sale_listing_is_evidence_with_the_exact_link_and_reason() -> None:
    signal, matches = _image_reuse(_lens(_match(OLX_SALE_TITLE, OLX_SALE_URL)))

    assert len(matches) == 1
    assert matches[0].source_url == OLX_SALE_URL
    assert matches[0].source_domain == "olx.in"
    assert matches[0].listing_type == "sale"
    assert matches[0].reasons == ["It is a listing for sale, but you submitted a rental."]
    assert signal.score == scoring.image_reuse_score(1)


def test_a_sale_listing_shows_its_price_but_is_not_compared_with_the_rent() -> None:
    _, matches = _image_reuse(_lens(_match(OLX_SALE_TITLE, OLX_SALE_URL, price=3_199_000)))

    assert matches[0].reasons == ["It is a listing for sale, but you submitted a rental. It shows ₹31,99,000."]


def test_the_same_photo_on_a_matching_rental_is_not_evidence() -> None:
    signal, matches = _image_reuse(
        _lens(_match("2BHK flat for rent in Agra", "https://www.magicbricks.com/propertyDetails/2-BHK-Flat-for-Rent-in-Agra&id=4d42383635"))
    )

    assert matches == []
    assert signal.score == 0
    assert "1 other listing(s) show the same photo without contradicting it" in signal.finding


def test_a_rental_in_another_city_is_evidence_naming_that_city() -> None:
    _, matches = _image_reuse(
        _lens(_match("2BHK for rent", "https://www.olx.in/item/for-rent-houses-apartments-2-bhk-in-lucknow-gomti-nagar-iid-9"))
    )

    assert len(matches) == 1
    assert matches[0].listed_city == "Lucknow"
    assert matches[0].reasons == ["Its title or address places it in Lucknow, but you submitted Agra."]


def test_a_rental_listed_at_a_different_rent_is_evidence_with_both_figures() -> None:
    _, matches = _image_reuse(
        _lens(_match("2BHK flat for rent in Agra", "https://www.olx.in/item/for-rent-agra-1", price=9_500)),
        price=15_000,
    )

    assert matches[0].reasons == ["It shows ₹9,500 a month, but you submitted ₹15,000."]


def test_a_rent_within_tolerance_is_not_a_contradiction() -> None:
    _, matches = _image_reuse(
        _lens(_match("2BHK flat for rent in Agra", "https://www.olx.in/item/for-rent-agra-1", price=15_500)),
        price=15_000,
    )
    assert matches == []


def test_every_evidence_item_states_at_least_one_reason() -> None:
    _, matches = _image_reuse(
        _lens(
            _match(OLX_SALE_TITLE, OLX_SALE_URL),
            _match("Flat for rent in Pune", "https://www.olx.in/item/for-rent-pune-2"),
            _match("Flat for rent in Agra II", "https://www.olx.in/item/for-rent-agra-3"),
        )
    )
    assert len(matches) == 2
    assert all(item.reasons for item in matches)


def test_look_alike_matches_are_never_read_as_evidence() -> None:
    # The default Lens mode returns other houses that merely resemble the photo.
    look_alikes = [{"visual_matches": [_match("Villa for sale in Chennai", "https://www.magicbricks.com/villa-for-sale-chennai")]}]
    signal, matches = _image_reuse(look_alikes)

    assert matches == []
    assert signal.score == 0


def test_one_photo_on_several_contradicting_pages_scores_once() -> None:
    signal, matches = _image_reuse(
        _lens(
            _match(OLX_SALE_TITLE, OLX_SALE_URL),
            _match("Flat for rent in Pune", "https://www.olx.in/item/for-rent-pune-2"),
        )
    )
    assert len(matches) == 2
    assert signal.score == scoring.image_reuse_score(1)


def test_two_photos_each_on_a_contradicting_page_score_twice() -> None:
    both = [
        {"exact_matches": [_match(OLX_SALE_TITLE, OLX_SALE_URL)]},
        {"exact_matches": [_match("Flat for rent in Pune", "https://www.olx.in/item/for-rent-pune-2")]},
    ]
    signal, _ = _image_reuse(both)
    assert signal.score == scoring.image_reuse_score(2)


def test_the_same_listing_served_under_two_urls_counts_once() -> None:
    _, matches = _image_reuse(
        _lens(
            _match(OLX_SALE_TITLE, OLX_SALE_URL),
            _match(OLX_SALE_TITLE, "https://www.olx.in/hi-in/item/iid-1853179855"),
        )
    )
    assert len(matches) == 1


def test_search_and_category_pages_that_show_the_photo_are_not_listings() -> None:
    # Real titles/URLs from a live exact-match search of an OLX listing photo.
    category_pages = _lens(
        _match("330 Flats & Apartments for Rent in Dhaulpur - OLX India", "https://www.olx.in/dhaulpur_g4059117/for-rent-houses-apartments_c1723?filter=bachelors_eq_no"),
        _match("Independent Houses - Buy, Sell & Rent Properties in Bharatpur | OLX", "https://www.olx.in/bharatpur_g4059109/properties_c3/q-independent-houses"),
        _match("Houses near Rainbow Ideal Mega Mart, Faizabad Road, Lucknow", "https://www.magicbricks.com/house-for-sale-near-rainbow-ideal-mega-mart-faizabad-road-lucknow-pppfs"),
        _match("152+ Villas in Mitra Nagar, Ram Nagar, Jaipur from Rs 2 Crores", "https://housing.com/in/buy/jaipur/mitra-nagar-ram-nagar-gid/villas-in-2-crores-to-3-crores-fid/"),
    )
    signal, matches = _image_reuse(category_pages)

    assert matches == []
    assert signal.score == 0
    assert "other property listing(s)" not in signal.finding


def test_a_real_listing_of_the_same_home_is_consistent_not_contradictory() -> None:
    real_listing = _match(
        "3BHK Independent House for Rent in Dream Castle Colony, Agra",
        "https://www.olx.in/item/for-rent-houses-apartments-c1723-3-bhk-houses-villas-1274-sq-ft-in-agra-utta",
    )
    signal, matches = _image_reuse(_lens(real_listing), price=15_000)

    assert matches == []
    assert "1 other listing(s) show the same photo without contradicting it" in signal.finding


def test_pages_that_are_not_property_listings_are_ignored() -> None:
    signal, matches = _image_reuse(
        _lens({"title": "Sunrise over the hills - photo gallery", "link": "https://someblog.example/post", "source": "Some Blog"})
    )
    assert matches == []
    assert signal.score == 0


def test_a_listing_on_a_site_with_unconfirmed_url_shapes_is_only_an_indicator() -> None:
    signal, matches = _image_reuse(
        _lens({"title": "3BHK House for Sale in Pune", "link": "https://www.somenewportal.com/property/3bhk-house-sale-pune-8801234", "source": "Some Portal"})
    )

    assert matches[0].tier == "indicator"
    assert matches[0].source_domain == "somenewportal.com"
    assert signal.basis == "indicator"
    assert signal.score == scoring.IMAGE_REUSE_INDICATOR_PER_PHOTO


def test_a_known_listing_url_is_proven_and_outranks_an_indicator_on_the_same_photo() -> None:
    signal, matches = _image_reuse(
        _lens(
            _match(OLX_SALE_TITLE, OLX_SALE_URL),
            {"title": "3BHK House for Sale in Pune", "link": "https://www.somenewportal.com/property/3bhk-house-sale-pune-8801234", "source": "P"},
        )
    )

    assert {m.tier for m in matches} == {"proven", "indicator"}
    assert signal.basis == "proven"
    assert signal.score == scoring.image_reuse_score(1)


def test_an_indicator_photo_and_a_proven_photo_add_up() -> None:
    both = [
        {"exact_matches": [_match(OLX_SALE_TITLE, OLX_SALE_URL)]},
        {"exact_matches": [{"title": "3BHK House for Sale in Pune", "link": "https://www.somenewportal.com/property/x-8801234", "source": "P"}]},
    ]
    signal, _ = _image_reuse(both)
    assert signal.score == scoring.image_reuse_score(1, 1)


@pytest.mark.parametrize(
    "title, link, expected",
    [
        ("House for sale in Pune", "https://someblog.example/post-8812345", True),
        ("3BHK Independent House for Rent in Dream Castle Colony, Agra", "https://www.99acres.com/3bhk-independent-house-for-rent-agra-spid-84512345", True),
        ("Buy 1050 sqft 3 BHK Villa for Sale in Medavakkam Chennai", "https://portal.example/propertyDetails/3-BHK-Villa-FOR-Sale&id=4d423836353230333839", True),
        # A listing page has an id in its URL; without one it is not treated as a single listing:
        ("House for sale in Pune", "https://someblog.example/post", False),
        # Real search/category/aggregate pages seen in live exact-match results:
        ("330 Flats & Apartments for Rent in Dhaulpur - OLX India", "https://www.olx.in/dhaulpur_g4059117/for-rent-houses-apartments_c1723?filter=bachelors_eq_no", False),
        ("Independent Houses - Buy, Sell & Rent Properties in Bharatpur | OLX", "https://www.olx.in/bharatpur_g4059109/properties_c3/q-independent-houses", False),
        ("3 Bhk For In in Bodla - OLX India", "https://www.olx.in/bodla_g5339343/q-3-bhk-for-in", False),
        ("Houses near Rainbow Ideal Mega Mart, Faizabad Road, Lucknow", "https://www.magicbricks.com/house-for-sale-near-rainbow-lucknow-pppfs", False),
        ("152+ Villas in Mitra Nagar, Ram Nagar, Jaipur from Rs 2 Crores", "https://housing.com/in/buy/jaipur/mitra-nagar-gid/villas-in-2-crores-to-3-crores-fid/", False),
        ("2 BHK Flats for Rent in Bengaluru", "https://housing.com/rent/2bhk-flats-for-rent-in-bangalore-karnataka-C4P38f9yfbk7p3m2h1f", False),
        # Real Magicbricks / 99acres category pages (no listing id in the URL):
        ("Single room for rent in Khar Mumbai - MagicBricks", "https://www.magicbricks.com/single-room-for-rent-in-khar-mumbai-pppfr", False),
        ("खार वेस्ट में किराए पर 1 BHK फ्लैट्स - MagicBricks", "https://www.magicbricks.com/hi-in/1-bhk-flats-for-rent-in-khar-west-mumbai-pppfr", False),
        ("Khar Danda Road में किराए पर 36 सिंगल रूम खोजें", "https://www.magicbricks.com/hi-in/single-room-for-rent-in-khar-danda-road-mumbai", False),
        ("Society / Gated Community Flats for Rent in Wadgaon Sheri, Pune", "https://www.99acres.com/society-flats-apartments-for-rent-in-wadgaon-sheri-pune-ffid", False),
        ("Danny DeVito - Wikipedia", "https://en.wikipedia.org/wiki/Danny_DeVito", False),
        ("Family home", "https://example.com/", False),
    ],
)
def test_looks_like_listing_page(title: str, link: str, expected: bool) -> None:
    assert evidence.looks_like_listing_page(title, link) is expected


@pytest.mark.parametrize(
    "link",
    [
        "https://www.olx.in/en-in/item/for-sale-x",
        "https://www.magicbricks.com/propertyDetails/3-BHK-Villa-FOR-Sale-Chennai&id=1",
        "https://www.facebook.com/groups/658002432047676/posts/1426067125241199/",
    ],
)
def test_a_property_site_is_recognised_by_its_link_not_its_display_name(link: str) -> None:
    lens_results = [{"exact_matches": [{"title": "House for sale", "link": link, "source": "Some Site Name"}]}]
    _, matches = _image_reuse(lens_results)
    assert len(matches) == 1


@pytest.mark.parametrize("link", ["https://notolx.in/x", "https://olx.in.evil.example/x", "https://example.com/olx.in"])
def test_a_look_alike_host_is_never_taken_for_olx_or_proven(link: str) -> None:
    _, matches = _image_reuse(_lens(_match("House for sale", link)))
    assert all(m.source_domain != "olx.in" and m.tier == "indicator" for m in matches)


def test_a_failed_call_degrades_gracefully() -> None:
    signal, matches = _image_reuse([httpx.TimeoutException("timed out")])
    assert matches == []
    assert signal.status == "unavailable"


# --- listing type is read from the page's own words ------------------------------


@pytest.mark.parametrize(
    "title, link, expected",
    [
        (OLX_SALE_TITLE, OLX_SALE_URL, "sale"),
        ("Houses near Rainbow Mega Mart", "https://www.magicbricks.com/house-for-sale-near-rainbow-lucknow", "sale"),
        ("Buy 1050 sqft 3 BHK Villa", "https://www.magicbricks.com/propertyDetails/x", "sale"),
        ("2BHK flat for rent", "https://www.olx.in/item/x", "rent"),
        ("Flat", "https://www.olx.in/en-in/item/for-rent-houses-apartments-iid-1", "rent"),
        ("Flat for rent or sale", "https://www.olx.in/item/x", None),
        ("Beautiful 3BHK", "https://www.olx.in/item/x", None),
        ("Nearby flat", "https://www.olx.in/item/x", None),
    ],
)
def test_listing_type(title: str, link: str, expected: str | None) -> None:
    assert evidence.listing_type(title, link) == expected


# --- address ------------------------------------------------------------------------


def _address(maps_result, city: str = "Bengaluru", city_added: bool = False):
    return evidence.extract_address_validity(maps_result, city, city_added=city_added)


def test_no_result_is_invalid() -> None:
    signal = _address({"error": "Google hasn't returned any results for this query."})
    assert signal.score == scoring.ADDRESS_INVALID_SCORE
    assert "even with the city added" not in signal.finding


def test_no_result_even_with_the_city_added_says_so() -> None:
    signal = _address({}, city_added=True)
    assert signal.score == scoring.ADDRESS_INVALID_SCORE
    assert "even with the city added" in signal.finding


def test_maps_answering_with_just_the_city_is_not_the_address_resolving() -> None:
    # Real: "Zzqxvlm Nonexistent Street 99999, Bengaluru" -> a place titled "Bengaluru".
    maps_result = {"local_results": [{"title": "Bengaluru", "address": "Karnataka, India", "place_id": "x"}]}
    signal = _address(maps_result, city_added=True)
    assert signal.score == scoring.ADDRESS_INVALID_SCORE
    assert signal.sources == []


def test_a_city_we_do_not_list_is_also_not_a_resolved_address() -> None:
    maps_result = {"local_results": [{"title": "Kota", "address": "Rajasthan, India"}]}
    assert _address(maps_result, city="Kota", city_added=True).score == scoring.ADDRESS_INVALID_SCORE


def test_a_resolved_place_is_listed_as_a_source_with_a_maps_link() -> None:
    # Real shape: place_results with title/address/gps/place_id and no type.
    maps_result = {
        "place_results": {
            "title": "4, 12th Main Rd",
            "address": "4, 12th Main Rd, HAL 2nd Stage, Indiranagar, Bengaluru, Karnataka 560008, India",
            "gps_coordinates": {"latitude": 12.97, "longitude": 77.64},
            "place_id": "ChIJsS8SMagWrjsRdnQ2pFrdsMk",
        }
    }
    signal = _address(maps_result)

    assert signal.score == scoring.ADDRESS_VALID_SCORE
    assert signal.sources[0].url == "https://www.google.com/maps/place/?q=place_id:ChIJsS8SMagWrjsRdnQ2pFrdsMk"
    assert "Indiranagar, Bengaluru" in signal.sources[0].detail


def test_an_address_found_only_after_adding_the_city_says_so() -> None:
    maps_result = {"place_results": {"title": "Gwalior Rd", "address": "Uttar Pradesh, India"}}
    signal = _address(maps_result, city="Agra", city_added=True)

    assert signal.score == scoring.ADDRESS_VALID_SCORE
    assert "Found by adding your city to the search" in signal.finding


def test_an_address_that_resolves_in_another_city_is_a_contradiction() -> None:
    maps_result = {"place_results": {"title": "MG Road", "address": "MG Road, Fort, Mumbai, Maharashtra 400001, India"}}
    signal = _address(maps_result, city="Bengaluru")

    assert signal.score == scoring.ADDRESS_WRONG_CITY_SCORE
    assert 'resolves to "MG Road" in Mumbai, not Bengaluru' in signal.finding


def test_a_street_named_after_a_city_is_not_a_wrong_city() -> None:
    maps_result = {"place_results": {"title": "Mysore Rd", "address": "Mysore Road, Bengaluru, Karnataka, India"}}
    assert _address(maps_result, city="Bengaluru").score == scoring.ADDRESS_VALID_SCORE


def test_mismatched_category_is_ambiguous() -> None:
    maps_result = {"local_results": [{"title": "Prestige Shantiniketan Whitefield", "type": "Technology park"}]}
    assert _address(maps_result).score == scoring.ADDRESS_AMBIGUOUS_SCORE


def test_residential_category_is_valid() -> None:
    maps_result = {"local_results": [{"title": "Prestige Pinewood", "type": "Condominium complex"}]}
    assert _address(maps_result).score == scoring.ADDRESS_VALID_SCORE


def test_a_type_field_returned_as_a_list_is_handled() -> None:
    # Real (confirmed live, crashed with AttributeError: 'list' object has no
    # attribute 'lower'): SerpApi's google_maps engine doesn't always return
    # "type" as a single string like the rest of this module assumes.
    maps_result = {"local_results": [{"title": "Prestige Pinewood", "type": ["Condominium complex"]}]}
    signal = _address(maps_result)
    assert signal.score == scoring.ADDRESS_VALID_SCORE
    assert "Condominium complex" in signal.finding


# --- price: computed only from listings that can be shown ---------------------------


def _organic(*items: tuple[str, str, str]) -> dict:
    return {"organic_results": [{"title": t, "snippet": s, "link": link} for t, s, link in items]}


def _rentals(*amounts: int, city: str = "Agra", bhk: str = "3 BHK") -> dict:
    return _organic(
        *(
            (f"{bhk} flat for rent in {city}", f"{bhk} for rent in {city}. ₹{amount:,}/month.", f"https://example.com/rent/{amount}")
            for amount in amounts
        )
    )


def _price(organic: dict, rent: int = 9_000, city: str = "Agra", bhk: str | None = "3BHK"):
    return evidence.extract_price_deviation(organic, submitted_rent=rent, city=city, bhk=bhk)


def test_the_median_of_matching_listings_is_scored_and_the_listings_are_the_sources() -> None:
    signal = _price(_rentals(18_000, 20_000, 22_000), rent=9_000)

    assert signal.score > 0
    assert "median (₹20,000) of 3 pages that quote a rent" in signal.finding
    assert [source.url for source in signal.sources] == [f"https://example.com/rent/{a}" for a in (18_000, 20_000, 22_000)]
    assert "₹18,000 a month" in signal.sources[0].detail


def test_listings_for_another_city_are_not_comparables() -> None:
    signal = _price(_rentals(20_000, 21_000, 22_000, city="Jaipur"))
    assert signal.status == "unavailable"
    assert signal.sources == []


def test_listings_for_a_different_home_size_are_not_comparables() -> None:
    signal = _price(_rentals(20_000, 21_000, 22_000, bhk="1 BHK"), bhk="3BHK")
    assert signal.status == "unavailable"
    assert "Found 0 page(s) quoting a rent for a 3BHK in Agra" in signal.finding


def test_a_snippet_that_does_not_state_the_home_size_is_not_a_comparable_when_it_is_known() -> None:
    organic = _organic(*((f"Flats for rent in Agra", f"Rent in Agra ₹{a:,}/month", f"https://example.com/{a}") for a in (10_000, 11_000, 12_000)))
    assert _price(organic, bhk="3BHK").status == "unavailable"


def test_a_snippet_quoting_several_sizes_or_figures_is_not_attributed_to_one_home() -> None:
    organic = _organic(
        ("Rent in Agra", "1 BHK ₹8,000, 2 BHK ₹15,000, 3 BHK ₹22,000 in Agra", "https://example.com/a"),
        ("3 BHK in Agra", "3 BHK for rent in Agra ₹20,000/month or ₹22,000/month", "https://example.com/b"),
    )
    assert _price(organic).sources == []


def test_sale_listings_are_not_comparables() -> None:
    organic = _organic(
        *(("3 BHK house for sale in Agra", f"3 BHK in Agra ₹{a:,}/month", f"https://example.com/for-sale/{a}") for a in (20_000, 21_000, 22_000))
    )
    assert _price(organic).status == "unavailable"


@pytest.mark.parametrize(
    "snippet",
    [
        "3 BHK Flats for rent under ₹10000 in Agra",
        "3 BHK for rent in Agra, from ₹8,000",
        "3 BHK for rent in Agra between ₹10,000 and ₹20,000",
        "3 BHK for rent in Agra: budget Rs. 15,000",
    ],
)
def test_a_price_bound_or_range_is_not_a_rent(snippet: str) -> None:
    assert _price(_organic(("3 BHK in Agra", snippet, "https://example.com/x"))).sources == []


def test_per_square_foot_figures_are_ignored() -> None:
    organic = _organic(("3 BHK for rent in Agra", "The average price per sqft to rent a 3 BHK in Agra is Rs. 44,897.", "https://example.com/x"))
    assert _price(organic).sources == []


def test_fewer_than_three_comparables_is_unavailable_and_says_how_many_were_found() -> None:
    signal = _price(_rentals(20_000, 22_000))

    assert signal.status == "unavailable"
    assert signal.score == 0
    assert "Found 2 page(s)" in signal.finding
    assert len(signal.sources) == 2


def test_a_failed_price_search_is_unavailable() -> None:
    signal = _price(httpx.TimeoutException("timed out"))
    assert signal.status == "unavailable"
    assert signal.score == 0


def test_price_counts_for_less_when_no_home_size_was_given() -> None:
    organic = _rentals(28_000, 30_000, 32_000)

    known = _price(organic, rent=5_000, bhk="3BHK")
    unknown = _price(organic, rent=5_000, bhk=None)

    assert known.max == scoring.PRICE_DEVIATION_MAX and known.score == scoring.PRICE_DEVIATION_MAX
    assert unknown.max == scoring.PRICE_DEVIATION_UNKNOWN_BHK_MAX
    assert unknown.score == scoring.PRICE_DEVIATION_UNKNOWN_BHK_MAX
    assert "all sizes" in unknown.finding
    assert "all sizes" not in known.finding


def test_a_rent_far_above_the_median_is_not_called_plausible() -> None:
    signal = _price(_rentals(19_000, 20_000, 21_000), rent=150_000)

    assert signal.score == 0
    assert "above the median" in signal.finding
    assert "plausible" not in signal.finding


# --- reading a flagged page's price from Google's entry for it ------------------------

# Real result for the OLX listing's URL: the snippet carries size and price.
OLX_PAGE_RESULTS = [
    {
        "link": "https://www.olx.in/item/for-sale-houses-apartments-c1725-3-bhk-house-villa-800-sq-ft-in-agra-cantonment-agra-iid-1855312754",
        "title": "3BHK semi furnished semi duplex house for sale in rohta ...",
        "snippet": "3BHK semi furnished semi duplex house for sale in rohta Gwalior Road. 3 BHK - 3 Bathroom - 800 sqft. ₹ 31,99,000. postedOn10 Sep, 2026.",
    }
]


def test_a_flagged_pages_price_and_text_are_read_from_googles_entry_for_it() -> None:
    details = evidence.page_details(OLX_PAGE_RESULTS, OLX_SALE_URL)

    assert details.price == 3_199_000
    assert "3 BHK - 3 Bathroom - 800 sqft" in details.snippet


def test_a_listing_is_recognised_across_the_url_variants_a_site_serves_it_under() -> None:
    hindi_variant = "https://www.olx.in/hi-in/item/for-sale-houses-apartments-c1725-3-bhk-house-villa-800-sq-ft-in-agra-cantonment-agra-iid-1855312754"
    assert evidence.page_details(OLX_PAGE_RESULTS, hindi_variant).price == 3_199_000


def test_a_page_google_does_not_return_has_no_details() -> None:
    assert evidence.page_details(OLX_PAGE_RESULTS, "https://www.olx.in/item/some-other-iid-1") is None
    assert evidence.page_details([], OLX_SALE_URL) is None


def test_two_different_prices_in_one_snippet_are_not_read_as_the_price() -> None:
    results = [{**OLX_PAGE_RESULTS[0], "snippet": "House ₹ 31,99,000. Was ₹ 35,00,000."}]
    assert evidence.page_details(results, OLX_SALE_URL).price is None


def test_the_pages_own_sale_price_goes_into_the_reason_and_the_evidence() -> None:
    details = evidence.page_details(OLX_PAGE_RESULTS, OLX_SALE_URL)
    _, matches = evidence.extract_image_reuse(
        _lens(_match(OLX_SALE_TITLE, OLX_SALE_URL)), 150_000, "Agra", {OLX_SALE_URL: details}
    )

    assert matches[0].listed_price == 3_199_000
    assert matches[0].reasons == ["It is a listing for sale, but you submitted a rental. It shows ₹31,99,000."]
    assert "₹ 31,99,000" in matches[0].source_snippet


def test_an_address_with_no_category_is_not_penalised() -> None:
    maps_result = {"place_results": {"title": "Gwalior Rd", "address": "Uttar Pradesh, India"}}
    signal = _address(maps_result, city="Agra", city_added=True)

    assert signal.score == 0
    assert signal.status == "ok"
    assert "confirms the place exists" in signal.finding


# --- stored comparables from earlier scans ------------------------------------------------


def _stored(*amounts: int) -> list[evidence.Comparable]:
    return [
        evidence.Comparable(a, "3 BHK for rent in Agra", f"https://example.com/old/{a}", "old snippet", earlier=True)
        for a in amounts
    ]


def test_earlier_comparables_top_up_a_thin_live_search() -> None:
    signal = evidence.extract_price_deviation(
        _rentals(20_000), submitted_rent=9_000, city="Agra", bhk="3BHK", stored=_stored(18_000, 22_000)
    )

    assert signal.status == "ok"
    assert len(signal.sources) == 3
    assert [s.detail.endswith("(from an earlier search)") for s in signal.sources] == [False, True, True]


def test_a_page_found_now_and_stored_counts_once() -> None:
    live = _rentals(20_000, 21_000, 22_000)
    stored = [evidence.Comparable(20_000, "x", "https://example.com/rent/20000", "x", earlier=True)]
    signal = evidence.extract_price_deviation(live, submitted_rent=9_000, city="Agra", bhk="3BHK", stored=stored)
    assert len(signal.sources) == 3


def test_a_failed_search_can_still_be_answered_from_earlier_comparables() -> None:
    signal = evidence.extract_price_deviation(
        httpx.TimeoutException("t"), submitted_rent=9_000, city="Agra", bhk="3BHK", stored=_stored(18_000, 20_000, 22_000)
    )
    assert signal.status == "ok"
    assert signal.score > 0


def test_a_failed_search_with_too_little_stored_is_still_unavailable() -> None:
    signal = evidence.extract_price_deviation(
        httpx.TimeoutException("t"), submitted_rent=9_000, city="Agra", bhk="3BHK", stored=_stored(18_000)
    )
    assert signal.status == "unavailable"
    assert "didn't respond" in signal.finding


# --- real Facebook posts that carried a stock photo: none of them is a property listing ---


@pytest.mark.parametrize(
    "title, link",
    [
        ("How to improve home energy efficiency and lower bills - Facebook", "https://www.facebook.com/entergy/posts/a-home-energy-audit-can-help-determine-your-homes-energy-performance"),
        ("Sober living tiny home community development - Facebook", "https://www.facebook.com/groups/guardiansofrecovery/posts/1153464549447629/"),
        ("Mortgage advisor services for home buyers - Facebook", "https://www.facebook.com/groups/fthomebuyers/posts/1893489557896176/"),
        ("What does a mortgage advisor do in the home buying process?", "https://www.facebook.com/groups/kiwifirsthomebuyers/posts/7932479020105723/"),
    ],
)
def test_a_facebook_post_that_is_not_about_a_property_for_rent_or_sale_is_not_a_listing(title: str, link: str) -> None:
    signal, matches = _image_reuse(_lens({"title": title, "link": link, "source": "Facebook"}), city="Pune")
    assert matches == []
    assert "other listing(s) show the same photo" not in signal.finding


def test_a_facebook_group_post_advertising_a_flat_is_an_indicator_not_proof() -> None:
    post = {
        "title": "Available Good Quality 1 Bhk Flat On Rent in Mumbai - Facebook",
        "link": "https://www.facebook.com/groups/747414650035066/posts/1828552098587977/",
        "source": "Facebook",
    }
    _, matches = _image_reuse(_lens(post), city="Bengaluru")

    assert matches[0].tier == "indicator"
    assert matches[0].listed_city == "Mumbai"


def test_a_non_property_item_on_a_known_classifieds_site_is_not_a_listing() -> None:
    phone_ad = {"title": "iPhone 13 for sale in Pune", "link": "https://www.olx.in/item/iphone-13-for-sale-iid-99887766", "source": "OLX"}
    _, matches = _image_reuse(_lens(phone_ad), city="Bengaluru")
    assert matches == []


# --- real OLX /item/ URL that Google shows with a category title and text ---------------------

KOLKHA_URL = "https://www.olx.in/item/for-rent-houses-apartments-c1723-2-bhk-houses-villas-1025-sq-ft-in-kolkha-agra-iid-1834835993"
KOLKHA_TITLE = "1925 Flats & Apartments for Rent in Kolkha - OLX India"
KOLKHA_SNIPPET = (
    "Explore flats for rent in Kolkha in the price range of ₹1000 - ₹5 Crores. "
    "OLX provides you options ranging from 1-5 BHK flats for rent in Kolkha. You can ..."
)


def test_an_item_url_with_a_category_title_is_not_a_listing() -> None:
    signal, matches = _image_reuse(_lens(_match(KOLKHA_TITLE, KOLKHA_URL)), city="Bengaluru")
    assert matches == []
    assert signal.score == 0


def test_a_price_range_in_the_snippet_is_not_read_as_the_pages_price() -> None:
    results = [{"link": KOLKHA_URL, "title": KOLKHA_TITLE, "snippet": KOLKHA_SNIPPET}]
    assert evidence.page_details(results, KOLKHA_URL).price is None


@pytest.mark.parametrize(
    "snippet",
    ["Flats from ₹8,000 in Agra", "Starting at ₹ 12,000 a month", "₹ 10,000 to ₹ 20,000 per month", "House for ₹ 1.2 Crore"],
)
def test_bounds_ranges_and_crore_prices_are_not_a_single_price(snippet: str) -> None:
    results = [{"link": OLX_SALE_URL, "title": "House", "snippet": snippet}]
    assert evidence.page_details(results, OLX_SALE_URL).price is None


def test_a_rent_that_is_not_a_plausible_monthly_figure_is_not_shown_as_the_pages_rent() -> None:
    lens = _lens(_match("2BHK flat for rent in Agra", "https://www.olx.in/item/for-rent-agra-1", price=1_000))
    _, matches = _image_reuse(lens, price=15_000, city="Agra")
    assert matches == []


# --- 99acres and housing.com: real single-listing vs category URLs -----------------------

@pytest.mark.parametrize(
    "title, link, expected_tier",
    [
        (
            "Flat for Rent in Vario Homes Hebbal, Bangalore - 99acres.com",
            "https://www.99acres.com/2-bhk-bedroom-apartment-flat-for-rent-in-vario-homes-hebbal-bangalore-north-1168-sqft-spid-W94480788",
            "proven",
        ),
        (
            "3 BHK Flat for rent in Powai, Mumbai - 1200 Sqft | Property ID",
            "https://housing.com/rent/20057298-1200-sqft-3-bhk-apartment-on-rent-in-powai-mumbai",
            "proven",
        ),
    ],
)
def test_a_real_99acres_or_housing_single_listing_is_proven(title: str, link: str, expected_tier: str) -> None:
    _, matches = _image_reuse(_lens({"title": title, "link": link, "source": "Some Site"}), city="Chennai")
    assert matches[0].tier == expected_tier
    assert matches[0].source_domain in ("99acres.com", "housing.com")


@pytest.mark.parametrize(
    "title, link",
    [
        ("2 BHK Semi Furnished Flats for rent in Hebbal, Bangalore - 99acres.com", "https://www.99acres.com/2-bhk-semi-furnished-flats-for-rent-in-hebbal-bangalore-north-ffid"),
        ("2 BHK Flats for Rent in Kharadi, Pune - 99acres.com", "https://www.99acres.com/2-bhk-flats-for-rent-in-kharadi-pune-ffid"),
        ("Flats for Rent in JVLR-Powai, Mumbai - Housing", "https://housing.com/rent/flats-for-rent-in-jvlr-powai-mumbai-P2ojfz8petk12yx22"),
        ("Flats for rent in Maharashtra | Housing.com", "https://housing.com/rent/3bhk-flat-in-maharashtra-C8M1P3mm15uxln8blpmn0?page=409"),
        ("10 Flats for rent in Gurukrupa Gyanam, Powai, Mumbai - Housing", "https://housing.com/rent-gurukrupa-gyanam-for-rent-in-powai-mumbai-rpid-AG6mu6AH0"),
    ],
)
def test_a_real_99acres_or_housing_category_or_project_page_is_not_a_listing(title: str, link: str) -> None:
    _, matches = _image_reuse(_lens({"title": title, "link": link, "source": "Some Site"}), city="Chennai")
    assert matches == []
