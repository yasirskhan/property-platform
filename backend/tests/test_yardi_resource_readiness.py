"""Yardi readiness must not imply financial migration is available."""
import pytest
from fastapi import HTTPException, Response
from app.models.platform_user import PlatformUserRole
from app.routers.yardi_migrations import yardi_resource_readiness
from test_yardi_migrations import _session, _platform_user


def test_readiness_is_read_only_and_blocks_financial_resources():
    db, engine = _session()
    try:
        actor = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        response = Response()
        result = yardi_resource_readiness(response=response, current_user=actor)
        assert result["provider"] == "YARDI"
        assert response.headers["cache-control"] == "no-store"
        assert "LEASE_OCCUPANCY" in result["supported_staging_only"]
        assert "GENERAL_LEDGER" in result["blocked_pending_source_contract"]
        assert result["financial_posting_enabled"] is False
        assert result["customer_records_created_by_upload"] is False
    finally:
        db.close()
        engine.dispose()
