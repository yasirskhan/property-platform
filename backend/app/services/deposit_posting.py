# ============================================================
# deposit_posting.py
# ------------------------------------------------------------
# Bank Deposit service.
#
# Deposits group un-deposited receipts into a batch that goes
# to the bank together.
#
# IMPORTANT: In this system, receipts already credit the cash
# GL account at the moment they're posted. Deposits therefore
# do NOT create a GL transaction — they simply tag receipts as
# "deposited" (by inserting rows into deposit_lines).
#
# deposit_lines is the SINGLE SOURCE OF TRUTH for "is this
# receipt deposited?". We do not store a column on receipts.
#
# Cannot be reversed. Corrections go through a journal entry.
# ============================================================

from __future__ import annotations

from decimal import Decimal
from typing import List

from sqlalchemy.orm import Session

from app.core.audit import log_action
from app.models.gl_account import GLAccount
from app.models.receipt import Receipt
from app.models.deposit import Deposit
from app.models.deposit_line import DepositLine
from app.models.user import User
from app.services.gl_posting import PostingError


# ============================================================
# Create a deposit
# ============================================================

def create_deposit(
    db: Session,
    *,
    organization_id: int,
    bank_gl_account_id: int,
    deposit_date,
    deposit_number,
    description,
    notes,
    receipt_ids: List[int],
    created_by: User,
) -> Deposit:
    """Create a deposit that tags the given receipts as
    deposited.

    Validations:
      1. All receipt_ids exist, belong to org, are not reversed.
      2. None of them are already deposited.
      3. The bank GL account exists, belongs to org, is active.
      4. At least one receipt.

    On success: commits and returns the Deposit with lines.
    On failure: rolls back and raises PostingError.
    """
    if not receipt_ids:
        raise PostingError("A deposit must include at least one receipt.")

    # ---------------------------------------------------------
    # 1. Validate bank account
    # ---------------------------------------------------------
    bank_acct = (
        db.query(GLAccount)
        .filter(
            GLAccount.id == bank_gl_account_id,
            GLAccount.organization_id == organization_id,
        )
        .first()
    )
    if bank_acct is None:
        raise PostingError(
            f"Bank GL account {bank_gl_account_id} not found in your org."
        )
    if not bank_acct.is_active:
        raise PostingError(
            f"Bank GL account {bank_acct.name} is inactive."
        )

    # ---------------------------------------------------------
    # 2. Load the receipts and validate
    # ---------------------------------------------------------
    receipts = (
        db.query(Receipt)
        .filter(
            Receipt.organization_id == organization_id,
            Receipt.id.in_(receipt_ids),
        )
        .all()
    )

    found_ids = {r.id for r in receipts}
    missing = set(receipt_ids) - found_ids
    if missing:
        raise PostingError(
            f"Receipt(s) not found in your org: {sorted(missing)}"
        )

    for r in receipts:
        if r.is_reversed:
            raise PostingError(
                f"Receipt #{r.id} is reversed and cannot be deposited."
            )
        if not r.is_active:
            raise PostingError(
                f"Receipt #{r.id} is inactive."
            )

    # ---------------------------------------------------------
    # 3. Reject receipts that are already in a deposit
    # ---------------------------------------------------------
    already = (
        db.query(DepositLine.receipt_id)
        .filter(DepositLine.receipt_id.in_(receipt_ids))
        .all()
    )
    if already:
        ids = sorted(rid for (rid,) in already)
        raise PostingError(
            f"Receipt(s) already deposited: {ids}"
        )

    # ---------------------------------------------------------
    # 4. Compute total from receipts
    # ---------------------------------------------------------
    total = Decimal("0")
    for r in receipts:
        total += Decimal(r.amount or 0)

    # ---------------------------------------------------------
    # 5. Save deposit + lines in one transaction
    # ---------------------------------------------------------
    try:
        deposit = Deposit(
            organization_id=organization_id,
            bank_gl_account_id=bank_gl_account_id,
            deposit_date=deposit_date,
            deposit_number=deposit_number,
            description=description,
            total=total,
            notes=notes,
            is_active=True,
            created_by_id=created_by.id if created_by else None,
        )
        db.add(deposit)
        db.flush()  # assigns deposit.id

        for rid in receipt_ids:
            db.add(
                DepositLine(
                    organization_id=organization_id,
                    deposit_id=deposit.id,
                    receipt_id=rid,
                )
            )

        # Auto deposit_number if not provided
        if not deposit.deposit_number:
            deposit.deposit_number = f"D-{deposit.id:05d}"

        db.commit()
        db.refresh(deposit)
    except Exception as e:
        db.rollback()
        raise PostingError(f"Failed to save deposit: {e}")

    # ---------------------------------------------------------
    # 6. Audit log (best-effort)
    # ---------------------------------------------------------
    try:
        log_action(
            db=db,
            user=created_by,
            entity_type="deposit",
            entity_id=deposit.id,
            action="create",
            field_name="total",
            old_value=None,
            new_value=f"{total} ({len(receipt_ids)} receipts)",
        )
    except Exception:
        pass

    return deposit


# ============================================================
# List un-deposited receipts (for the picker)
# ============================================================

def list_undeposited_receipts(
    db: Session,
    *,
    organization_id: int,
    bank_gl_account_id: int | None = None,
) -> List[Receipt]:
    """Return receipts that are not yet in any deposit.

    Optional filter: only receipts whose cash_gl_account_id
    matches the given bank account.
    """
    # Subquery: all receipt_ids that appear in deposit_lines
    deposited_subq = (
        db.query(DepositLine.receipt_id)
        .filter(DepositLine.organization_id == organization_id)
        .subquery()
    )

    q = (
        db.query(Receipt)
        .filter(Receipt.organization_id == organization_id)
        .filter(Receipt.is_active.is_(True))
        .filter(Receipt.is_reversed.is_(False))
        .filter(~Receipt.id.in_(db.query(deposited_subq.c.receipt_id)))
    )

    if bank_gl_account_id is not None:
        q = q.filter(Receipt.cash_gl_account_id == bank_gl_account_id)

    return q.order_by(Receipt.receipt_date.asc(), Receipt.id.asc()).all()