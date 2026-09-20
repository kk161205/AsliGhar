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

    assert matches[0].reasons == ["It is a listing for sale, but you submitted a rental. It shows ₹3,199,000."]


def test_the_same_photo_on_a_matching_rental_is_not_evidence() -> None:
    signal, matches = _image_reuse(
        _lens(_match("2BHK flat for rent in Agra", "https://www.magicbricks.com/propertyDetails/2-BHK-Flat-for-Rent-in-Agra&id=4d42383635"))
    )

    assert matches == []
    assert signal.score == 0
    assert "1 other property listing(s) show the same photo without contradicting it" in signal.finding


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
    assert "1 other property listing(s) show the same photo without contradicting it" in signal.finding


def test_pages_that_are_not_property_sites_are_ignored() -> None:
    signal, matches = _image_reuse(
        _lens({"title": "House for sale in Pune", "link": "https://someblog.example/post", "source": "Some Blog"})
    )
    assert matches == []
    assert signal.score == 0


@pytest.mark.parametrize(
    "link",
    [
        "https://www.olx.in/en-in/item/for-sale-x",
        "https://m.facebook.com/marketplace/item/for-sale-x",
        "https://www.magicbricks.com/propertyDetails/3-BHK-Villa-FOR-Sale-Chennai&id=1",
        "https://www.facebook.com/groups/658002432047676/posts/1426067125241199/",
    ],
)
def test_a_property_site_is_recognised_by_its_link_not_its_display_name(link: str) -> None:
    lens_results = [{"exact_matches": [{"title": "House for sale", "link": link, "source": "Some Site Name"}]}]
    _, matches = _image_reuse(lens_results)
    assert len(matches) == 1


@pytest.mark.parametrize("link", ["https://notolx.in/x", "https://olx.in.evil.example/x", "https://example.com/olx.in"])
def test_a_look_alike_host_is_not_a_property_site(link: str) -> None:
    _, matches = _image_reuse(_lens(_match("House for sale", link)))
    assert matches == []


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

    assert signal.score == scoring.ADDRESS_NO_CATEGORY_DATA_SCORE
    assert signal.sources[0].url == "https://www.google.com/maps/place/?q=place_id:ChIJsS8SMagWrjsRdnQ2pFrdsMk"
    assert "Indiranagar, Bengaluru" in signal.sources[0].detail


def test_an_address_found_only_after_adding_the_city_says_so() -> None:
    maps_result = {"place_results": {"title": "Gwalior Rd", "address": "Uttar Pradesh, India"}}
    signal = _address(maps_result, city="Agra", city_added=True)

    assert signal.score == scoring.ADDRESS_NO_CATEGORY_DATA_SCORE
    assert "Only found once the city was added" in signal.finding


def test_an_address_that_resolves_in_another_city_is_a_contradiction() -> None:
    maps_result = {"place_results": {"title": "MG Road", "address": "MG Road, Fort, Mumbai, Maharashtra 400001, India"}}
    signal = _address(maps_result, city="Bengaluru")

    assert signal.score == scoring.ADDRESS_WRONG_CITY_SCORE
    assert 'resolves to "MG Road" in Mumbai, not Bengaluru' in signal.finding


def test_a_street_named_after_a_city_is_not_a_wrong_city() -> None:
    maps_result = {"place_results": {"title": "Mysore Rd", "address": "Mysore Road, Bengaluru, Karnataka, India"}}
    assert _address(maps_result, city="Bengaluru").score == scoring.ADDRESS_NO_CATEGORY_DATA_SCORE


def test_mismatched_category_is_ambiguous() -> None:
    maps_result = {"local_results": [{"title": "Prestige Shantiniketan Whitefield", "type": "Technology park"}]}
    assert _address(maps_result).score == scoring.ADDRESS_AMBIGUOUS_SCORE


def test_residential_category_is_valid() -> None:
    maps_result = {"local_results": [{"title": "Prestige Pinewood", "type": "Condominium complex"}]}
    assert _address(maps_result).score == scoring.ADDRESS_VALID_SCORE


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
    assert "median (₹20,000) of 3 listings" in signal.finding
    assert [source.url for source in signal.sources] == [f"https://example.com/rent/{a}" for a in (18_000, 20_000, 22_000)]
    assert "₹18,000 a month" in signal.sources[0].detail


def test_listings_for_another_city_are_not_comparables() -> None:
    signal = _price(_rentals(20_000, 21_000, 22_000, city="Jaipur"))
    assert signal.status == "unavailable"
    assert signal.sources == []


def test_listings_for_a_different_home_size_are_not_comparables() -> None:
    signal = _price(_rentals(20_000, 21_000, 22_000, bhk="1 BHK"), bhk="3BHK")
    assert signal.status == "unavailable"
    assert "Found 0 listing(s) stating a rent for a 3BHK in Agra" in signal.finding


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
    assert "Found 2 listing(s)" in signal.finding
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
