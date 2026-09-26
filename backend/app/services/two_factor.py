from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import struct
import time
from datetime import datetime
from urllib.parse import quote

from cryptography.fernet import Fernet
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.user import User
from app.models.user_two_factor import UserTwoFactorSettings

TOTP_PERIOD_SECONDS = 30
TOTP_DIGITS = 6
RECOVERY_CODE_COUNT = 10


def _fernet() -> Fernet:
    return Fernet(settings.ENCRYPTION_KEY.encode("utf-8"))


def generate_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def encrypt_secret(secret: str) -> str:
    return _fernet().encrypt(secret.encode("utf-8")).decode("ascii")


def decrypt_secret(ciphertext: str) -> str:
    return _fernet().decrypt(ciphertext.encode("ascii")).decode("utf-8")


def _secret_bytes(secret: str) -> bytes:
    padded = secret + ("=" * ((8 - len(secret) % 8) % 8))
    return base64.b32decode(padded, casefold=True)


def totp_code(secret: str, *, at_time: int | None = None) -> str:
    now = int(time.time() if at_time is None else at_time)
    counter = now // TOTP_PERIOD_SECONDS
    digest = hmac.new(
        _secret_bytes(secret),
        struct.pack(">Q", counter),
        hashlib.sha1,
    ).digest()
    offset = digest[-1] & 0x0F
    binary = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(binary % (10**TOTP_DIGITS)).zfill(TOTP_DIGITS)


def verify_totp(secret: str, code: str, *, at_time: int | None = None, window: int = 1) -> bool:
    normalized = "".join(ch for ch in str(code) if ch.isdigit())
    if len(normalized) != TOTP_DIGITS:
        return False
    now = int(time.time() if at_time is None else at_time)
    for step in range(-window, window + 1):
        candidate = totp_code(secret, at_time=now + step * TOTP_PERIOD_SECONDS)
        if hmac.compare_digest(candidate, normalized):
            return True
    return False


def _recovery_hash(code: str) -> str:
    normalized = code.strip().upper().replace("-", "")
    return hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        normalized.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def generate_recovery_codes() -> tuple[list[str], list[str]]:
    codes = []
    for _ in range(RECOVERY_CODE_COUNT):
        raw = secrets.token_hex(6).upper()
        codes.append(f"{raw[:6]}-{raw[6:]}")
    return codes, [_recovery_hash(code) for code in codes]


def otpauth_uri(secret: str, user: User) -> str:
    issuer = settings.APP_NAME or "Property Platform"
    label = f"{issuer}:{user.email}"
    return (
        f"otpauth://totp/{quote(label)}"
        f"?secret={secret}&issuer={quote(issuer)}&algorithm=SHA1&digits={TOTP_DIGITS}&period={TOTP_PERIOD_SECONDS}"
    )


def get_settings(db: Session, user_id: int) -> UserTwoFactorSettings | None:
    return db.query(UserTwoFactorSettings).filter(UserTwoFactorSettings.user_id == user_id).first()


def begin_setup(db: Session, *, user: User) -> tuple[UserTwoFactorSettings, str, list[str]]:
    if user.organization_id is None:
        raise ValueError("User has no organization.")
    secret = generate_secret()
    codes, hashes = generate_recovery_codes()
    row = get_settings(db, user.id)
    if row is None:
        row = UserTwoFactorSettings(
            user_id=user.id,
            organization_id=user.organization_id,
            secret_ciphertext=encrypt_secret(secret),
            recovery_code_hashes=hashes,
            is_enabled=False,
        )
        db.add(row)
    else:
        row.organization_id = user.organization_id
        row.secret_ciphertext = encrypt_secret(secret)
        row.recovery_code_hashes = hashes
        row.is_enabled = False
        row.verified_at = None
    db.flush()
    return row, secret, codes


def enable(db: Session, *, user: User, code: str) -> UserTwoFactorSettings:
    row = get_settings(db, user.id)
    if row is None:
        raise ValueError("Start two-step setup first.")
    if not verify_totp(decrypt_secret(row.secret_ciphertext), code):
        raise ValueError("Invalid verification code.")
    row.is_enabled = True
    row.verified_at = datetime.utcnow()
    db.flush()
    return row


def verify_login_code(db: Session, *, row: UserTwoFactorSettings, code: str) -> bool:
    if not row.is_enabled:
        return False
    if verify_totp(decrypt_secret(row.secret_ciphertext), code):
        return True
    target = _recovery_hash(code)
    hashes = list(row.recovery_code_hashes or [])
    for index, stored in enumerate(hashes):
        if hmac.compare_digest(stored, target):
            hashes.pop(index)
            row.recovery_code_hashes = hashes
            db.flush()
            return True
    return False


def disable(db: Session, *, row: UserTwoFactorSettings) -> None:
    row.is_enabled = False
    row.recovery_code_hashes = []
    row.verified_at = None
    db.delete(row)
    db.flush()
