# ============================================================
# schemas/auth.py
# ------------------------------------------------------------
# Schemas specifically for login requests.
# ============================================================

from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str