import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.core.rate_limit import limiter
from app.main import app
from app.models.schemas import ScanResponse, ScanSignals, SignalResult

PHOTO = ("photos", ("room.jpg", b"\xff\xd8\xffjpeg-bytes", "image/jpeg"))


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


# --- optional inputs -----------------------------------------------------------------------


def test_a_valid_phone_and_link_reach_the_scan_in_normalized_form(client, scan_calls) -> None:
    response = _scan(client, 25_000, phone="+91 98765 43210", listing_url="https://www.olx.in/item/x-iid-1")

    assert response.status_code == 200
    assert scan_calls[0]["phone"] == "9876543210"
    assert scan_calls[0]["listing_url"] == "https://www.olx.in/item/x-iid-1"


def test_the_optional_inputs_can_be_left_out_or_blank(client, scan_calls) -> None:
    assert _scan(client, 25_000).status_code == 200
    assert _scan(client, 25_000, phone="  ", listing_url="").status_code == 200
    assert scan_calls[0]["phone"] is None and scan_calls[0]["listing_url"] is None


@pytest.mark.parametrize("phone", ["12345", "0000000000", "98765abcde", "1234567890"])
def test_an_invalid_phone_is_refused_before_any_work(client, scan_calls, phone: str) -> None:
    response = _scan(client, 25_000, phone=phone)
    assert response.status_code == 422
    assert "10-digit" in response.json()["detail"]
    assert scan_calls == []


@pytest.mark.parametrize(
    "url", ["not a link", "ftp://example.com/x", "javascript:alert(1)", "https://", "https://x.com/" + "a" * 600]
)
def test_an_invalid_listing_link_is_refused_before_any_work(client, scan_calls, url: str) -> None:
    response = _scan(client, 25_000, listing_url=url)
    assert response.status_code == 422
    assert "web address" in response.json()["detail"]
    assert scan_calls == []


# --- photo formats --------------------------------------------------------------------------


def test_a_webp_photo_is_accepted(client, scan_calls) -> None:
    webp_bytes = b"RIFF\x00\x00\x00\x00WEBPwebp-bytes"
    webp_photo = ("photos", ("room.webp", webp_bytes, "image/webp"))
    data = {"address": "Indiranagar", "city": "Bengaluru", "rent": "25000"}
    response = client.post("/api/v1/scan", data=data, files=[webp_photo])

    assert response.status_code == 200
    assert scan_calls[0]["photos"][0][1] == ".webp"


def test_an_unsupported_photo_format_is_refused_before_any_work(client, scan_calls) -> None:
    gif_photo = ("photos", ("room.gif", b"gif-bytes", "image/gif"))
    data = {"address": "Indiranagar", "city": "Bengaluru", "rent": "25000"}
    response = client.post("/api/v1/scan", data=data, files=[gif_photo])

    assert response.status_code == 422
    assert "Unsupported photo type" in response.json()["detail"]


def test_a_photo_whose_bytes_dont_match_its_declared_type_is_refused(client, scan_calls) -> None:
    # Content-Type header says JPEG, but the bytes aren't a JPEG signature.
    fake_photo = ("photos", ("room.jpg", b"not-actually-a-jpeg", "image/jpeg"))
    data = {"address": "Indiranagar", "city": "Bengaluru", "rent": "25000"}
    response = client.post("/api/v1/scan", data=data, files=[fake_photo])

    assert response.status_code == 422
    assert "isn't a valid image file" in response.json()["detail"]
    assert scan_calls == []


# --- photo count / size bounds ---------------------------------------------------------------


def test_more_than_five_photos_is_refused_before_any_work(client, scan_calls) -> None:
    data = {"address": "Indiranagar", "city": "Bengaluru", "rent": "25000"}
    response = client.post("/api/v1/scan", data=data, files=[PHOTO] * 6)

    assert response.status_code == 422
    assert "between 1 and 5 photos" in response.json()["detail"]
    assert scan_calls == []


def test_an_oversized_photo_is_refused_before_any_work(client, scan_calls) -> None:
    oversized = ("photos", ("room.jpg", b"\xff\xd8\xff" + b"x" * (5 * 1024 * 1024), "image/jpeg"))
    data = {"address": "Indiranagar", "city": "Bengaluru", "rent": "25000"}
    response = client.post("/api/v1/scan", data=data, files=[oversized])

    assert response.status_code == 422
    assert "exceeds 5MB" in response.json()["detail"]
    assert scan_calls == []
