import uuid
from datetime import datetime

from fastapi.testclient import TestClient

from app.main import app
from app.models.db import Scan, async_session


async def _seed_scan(user_id: str, risk_score: int, risk_band: str) -> None:
    async with async_session() as session:
        session.add(
            Scan(
                id=uuid.uuid4().hex[:10],
                user_id=user_id,
                address="Test Address",
                city="Bengaluru",
                rent=15000,
                risk_score=risk_score,
                risk_band=risk_band,
                signals_json={
                    "image_reuse": {"score": 0, "max": 40, "finding": "test"},
                    "price_deviation": {"score": 0, "max": 30, "finding": "test"},
                    "address_validity": {"score": 0, "max": 30, "finding": "test"},
                },
                evidence_json=[],
                ai_summary=None,
            )
        )
        await session.commit()


def test_list_scans_returns_this_users_scans_ordered_newest_first(monkeypatch) -> None:
    email = f"list-test-{uuid.uuid4().hex[:10]}@example.com"

    with TestClient(app) as client:
        signup = client.post(
            "/api/v1/auth/signup",
            json={
                "email": email,
                "password": "correct-horse-1",
                "full_name": "List Test",
                "city": "Bengaluru",
            },
        )
        assert signup.status_code == 201
        user_id = signup.json()["id"]

        import asyncio

        asyncio.run(_seed_scan(user_id, risk_score=10, risk_band="Low"))
        asyncio.run(_seed_scan(user_id, risk_score=60, risk_band="High"))

        response = client.get("/api/v1/scans")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2

    for item in body:
        assert {"scan_id", "address", "city", "risk_score", "risk_band", "created_at"} <= item.keys()
        assert 0 <= item["risk_score"] <= 100
        assert item["risk_band"] in {"Low", "Moderate", "High", "Severe"}

    # Newest first — the "High" scan was seeded second.
    assert body[0]["risk_band"] == "High"
    assert body[1]["risk_band"] == "Low"

    timestamps = [datetime.fromisoformat(item["created_at"]) for item in body]
    assert timestamps == sorted(timestamps, reverse=True)
