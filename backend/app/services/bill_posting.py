# ============================================================
# bill_posting.py
# ------------------------------------------------------------
# Two-step accrual posting for Bills.
#
#   1. post_bill()    -> GL: DR Expense / CR Accounts Payable
#   2. pay_bill()     -> GL: DR Accounts Payable / CR Cash
#   3. reverse_bill() -> reverses the ORIGINAL bill entry
#                        (only allowed if unpaid)
#
# Every function calls post_transaction() from gl_posting.py.
# Nothing writes to gl_transactions / gl_entries directly.
#
# As of Step 8a, owner_id (nullable) is carried on the bill
# and on every GL line it produces.
# ============================================================

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import List, Optional

from sqlalchemy.orm import Session

from app.core.audit import log_action
from app.models.gl_account import GLAccount
from app.models.gl_transaction import GLTransaction
from app.models.bill import Bill
from app.models.bill_line import BillLine
from app.models.user import User
from app.schemas.gl_transaction import PostingLine
from app.schemas.bill import BillCreateIn, BillPayIn
from app.services.gl_posting import (
    PostingError,
    post_transaction,
    reverse_transaction,
)


# ============================================================
# Helpers
# ============================================================

def _get_account(
    db: Session, organization_id: int, gl_account_id: int
) -> GLAccount:
    acct = (
        db.query(GLAccount)
        .filter(
            GLAccount.id == gl_account_id,
            GLAccount.organization_id == organization_id,
        )
        .first()
    )
    if acct is None:
        raise PostingError(
            f"GL account {gl_account_id} not found in your organization."
        )
    if not acct.is_active:
        raise PostingError(
            f"GL account {gl_account_id} ({acct.name}) is inactive."
        )
    return acct


def _default_payable_account(db: Session, organization_id: int) -> GLAccount:
    acct = (
        db.query(GLAccount)
        .filter(
            GLAccount.organization_id == organization_id,
            GLAccount.gl_number == "2100",
        )
        .first()
    )
    if acct is None:
        raise PostingError(
            "GL account 2100 Accounts Payable not found. Run migrations."
        )
    return acct


# ============================================================
# 1. ENTER A BILL
# ============================================================

def post_bill(
    db: Session,
    *,
    organization_id: int,
    payload: BillCreateIn,
    created_by: User,
) -> Bill:
    """Enter a bill. Posts DR Expense / CR Accounts Payable.

    On success: commits, returns the Bill (with .lines loaded).
    On failure: rolls back and raises PostingError.
    """
    # ---------------------------------------------------------
    # 1. Validate lines and total
    # ---------------------------------------------------------
    if not payload.lines:
        raise PostingError("A bill must have at least one line.")

    total = Decimal("0")
    for i, ln in enumerate(payload.lines):
        amt = Decimal(ln.amount or 0)
        if amt <= 0:
            raise PostingError(
                f"Line {i + 1}: amount must be greater than zero."
            )
        total += amt

    # ---------------------------------------------------------
    # 2. Determine the payable account
    # ---------------------------------------------------------
    if payload.payable_gl_account_id is not None:
        payable_acct = _get_account(
            db, organization_id, payload.payable_gl_account_id
        )
    else:
        payable_acct = _default_payable_account(db, organization_id)

    # ---------------------------------------------------------
    # 3. Build GL lines
    #    DR each expense line, CR the payable once for total.
    # ---------------------------------------------------------
    posting_lines: List[PostingLine] = []

    for ln in payload.lines:
        _get_account(db, organization_id, ln.gl_account_id)
        posting_lines.append(
            PostingLine(
                gl_account_id=ln.gl_account_id,
                property_id=ln.property_id or payload.property_id,
                unit_id=ln.unit_id or payload.unit_id,
                owner_id=payload.owner_id,
                description=ln.description or payload.payee_name,
                debit=Decimal(ln.amount),
                credit=Decimal("0"),
            )
        )

    posting_lines.append(
        PostingLine(
            gl_account_id=payable_acct.id,
            property_id=payload.property_id,
            unit_id=payload.unit_id,
            owner_id=payload.owner_id,
            description=f"Payable: {payload.payee_name}",
            debit=Decimal("0"),
            credit=total,
        )
    )

    # ---------------------------------------------------------
    # 4. Post to the GL
    # ---------------------------------------------------------
    try:
        txn: GLTransaction = post_transaction(
            db=db,
            organization_id=organization_id,
            transaction_date=payload.bill_date,
            transaction_type="BILL",
            memo=payload.remarks,
            lines=posting_lines,
            created_by=created_by,
            reference_number=payload.reference_number,
            source_type=payload.source_type or "bill",
            source_id=payload.source_id,
        )
    except PostingError:
        raise
    except Exception as e:
        raise PostingError(f"Failed to post GL transaction: {e}")

    # ---------------------------------------------------------
    # 5. Save Bill + BillLine rows linked to the GL txn
    # ---------------------------------------------------------
    try:
        bill = Bill(
            organization_id=organization_id,
            bill_number=payload.bill_number,
            payee_name=payload.payee_name,
            payee_user_id=payload.payee_user_id,
            bill_date=payload.bill_date,
            due_date=payload.due_date,
            reference_number=payload.reference_number,
            amount=total,
            amount_paid=Decimal("0.00"),
            status="UNPAID",
            property_id=payload.property_id,
            unit_id=payload.unit_id,
            owner_id=payload.owner_id,
            payable_gl_account_id=payable_acct.id,
            remarks=payload.remarks,
            source_type=payload.source_type,
            source_id=payload.source_id,
            gl_transaction_id=txn.id,
            is_reversed=False,
            is_active=True,
            created_by_id=created_by.id if created_by else None,
        )
        db.add(bill)
        db.flush()  # assigns bill.id

        for ln in payload.lines:
            db.add(
                BillLine(
                    organization_id=organization_id,
                    bill_id=bill.id,
                    gl_account_id=ln.gl_account_id,
                    property_id=ln.property_id or payload.property_id,
                    unit_id=ln.unit_id or payload.unit_id,
                    description=ln.description,
                    amount=Decimal(ln.amount),
                )
            )

        # Link the GL transaction back to this bill.
        txn.source_id = bill.id
        txn.source_type = "bill"

        # Auto bill_number if not provided
        if not bill.bill_number:
            bill.bill_number = f"B-{bill.id:05d}"

        db.commit()
        db.refresh(bill)
        db.refresh(txn)

    except Exception as e:
        db.rollback()
        raise PostingError(f"Failed to save bill: {e}")

    try:
        log_action(
            db=db,
            user=created_by,
            entity_type="bill",
            entity_id=bill.id,
            action="create",
            field_name="amount",
            old_value=None,
            new_value=f"{total} via GL txn #{txn.id}",
        )
    except Exception:
        pass

    return bill


# ============================================================
# 2. PAY A BILL
# ============================================================

def pay_bill(
    db: Session,
    *,
    organization_id: int,
    bill: Bill,
    payload: BillPayIn,
    created_by: User,
) -> Bill:
    """Pay (or partially pay) a bill.

    Posts: DR Accounts Payable / CR Cash.

    Updates bill.amount_paid and bill.status (PARTIAL / PAID).
    """
    if bill.is_reversed:
        raise PostingError("Cannot pay a reversed bill.")
    if bill.status == "PAID":
        raise PostingError("This bill is already fully paid.")

    # Outstanding balance
    outstanding = Decimal(bill.amount) - Decimal(bill.amount_paid)
    if outstanding <= 0:
        raise PostingError("This bill has no outstanding balance.")

    pay_amount = Decimal(payload.amount)
    if pay_amount <= 0:
        raise PostingError("Payment amount must be greater than zero.")
    if pay_amount > outstanding + Decimal("0.01"):
        raise PostingError(
            f"Payment amount {pay_amount} exceeds outstanding "
            f"balance {outstanding}."
        )

    # Validate accounts
    _get_account(db, organization_id, bill.payable_gl_account_id)
    _get_account(db, organization_id, payload.cash_gl_account_id)

    # GL lines: DR AP / CR Cash
    posting_lines: List[PostingLine] = [
        PostingLine(
            gl_account_id=bill.payable_gl_account_id,
            property_id=bill.property_id,
            unit_id=bill.unit_id,
            owner_id=bill.owner_id,
            description=f"Payment: {bill.payee_name}",
            debit=pay_amount,
            credit=Decimal("0"),
        ),
        PostingLine(
            gl_account_id=payload.cash_gl_account_id,
            property_id=bill.property_id,
            unit_id=bill.unit_id,
            owner_id=bill.owner_id,
            description=f"Payment: {bill.payee_name}",
            debit=Decimal("0"),
            credit=pay_amount,
        ),
    ]

    try:
        txn: GLTransaction = post_transaction(
            db=db,
            organization_id=organization_id,
            transaction_date=payload.payment_date,
            transaction_type="BILL",
            memo=payload.remarks or f"Payment of bill #{bill.id}",
            lines=posting_lines,
            created_by=created_by,
            reference_number=payload.reference_number,
            source_type="bill_payment",
            source_id=bill.id,
        )
    except PostingError:
        raise
    except Exception as e:
        raise PostingError(f"Failed to post payment to GL: {e}")

    try:
        bill.amount_paid = Decimal(bill.amount_paid) + pay_amount
        if bill.amount_paid >= Decimal(bill.amount) - Decimal("0.01"):
            bill.amount_paid = Decimal(bill.amount)
            bill.status = "PAID"
        else:
            bill.status = "PARTIAL"

        db.commit()
        db.refresh(bill)
        db.refresh(txn)

    except Exception as e:
        db.rollback()
        raise PostingError(f"Failed to save payment: {e}")

    try:
        log_action(
            db=db,
            user=created_by,
            entity_type="bill",
            entity_id=bill.id,
            action="pay",
            field_name="amount_paid",
            old_value=None,
            new_value=f"{pay_amount} via GL txn #{txn.id} (status: {bill.status})",
        )
    except Exception:
        pass

    return bill


# ============================================================
# 3. REVERSE A BILL
# ============================================================

def reverse_bill(
    db: Session,
    *,
    original: Bill,
    reversal_date: date,
    memo: Optional[str],
    created_by: User,
) -> Bill:
    """Reverse an entered bill. Only allowed if not paid.

    Reverses the original GL transaction (DR Expense / CR AP)
    by flipping it. Marks original is_reversed=True. Creates a
    mirror Bill row linked via reversal_of_id.
    """
    if original.is_reversed:
        raise PostingError("This bill has already been reversed.")
    if original.status in ("PAID", "PARTIAL"):
        raise PostingError(
            "Cannot reverse a bill that has payments against it. "
            "Reverse the payments first."
        )
    if original.gl_transaction_id is None:
        raise PostingError("This bill has no GL transaction.")

    txn = (
        db.query(GLTransaction)
        .filter(GLTransaction.id == original.gl_transaction_id)
        .first()
    )
    if txn is None:
        raise PostingError("Underlying GL transaction not found.")

    reversed_txn = reverse_transaction(
        db=db,
        original=txn,
        reversal_date=reversal_date,
        created_by=created_by,
        memo=memo or f"Reversal of bill #{original.id}",
    )

    original.is_reversed = True
    db.flush()

    try:
        mirror = Bill(
            organization_id=original.organization_id,
            bill_number=f"REV-{original.bill_number or original.id}",
            payee_name=original.payee_name,
            payee_user_id=original.payee_user_id,
            bill_date=reversal_date,
            due_date=None,
            reference_number=original.reference_number,
            amount=Decimal(original.amount),
            amount_paid=Decimal("0.00"),
            status="VOID",
            property_id=original.property_id,
            unit_id=original.unit_id,
            owner_id=original.owner_id,
            payable_gl_account_id=original.payable_gl_account_id,
            remarks=memo or f"Reversal of bill #{original.id}",
            source_type=original.source_type,
            source_id=original.source_id,
            gl_transaction_id=reversed_txn.id,
            is_reversed=False,
            reversal_of_id=original.id,
            is_active=True,
            created_by_id=created_by.id if created_by else None,
        )
        db.add(mirror)
        db.commit()
        db.refresh(mirror)
        db.refresh(original)
    except Exception as e:
        db.rollback()
        raise PostingError(f"Failed to save reversal bill: {e}")

    try:
        log_action(
            db=db,
            user=created_by,
            entity_type="bill",
            entity_id=original.id,
            action="reverse",
            field_name="is_reversed",
            old_value="False",
            new_value=f"True (mirror bill #{mirror.id})",
        )
    except Exception:
        pass

    return mirror