import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.core.rate_limit import limiter
from app.main import app
from app.models.schemas import ScanResponse, ScanSignals, SignalResult

PHOTO = ("photos", ("room.jpg", b"jpeg-bytes", "image/jpeg"))


@pytest.fixture(autouse=True)
def _no_rate_limit():
    limiter.enabled = False
    yield
    limiter.enabled = True


@pytest.fixture
def scan_calls(monkeypatch) -> list[dict]:
    calls: list[dict] = []

    async def fake_run_scan(**kwargs):
        calls.append(kwargs)
        signal = SignalResult(score=0, max=10, finding="test")
        return ScanResponse(
            scan_id="abc",
            risk_score=0,
            risk_band="Low",
            signals=ScanSignals(image_reuse=signal, price_deviation=signal, address_validity=signal),
            evidence=[],
            created_at=datetime.now(timezone.utc),
            override_reason=kwargs["override_reason"],
        )

    monkeypatch.setattr("app.api.scan.scan_service.run_scan", fake_run_scan)
    return calls


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        signup = test_client.post(
            "/api/v1/auth/signup",
            json={
                "email": f"gate-{uuid.uuid4().hex[:10]}@example.com",
                "password": "correct-horse-1",
                "full_name": "Gate Test",
                "city": "Bengaluru",
            },
        )
        assert signup.status_code == 201
        yield test_client


def _scan(client: TestClient, rent: int, **extra):
    data = {"address": "Indiranagar", "city": "Bengaluru", "rent": str(rent), **extra}
    return client.post("/api/v1/scan", data=data, files=[PHOTO])


def test_an_impossible_rent_is_refused_before_any_work(client, scan_calls) -> None:
    for rent in (100, 5_000_001):
        response = _scan(client, rent, override_reason="I am certain this is the real rent")
        assert response.status_code == 422
        assert "isn't a possible rent" in response.json()["detail"]
    assert scan_calls == []


def test_an_unusual_rent_needs_a_reason(client, scan_calls) -> None:
    for extra in ({}, {"override_reason": "   "}, {"override_reason": "no"}):
        response = _scan(client, 1_500, **extra)
        assert response.status_code == 422
        assert "say why" in response.json()["detail"]
    assert scan_calls == []


def test_an_unusual_rent_with_a_reason_is_scanned_and_the_reason_kept(client, scan_calls) -> None:
    response = _scan(client, 1_500, override_reason="  Single room in a family home  ")

    assert response.status_code == 200
    assert response.json()["override_reason"] == "Single room in a family home"
    assert scan_calls[0]["override_reason"] == "Single room in a family home"


def test_a_reason_on_a_normal_rent_is_not_recorded(client, scan_calls) -> None:
    response = _scan(client, 25_000, override_reason="Not needed for this rent")

    assert response.status_code == 200
    assert scan_calls[0]["override_reason"] is None


def test_an_overlong_reason_is_refused(client, scan_calls) -> None:
    response = _scan(client, 1_500, override_reason="x" * 301)
    assert response.status_code == 422
    assert scan_calls == []


@pytest.mark.parametrize(
    "rent, status",
    [(25_000, "ok"), (1_500, "needs_confirmation"), (600_000, "needs_confirmation"), (50, "rejected")],
)
def test_precheck_reports_the_gate_decision(client, rent: int, status: str) -> None:
    response = client.post("/api/v1/scan/precheck", json={"rent": rent})
    assert response.status_code == 200
    assert response.json()["status"] == status
    assert (response.json()["issues"] == []) == (status == "ok")


def test_precheck_requires_login() -> None:
    with TestClient(app) as anonymous:
        assert anonymous.post("/api/v1/scan/precheck", json={"rent": 25_000}).status_code == 401
