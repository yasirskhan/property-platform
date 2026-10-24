"""Organization-aware database routing.

The platform starts in one physical region, but all org-aware routing goes
through this layer so adding regional databases later does not require
rewriting business services. Unknown regions fail closed.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.core.database import SessionLocal


class RegionRoutingError(RuntimeError):
    """Raised when an organization cannot be routed safely."""


def _normalize_region(value: str | None) -> str:
    region = (value or "").strip().lower()
    if not region:
        raise RegionRoutingError("Organization data_region is required")
    return region


def effective_data_region(organization: Any, property_obj: Any | None = None) -> str:
    """Return property override when present, otherwise the org region."""
    property_region = getattr(property_obj, "data_region", None) if property_obj else None
    if property_region:
        return _normalize_region(property_region)
    return _normalize_region(getattr(organization, "data_region", None))


def _configured_region_urls() -> dict[str, str]:
    raw = (settings.REGIONAL_DATABASE_URLS_JSON or "{}").strip()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RegionRoutingError("REGIONAL_DATABASE_URLS_JSON is invalid JSON") from exc

    if not isinstance(parsed, dict):
        raise RegionRoutingError("REGIONAL_DATABASE_URLS_JSON must be a JSON object")

    result: dict[str, str] = {}
    for key, value in parsed.items():
        if not isinstance(key, str) or not isinstance(value, str) or not value.strip():
            raise RegionRoutingError(
                "REGIONAL_DATABASE_URLS_JSON values must be non-empty URL strings"
            )
        result[_normalize_region(key)] = value.strip()
    return result


def get_database_url_for_region(region: str) -> str:
    normalized = _normalize_region(region)
    primary = _normalize_region(settings.PRIMARY_DATA_REGION)

    if normalized == primary:
        return settings.DATABASE_URL

    configured = _configured_region_urls()
    url = configured.get(normalized)
    if url is None:
        raise RegionRoutingError(
            f"No database is configured for data region '{normalized}'"
        )
    return url


@lru_cache(maxsize=16)
def _regional_session_factory(database_url: str) -> sessionmaker:
    engine = create_engine(
        database_url,
        connect_args={"check_same_thread": False}
        if database_url.startswith("sqlite")
        else {},
        echo=False,
    )
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def clear_region_engine_cache() -> None:
    """Test/deployment helper after routing configuration changes."""
    _regional_session_factory.cache_clear()


def get_db_for_org(organization: Any, property_obj: Any | None = None) -> Session:
    """Open a session for the org/property effective region.

    Caller owns and must close the returned session. The primary region uses
    the application's normal SessionLocal. Secondary regions use explicitly
    configured database URLs. There is no fallback for unknown regions.
    """
    region = effective_data_region(organization, property_obj)
    primary = _normalize_region(settings.PRIMARY_DATA_REGION)

    if region == primary:
        return SessionLocal()

    database_url = get_database_url_for_region(region)
    return _regional_session_factory(database_url)()
