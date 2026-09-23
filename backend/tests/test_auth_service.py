from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app.core.config import get_settings
from app.services import auth_service


def test_a_password_verifies_against_its_own_hash_but_not_another() -> None:
    hashed = auth_service.hash_password("correct-horse-1")
    assert auth_service.verify_password("correct-horse-1", hashed)
    assert not auth_service.verify_password("wrong-password", hashed)


def test_a_token_round_trips_to_the_user_id_that_created_it() -> None:
    token = auth_service.create_access_token("user-123")
    assert auth_service.decode_access_token(token) == "user-123"


def test_an_expired_token_decodes_to_none() -> None:
    settings = get_settings()
    expired = jwt.encode(
        {"sub": "user-123", "exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
        settings.jwt_secret,
        algorithm=auth_service.JWT_ALGORITHM,
    )
    assert auth_service.decode_access_token(expired) is None


def test_a_token_signed_with_a_different_secret_decodes_to_none() -> None:
    forged = jwt.encode(
        {"sub": "user-123", "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        "not-the-real-secret",
        algorithm=auth_service.JWT_ALGORITHM,
    )
    assert auth_service.decode_access_token(forged) is None


def test_a_malformed_token_decodes_to_none() -> None:
    assert auth_service.decode_access_token("not-a-jwt-at-all") is None


def test_creating_a_token_without_a_configured_secret_fails_closed(monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "jwt_secret", "")
    with pytest.raises(RuntimeError):
        auth_service.create_access_token("user-123")


def test_decoding_without_a_configured_secret_returns_none_rather_than_raising(monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "jwt_secret", "")
    assert auth_service.decode_access_token("anything") is None
