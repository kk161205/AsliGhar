from app.services import query_builder


def test_city_level_query_is_unchanged_when_nothing_else_is_known() -> None:
    assert query_builder.price_query(None, None, "Bengaluru") == "rent Bengaluru price"


def test_bhk_only_matches_the_previous_format() -> None:
    assert query_builder.price_query("2BHK", None, "Bengaluru") == "2BHK rent Bengaluru price"


def test_locality_narrows_the_query() -> None:
    assert (
        query_builder.price_query("2BHK", "Indiranagar", "Bengaluru")
        == "2BHK rent Indiranagar Bengaluru price"
    )
    assert query_builder.price_query(None, "Whitefield", "Bengaluru") == "rent Whitefield Bengaluru price"
