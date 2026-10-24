"""Owner payout preview and reviewable draft workflow.

This module prepares payout instructions for staff review. It does not create
bank files, move funds, or post the general ledger.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.core.audit import log_action
from app.models.bank_account import BankAccount
from app.models.gl_entry import GLEntry
from app.models.owner_ach import OwnerACHAccount
from app.models.owner_payout import OwnerPayout
from app.models.user import User, UserRole
from app.schemas.owner_payout import OwnerPayoutDraftIn
from app.services.owner_ledger import get_owner_subledger

CENT = Decimal("0.01")


class OwnerPayoutError(ValueError):
    pass


def _money(value) -> Decimal:
    return Decimal(value or 0).quantize(CENT, rounding=ROUND_HALF_UP)


def _role_value(role) -> str:
    return (role.value if hasattr(role, "value") else str(role or "")).upper()


def _owner_name(owner: User) -> str:
    return getattr(owner, "full_name", None) or owner.email


def _source_bank(
    db: Session,
    *,
    organization_id: int,
    bank_account_id: int,
) -> BankAccount:
    bank = (
        db.query(BankAccount)
        .options(
            joinedload(BankAccount.organization),
            joinedload(BankAccount.gl_account),
        )
        .filter(
            BankAccount.id == bank_account_id,
            BankAccount.organization_id == organization_id,
            BankAccount.is_active.is_(True),
        )
        .first()
    )
    if bank is None:
        raise OwnerPayoutError("Bank account not found.")
    if (bank.account_type or "").upper() != "OPERATING":
        raise OwnerPayoutError("Owner payouts must use an active operating bank account.")
    if bank.gl_account is None or not bank.gl_account.is_active:
        raise OwnerPayoutError("The bank account's GL cash account is not active.")
    if (bank.gl_account.account_type or "").upper() != "ASSET":
        raise OwnerPayoutError("The bank account must map to an asset GL cash account.")
    return bank


def _bank_book_balance(
    db: Session,
    *,
    organization_id: int,
    gl_account_id: int,
) -> Decimal:
    debits, credits = (
        db.query(
            func.coalesce(func.sum(GLEntry.debit), 0),
            func.coalesce(func.sum(GLEntry.credit), 0),
        )
        .filter(
            GLEntry.organization_id == organization_id,
            GLEntry.gl_account_id == gl_account_id,
        )
        .one()
    )
    return _money(Decimal(debits or 0) - Decimal(credits or 0))


def _owner_ach(
    db: Session,
    *,
    organization_id: int,
    owner_id: int,
) -> OwnerACHAccount | None:
    return (
        db.query(OwnerACHAccount)
        .filter(
            OwnerACHAccount.organization_id == organization_id,
            OwnerACHAccount.owner_id == owner_id,
        )
        .first()
    )


def preview_owner_payouts(
    db: Session,
    *,
    organization_id: int,
    bank_account_id: int,
) -> dict:
    bank = _source_bank(
        db,
        organization_id=organization_id,
        bank_account_id=bank_account_id,
    )
    book_balance = _bank_book_balance(
        db,
        organization_id=organization_id,
        gl_account_id=bank.gl_account_id,
    )
    owners = (
        db.query(User)
        .filter(
            User.organization_id == organization_id,
            User.role == UserRole.OWNER,
            User.is_active.is_(True),
        )
        .order_by(User.last_name.asc(), User.first_name.asc(), User.id.asc())
        .all()
    )

    candidates: list[dict] = []
    for owner in owners:
        ledger = get_owner_subledger(
            db,
            organization_id=organization_id,
            owner_id=owner.id,
        )
        available = _money(ledger["balance"] if ledger else Decimal("0"))
        ach = _owner_ach(
            db,
            organization_id=organization_id,
            owner_id=owner.id,
        )
        configured = ach is not None
        enabled = bool(ach and ach.is_enabled)
        can_pay = available > 0 and enabled
        if available <= 0:
            reason = "No positive owner balance is available."
        elif not configured:
            reason = "Owner ACH destination is not configured."
        elif not enabled:
            reason = "Owner ACH destination is disabled."
        else:
            reason = None
        candidates.append(
            {
                "owner_id": owner.id,
                "owner_name": _owner_name(owner),
                "owner_email": owner.email,
                "available_balance": available,
                "ach_configured": configured,
                "ach_enabled": enabled,
                "account_last4": ach.account_number[-4:] if ach else None,
                "can_pay": can_pay,
                "reason": reason,
            }
        )

    return {
        "bank_account_id": bank.id,
        "bank_account_name": bank.name,
        "book_balance": book_balance,
        "candidates": candidates,
    }


def create_owner_payout_draft(
    db: Session,
    *,
    organization_id: int,
    payload: OwnerPayoutDraftIn,
    created_by: User,
) -> tuple[str, Decimal, list[OwnerPayout]]:
    bank = _source_bank(
        db,
        organization_id=organization_id,
        bank_account_id=payload.bank_account_id,
    )

    seen_owner_ids: set[int] = set()
    validated: list[tuple[User, OwnerACHAccount, Decimal]] = []
    total = Decimal("0.00")

    for requested in payload.payouts:
        if requested.owner_id in seen_owner_ids:
            raise OwnerPayoutError("Each owner may appear only once in a payout batch.")
        seen_owner_ids.add(requested.owner_id)

        owner = (
            db.query(User)
            .filter(
                User.id == requested.owner_id,
                User.organization_id == organization_id,
                User.is_active.is_(True),
            )
            .first()
        )
        if owner is None or _role_value(owner.role) != UserRole.OWNER.value:
            raise OwnerPayoutError(f"Owner {requested.owner_id} not found.")

        amount = _money(requested.amount)
        ledger = get_owner_subledger(
            db,
            organization_id=organization_id,
            owner_id=owner.id,
        )
        available = _money(ledger["balance"] if ledger else Decimal("0"))
        if available <= 0:
            raise OwnerPayoutError(
                f"{_owner_name(owner)} has no positive balance available for payout."
            )
        if amount > available:
            raise OwnerPayoutError(
                f"Payout for {_owner_name(owner)} exceeds the available balance "
                f"({available:.2f})."
            )

        ach = _owner_ach(
            db,
            organization_id=organization_id,
            owner_id=owner.id,
        )
        if ach is None or not ach.is_enabled:
            raise OwnerPayoutError(
                f"ACH destination for {_owner_name(owner)} is not configured and enabled."
            )

        validated.append((owner, ach, amount))
        total += amount

    total = _money(total)
    book_balance = _bank_book_balance(
        db,
        organization_id=organization_id,
        gl_account_id=bank.gl_account_id,
    )
    if total > book_balance:
        raise OwnerPayoutError(
            f"Payout total ({total:.2f}) exceeds the source bank book balance "
            f"({book_balance:.2f})."
        )

    batch_reference = (
        f"OWN-DRAFT-{payload.effective_date.strftime('%Y%m%d')}-"
        f"{uuid4().hex[:10].upper()}"
    )
    rows: list[OwnerPayout] = []
    try:
        for owner, ach, amount in validated:
            row = OwnerPayout(
                organization_id=organization_id,
                batch_reference=batch_reference,
                owner_id=owner.id,
                bank_account_id=bank.id,
                effective_date=payload.effective_date,
                amount=amount,
                destination_last4=ach.account_number[-4:],
                status="DRAFT",
                created_by_id=created_by.id if created_by else None,
            )
            db.add(row)
            rows.append(row)
        db.commit()
        for row in rows:
            db.refresh(row)
    except Exception as exc:
        db.rollback()
        raise OwnerPayoutError(f"Failed to save owner payout draft: {exc}") from exc

    for row in rows:
        try:
            log_action(
                db=db,
                user=created_by,
                entity_type="owner_payout",
                entity_id=row.id,
                action="create",
                field_name="status",
                old_value=None,
                new_value=f"DRAFT batch={batch_reference} amount={row.amount}",
            )
        except Exception:
            pass

    return batch_reference, total, rows


def list_owner_payouts(
    db: Session,
    *,
    organization_id: int,
    limit: int = 100,
) -> list[OwnerPayout]:
    return (
        db.query(OwnerPayout)
        .options(
            joinedload(OwnerPayout.owner),
            joinedload(OwnerPayout.bank_account),
        )
        .filter(OwnerPayout.organization_id == organization_id)
        .order_by(OwnerPayout.created_at.desc(), OwnerPayout.id.desc())
        .limit(limit)
        .all()
    )
