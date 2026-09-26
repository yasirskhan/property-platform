from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import verify_password
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.two_factor import (
    TwoFactorDisableRequest,
    TwoFactorEnableRequest,
    TwoFactorSetupRequest,
    TwoFactorSetupResponse,
    TwoFactorStatus,
)
from app.services.audit import append_audit_log
from app.services.two_factor import (
    begin_setup,
    disable,
    enable,
    get_settings,
    otpauth_uri,
    verify_login_code,
)

router = APIRouter(prefix="/api/settings/my/two-factor", tags=["My Settings"])


def _status(user: User, row) -> TwoFactorStatus:
    return TwoFactorStatus(
        enabled=bool(row and row.is_enabled),
        recovery_codes_remaining=len(row.recovery_code_hashes or []) if row and row.is_enabled else 0,
        verified_at=row.verified_at if row and row.is_enabled else None,
    )


@router.get("", response_model=TwoFactorStatus)
def status_view(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return _status(current_user, get_settings(db, current_user.id))


@router.post("/setup", response_model=TwoFactorSetupResponse)
def setup(payload: TwoFactorSetupRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect.")
    row, secret, codes = begin_setup(db, user=current_user)
    append_audit_log(db, user_id=current_user.id, organization_id=current_user.organization_id, entity_type="user_security", entity_id=current_user.id, action="two_factor_setup_started")
    db.commit()
    return TwoFactorSetupResponse(secret=secret, otpauth_uri=otpauth_uri(secret, current_user), recovery_codes=codes)


@router.post("/enable", response_model=TwoFactorStatus)
def enable_view(payload: TwoFactorEnableRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        row = enable(db, user=current_user, code=payload.code)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    append_audit_log(db, user_id=current_user.id, organization_id=current_user.organization_id, entity_type="user_security", entity_id=current_user.id, action="two_factor_enabled")
    db.commit()
    db.refresh(row)
    return _status(current_user, row)


@router.post("/disable", response_model=TwoFactorStatus)
def disable_view(payload: TwoFactorDisableRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect.")
    row = get_settings(db, current_user.id)
    if row is None or not row.is_enabled or not verify_login_code(db, row=row, code=payload.code):
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid verification or recovery code.")
    disable(db, row=row)
    append_audit_log(db, user_id=current_user.id, organization_id=current_user.organization_id, entity_type="user_security", entity_id=current_user.id, action="two_factor_disabled")
    db.commit()
    return TwoFactorStatus(enabled=False)
