from __future__ import annotations

from datetime import timedelta

import jwt

from app.core.config import settings
from app.core.security import (
    CUSTOMER_TOKEN_AUDIENCE,
    PLATFORM_TOKEN_AUDIENCE,
    create_access_token,
    create_platform_access_token,
    decode_access_token,
    decode_platform_access_token,
)


def test_customer_access_token_round_trip_uses_hs256_and_customer_audience() -> None:
    token = create_access_token("123", expires_delta=timedelta(minutes=5))
    header = jwt.get_unverified_header(token)
    payload = decode_access_token(token)

    assert settings.ALGORITHM == "HS256"
    assert header["alg"] == "HS256"
    assert payload is not None
    assert payload["sub"] == "123"
    assert payload["aud"] == CUSTOMER_TOKEN_AUDIENCE
    assert "exp" in payload


def test_platform_access_token_round_trip_uses_platform_audience() -> None:
    token = create_platform_access_token("42", expires_delta=timedelta(minutes=5))
    payload = decode_platform_access_token(token)

    assert payload is not None
    assert payload["sub"] == "42"
    assert payload["aud"] == PLATFORM_TOKEN_AUDIENCE


def test_customer_and_platform_tokens_are_not_interchangeable() -> None:
    customer_token = create_access_token("123")
    platform_token = create_platform_access_token("42")

    assert decode_platform_access_token(customer_token) is None
    assert decode_access_token(platform_token) is None


def test_invalid_access_tokens_return_none() -> None:
    assert decode_access_token("not-a-valid-jwt") is None
    assert decode_platform_access_token("not-a-valid-jwt") is None
