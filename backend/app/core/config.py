# ============================================================
# config.py
# ------------------------------------------------------------
# This file stores all the settings for our backend.
# Think of it as the "control panel" for the app.
# ============================================================

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    Application settings.
    These values can be changed here or overridden by a .env file later.
    """

    # --- App Info ---
    APP_NAME: str = "Property Platform"
    APP_VERSION: str = "0.1.0"

    # --- Security ---
    # This secret key is used to sign login tokens (JWT).
    # We'll replace it with a stronger one when we deploy to a server.
    SECRET_KEY: str = "dev-secret-key-change-this-later"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # --- Database ---
    # SQLite file lives in the backend folder.
    # Later, when we move to a server, this becomes a PostgreSQL URL.
    DATABASE_URL: str = "sqlite:///./property_platform.db"

    # --- Stripe (leave blank until you have an account) ---
    STRIPE_SECRET_KEY: str = ""
    STRIPE_PUBLISHABLE_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_ENABLED: bool = False
    class Config:
        env_file = ".env"

# --- Email / SMTP ---
    # Modes: "console" (prints to log) or "smtp" (real email)
    EMAIL_MODE: str = "console"

    EMAIL_FROM: str = "noreply@propertyplatform.local"
    EMAIL_FROM_NAME: str = "Property Platform"

    SMTP_HOST: str = ""       # e.g. smtp.gmail.com
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_USE_TLS: bool = True

    FRONTEND_URL: str = "http://localhost:3000"

        # --- File uploads ---
    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_MB: int = 10
    
    # --- Encryption key for sensitive data (SMTP passwords) ---
    # Generate one with:
    #   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    ENCRYPTION_KEY: str = "t7RXJ_ZoNCs_EYYQ96BLQD3aLsoeGhKELpQvcfMzWH8="

# A single instance we can import anywhere in the app
settings = Settings()