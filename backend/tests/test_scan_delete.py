import asyncio
import uuid

from fastapi.testclient import TestClient

from app.main import app
from app.models.db import Scan, async_session


async def _seed_scan(user_id: str) -> str:
    scan_id = uuid.uuid4().hex[:10]
    async with async_session() as session:
        session.add(
            Scan(
                id=scan_id,
                user_id=user_id,
                address="Test Address",
                city="Bengaluru",
                rent=15000,
                risk_score=10,
                risk_band="Low",
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
    return scan_id


def _signup(client: TestClient) -> str:
    email = f"delete-test-{uuid.uuid4().hex[:10]}@example.com"
    signup = client.post(
        "/api/v1/auth/signup",
        json={
            "email": email,
            "password": "correct-horse-1",
            "full_name": "Delete Test",
            "city": "Bengaluru",
        },
    )
    assert signup.status_code == 201
    return signup.json()["id"]


def test_delete_scan_removes_it_from_the_owners_list() -> None:
    with TestClient(app) as client:
        user_id = _signup(client)
        scan_id = asyncio.run(_seed_scan(user_id))

        response = client.delete(f"/api/v1/scans/{scan_id}")
        assert response.status_code == 204

        remaining = client.get("/api/v1/scans").json()
        assert all(item["scan_id"] != scan_id for item in remaining)


def test_delete_scan_owned_by_someone_else_is_not_allowed() -> None:
    with TestClient(app) as client:
        owner_id = _signup(client)
        scan_id = asyncio.run(_seed_scan(owner_id))

    with TestClient(app) as other_client:
        _signup(other_client)
        response = other_client.delete(f"/api/v1/scans/{scan_id}")
        assert response.status_code == 404

        # Still there — the other user's delete didn't touch it.
        async def _still_exists() -> bool:
            async with async_session() as session:
                return await session.get(Scan, scan_id) is not None

        assert asyncio.run(_still_exists())


def test_delete_scan_that_does_not_exist_returns_404() -> None:
    with TestClient(app) as client:
        _signup(client)
        response = client.delete("/api/v1/scans/does-not-exist")
        assert response.status_code == 404


def test_delete_scan_requires_authentication() -> None:
    with TestClient(app) as client:
        response = client.delete("/api/v1/scans/some-scan-id")
        assert response.status_code == 401
