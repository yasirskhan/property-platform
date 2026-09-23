# ============================================================
# security.py
# ------------------------------------------------------------
# Handles two things:
#
#   1. Password hashing — we NEVER store raw passwords.
#      We store a hash, which can't be reversed.
#
#   2. JWT tokens — after login, the user gets a signed token.
#      They send it with every request to prove who they are.
# ============================================================

from datetime import datetime, timedelta
from typing import Any, Optional

import jwt
from passlib.context import CryptContext

from app.core.config import settings


# ------------------------------------------------------------
# PASSWORD HASHING
# ------------------------------------------------------------
# bcrypt is a strong, industry-standard hashing algorithm.
# deprecated="auto" means older algorithms still verify but
# new hashes always use bcrypt.
# ------------------------------------------------------------
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Turn a plain password into a secure hash."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Check if a plain password matches a stored hash."""
    return pwd_context.verify(plain_password, hashed_password)


# ------------------------------------------------------------
# JWT TOKENS
# ------------------------------------------------------------
def create_access_token(
    subject: str | Any,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Create a signed JWT token.
    'subject' is usually the user's ID (as a string).
    """
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )

    to_encode = {
        "sub": str(subject),
        "exp": expire,
    }

    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict]:
    """
    Decode a JWT token. Returns the payload dict, or None if invalid.
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        return payload
    except jwt.InvalidTokenError:
        return None