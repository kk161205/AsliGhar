from app.services import cities


def test_spelling_variants_are_the_same_city() -> None:
    assert cities.canonical_city("Bangalore") == cities.canonical_city("Bengaluru") == "bengaluru"
    assert cities.canonical_city("Gurgaon") == "gurugram"
    assert cities.canonical_city("Bombay") == "mumbai"
    assert cities.canonical_city("Vizag") == "visakhapatnam"


def test_city_field_with_extra_words_still_resolves() -> None:
    assert cities.canonical_city("Bengaluru, Karnataka") == "bengaluru"
    assert cities.canonical_city("  New Delhi ") == "delhi"


def test_unlisted_city_falls_back_to_its_own_text() -> None:
    assert cities.canonical_city("Kota") == "kota"
    assert cities.canonical_city("   ") is None


def test_street_and_institution_names_are_not_city_mentions() -> None:
    assert cities.cities_mentioned("1BHK on Mysore Road") == set()
    assert cities.cities_mentioned("Near Delhi Public School, Bengaluru") == {"bengaluru"}
    assert cities.cities_mentioned("Hyderabad Highway, Pune") == {"pune"}


def test_longest_name_wins_over_its_substring() -> None:
    assert cities.cities_mentioned("Flat in Navi Mumbai") == {"navi mumbai"}
    assert cities.cities_mentioned("Connaught Place, New Delhi") == {"delhi"}


def test_names_inside_longer_words_do_not_match() -> None:
    assert cities.cities_mentioned("Suratkal beach house") == set()
