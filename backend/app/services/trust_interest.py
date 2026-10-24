"""Read-only readiness and proposed routing; no interest transactions, rates or payees."""
from __future__ import annotations
from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.models.bank_account import BankAccount
from app.models.gl_account import GLAccount
from app.models.trust_interest import TrustInterestReadiness
from app.models.user import User, UserRole
from app.schemas.trust_interest import TrustInterestInput, TrustInterestOut
from app.services.audit import append_audit_log
from app.services.customer_features import resolve_customer_features
from app.services.menu_resolver import permission_allows_user

FEATURE_KEY = "release.accounting.bank_accounts"


def _access(db: Session, current_user: User) -> int:
    if (current_user.organization_id is None or not current_user.is_active
            or current_user.deleted_at is not None
            or current_user.role not in {UserRole.ADMIN, UserRole.OWNER}
            or not permission_allows_user(db, user=current_user, menu_key="ACCOUNTING.BANK_ACCOUNTS")):
        raise HTTPException(status_code=403, detail="Bank account permission required.")
    enabled = next(
        (x for x in resolve_customer_features(db, user=current_user) if x.key == FEATURE_KEY),
        None,
    )
    if enabled is None or not enabled.allowed:
        raise HTTPException(status_code=404, detail="Bank account setup unavailable.")
    return int(current_user.organization_id)


def _bank(db: Session, *, organization_id: int, bank_id: int) -> BankAccount:
    bank = db.query(BankAccount).filter(
        BankAccount.organization_id == organization_id,
        BankAccount.id == bank_id,
        BankAccount.is_active.is_(True),
        BankAccount.deleted_at.is_(None),
    ).first()
    if bank is None:
        raise HTTPException(status_code=404, detail="Trust bank account not found.")
    account = db.query(GLAccount).filter(
        GLAccount.id == bank.gl_account_id,
        GLAccount.organization_id == organization_id,
        GLAccount.is_active.is_(True),
        GLAccount.deleted_at.is_(None),
        GLAccount.account_type == "ASSET",
    ).first()
    if bank.account_type not in {"OPERATING", "ESCROW"} or account is None:
        raise HTTPException(status_code=422, detail="Valid active trust bank and cash GL mapping required.")
    return bank


def _out(bank: BankAccount, row: TrustInterestReadiness | None) -> TrustInterestOut:
    return TrustInterestOut(
        bank_account_id=bank.id, bank_account_type=bank.account_type,
        configured=row is not None,
        jurisdiction=row.jurisdiction if row else None,
        proposed_recipient=row.proposed_recipient if row else "UNDETERMINED",
        basis_reference_recorded=bool(row and row.basis_reference),
        updated_at=row.updated_at if row else None,
    )


def read_interest(db: Session, *, bank_id: int, current_user: User) -> TrustInterestOut:
    organization_id = _access(db, current_user)
    bank = _bank(db, organization_id=organization_id, bank_id=bank_id)
    row = db.query(TrustInterestReadiness).filter(
        TrustInterestReadiness.organization_id == organization_id,
        TrustInterestReadiness.bank_account_id == bank.id,
    ).first()
    return _out(bank, row)


def save_interest(
    db: Session, *, bank_id: int, payload: TrustInterestInput, current_user: User,
) -> TrustInterestOut:
    organization_id = _access(db, current_user)
    bank = _bank(db, organization_id=organization_id, bank_id=bank_id)
    row = db.query(TrustInterestReadiness).filter(
        TrustInterestReadiness.organization_id == organization_id,
        TrustInterestReadiness.bank_account_id == bank.id,
    ).first()
    created = row is None
    if row is None:
        row = TrustInterestReadiness(
            organization_id=organization_id, bank_account_id=bank.id,
        )
        db.add(row)
    row.jurisdiction = payload.jurisdiction
    row.proposed_recipient = payload.proposed_recipient
    row.basis_reference = payload.basis_reference
    row.updated_by_id = current_user.id
    db.flush()
    # Metadata only; no bank identifiers, legal notes or private records.
    append_audit_log(
        db, user_id=current_user.id, organization_id=organization_id,
        entity_type="trust_interest_readiness", entity_id=row.id,
        action="created" if created else "updated",
        new_value={"bank_account_id": bank.id, "manual_review_required": True},
    )
    db.commit()
    db.refresh(row)
    return _out(bank, row)
