# ============================================================
# schemas/token.py
# ------------------------------------------------------------
# Defines the shape of authentication tokens returned
# to the client after a successful login.
# ============================================================

from pydantic import BaseModel


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    sub: str | None = None   # subject (usually user id or email)
    exp: int | None = None   # expiry timestamp