# ============================================================
# config.py
# ------------------------------------------------------------
# Application settings. Local development has safe-to-share defaults;
# staging/production must provide real secrets through environment.
# ============================================================

from cryptography.fernet import Fernet
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_SECRET_KEY = "dev-secret-key-change-this-later"
DEV_ENCRYPTION_KEY = "t7RXJ_ZoNCs_EYYQ96BLQD3aLsoeGhKELpQvcfMzWH8="


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Environment / app info ---
    ENVIRONMENT: str = "development"
    APP_NAME: str = "Property Platform"
    APP_VERSION: str = "0.1.0"

    # --- Security ---
    SECRET_KEY: str = DEV_SECRET_KEY
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24

    # --- Database ---
    DATABASE_URL: str = "sqlite:///./property_platform.db"

    # --- Stripe ---
    STRIPE_SECRET_KEY: str = ""
    STRIPE_PUBLISHABLE_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_ENABLED: bool = False

    # --- Email / SMTP ---
    EMAIL_MODE: str = "console"
    EMAIL_FROM: str = "noreply@propertyplatform.local"
    EMAIL_FROM_NAME: str = "Property Platform"
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_USE_TLS: bool = True

    FRONTEND_URL: str = "http://localhost:3000"

    # --- File uploads ---
    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_MB: int = 10

    # --- Encryption key for sensitive data ---
    ENCRYPTION_KEY: str = DEV_ENCRYPTION_KEY

    @model_validator(mode="after")
    def reject_development_secrets_outside_development(self) -> "Settings":
        env = self.ENVIRONMENT.strip().lower()
        if env not in {"staging", "production"}:
            return self

        if self.SECRET_KEY == DEV_SECRET_KEY or len(self.SECRET_KEY) < 32:
            raise ValueError(
                f"{env} requires a non-default SECRET_KEY of at least 32 characters"
            )

        if self.ENCRYPTION_KEY == DEV_ENCRYPTION_KEY:
            raise ValueError(f"{env} requires a non-default ENCRYPTION_KEY")
        try:
            Fernet(self.ENCRYPTION_KEY.encode("utf-8"))
        except Exception as exc:
            raise ValueError(f"{env} ENCRYPTION_KEY must be a valid Fernet key") from exc

        return self


settings = Settings()
