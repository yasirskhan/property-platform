from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.bank_account import BankAccount
from app.models.bank_check_setup import BankCheckSetup
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.bank_check_setup import BankCheckSetupOut, BankCheckSetupUpdateIn
from app.services.customer_features import resolve_customer_features

router = APIRouter(prefix="/api/accounting/bank-accounts", tags=["Check Setup"])
WRITE_ROLES = {"ADMIN", "OWNER", "MANAGER"}

def _role(user: User) -> str:
    role = user.role.value if hasattr(user.role, "value") else str(user.role or "")
    return role.upper()

def _require_feature(db: Session, user: User) -> int:
    if user.organization_id is None:
        raise HTTPException(status_code=400, detail="User has no organization.")
    decision = next((item for item in resolve_customer_features(db, user=user) if item.key == "release.accounting.check_setup"), None)
    if decision is None or not decision.allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Check Setup is not enabled.")
    return user.organization_id

def _bank(db: Session, organization_id: int, bank_id: int) -> BankAccount:
    row = db.query(BankAccount).filter(BankAccount.id == bank_id, BankAccount.organization_id == organization_id, BankAccount.is_active.is_(True)).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Bank account not found.")
    return row

def _out(bank: BankAccount, setup: BankCheckSetup | None) -> BankCheckSetupOut:
    return BankCheckSetupOut(
        id=setup.id if setup else None,
        organization_id=bank.organization_id,
        bank_account_id=bank.id,
        bank_account_name=bank.name,
        next_check_number=setup.next_check_number if setup else 1,
        check_number_prefix=setup.check_number_prefix if setup else None,
        check_stock_position=setup.check_stock_position if setup else "TOP",
        memo_line_enabled=setup.memo_line_enabled if setup else True,
        signature_line_enabled=setup.signature_line_enabled if setup else True,
        created_at=setup.created_at if setup else None,
        updated_at=setup.updated_at if setup else None,
    )

@router.get("/{bank_id}/check-setup", response_model=BankCheckSetupOut)
def get_check_setup(bank_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    organization_id = _require_feature(db, current_user)
    bank = _bank(db, organization_id, bank_id)
    setup = db.query(BankCheckSetup).filter(BankCheckSetup.organization_id == organization_id, BankCheckSetup.bank_account_id == bank.id).first()
    return _out(bank, setup)

@router.put("/{bank_id}/check-setup", response_model=BankCheckSetupOut)
def update_check_setup(bank_id: int, payload: BankCheckSetupUpdateIn, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if _role(current_user) not in WRITE_ROLES:
        raise HTTPException(status_code=403, detail="You are not allowed to change Check Setup.")
    organization_id = _require_feature(db, current_user)
    bank = _bank(db, organization_id, bank_id)
    setup = db.query(BankCheckSetup).filter(BankCheckSetup.organization_id == organization_id, BankCheckSetup.bank_account_id == bank.id).first()
    if setup is None:
        setup = BankCheckSetup(organization_id=organization_id, bank_account_id=bank.id)
        db.add(setup)
    setup.next_check_number = payload.next_check_number
    setup.check_number_prefix = payload.check_number_prefix
    setup.check_stock_position = payload.check_stock_position
    setup.memo_line_enabled = payload.memo_line_enabled
    setup.signature_line_enabled = payload.signature_line_enabled
    db.commit()
    db.refresh(setup)
    return _out(bank, setup)
