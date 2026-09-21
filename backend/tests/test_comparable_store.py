import uuid

from app.services import comparable_store
from app.services.evidence import Comparable


def _comparable(rent: int, link: str) -> Comparable:
    return Comparable(rent, "3 BHK for rent", link, "3 BHK for rent. rent text")


async def test_saved_comparables_are_loaded_for_the_same_city_and_home_size() -> None:
    city = f"Teststore{uuid.uuid4().hex[:8]}"
    tag = uuid.uuid4().hex
    await comparable_store.save(
        city,
        "3BHK",
        [_comparable(20_000, f"https://example.com/{tag}/a"), _comparable(22_000, f"https://example.com/{tag}/b")],
    )

    loaded = await comparable_store.load(city, "3BHK")

    assert sorted(item.rent for item in loaded) == [20_000, 22_000]
    assert all(item.earlier for item in loaded)
    assert await comparable_store.load(city, "2BHK") == []
    assert await comparable_store.load("Elsewhere" + city, "3BHK") == []


async def test_a_page_is_stored_once_and_an_unknown_home_size_stores_nothing() -> None:
    city = f"Teststore{uuid.uuid4().hex[:8]}"
    link = f"https://example.com/{uuid.uuid4().hex}"

    await comparable_store.save(city, "3BHK", [_comparable(20_000, link)])
    await comparable_store.save(city, "3BHK", [_comparable(20_000, link)])
    await comparable_store.save(city, None, [_comparable(9_000, link + "-x")])

    assert len(await comparable_store.load(city, "3BHK")) == 1
    assert await comparable_store.load(city, None) == []


async def test_a_database_problem_never_raises(monkeypatch) -> None:
    def broken():
        raise RuntimeError("db down")

    monkeypatch.setattr(comparable_store, "async_session", broken)

    assert await comparable_store.load("Agra", "3BHK") == []
    await comparable_store.save("Agra", "3BHK", [_comparable(20_000, "https://example.com/z")])
