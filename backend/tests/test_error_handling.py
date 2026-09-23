from fastapi.testclient import TestClient

from app.main import app
from app.services import scan_service


def test_an_unhandled_exception_returns_a_parseable_json_500_not_a_bare_crash(monkeypatch) -> None:
    # Regression test: a real production request came back as a plain
    # "Request failed with status 500" with no JSON body, which is what
    # Starlette's default handler does for an unhandled exception (and is
    # what the frontend's ApiError falls back to when response.json() fails
    # on the response). Any surviving unexpected exception must still answer
    # with the same {"detail": ...} shape every other error uses.
    async def broken(_scan_id: str):
        raise RuntimeError("something unexpected")

    monkeypatch.setattr(scan_service, "get_scan", broken)

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/api/v1/scan/doesnotmatter")

    assert response.status_code == 500
    assert response.json() == {"detail": "Something went wrong on our end. Please try again."}


def test_a_normal_404_is_unaffected_by_the_catch_all_handler() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/scan/no-such-scan-id")

    assert response.status_code == 404
    assert response.json() == {"detail": "Scan not found."}
