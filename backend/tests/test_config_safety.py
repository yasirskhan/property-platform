from __future__ import annotations

import pytest
from cryptography.fernet import Fernet
from pydantic import ValidationError

from app.core.config import DEV_ENCRYPTION_KEY, DEV_SECRET_KEY, Settings


def test_development_defaults_remain_available_locally() -> None:
    settings = Settings(
        _env_file=None,
        ENVIRONMENT="development",
        SECRET_KEY=DEV_SECRET_KEY,
        ENCRYPTION_KEY=DEV_ENCRYPTION_KEY,
    )
    assert settings.ENVIRONMENT == "development"


def test_staging_refuses_default_secrets() -> None:
    with pytest.raises(ValidationError, match="non-default SECRET_KEY"):
        Settings(
            _env_file=None,
            ENVIRONMENT="staging",
            SECRET_KEY=DEV_SECRET_KEY,
            ENCRYPTION_KEY=DEV_ENCRYPTION_KEY,
        )


def test_production_accepts_strong_distinct_secrets() -> None:
    key = Fernet.generate_key().decode("utf-8")
    settings = Settings(
        _env_file=None,
        ENVIRONMENT="production",
        SECRET_KEY="a-strong-production-jwt-secret-that-is-not-default",
        ENCRYPTION_KEY=key,
    )
    assert settings.ENVIRONMENT == "production"
