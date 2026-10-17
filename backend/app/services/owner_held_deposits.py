"""Owner Held Security Deposit setup and validation."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.accounting_key_account import AccountingKeyAccount
from app.models.bank_account import BankAccount
from app.models.gl_account import GLAccount
from app.models.user import User
from app.services.customer_features import resolve_customer_features

FEATURE_KEY = "release.accounting.owner_held_security_deposits"
OWNER_HELD_DEPOSIT_KEY_TYPE = "DEPOSIT_LIABILITY"


class OwnerHeldDepositError(Exception):
    pass


def owner_held_feature_allowed(db: Session, *, user: User) -> bool:
    return any(
        item.key == FEATURE_KEY and item.allowed
        for item in resolve_customer_features(db, user=user)
    )


def operating_cash_account(db: Session, *, organization_id: int) -> GLAccount:
    bank = (
        db.query(BankAccount)
        .filter(
            BankAccount.organization_id == organization_id,
            BankAccount.account_type == "OPERATING",
            BankAccount.is_active.is_(True),
        )
        .order_by(BankAccount.id.asc())
        .first()
    )
    if bank is not None:
        account = (
            db.query(GLAccount)
            .filter(
                GLAccount.id == bank.gl_account_id,
                GLAccount.organization_id == organization_id,
                GLAccount.is_active.is_(True),
            )
            .first()
        )
        if account is not None:
            return account

    fallback = (
        db.query(GLAccount)
        .filter(
            GLAccount.organization_id == organization_id,
            GLAccount.gl_number == "1150",
            GLAccount.is_active.is_(True),
        )
        .first()
    )
    if fallback is None:
        raise OwnerHeldDepositError(
            "Owner Held Security Deposits require an active Operating Cash account."
        )
    return fallback


def validate_owner_held_deposit_account(
    db: Session,
    *,
    organization_id: int,
    gl_account_id: int,
) -> GLAccount:
    account = (
        db.query(GLAccount)
        .filter(
            GLAccount.id == gl_account_id,
            GLAccount.organization_id == organization_id,
            GLAccount.is_active.is_(True),
        )
        .first()
    )
    if account is None:
        raise OwnerHeldDepositError("GL account not found in your organization.")
    if (account.account_type or "").upper() != "LIABILITY":
        raise OwnerHeldDepositError("Deposit Key Account must be a LIABILITY account.")

    operating = operating_cash_account(db, organization_id=organization_id)
    if (account.offset_account or "").strip() != operating.gl_number:
        raise OwnerHeldDepositError(
            f"Deposit Key Account must offset to Operating Cash GL {operating.gl_number}."
        )
    if bool(account.subject_to_mgmt_fees):
        raise OwnerHeldDepositError(
            "Owner-held deposit accounts cannot be subject to management fees."
        )
    if bool(account.include_on_cash_flow):
        raise OwnerHeldDepositError(
            "Owner-held deposit accounts must be excluded from cash flow."
        )
    return account


def list_eligible_deposit_accounts(
    db: Session,
    *,
    organization_id: int,
) -> list[GLAccount]:
    operating = operating_cash_account(db, organization_id=organization_id)
    return (
        db.query(GLAccount)
        .filter(
            GLAccount.organization_id == organization_id,
            GLAccount.is_active.is_(True),
            GLAccount.account_type == "LIABILITY",
            GLAccount.offset_account == operating.gl_number,
            GLAccount.subject_to_mgmt_fees.is_(False),
            GLAccount.include_on_cash_flow.is_(False),
        )
        .order_by(GLAccount.gl_number.asc())
        .all()
    )


def list_deposit_key_accounts(
    db: Session,
    *,
    organization_id: int,
) -> list[AccountingKeyAccount]:
    return (
        db.query(AccountingKeyAccount)
        .filter(
            AccountingKeyAccount.organization_id == organization_id,
            AccountingKeyAccount.key_type == OWNER_HELD_DEPOSIT_KEY_TYPE,
        )
        .order_by(AccountingKeyAccount.id.asc())
        .all()
    )


def add_deposit_key_account(
    db: Session,
    *,
    organization_id: int,
    gl_account_id: int,
    created_by: User,
) -> AccountingKeyAccount:
    validate_owner_held_deposit_account(
        db,
        organization_id=organization_id,
        gl_account_id=gl_account_id,
    )
    existing = (
        db.query(AccountingKeyAccount)
        .filter(
            AccountingKeyAccount.organization_id == organization_id,
            AccountingKeyAccount.key_type == OWNER_HELD_DEPOSIT_KEY_TYPE,
            AccountingKeyAccount.gl_account_id == gl_account_id,
        )
        .first()
    )
    if existing is not None:
        return existing

    row = AccountingKeyAccount(
        organization_id=organization_id,
        key_type=OWNER_HELD_DEPOSIT_KEY_TYPE,
        gl_account_id=gl_account_id,
        created_by_id=created_by.id if created_by else None,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def remove_deposit_key_account(
    db: Session,
    *,
    organization_id: int,
    key_account_id: int,
) -> None:
    row = (
        db.query(AccountingKeyAccount)
        .filter(
            AccountingKeyAccount.id == key_account_id,
            AccountingKeyAccount.organization_id == organization_id,
            AccountingKeyAccount.key_type == OWNER_HELD_DEPOSIT_KEY_TYPE,
        )
        .first()
    )
    if row is None:
        raise OwnerHeldDepositError("Deposit Key Account not found.")

    from app.models.lease import Lease

    in_use = (
        db.query(Lease)
        .join(
            # Lease has no organization_id; scope it through Unit -> Property.
            __import__("app.models.property", fromlist=["Unit"]).Unit,
            __import__("app.models.property", fromlist=["Unit"]).Unit.id == Lease.unit_id,
        )
        .join(
            __import__("app.models.property", fromlist=["Property"]).Property,
            __import__("app.models.property", fromlist=["Property"]).Property.id
            == __import__("app.models.property", fromlist=["Unit"]).Unit.property_id,
        )
        .filter(
            __import__("app.models.property", fromlist=["Property"]).Property.organization_id
            == organization_id,
            Lease.security_deposit_gl_account_id == row.gl_account_id,
        )
        .first()
    )
    if in_use is not None:
        raise OwnerHeldDepositError(
            "This deposit Key Account is in use by a lease and cannot be removed."
        )

    db.delete(row)
    db.commit()
