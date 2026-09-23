from __future__ import annotations

from datetime import timedelta

import jwt

from app.core.config import settings
from app.core.security import create_access_token, decode_access_token


def test_access_token_round_trip_uses_configured_hs256() -> None:
    token = create_access_token("123", expires_delta=timedelta(minutes=5))

    header = jwt.get_unverified_header(token)
    payload = decode_access_token(token)

    assert settings.ALGORITHM == "HS256"
    assert header["alg"] == "HS256"
    assert payload is not None
    assert payload["sub"] == "123"
    assert "exp" in payload


def test_invalid_access_token_returns_none() -> None:
    assert decode_access_token("not-a-valid-jwt") is None
