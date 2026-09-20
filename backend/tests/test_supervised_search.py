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


@pytest.fixture
def searches(monkeypatch, tmp_path) -> _Recorder:
    recorder = _Recorder()

    async def lens(url: str) -> dict:
        recorder.lens.append(url)
        return {"visual_matches": []}

    async def maps(address: str) -> dict:
        recorder.maps.append(address)
        return {"place_results": {"title": "Koramangala", "type": "Apartment complex"}}

    async def price(query: str, city: str) -> dict:
        recorder.price.append(query)
        snippets = [{"title": "2 BHK", "snippet": f"₹{amount:,}/month"} for amount in (28_000, 30_000, 32_000)]
        return {"organic_results": snippets}

    async def summary(**_kwargs) -> str:
        return "summary"

    monkeypatch.setattr(image_host, "STATIC_DIR", tmp_path)
    monkeypatch.setattr(image_host, "was_fetched", lambda _name: True)
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
    # The reviewer can tidy the text, but "does this place exist" must still be
    # answered by searching what the user actually typed.
    async def no_such_place(address: str) -> dict:
        searches.maps.append(address)
        return {}

    monkeypatch.setattr(serpapi_client, "resolve_address", no_such_place)
    _reviewer(
        monkeypatch,
        NormalizedInput(address_resolvable=False, confidence=0.9),
    )

    result = await _scan()

    assert searches.maps == [ADDRESS]
    assert result.signals.address_validity.score == 30
    assert "does not resolve" in result.signals.address_validity.finding


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
