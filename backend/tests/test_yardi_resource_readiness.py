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
        assert result["customer_business_mutation_enabled"] is False
        assert result["official_api_adapter_enabled"] is False
        assert result["lease_relationship_preview_enabled"] is True
        capabilities = result["resource_capabilities"]
        assert set(capabilities) == set(result["supported_staging_only"])
        assert set(result["existing_target_metadata_binding_resources"]) == (
            set(capabilities) - {"LEASE_OCCUPANCY"}
        )
        assert all(item["csv_xlsx_staging"] for item in capabilities.values())
        assert all(
            item["customer_record_creation_enabled"] is False
            for item in capabilities.values()
        )
        assert all(
            capabilities[resource]["reviewed_existing_target_binding"] is True
            for resource in ("PROPERTIES", "UNITS", "OWNERS", "VENDORS", "TENANTS")
        )
        assert capabilities["UNITS"]["requires_same_run_parent_property"] is True
        assert capabilities["OWNERS"]["ownership_relationship_import_enabled"] is False
        assert capabilities["TENANTS"]["login_creation_enabled"] is False
        assert capabilities["TENANTS"]["occupancy_import_enabled"] is False
        assert capabilities["LEASE_OCCUPANCY"]["reviewed_existing_target_binding"] is False
        assert capabilities["LEASE_OCCUPANCY"]["read_only_identity_relationship_preview"] is True
        assert capabilities["LEASE_OCCUPANCY"]["lease_creation_enabled"] is False
    finally:
        db.close()
        engine.dispose()
