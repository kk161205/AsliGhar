from fastapi.testclient import TestClient

from app.main import app


def test_health_ok(monkeypatch) -> None:
    async def fake_check_dependencies() -> dict:
        return {"serpapi": True, "groq": True}

    monkeypatch.setattr("app.main.check_dependencies", fake_check_dependencies)
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "dependencies": {"serpapi": True, "groq": True},
    }


def test_health_degraded_when_a_key_is_bad(monkeypatch) -> None:
    async def fake_check_dependencies() -> dict:
        return {"serpapi": True, "groq": False}

    monkeypatch.setattr("app.main.check_dependencies", fake_check_dependencies)
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "degraded",
        "dependencies": {"serpapi": True, "groq": False},
    }
