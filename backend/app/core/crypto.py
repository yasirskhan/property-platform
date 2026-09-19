# ============================================================
# crypto.py
# ------------------------------------------------------------
# Encrypts/decrypts sensitive strings (SMTP passwords).
# Uses Fernet symmetric encryption.
# ============================================================

from cryptography.fernet import Fernet

from app.core.config import settings


def _fernet() -> Fernet:
    if not settings.ENCRYPTION_KEY or settings.ENCRYPTION_KEY == "PASTE_YOUR_GENERATED_KEY_HERE":
        raise RuntimeError(
            "ENCRYPTION_KEY is not set. Generate one and add it to config.py."
        )
    return Fernet(settings.ENCRYPTION_KEY.encode())


def encrypt(plain: str) -> str:
    """Encrypt a string, return base64-encoded ciphertext."""
    if plain is None:
        return ""
    return _fernet().encrypt(plain.encode()).decode()


def decrypt(ciphertext: str) -> str:
    """Decrypt a base64-encoded ciphertext back to plaintext."""
    if not ciphertext:
        return ""
    return _fernet().decrypt(ciphertext.encode()).decode()