"""Phase 4.17 DoorLoop read-only provider boundary regressions."""
import pytest
from fastapi import HTTPException, Response
from app.models.platform_user import PlatformUser, PlatformUserRole
from app.routers.doorloop_migrations import _authorize, doorloop_resource_readiness


def test_doorloop_readiness_fails_closed():
    user = PlatformUser(role=PlatformUserRole.PLATFORM_ADMIN)
    response = Response()
    result = doorloop_resource_readiness(response, user)
    assert result["provider"] == "DOORLOOP"
    assert result["file_staging_enabled"] is False
    assert result["controlled_commit_enabled"] is False
    assert result["customer_business_mutation"] is False
    assert response.headers["cache-control"] == "no-store"


def test_doorloop_rejects_sales_role():
    user = PlatformUser(role=PlatformUserRole.PLATFORM_SALES)
    with pytest.raises(HTTPException) as error:
        _authorize(user)
    assert error.value.status_code == 403
