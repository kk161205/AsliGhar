import httpx

from app.services import evidence, scoring

# Fixtures below mirror real response shapes captured from live SerpApi calls
# while verifying the integrations, not guesses at the schema.


def test_extract_image_reuse_flags_classifieds_price_mismatch() -> None:
    lens_results = [
        {
            "visual_matches": [
                {
                    "title": "2BHK flat for rent - Pune",
                    "link": "https://www.olx.in/en-in/item/xxxxx",
                    "source": "OLX",
                    "price": {"value": "₹9,500", "extracted_value": 9500},
                },
                {
                    "title": "Unrelated furniture ad",
                    "link": "https://example.com/x",
                    "source": "Example",
                    "price": {"extracted_value": 9500},
                },
            ]
        }
    ]

    signal, matches = evidence.extract_image_reuse(
        lens_results, submitted_price=15000, submitted_city="Bengaluru"
    )

    assert len(matches) == 1
    assert matches[0].source_domain == "olx.in"
    assert matches[0].listed_price == 9500
    assert signal.score == scoring.image_reuse_score(1)


def test_extract_image_reuse_ignores_non_classifieds_domains() -> None:
    lens_results = [
        {
            "visual_matches": [
                {
                    "title": "Random blog repost",
                    "link": "https://someblog.example",
                    "source": "Some Blog",
                    "price": {"extracted_value": 1},
                }
            ]
        }
    ]
    signal, matches = evidence.extract_image_reuse(
        lens_results, submitted_price=15000, submitted_city="Bengaluru"
    )
    assert matches == []
    assert signal.score == 0


def test_extract_image_reuse_degrades_gracefully_on_failed_call() -> None:
    lens_results = [httpx.TimeoutException("timed out")]
    signal, matches = evidence.extract_image_reuse(
        lens_results, submitted_price=15000, submitted_city="Bengaluru"
    )
    assert matches == []
    assert signal.score == 0


def test_extract_address_validity_no_result_is_invalid() -> None:
    signal = evidence.extract_address_validity({"search_metadata": {"status": "Success"}})
    assert signal.score == scoring.ADDRESS_INVALID_SCORE


def test_extract_address_validity_place_results_without_type_is_neutral() -> None:
    # Real shape observed for a locality-level google_maps query: no type/types field at all.
    maps_result = {
        "place_results": {
            "title": "5th Block",
            "address": "Koramangala, Bengaluru, Karnataka, India",
            "gps_coordinates": {"latitude": 12.9, "longitude": 77.6},
        }
    }
    signal = evidence.extract_address_validity(maps_result)
    assert signal.score == scoring.ADDRESS_NO_CATEGORY_DATA_SCORE


def test_extract_address_validity_local_results_mismatched_category() -> None:
    # Real shape observed for a named-place google_maps query: local_results list with type.
    maps_result = {
        "local_results": [
            {"title": "Prestige Shantiniketan Whitefield", "type": "Technology park"}
        ]
    }
    signal = evidence.extract_address_validity(maps_result)
    assert signal.score == scoring.ADDRESS_AMBIGUOUS_SCORE


def test_extract_address_validity_residential_category_is_valid() -> None:
    maps_result = {"local_results": [{"title": "Prestige Pinewood", "type": "Condominium complex"}]}
    signal = evidence.extract_address_validity(maps_result)
    assert signal.score == scoring.ADDRESS_VALID_SCORE


def test_extract_price_deviation_ignores_per_sqft_figures() -> None:
    organic_result = {
        "organic_results": [
            {
                "title": "2 BHK Flats for Rent in Koramangala, Bengaluru",
                "snippet": "The average price per sqft to rent a 2 BHK Flats is Rs. 44,897.",
            }
        ]
    }
    signal = evidence.extract_price_deviation(organic_result, submitted_rent=9000, bhk_known=True)
    # Only one real (non-sqft) sample below MIN_PRICE_SAMPLES threshold -> no score.
    assert signal.score == 0
    assert "Not enough" in signal.finding


def test_extract_price_deviation_computes_median_from_snippets() -> None:
    organic_result = {
        "organic_results": [
            {"title": "Flat A", "snippet": "Regular Rent. 27,000/Month."},
            {"title": "Flat B", "snippet": "2 BHK semi furnished flat for Rent. 18,000. Rent."},
            {"title": "Flat C", "snippet": "3 BHK independent house for Rent. 24,000. Rent."},
        ]
    }
    signal = evidence.extract_price_deviation(organic_result, submitted_rent=9000, bhk_known=True)
    # median is 24000; 9000 is well below tolerance -> should score above zero.
    assert signal.score > 0


def test_extract_price_deviation_below_min_samples_reports_not_enough_data() -> None:
    organic_result = {
        "organic_results": [
            {"title": "Flat A", "snippet": "Regular Rent. 27,000/Month."},
            {"title": "Flat B", "snippet": "2 BHK semi furnished flat for Rent. 18,000. Rent."},
        ]
    }
    # Only 2 valid samples — below MIN_PRICE_SAMPLES (3) — should honestly
    # report insufficient data rather than compute a median from too little.
    signal = evidence.extract_price_deviation(organic_result, submitted_rent=9000, bhk_known=True)
    assert signal.score == 0
    assert "Not enough" in signal.finding


def test_extract_price_deviation_degrades_gracefully_on_failed_call() -> None:
    signal = evidence.extract_price_deviation(httpx.TimeoutException("timed out"), submitted_rent=9000, bhk_known=True)
    assert signal.score == 0


def test_price_deviation_counts_for_less_when_no_bhk_was_given() -> None:
    organic_result = {"organic_results": [{"title": "", "snippet": f"₹{amount:,}/month"} for amount in (28_000, 30_000, 32_000)]}

    known = evidence.extract_price_deviation(organic_result, submitted_rent=5_000, bhk_known=True)
    unknown = evidence.extract_price_deviation(organic_result, submitted_rent=5_000, bhk_known=False)

    assert known.max == scoring.PRICE_DEVIATION_MAX and known.score == scoring.PRICE_DEVIATION_MAX
    assert unknown.max == scoring.PRICE_DEVIATION_UNKNOWN_BHK_MAX
    assert unknown.score == scoring.PRICE_DEVIATION_UNKNOWN_BHK_MAX
    assert "all sizes" in unknown.finding
    assert "all sizes" not in known.finding


def test_a_classifieds_site_is_recognised_by_its_link_not_its_display_name() -> None:
    links = [
        "https://www.olx.in/en-in/item/3-bhk-house-iid-1855312754",
        "https://m.facebook.com/marketplace/item/123",
        "https://housing.com/rent/flat-1",
    ]
    for link in links:
        lens_results = [
            {"visual_matches": [{"title": "Flat", "link": link, "source": "Some Site Name", "price": {"extracted_value": 9500}}]}
        ]
        _, matches = evidence.extract_image_reuse(lens_results, submitted_price=15000, submitted_city="Bengaluru")
        assert len(matches) == 1, link


def test_a_look_alike_host_is_not_a_classifieds_site() -> None:
    for link in ("https://notolx.in/x", "https://olx.in.evil.example/x", "https://example.com/olx.in"):
        lens_results = [{"visual_matches": [{"title": "Flat", "link": link, "source": "OLX", "price": {"extracted_value": 9500}}]}]
        _, matches = evidence.extract_image_reuse(lens_results, submitted_price=15000, submitted_city="Bengaluru")
        assert matches == [], link


def test_a_classifieds_match_with_nothing_to_compare_is_mentioned_but_not_scored() -> None:
    lens_results = [
        {"visual_matches": [{"title": "3BHK house for sale", "link": "https://www.olx.in/item/1", "source": "OLX"}]}
    ]
    signal, matches = evidence.extract_image_reuse(lens_results, submitted_price=150000, submitted_city="Agra")

    assert matches == []
    assert signal.score == 0
    assert "1 classifieds listing(s) show the same photo" in signal.finding


def test_a_rent_far_above_the_median_is_not_called_plausible() -> None:
    organic_result = {"organic_results": [{"title": "", "snippet": f"₹{amount:,}/month"} for amount in (19_000, 20_000, 21_000)]}

    signal = evidence.extract_price_deviation(organic_result, submitted_rent=150_000, bhk_known=True)

    assert signal.score == 0
    assert "above the estimated local median" in signal.finding
    assert "plausible" not in signal.finding
