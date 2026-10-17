from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.models.bank_account import BankAccount
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.ach_file import ACHGenerateIn, ACHGenerateOut
from app.services.ach_file import ACHFileError, generate_ach_file
from app.services.customer_features import resolve_customer_features

router = APIRouter(prefix="/api/accounting/bank-accounts", tags=["ACH Files"])


def _require_feature(db: Session, user: User) -> int:
    if user.organization_id is None:
        raise HTTPException(status_code=400, detail="User has no organization.")
    decision = next(
        (item for item in resolve_customer_features(db, user=user) if item.key == "release.accounting.ach_files"),
        None,
    )
    if decision is None or not decision.allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="ACH File Generation is not enabled.")
    return user.organization_id


@router.post("/{bank_id}/ach-file", response_model=ACHGenerateOut)
def create_ach_file(
    bank_id: int,
    payload: ACHGenerateIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    organization_id = _require_feature(db, current_user)
    bank = (
        db.query(BankAccount)
        .options(joinedload(BankAccount.organization))
        .filter(
            BankAccount.id == bank_id,
            BankAccount.organization_id == organization_id,
            BankAccount.is_active.is_(True),
        )
        .first()
    )
    if bank is None:
        raise HTTPException(status_code=404, detail="Bank account not found.")
    try:
        filename, content_type, content, total = generate_ach_file(
            bank=bank,
            organization=bank.organization,
            payload=payload,
        )
    except ACHFileError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ACHGenerateOut(
        format=(bank.ach_format or "").upper(),
        filename=filename,
        content_type=content_type,
        content=content,
        entry_count=len(payload.entries),
        total_amount=total,
    )
