# ============================================================
# organizations.py (router)
# ------------------------------------------------------------
# Read-only endpoints for the current user's organization.
#
#   GET /organizations/{id}  -> {id, name}
#
# Security:
#   A user can ONLY fetch their own organization. Requesting a
#   different org's id returns 404 (not 403 — we don't even
#   confirm the other org exists). This keeps the isolation wall
#   solid.
# ============================================================

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.regional_database import RegionRoutingError, get_database_url_for_region
from app.models.data_retention_policy import DataRetentionPolicy
from app.models.user import User, Organization, UserRole
from app.routers.auth import get_current_user
from app.schemas.organization_settings import FoundationSettingsUpdate
from app.services.audit import append_audit_log
from app.services.retention_policy import set_retention_policy

router = APIRouter(prefix="/organizations", tags=["Organizations"])


@router.get("/{org_id}")
def get_organization(
    org_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # A user without an org can't fetch any org.
    if current_user.organization_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    # Only your own org. Anything else looks like it doesn't exist.
    if current_user.organization_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    org = (
        db.query(Organization)
        .filter(Organization.id == org_id)
        .first()
    )
    if org is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    return {"id": org.id, "name": org.name}


def _require_org_admin(current_user: User, org_id: int) -> None:
    if current_user.organization_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization admin only",
        )


def _foundation_settings_snapshot(db: Session, org: Organization) -> dict:
    policies = (
        db.query(DataRetentionPolicy)
        .filter(DataRetentionPolicy.organization_id == org.id)
        .order_by(DataRetentionPolicy.data_class.asc())
        .all()
    )
    return {
        "locked_through_date": org.locked_through_date,
        "data_region": org.data_region,
        "retention_policies": {
            row.data_class: row.retention_days for row in policies
        },
    }


@router.get("/{org_id}/foundation-settings")
def get_foundation_settings(
    org_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_org_admin(current_user, org_id)
    org = db.get(Organization, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    return _foundation_settings_snapshot(db, org)


@router.put("/{org_id}/foundation-settings")
def update_foundation_settings(
    org_id: int,
    payload: FoundationSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_org_admin(current_user, org_id)
    org = db.get(Organization, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")

    before = _foundation_settings_snapshot(db, org)

    if "locked_through_date" in payload.model_fields_set:
        org.locked_through_date = payload.locked_through_date

    if "data_region" in payload.model_fields_set:
        region = (payload.data_region or "").strip().lower()
        if not region:
            raise HTTPException(status_code=400, detail="data_region is required")
        try:
            get_database_url_for_region(region)
        except RegionRoutingError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        org.data_region = region

    if payload.retention_policies is not None:
        for data_class, retention_days in payload.retention_policies.items():
            try:
                set_retention_policy(
                    db,
                    organization_id=org.id,
                    data_class=data_class,
                    retention_days=retention_days,
                )
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

    db.flush()
    after = _foundation_settings_snapshot(db, org)
    append_audit_log(
        db,
        user_id=current_user.id,
        organization_id=org.id,
        entity_type="organization",
        entity_id=org.id,
        action="foundation_settings_updated",
        old_value=before,
        new_value=after,
    )
    db.commit()
    return after
