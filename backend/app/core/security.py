# ============================================================
# security.py
# ------------------------------------------------------------
# Password hashing plus strict JWT audience separation.
#
# Customer users and internal platform users are separate identity
# domains. Their JWTs are never interchangeable because each decoder
# requires its own audience claim.
# ============================================================

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import jwt
from passlib.context import CryptContext

from app.core.config import settings


CUSTOMER_TOKEN_AUDIENCE = "customer"
PLATFORM_TOKEN_AUDIENCE = "platform"

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Turn a plain password into a secure hash."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Check if a plain password matches a stored hash."""
    return pwd_context.verify(plain_password, hashed_password)


def _create_token(
    subject: str | Any,
    audience: str,
    expires_delta: Optional[timedelta] = None,
) -> str:
    now = datetime.now(timezone.utc)
    expire = now + (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload = {
        "sub": str(subject),
        "aud": audience,
        "iat": now,
        "exp": expire,
    }
    return jwt.encode(
        payload,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )


def _decode_token(token: str, audience: str) -> Optional[dict]:
    try:
        return jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
            audience=audience,
            options={"require": ["sub", "aud", "exp"]},
        )
    except jwt.InvalidTokenError:
        return None


def create_access_token(
    subject: str | Any,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create a customer-side access token."""
    return _create_token(subject, CUSTOMER_TOKEN_AUDIENCE, expires_delta)


def decode_access_token(token: str) -> Optional[dict]:
    """Decode only customer-side tokens."""
    return _decode_token(token, CUSTOMER_TOKEN_AUDIENCE)


def create_platform_access_token(
    subject: str | Any,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create an internal platform-side access token."""
    return _create_token(subject, PLATFORM_TOKEN_AUDIENCE, expires_delta)


def decode_platform_access_token(token: str) -> Optional[dict]:
    """Decode only internal platform-side tokens."""
    return _decode_token(token, PLATFORM_TOKEN_AUDIENCE)
