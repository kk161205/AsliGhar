import time

import httpx
import pytest

from app.services import serpapi_client


class _FakeResponse:
    def __init__(self, json_data: dict):
        self._json_data = json_data

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict:
        return self._json_data


class _FakeAsyncClient:
    """Stands in for httpx.AsyncClient: returns queued responses/exceptions in order."""

    def __init__(self, calls: list, queue: list):
        self._calls = calls
        self._queue = queue

    async def __aenter__(self) -> "_FakeAsyncClient":
        return self

    async def __aexit__(self, *exc) -> bool:
        return False

    async def get(self, url: str, params: dict | None = None) -> _FakeResponse:
        self._calls.append(params)
        result = self._queue.pop(0)
        if isinstance(result, Exception):
            raise result
        return _FakeResponse(result)


@pytest.fixture(autouse=True)
def _clean_cache():
    serpapi_client._cache.clear()
    yield
    serpapi_client._cache.clear()


def _fake_client_factory(calls: list, queue: list):
    def factory(*, timeout=None):
        return _FakeAsyncClient(calls, queue)

    return factory


async def test_a_single_timeout_is_retried_once_and_then_succeeds(monkeypatch) -> None:
    calls: list = []
    queue = [httpx.TimeoutException("slow"), {"organic_results": ["ok"]}]
    monkeypatch.setattr(serpapi_client.httpx, "AsyncClient", _fake_client_factory(calls, queue))

    result = await serpapi_client._get("google", {"q": "retry-once"}, cache_ttl_seconds=60)

    assert result == {"organic_results": ["ok"]}
    assert len(calls) == 2


async def test_exhausting_retries_raises_the_timeout(monkeypatch) -> None:
    calls: list = []
    queue = [httpx.TimeoutException("slow"), httpx.TimeoutException("still slow")]
    monkeypatch.setattr(serpapi_client.httpx, "AsyncClient", _fake_client_factory(calls, queue))

    with pytest.raises(httpx.TimeoutException):
        await serpapi_client._get("google", {"q": "always-times-out"}, cache_ttl_seconds=60)

    assert len(calls) == 2


async def test_an_http_status_error_is_not_retried(monkeypatch) -> None:
    calls: list = []
    request = httpx.Request("GET", "https://serpapi.com/search")
    response = httpx.Response(status_code=500, request=request)
    error = httpx.HTTPStatusError("server error", request=request, response=response)
    queue = [error]
    monkeypatch.setattr(serpapi_client.httpx, "AsyncClient", _fake_client_factory(calls, queue))

    with pytest.raises(httpx.HTTPStatusError):
        await serpapi_client._get("google", {"q": "server-error"}, cache_ttl_seconds=60)

    assert len(calls) == 1


async def test_a_second_call_with_the_same_key_hits_the_cache(monkeypatch) -> None:
    calls: list = []
    queue = [{"organic_results": ["first"]}]
    monkeypatch.setattr(serpapi_client.httpx, "AsyncClient", _fake_client_factory(calls, queue))

    first = await serpapi_client._get("google", {"q": "cache-me"}, cache_ttl_seconds=60)
    second = await serpapi_client._get("google", {"q": "cache-me"}, cache_ttl_seconds=60)

    assert first == second == {"organic_results": ["first"]}
    assert len(calls) == 1


async def test_an_expired_cache_entry_triggers_a_fresh_call(monkeypatch) -> None:
    calls: list = []
    queue = [{"organic_results": ["v1"]}, {"organic_results": ["v2"]}]
    monkeypatch.setattr(serpapi_client.httpx, "AsyncClient", _fake_client_factory(calls, queue))

    first = await serpapi_client._get("google", {"q": "expiring"}, cache_ttl_seconds=0.01)
    time.sleep(0.05)
    second = await serpapi_client._get("google", {"q": "expiring"}, cache_ttl_seconds=0.01)

    assert first == {"organic_results": ["v1"]}
    assert second == {"organic_results": ["v2"]}
    assert len(calls) == 2


def test_purge_expired_cache_drops_only_entries_past_their_own_ttl() -> None:
    now = time.monotonic()
    serpapi_client._cache["fresh"] = (now, 60.0, {"a": 1})
    serpapi_client._cache["stale"] = (now - 120.0, 60.0, {"b": 2})

    serpapi_client.purge_expired_cache()

    assert "fresh" in serpapi_client._cache
    assert "stale" not in serpapi_client._cache
