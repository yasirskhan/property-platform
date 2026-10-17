from __future__ import annotations

from types import SimpleNamespace

import pytest
from sqlalchemy import text

from app.core.config import settings
from app.core.regional_database import (
    RegionRoutingError,
    clear_region_engine_cache,
    effective_data_region,
    get_database_url_for_region,
    get_db_for_org,
)


@pytest.fixture(autouse=True)
def reset_region_cache() -> None:
    clear_region_engine_cache()
    yield
    clear_region_engine_cache()


def test_primary_region_routes_to_normal_database(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "PRIMARY_DATA_REGION", "us-east-1")
    org = SimpleNamespace(data_region="us-east-1")

    assert get_database_url_for_region(org.data_region) == settings.DATABASE_URL

    db = get_db_for_org(org)
    try:
        assert db.execute(text("SELECT 1")).scalar_one() == 1
    finally:
        db.close()


def test_property_region_override_wins() -> None:
    org = SimpleNamespace(data_region="us-east-1")
    property_obj = SimpleNamespace(data_region="eu-west-1")

    assert effective_data_region(org, property_obj) == "eu-west-1"


def test_unknown_secondary_region_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "PRIMARY_DATA_REGION", "us-east-1")
    monkeypatch.setattr(settings, "REGIONAL_DATABASE_URLS_JSON", "{}")

    with pytest.raises(RegionRoutingError, match="No database is configured"):
        get_db_for_org(SimpleNamespace(data_region="eu-west-1"))


def test_configured_secondary_region_gets_its_own_session(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    secondary = tmp_path / "eu.db"
    monkeypatch.setattr(settings, "PRIMARY_DATA_REGION", "us-east-1")
    monkeypatch.setattr(
        settings,
        "REGIONAL_DATABASE_URLS_JSON",
        '{"eu-west-1":"sqlite:///' + secondary.as_posix() + '"}',
    )

    db = get_db_for_org(SimpleNamespace(data_region="eu-west-1"))
    try:
        assert db.execute(text("SELECT 1")).scalar_one() == 1
    finally:
        db.close()


def test_invalid_region_mapping_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "REGIONAL_DATABASE_URLS_JSON", "[]")
    with pytest.raises(RegionRoutingError, match="must be a JSON object"):
        get_database_url_for_region("eu-west-1")
