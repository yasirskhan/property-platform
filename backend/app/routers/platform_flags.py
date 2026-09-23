"""Internal platform release-gate control API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.platform_user import PlatformUser, PlatformUserRole
from app.models.release_gate import ReleaseGate, ReleaseGateOrganization, ReleaseStage
from app.models.user import Organization
from app.routers.platform_auth import get_current_platform_user
from app.schemas.platform_control import ReleaseGateOut, ReleaseGateUpdateIn
from app.services.audit import append_audit_log


router = APIRouter(prefix="/api/platform/flags", tags=["Platform Release Gates"])

_RELEASE_MANAGERS = {
    PlatformUserRole.PLATFORM_ADMIN,
    PlatformUserRole.PLATFORM_DEV,
}


def _require_release_manager(user: PlatformUser) -> None:
    if user.role not in _RELEASE_MANAGERS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Platform admin or dev role required",
        )


def _serialize_gate(gate: ReleaseGate) -> ReleaseGateOut:
    return ReleaseGateOut(
        key=gate.key,
        stage=gate.stage,
        organization_ids=sorted(row.organization_id for row in gate.organizations),
        updated_at=gate.updated_at,
    )


@router.put("/{key}", response_model=ReleaseGateOut)
def update_release_gate(
    key: str,
    payload: ReleaseGateUpdateIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
) -> ReleaseGateOut:
    _require_release_manager(current_user)

    gate = db.query(ReleaseGate).filter(ReleaseGate.key == key.strip()).first()
    if gate is None:
        raise HTTPException(status_code=404, detail="Release gate not found")

    requested_ids = sorted(set(payload.organization_ids))
    if payload.stage in {ReleaseStage.HIDDEN, ReleaseStage.ALL_ORGS}:
        requested_ids = []

    if requested_ids:
        found_ids = {
            row[0]
            for row in db.query(Organization.id)
            .filter(Organization.id.in_(requested_ids))
            .all()
        }
        missing = sorted(set(requested_ids) - found_ids)
        if missing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown organization ids: {missing}",
            )

    old_value = {
        "stage": gate.stage.value if hasattr(gate.stage, "value") else str(gate.stage),
        "organization_ids": sorted(
            row.organization_id for row in gate.organizations
        ),
    }

    gate.stage = payload.stage
    gate.organizations.clear()
    db.flush()
    for organization_id in requested_ids:
        gate.organizations.append(
            ReleaseGateOrganization(organization_id=organization_id)
        )

    db.flush()
    new_value = {
        "stage": payload.stage.value,
        "organization_ids": requested_ids,
    }
    append_audit_log(
        db,
        platform_user_id=current_user.id,
        entity_type="release_gate",
        entity_id=gate.id,
        action="stage_change",
        field_name=gate.key,
        old_value=old_value,
        new_value=new_value,
    )
    db.commit()
    db.refresh(gate)
    return _serialize_gate(gate)
