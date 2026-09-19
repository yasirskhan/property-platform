# ============================================================
# routers/password_reset.py
# ------------------------------------------------------------
#   POST /auth/forgot-password             start the flow
#   POST /auth/reset-password              complete with token
#   POST /auth/change-password             logged-in change
#   POST /users/{user_id}/force-reset      owner/manager/admin
# ============================================================

import secrets

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core import auth as auth_logic
from app.core.config import settings
from app.core.database import get_db
from app.core.email import send_password_reset_email
from app.core.security import hash_password, verify_password
from app.models.password_reset import PasswordResetToken
from app.models.user import User, UserRole
from app.routers.auth import get_current_user
from app.schemas.password_reset import (
    ForgotPasswordRequest,
    ResetPasswordRequest,
    ChangePasswordRequest,
    MessageResponse,
)


router = APIRouter(tags=["Password Reset"])


# ------------------------------------------------------------
# FORGOT PASSWORD — start the flow
# ------------------------------------------------------------
@router.post("/auth/forgot-password", response_model=MessageResponse)
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    user = auth_logic.get_user_by_email(db, payload.email)

    if user:
        # Invalidate previous unused tokens for this user
        db.query(PasswordResetToken).filter(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used == False,  # noqa: E712
        ).update({"used": True})

        # Create a fresh token
        token = secrets.token_urlsafe(32)
        prt = PasswordResetToken(
            user_id=user.id,
            token=token,
            expires_at=PasswordResetToken.default_expiry(),
        )
        db.add(prt)
        db.commit()

        reset_link = f"{settings.FRONTEND_URL}/reset-password?token={token}"
        send_password_reset_email(
            to=user.email,
            reset_link=reset_link,
            first_name=user.first_name,
            organization_id=user.organization_id,
            db=db,
        )

    return MessageResponse(detail="If that email exists, we've sent a reset link.")


# ------------------------------------------------------------
# RESET PASSWORD — complete with token
# ------------------------------------------------------------
@router.post("/auth/reset-password", response_model=MessageResponse)
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    prt = (
        db.query(PasswordResetToken)
        .filter(PasswordResetToken.token == payload.token)
        .first()
    )
    if not prt or not prt.is_valid():
        raise HTTPException(status_code=400, detail="Invalid or expired reset link")

    user = auth_logic.get_user_by_id(db, prt.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.hashed_password = hash_password(payload.new_password)
    prt.used = True
    db.commit()
    return MessageResponse(detail="Password updated. You can now log in.")


# ------------------------------------------------------------
# CHANGE PASSWORD — logged-in user
# ------------------------------------------------------------
@router.post("/auth/change-password", response_model=MessageResponse)
def change_password(
    payload: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    current_user.hashed_password = hash_password(payload.new_password)
    db.commit()
    return MessageResponse(detail="Password updated.")


# ------------------------------------------------------------
# FORCE RESET — owner/manager/admin resets another user
# ------------------------------------------------------------
@router.post("/users/{user_id}/force-reset", response_model=MessageResponse)
def force_reset(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in (UserRole.ADMIN, UserRole.OWNER, UserRole.MANAGER):
        raise HTTPException(status_code=403, detail="Not allowed")

    target = auth_logic.get_user_by_id(db, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    if current_user.role in (UserRole.OWNER, UserRole.MANAGER):
        if target.organization_id != current_user.organization_id:
            raise HTTPException(status_code=403, detail="Not in your organization")

    db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == target.id,
        PasswordResetToken.used == False,  # noqa: E712
    ).update({"used": True})

    token = secrets.token_urlsafe(32)
    prt = PasswordResetToken(
        user_id=target.id,
        token=token,
        expires_at=PasswordResetToken.default_expiry(),
    )
    db.add(prt)
    db.commit()

    reset_link = f"{settings.FRONTEND_URL}/reset-password?token={token}"
    send_password_reset_email(
        to=target.email,
        reset_link=reset_link,
        first_name=target.first_name,
        organization_id=target.organization_id,
        db=db,
    )
    return MessageResponse(detail=f"Reset link sent to {target.email}.")