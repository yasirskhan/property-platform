"""Record externally completed owner payouts in the accounting ledger.

This service does not initiate or transmit a payment. It only records a payout
after an authorized staff member confirms the payment was completed externally.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy.orm import Session, joinedload

from app.core.audit import log_action
from app.models.gl_account import GLAccount
from app.models.owner_payout import OwnerPayout
from app.models.user import User
from app.schemas.gl_transaction import PostingLine
from app.services.gl_posting import PostingError, post_transaction
from app.services.owner_ledger import get_owner_subledger
from app.services.owner_payouts import OwnerPayoutError, _bank_book_balance

OWNER_FUNDS_GL = "2401"


def confirm_external_payout_batch(
    db: Session,
    *,
    organization_id: int,
    batch_reference: str,
    confirmation_date: date,
    confirmed_by: User,
) -> list[OwnerPayout]:
    rows = (
        db.query(OwnerPayout)
        .options(
            joinedload(OwnerPayout.owner),
            joinedload(OwnerPayout.bank_account),
        )
        .filter(
            OwnerPayout.organization_id == organization_id,
            OwnerPayout.batch_reference == batch_reference,
        )
        .order_by(OwnerPayout.id.asc())
        .all()
    )
    if not rows:
        raise OwnerPayoutError("Payout batch not found.")
    if any(row.status != "DRAFT" for row in rows):
        raise OwnerPayoutError("Only a draft payout batch can be confirmed.")

    bank_ids = {row.bank_account_id for row in rows}
    if len(bank_ids) != 1 or rows[0].bank_account is None:
        raise OwnerPayoutError("Payout batch source bank is invalid.")
    bank = rows[0].bank_account
    if not bank.is_active:
        raise OwnerPayoutError("Payout batch source bank is inactive.")

    total = sum((Decimal(row.amount or 0) for row in rows), Decimal("0.00"))
    book_balance = _bank_book_balance(
        db,
        organization_id=organization_id,
        gl_account_id=bank.gl_account_id,
    )
    if total > book_balance:
        raise OwnerPayoutError(
            f"Payout total ({total:.2f}) exceeds the current source bank book "
            f"balance ({book_balance:.2f})."
        )

    owner_funds = (
        db.query(GLAccount)
        .filter(
            GLAccount.organization_id == organization_id,
            GLAccount.gl_number == OWNER_FUNDS_GL,
            GLAccount.is_active.is_(True),
        )
        .first()
    )
    if owner_funds is None or (owner_funds.account_type or "").upper() != "LIABILITY":
        raise OwnerPayoutError(
            f"Owner Funds GL account {OWNER_FUNDS_GL} must be an active liability account."
        )

    for row in rows:
        ledger = get_owner_subledger(
            db,
            organization_id=organization_id,
            owner_id=row.owner_id,
        )
        available = Decimal(ledger["balance"] if ledger else 0)
        if Decimal(row.amount) > available:
            raise OwnerPayoutError(
                f"Owner {row.owner_id} no longer has enough available balance "
                "for this draft."
            )

    try:
        for row in rows:
            owner_name = (
                getattr(row.owner, "full_name", None)
                if row.owner is not None
                else None
            ) or (row.owner.email if row.owner is not None else f"Owner #{row.owner_id}")
            amount = Decimal(row.amount)
            txn = post_transaction(
                db=db,
                organization_id=organization_id,
                transaction_date=confirmation_date,
                transaction_type="OWNER_DRAW",
                reference_number=batch_reference[:40],
                memo=f"Externally confirmed owner payout to {owner_name}",
                source_type="owner_payout",
                source_id=row.id,
                created_by=confirmed_by,
                lines=[
                    PostingLine(
                        gl_account_id=owner_funds.id,
                        property_id=None,
                        unit_id=None,
                        owner_id=None,
                        description=f"Owner payout to {owner_name}",
                        debit=amount,
                        credit=Decimal("0.00"),
                    ),
                    PostingLine(
                        gl_account_id=bank.gl_account_id,
                        property_id=None,
                        unit_id=None,
                        owner_id=row.owner_id,
                        description=f"Owner payout to {owner_name}",
                        debit=Decimal("0.00"),
                        credit=amount,
                    ),
                ],
                commit=False,
                write_audit=False,
            )
            row.gl_transaction_id = txn.id
            row.status = "PAID"
            row.confirmed_by_id = confirmed_by.id
            row.confirmed_at = datetime.utcnow()

        db.commit()
        for row in rows:
            db.refresh(row)
    except PostingError as exc:
        db.rollback()
        raise OwnerPayoutError(str(exc)) from exc
    except Exception as exc:
        db.rollback()
        raise OwnerPayoutError(
            f"Failed to record externally completed payout batch: {exc}"
        ) from exc

    for row in rows:
        try:
            log_action(
                db=db,
                user=confirmed_by,
                entity_type="owner_payout",
                entity_id=row.id,
                action="confirm_external_payment",
                field_name="status",
                old_value="DRAFT",
                new_value=f"PAID gl_transaction={row.gl_transaction_id}",
            )
        except Exception:
            pass

    return rows
