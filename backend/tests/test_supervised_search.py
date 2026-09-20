import uuid

import pytest

from app.core.config import get_settings
from app.models.db import Scan, User, async_session
from app.services import groq_client, image_host, input_review, scan_service, serpapi_client
from app.services.input_review import NormalizedInput

ADDRESS = "flat 302 sri sai residency near forum mall koramangala 5th blk"


class _Recorder:
    """Stands in for the SerpApi wrapper and records the queries it was sent."""

    def __init__(self) -> None:
        self.maps: list[str] = []
        self.price: list[str] = []
        self.lens: list[str] = []
        self.price_results = None
        self.lens_result: dict = {"exact_matches": []}
        self.page_lookups: list[str] = []


@pytest.fixture
def searches(monkeypatch, tmp_path) -> _Recorder:
    recorder = _Recorder()

    async def lens(url: str) -> dict:
        recorder.lens.append(url)
        return recorder.lens_result

    async def maps(address: str) -> dict:
        recorder.maps.append(address)
        return {"place_results": {"title": "Koramangala", "type": "Apartment complex"}}

    async def price(query: str, city: str) -> dict:
        recorder.price.append(query)
        if recorder.price_results is not None:
            return recorder.price_results(query)
        snippets = [
            {
                "title": "2 BHK flat for rent in Bengaluru",
                "snippet": f"2 BHK for rent in Bengaluru. ₹{amount:,}/month.",
                "link": f"https://example.com/rent/{amount}",
            }
            for amount in (28_000, 30_000, 32_000)
        ]
        return {"organic_results": snippets}

    async def summary(**_kwargs) -> str:
        return "summary"

    monkeypatch.setattr(image_host, "STATIC_DIR", tmp_path)
    monkeypatch.setattr(image_host, "was_fetched", lambda _name: True)
    async def search_page(url: str) -> dict:
        recorder.page_lookups.append(url)
        return {"organic_results": [{"link": url, "title": "House", "snippet": "House for sale. ₹ 31,99,000."}]}

    monkeypatch.setattr(serpapi_client, "search_page", search_page)
    monkeypatch.setattr(serpapi_client, "reverse_image_search", lens)
    monkeypatch.setattr(serpapi_client, "resolve_address", maps)
    monkeypatch.setattr(serpapi_client, "organic_price_search", price)
    monkeypatch.setattr(groq_client, "summarize_evidence", summary)
    return recorder


async def _user_id() -> str:
    # Inserted directly: the password is never used, and hashing one per test is slow.
    user = User(id=uuid.uuid4().hex, email=f"search-{uuid.uuid4().hex[:10]}@example.com", password_hash="unused")
    async with async_session() as session:
        session.add(user)
        await session.commit()
    return user.id


async def _scan(*, bhk: str | None = None, description: str | None = None, override_reason: str | None = None):
    return await scan_service.run_scan(
        photos=[(b"jpeg-bytes", ".jpg")],
        address=ADDRESS,
        city="Bengaluru",
        rent=29_000,
        bhk=bhk,
        description=description,
        user_id=await _user_id(),
        override_reason=override_reason,
    )


def _reviewer(monkeypatch, result: NormalizedInput | None) -> None:
    async def fake_review(*_args) -> NormalizedInput | None:
        return result

    monkeypatch.setattr(input_review, "review_input", fake_review)


KORAMANGALA = NormalizedInput(
    address_city="Bengaluru",
    locality="Koramangala 5th Block",
    landmark="Forum Mall",
    address_resolvable=True,
    confidence=0.9,
)


async def test_price_query_uses_the_locality_and_the_maps_query_is_the_original_address(
    searches, monkeypatch
) -> None:
    _reviewer(monkeypatch, KORAMANGALA)

    result = await _scan(bhk="2BHK")

    assert searches.price == ["2BHK rent Koramangala 5th Block Bengaluru price"]
    assert searches.maps == [ADDRESS]
    assert result.search_trace.reviewer_used is True
    assert result.search_trace.understood.locality == "Koramangala 5th Block"
    assert [(q.check, q.query) for q in result.search_trace.queries] == [
        ("address", ADDRESS),
        ("price", "2BHK rent Koramangala 5th Block Bengaluru price"),
    ]


async def test_scan_falls_back_to_the_city_level_query_when_the_reviewer_fails(searches, monkeypatch) -> None:
    _reviewer(monkeypatch, None)

    result = await _scan(bhk="2BHK")

    assert searches.price == ["2BHK rent Bengaluru price"]
    assert searches.maps == [ADDRESS]
    assert result.search_trace.reviewer_used is False
    assert result.signals.price_deviation.status == "ok"


async def test_scan_does_not_call_the_reviewer_when_it_is_switched_off(searches, monkeypatch) -> None:
    async def must_not_run(*_args):
        raise AssertionError("reviewer called while supervisor_enabled is false")

    monkeypatch.setattr(input_review, "review_input", must_not_run)
    monkeypatch.setattr(get_settings(), "supervisor_enabled", False)

    result = await _scan()

    assert searches.price == ["rent Bengaluru price"]
    assert result.search_trace.reviewer_used is False


async def test_bhk_is_taken_from_the_description_only_when_the_form_leaves_it_out(searches, monkeypatch) -> None:
    _reviewer(monkeypatch, None)

    await _scan(description="Spacious 3 BHK, semi furnished")
    await _scan(bhk="2BHK", description="Spacious 3 BHK, semi furnished")
    await _scan(description="Spacious, semi furnished")

    assert searches.price == ["3BHK rent Bengaluru price", "2BHK rent Bengaluru price", "rent Bengaluru price"]


async def test_a_gibberish_address_still_fails_the_address_check(searches, monkeypatch) -> None:
    # The address is always searched as typed first. Adding the city may make
    # Maps answer with the city itself — that must not count as resolving.
    async def no_such_place(query: str) -> dict:
        searches.maps.append(query)
        if query == ADDRESS:
            return {}
        return {"local_results": [{"title": "Bengaluru", "address": "Karnataka, India"}]}

    monkeypatch.setattr(serpapi_client, "resolve_address", no_such_place)
    _reviewer(monkeypatch, NormalizedInput(address_resolvable=False, confidence=0.9))

    result = await _scan()

    assert searches.maps == [ADDRESS, f"{ADDRESS}, Bengaluru"]
    assert result.signals.address_validity.score == 30
    assert "even with the city added" in result.signals.address_validity.finding
    assert [q.query for q in result.search_trace.queries if q.check == "address"] == searches.maps


async def test_an_address_that_only_resolves_with_the_city_added_says_so(searches, monkeypatch) -> None:
    async def resolves_with_city(query: str) -> dict:
        searches.maps.append(query)
        if query == ADDRESS:
            return {}
        return {"place_results": {"title": "Gwalior Rd", "address": "Uttar Pradesh, India", "place_id": "abc"}}

    monkeypatch.setattr(serpapi_client, "resolve_address", resolves_with_city)
    _reviewer(monkeypatch, None)

    result = await _scan()

    assert searches.maps == [ADDRESS, f"{ADDRESS}, Bengaluru"]
    assert "Found by adding your city to the search" in result.signals.address_validity.finding
    assert result.signals.address_validity.sources[0].url.endswith("place_id:abc")


async def test_the_city_is_not_added_when_the_address_alone_resolves(searches, monkeypatch) -> None:
    _reviewer(monkeypatch, None)
    await _scan()
    assert searches.maps == [ADDRESS]


async def test_a_failed_maps_lookup_is_unavailable_not_invalid(searches, monkeypatch) -> None:
    async def down(_query: str) -> dict:
        raise TimeoutError("maps down")

    monkeypatch.setattr(serpapi_client, "resolve_address", down)
    _reviewer(monkeypatch, None)

    result = await _scan()

    assert result.signals.address_validity.status == "unavailable"


async def test_the_override_reason_is_stored_and_never_changes_the_score(searches, monkeypatch) -> None:
    _reviewer(monkeypatch, KORAMANGALA)

    plain = await _scan()
    explained = await _scan(override_reason="Single room in a family home")
    stored = await scan_service.get_scan(explained.scan_id)

    assert explained.override_reason == "Single room in a family home"
    assert explained.risk_score == plain.risk_score
    assert explained.signals == plain.signals
    assert stored is not None
    assert stored.override_reason == "Single room in a family home"
    assert stored.search_trace == explained.search_trace


async def test_a_scan_stored_before_traces_existed_still_loads(searches, monkeypatch) -> None:
    _reviewer(monkeypatch, None)
    result = await _scan()

    async with async_session() as session:
        row = await session.get(Scan, result.scan_id)
        row.trace_json = None
        row.override_reason = None
        await session.commit()

    stored = await scan_service.get_scan(result.scan_id)
    assert stored is not None
    assert stored.search_trace is None
    assert stored.override_reason is None


async def test_the_price_check_counts_for_less_only_when_no_bhk_is_known(searches, monkeypatch) -> None:
    _reviewer(monkeypatch, None)

    with_form_bhk = await _scan(bhk="2BHK")
    with_description_bhk = await _scan(description="Spacious 3 BHK")
    without = await _scan()

    assert with_form_bhk.signals.price_deviation.max == 30
    assert with_description_bhk.signals.price_deviation.max == 30
    assert without.signals.price_deviation.max == 20


def _rentals(*amounts: int) -> list[dict]:
    return [
        {
            "title": "2 BHK flat for rent in Bengaluru",
            "snippet": f"2 BHK for rent in Bengaluru. ₹{amount:,}/month.",
            "link": f"https://example.com/rent/{amount}",
        }
        for amount in amounts
    ]


async def test_too_few_comparables_at_locality_level_widens_to_the_city_once(searches, monkeypatch) -> None:
    searches.price_results = lambda query: {
        "organic_results": _rentals(28_000) if "Koramangala" in query else _rentals(28_000, 30_000, 32_000)
    }
    _reviewer(monkeypatch, KORAMANGALA)

    result = await _scan(bhk="2BHK")

    assert searches.price == ["2BHK rent Koramangala 5th Block Bengaluru price", "2BHK rent Bengaluru price"]
    assert [q.query for q in result.search_trace.queries if q.check == "price"] == searches.price
    price = result.signals.price_deviation
    assert price.status == "ok"
    assert len(price.sources) == 3


async def test_enough_comparables_at_locality_level_costs_no_extra_search(searches, monkeypatch) -> None:
    _reviewer(monkeypatch, KORAMANGALA)
    await _scan(bhk="2BHK")
    assert len(searches.price) == 1


async def test_a_failed_wider_search_keeps_what_the_locality_search_found(searches, monkeypatch) -> None:
    def results(query: str) -> dict:
        if "Koramangala" not in query:
            raise TimeoutError("wider search down")
        return {"organic_results": _rentals(28_000)}

    searches.price_results = results
    _reviewer(monkeypatch, KORAMANGALA)

    result = await _scan(bhk="2BHK")

    assert result.signals.price_deviation.status == "unavailable"
    assert len(result.signals.price_deviation.sources) == 1


async def test_the_summary_is_told_the_submitted_rent_and_city(searches, monkeypatch) -> None:
    seen = {}

    async def capture(**kwargs) -> str:
        seen.update(kwargs)
        return "summary"

    monkeypatch.setattr(groq_client, "summarize_evidence", capture)
    _reviewer(monkeypatch, None)

    await _scan(bhk="2BHK")

    import json

    submitted = json.loads(seen["evidence_json"])["submitted_listing"]
    assert submitted == {"monthly_rent": 29_000, "city": "Bengaluru", "home_size": "2BHK"}


OLX_SALE = {
    "title": "3BHK house for sale in Bengaluru",
    "link": "https://www.olx.in/item/for-sale-houses-apartments-3-bhk-iid-100",
    "source": "OLX",
}


async def test_a_flagged_page_is_looked_up_and_its_sale_price_shown(searches, monkeypatch) -> None:
    searches.lens_result = {"exact_matches": [OLX_SALE]}
    _reviewer(monkeypatch, None)

    result = await _scan()

    assert searches.page_lookups == [OLX_SALE["link"]]
    assert result.evidence[0].listed_price == 3_199_000
    assert "₹31,99,000" in result.evidence[0].reasons[0]
    assert result.evidence[0].source_snippet.endswith("₹ 31,99,000.")


async def test_no_page_is_looked_up_when_nothing_is_flagged(searches, monkeypatch) -> None:
    _reviewer(monkeypatch, None)
    await _scan()
    assert searches.page_lookups == []


async def test_page_lookups_are_capped(searches, monkeypatch) -> None:
    searches.lens_result = {
        "exact_matches": [{**OLX_SALE, "title": f"House {n} for sale", "link": f"https://www.olx.in/item/for-sale-x-iid-{n}"} for n in range(6)]
    }
    _reviewer(monkeypatch, None)

    result = await _scan()

    assert len(searches.page_lookups) == scan_service.MAX_PAGE_LOOKUPS
    assert len(result.evidence) == 6


async def test_a_failed_page_lookup_keeps_the_evidence_without_its_price(searches, monkeypatch) -> None:
    async def down(_url: str) -> dict:
        raise TimeoutError("search down")

    monkeypatch.setattr(serpapi_client, "search_page", down)
    searches.lens_result = {"exact_matches": [OLX_SALE]}
    _reviewer(monkeypatch, None)

    result = await _scan()

    assert len(result.evidence) == 1
    assert result.evidence[0].listed_price is None
    assert result.evidence[0].reasons == ["It is a listing for sale, but you submitted a rental."]
