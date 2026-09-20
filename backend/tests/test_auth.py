import uuid

from fastapi.testclient import TestClient

from app.main import app


def _unique_email() -> str:
    return f"test-{uuid.uuid4().hex[:10]}@example.com"


def _signup_payload(email: str, password: str = "correct-horse-1") -> dict:
    return {
        "email": email,
        "password": password,
        "full_name": "Test User",
        "city": "Bengaluru",
    }


def test_signup_then_me_returns_the_new_user_with_profile_fields() -> None:
    email = _unique_email()
    with TestClient(app) as client:
        signup_response = client.post("/api/v1/auth/signup", json=_signup_payload(email))
        assert signup_response.status_code == 201
        body = signup_response.json()
        assert body["email"] == email
        assert body["full_name"] == "Test User"
        assert body["city"] == "Bengaluru"
        assert "access_token" in signup_response.cookies

        me_response = client.get("/api/v1/auth/me")
        assert me_response.status_code == 200
        assert me_response.json()["full_name"] == "Test User"


def test_signup_without_full_name_or_city_is_rejected() -> None:
    email = _unique_email()
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/signup", json={"email": email, "password": "correct-horse-1"}
        )
    assert response.status_code == 422


def test_signup_with_existing_email_is_rejected() -> None:
    email = _unique_email()
    with TestClient(app) as client:
        first = client.post("/api/v1/auth/signup", json=_signup_payload(email))
        assert first.status_code == 201

        second = client.post(
            "/api/v1/auth/signup", json=_signup_payload(email, password="a-different-pw")
        )
        assert second.status_code == 409


def test_login_with_wrong_password_is_rejected() -> None:
    email = _unique_email()
    with TestClient(app) as client:
        client.post("/api/v1/auth/signup", json=_signup_payload(email))
        client.cookies.clear()

        response = client.post(
            "/api/v1/auth/login", json={"email": email, "password": "wrong-password"}
        )
        assert response.status_code == 401


def test_login_with_correct_password_succeeds() -> None:
    email = _unique_email()
    with TestClient(app) as client:
        client.post("/api/v1/auth/signup", json=_signup_payload(email))
        client.cookies.clear()

        response = client.post(
            "/api/v1/auth/login", json={"email": email, "password": "correct-horse-1"}
        )
        assert response.status_code == 200
        assert "access_token" in response.cookies


def test_me_without_a_session_is_unauthorized() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/auth/me")
    assert response.status_code == 401


def test_scans_endpoint_requires_auth() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/scans")
    assert response.status_code == 401


def test_logout_clears_the_session() -> None:
    email = _unique_email()
    with TestClient(app) as client:
        client.post("/api/v1/auth/signup", json=_signup_payload(email))
        assert client.get("/api/v1/auth/me").status_code == 200

        logout_response = client.post("/api/v1/auth/logout")
        assert logout_response.status_code == 200

        assert client.get("/api/v1/auth/me").status_code == 401


def test_scans_list_is_scoped_to_the_logged_in_user() -> None:
    email_a = _unique_email()
    email_b = _unique_email()

    with TestClient(app) as client:
        client.post("/api/v1/auth/signup", json=_signup_payload(email_a))
        user_a_scans = client.get("/api/v1/scans")
        assert user_a_scans.status_code == 200
        assert user_a_scans.json() == []  # brand-new user, no scans yet

        client.cookies.clear()
        client.post("/api/v1/auth/signup", json=_signup_payload(email_b))
        user_b_scans = client.get("/api/v1/scans")
        assert user_b_scans.status_code == 200
        assert user_b_scans.json() == []
