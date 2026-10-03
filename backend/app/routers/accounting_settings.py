"""Organization Accounting Settings API."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.accounting_key_account import AccountingKeyAccount
from app.models.accounting_settings import AccountingSettings
from app.models.bank_account import BankAccount
from app.models.bank_check_setup import BankCheckSetup
from app.models.gl_account import GLAccount
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.accounting_settings import (
    AccountingCheckSetupSummary,
    AccountingGLAccountChoice,
    AccountingKeyAccountSummary,
    AccountingSettingsOut,
    AccountingSettingsUpdate,
)
from app.services.audit import append_audit_log
from app.services.customer_features import resolve_customer_features
from app.services.menu_resolver import permission_allows_user


router = APIRouter(prefix="/api/settings/accounting", tags=["Accounting Settings"])

FEATURE_KEY = "release.settings.accounting"
WRITE_ROLES = {"ADMIN", "OWNER"}


def _role(user: User) -> str:
    value = getattr(user.role, "value", user.role)
    return str(value or "").upper()


def _require_access(db: Session, user: User) -> int:
    if user.organization_id is None:
        raise HTTPException(status_code=400, detail="User has no organization.")
    if not permission_allows_user(db, user=user, menu_key="SETTINGS.ACCOUNTING"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accounting Settings permission required.",
        )
    decision = next(
        (item for item in resolve_customer_features(db, user=user) if item.key == FEATURE_KEY),
        None,
    )
    if decision is None or not decision.allowed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Accounting Settings is not available.",
        )
    return user.organization_id


def _require_write(user: User) -> None:
    if _role(user) not in WRITE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only ADMIN or OWNER can change Accounting Settings.",
        )


def _choice(account: GLAccount | None) -> AccountingGLAccountChoice | None:
    if account is None:
        return None
    return AccountingGLAccountChoice(
        id=account.id,
        gl_number=account.gl_number,
        name=account.name,
        account_type=account.account_type,
    )


def _validated_account(
    db: Session,
    *,
    organization_id: int,
    account_id: int | None,
    expected_type: str,
    label: str,
) -> GLAccount | None:
    if account_id is None:
        return None
    account = (
        db.query(GLAccount)
        .filter(
            GLAccount.id == account_id,
            GLAccount.organization_id == organization_id,
            GLAccount.is_active.is_(True),
        )
        .first()
    )
    if account is None:
        raise HTTPException(status_code=422, detail=f"{label} account is not active in this organization.")
    if account.account_type != expected_type:
        raise HTTPException(
            status_code=422,
            detail=f"{label} account must be an active {expected_type} account.",
        )
    return account


def _out(db: Session, organization_id: int, row: AccountingSettings | None) -> AccountingSettingsOut:
    income = (
        db.query(GLAccount)
        .filter(
            GLAccount.organization_id == organization_id,
            GLAccount.account_type == "INCOME",
            GLAccount.is_active.is_(True),
        )
        .order_by(GLAccount.gl_number.asc())
        .all()
    )
    cash = (
        db.query(GLAccount)
        .filter(
            GLAccount.organization_id == organization_id,
            GLAccount.account_type == "ASSET",
            GLAccount.is_active.is_(True),
        )
        .order_by(GLAccount.gl_number.asc())
        .all()
    )
    keys = (
        db.query(AccountingKeyAccount)
        .filter(AccountingKeyAccount.organization_id == organization_id)
        .order_by(AccountingKeyAccount.key_type.asc(), AccountingKeyAccount.id.asc())
        .all()
    )
    banks = (
        db.query(BankAccount)
        .filter(
            BankAccount.organization_id == organization_id,
            BankAccount.is_active.is_(True),
        )
        .order_by(BankAccount.name.asc(), BankAccount.id.asc())
        .all()
    )
    setups = {
        item.bank_account_id: item
        for item in db.query(BankCheckSetup)
        .filter(BankCheckSetup.organization_id == organization_id)
        .all()
    }

    return AccountingSettingsOut(
        organization_id=organization_id,
        gpr_rent_gl_account_id=row.gpr_rent_gl_account_id if row else None,
        gpr_market_gl_account_id=row.gpr_market_gl_account_id if row else None,
        gpr_loss_gain_gl_account_id=row.gpr_loss_gain_gl_account_id if row else None,
        receipt_cash_gl_account_id=row.receipt_cash_gl_account_id if row else None,
        report_export_format=row.report_export_format if row else "CSV",
        fiscal_year_start_month=row.fiscal_year_start_month if row else 1,
        accounting_basis=row.accounting_basis if row else "ACCRUAL",
        gpr_rent_gl_account=_choice(row.gpr_rent_gl_account) if row else None,
        gpr_market_gl_account=_choice(row.gpr_market_gl_account) if row else None,
        gpr_loss_gain_gl_account=_choice(row.gpr_loss_gain_gl_account) if row else None,
        receipt_cash_gl_account=_choice(row.receipt_cash_gl_account) if row else None,
        eligible_income_accounts=[_choice(account) for account in income],
        eligible_cash_accounts=[_choice(account) for account in cash],
        key_accounts=[
            AccountingKeyAccountSummary(
                id=item.id,
                key_type=item.key_type,
                gl_account_id=item.gl_account.id,
                gl_number=item.gl_account.gl_number,
                name=item.gl_account.name,
            )
            for item in keys
            if item.gl_account is not None
        ],
        check_setups=[
            AccountingCheckSetupSummary(
                bank_account_id=bank.id,
                bank_account_name=bank.name,
                configured=bank.id in setups,
                next_check_number=(
                    setups[bank.id].next_check_number if bank.id in setups else None
                ),
            )
            for bank in banks
        ],
    )


@router.get("", response_model=AccountingSettingsOut)
def get_accounting_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    organization_id = _require_access(db, current_user)
    row = db.get(AccountingSettings, organization_id)
    return _out(db, organization_id, row)


@router.put("", response_model=AccountingSettingsOut)
def update_accounting_settings(
    payload: AccountingSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_write(current_user)
    organization_id = _require_access(db, current_user)

    _validated_account(
        db,
        organization_id=organization_id,
        account_id=payload.gpr_rent_gl_account_id,
        expected_type="INCOME",
        label="Scheduled rent",
    )
    _validated_account(
        db,
        organization_id=organization_id,
        account_id=payload.gpr_market_gl_account_id,
        expected_type="INCOME",
        label="Gross potential rent",
    )
    _validated_account(
        db,
        organization_id=organization_id,
        account_id=payload.gpr_loss_gain_gl_account_id,
        expected_type="INCOME",
        label="Loss/gain",
    )
    _validated_account(
        db,
        organization_id=organization_id,
        account_id=payload.receipt_cash_gl_account_id,
        expected_type="ASSET",
        label="Receipt cash",
    )

    row = db.get(AccountingSettings, organization_id)
    old_value = None
    if row is None:
        row = AccountingSettings(organization_id=organization_id)
        db.add(row)
    else:
        old_value = {
            "gpr_rent_gl_account_id": row.gpr_rent_gl_account_id,
            "gpr_market_gl_account_id": row.gpr_market_gl_account_id,
            "gpr_loss_gain_gl_account_id": row.gpr_loss_gain_gl_account_id,
            "receipt_cash_gl_account_id": row.receipt_cash_gl_account_id,
            "report_export_format": row.report_export_format,
            "fiscal_year_start_month": row.fiscal_year_start_month,
            "accounting_basis": row.accounting_basis,
        }

    for field, value in payload.model_dump().items():
        setattr(row, field, value)
    db.flush()
    append_audit_log(
        db,
        user_id=current_user.id,
        organization_id=organization_id,
        entity_type="accounting_settings",
        entity_id=organization_id,
        action="updated",
        old_value=old_value,
        new_value=payload.model_dump(),
    )
    db.commit()
    db.refresh(row)
    return _out(db, organization_id, row)
