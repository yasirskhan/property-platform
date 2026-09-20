# ============================================================
# management_fee_posting.py
# ------------------------------------------------------------
# Computes and posts Management Fees — AppFolio parity.
#
# AppFolio flow (two-step, like any other payable):
#   1. Pay Management Fees -> creates a BILL
#        DR 6001 Management Fees
#        CR 2100 Accounts Payable
#   2. Pay the Bill (existing Bills flow)
#        DR 2100 Accounts Payable
#        CR 1150 Rental Trust
#
# Rules:
#   * Only GL accounts flagged `subject_to_mgmt_fees = True`
#     contribute to the base.
#   * Only RECEIPTS count. Manual journal entries never create
#     fees.
#   * Receipts with `exclude_from_mgmt_fee = True` are skipped.
#   * Two-tier rate:
#       Rent income (4100, 4105)  -> property.mgmt_fee_pct (9% default)
#       All other eligible income -> 100%
#   * Flat / min overrides:
#       mgmt_fee_flat -> ignore percentages, charge flat
#       mgmt_fee_min  -> never charge less than the floor
#   * `mgmt_fee_end_date` blocks runs past that date.
# ============================================================

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.audit import log_action
from app.models.bill import Bill
from app.models.bill_line import BillLine
from app.models.gl_account import GLAccount
from app.models.gl_entry import GLEntry
from app.models.gl_transaction import GLTransaction
from app.models.management_fee_run import ManagementFeeRun
from app.models.property import Property
from app.models.receipt import Receipt
from app.models.user import User
from app.schemas.gl_transaction import PostingLine
from app.services.gl_posting import PostingError, post_transaction


DEFAULT_RENT_FEE_PCT = Decimal("9.00")
DEFAULT_OTHER_FEE_PCT = Decimal("100.00")
RENT_GL_NUMBERS = ("4100", "4105")
DEFAULT_EXPENSE_GL = "6001"   # Management Fees
DEFAULT_PAYABLE_GL = "2100"   # Accounts Payable
DEFAULT_CASH_GL = "1150"      # Rental Trust (kept for compat)


# ============================================================
# Helpers
# ============================================================

def _fetch_account_by_number(
    db: Session, organization_id: int, gl_number: str
) -> Optional[GLAccount]:
    return (
        db.query(GLAccount)
        .filter(
            GLAccount.organization_id == organization_id,
            GLAccount.gl_number == gl_number,
        )
        .first()
    )


def _fetch_account_by_id(
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
            f"GL account {acct.name} ({acct.gl_number}) is inactive."
        )
    return acct


def _fetch_property(
    db: Session, organization_id: int, property_id: int
) -> Property:
    prop = (
        db.query(Property)
        .filter(
            Property.id == property_id,
            Property.organization_id == organization_id,
        )
        .first()
    )
    if prop is None:
        raise PostingError(
            f"Property {property_id} not found in your organization."
        )
    return prop


# ============================================================
# Compute eligible income
# ============================================================

def _collect_eligible_income(
    db: Session,
    organization_id: int,
    property_id: int,
    period_start: date,
    period_end: date,
) -> Tuple[Decimal, Decimal, List[dict], List[dict]]:
    eligible_accounts = {
        a.id: a
        for a in (
            db.query(GLAccount)
            .filter(
                GLAccount.organization_id == organization_id,
                GLAccount.subject_to_mgmt_fees.is_(True),
                GLAccount.account_type == "INCOME",
            )
            .all()
        )
    }
    if not eligible_accounts:
        return Decimal("0"), Decimal("0"), [], []

    rows = (
        db.query(GLEntry, GLTransaction, Receipt)
        .join(GLTransaction, GLTransaction.id == GLEntry.transaction_id)
        .join(
            Receipt,
            Receipt.gl_transaction_id == GLTransaction.id,
            isouter=False,
        )
        .filter(
            GLEntry.organization_id == organization_id,
            GLEntry.property_id == property_id,
            GLEntry.gl_account_id.in_(list(eligible_accounts.keys())),
            Receipt.exclude_from_mgmt_fee.is_(False),
            Receipt.is_reversed.is_(False),
            GLTransaction.transaction_date >= period_start,
            GLTransaction.transaction_date <= period_end,
        )
        .all()
    )

    rent_total = Decimal("0")
    other_total = Decimal("0")
    rent_lines: List[dict] = []
    other_lines: List[dict] = []

    for entry, txn, receipt in rows:
        acct = eligible_accounts[entry.gl_account_id]
        amount = Decimal(entry.credit or 0) - Decimal(entry.debit or 0)
        if amount <= 0:
            continue
        line = {
            "receipt_id": receipt.id,
            "transaction_id": txn.id,
            "transaction_date": txn.transaction_date,
            "gl_account_id": acct.id,
            "gl_account_number": acct.gl_number,
            "gl_account_name": acct.name,
            "amount": amount,
        }
        if acct.gl_number in RENT_GL_NUMBERS:
            rent_total += amount
            rent_lines.append(line)
        else:
            other_total += amount
            other_lines.append(line)

    return rent_total, other_total, rent_lines, other_lines


# ============================================================
# Preview (read-only)
# ============================================================

def preview_management_fee(
    db: Session,
    *,
    organization_id: int,
    property_id: int,
    period_start: date,
    period_end: date,
) -> dict:
    prop = _fetch_property(db, organization_id, property_id)

    if prop.mgmt_fee_end_date and period_end > prop.mgmt_fee_end_date:
        return {
            "property_id": prop.id,
            "property_name": prop.name,
            "period_start": period_start,
            "period_end": period_end,
            "rent_income_total": Decimal("0"),
            "other_fee_income_total": Decimal("0"),
            "rent_fee_pct": Decimal("0"),
            "other_fee_pct": Decimal("0"),
            "rent_fee_amount": Decimal("0"),
            "other_fee_amount": Decimal("0"),
            "total_fee": Decimal("0"),
            "rent_lines": [],
            "other_lines": [],
            "can_run": False,
            "reason": (
                f"Management fee end date ({prop.mgmt_fee_end_date}) "
                f"is before the period end."
            ),
        }

    rent_total, other_total, rent_lines, other_lines = (
        _collect_eligible_income(
            db, organization_id, property_id, period_start, period_end
        )
    )

    rent_pct = (
        Decimal(prop.mgmt_fee_pct)
        if prop.mgmt_fee_pct is not None
        else DEFAULT_RENT_FEE_PCT
    )
    other_pct = DEFAULT_OTHER_FEE_PCT

    rent_fee = (rent_total * rent_pct / Decimal("100")).quantize(Decimal("0.01"))
    other_fee = (other_total * other_pct / Decimal("100")).quantize(Decimal("0.01"))
    total_fee = rent_fee + other_fee

    if prop.mgmt_fee_flat is not None and prop.mgmt_fee_flat > 0:
        total_fee = Decimal(prop.mgmt_fee_flat)
        rent_fee = total_fee
        other_fee = Decimal("0")

    if prop.mgmt_fee_min is not None and prop.mgmt_fee_min > 0:
        if total_fee < Decimal(prop.mgmt_fee_min):
            total_fee = Decimal(prop.mgmt_fee_min)

    can_run = total_fee > 0
    return {
        "property_id": prop.id,
        "property_name": prop.name,
        "period_start": period_start,
        "period_end": period_end,
        "rent_income_total": rent_total,
        "other_fee_income_total": other_total,
        "rent_fee_pct": rent_pct,
        "other_fee_pct": other_pct,
        "rent_fee_amount": rent_fee,
        "other_fee_amount": other_fee,
        "total_fee": total_fee,
        "rent_lines": rent_lines,
        "other_lines": other_lines,
        "can_run": can_run,
        "reason": None if can_run else "No eligible income or fee is zero.",
    }


# ============================================================
# Run the fee — creates a Bill (AppFolio parity)
# ============================================================

def run_management_fee(
    db: Session,
    *,
    organization_id: int,
    property_id: int,
    period_start: date,
    period_end: date,
    expense_gl_account_id: Optional[int],
    cash_gl_account_id: Optional[int],   # kept for API compat; unused now
    notes: Optional[str],
    created_by: User,
) -> ManagementFeeRun:
    """Compute the fee, create a Bill, and post DR Expense / CR AP."""

    preview = preview_management_fee(
        db,
        organization_id=organization_id,
        property_id=property_id,
        period_start=period_start,
        period_end=period_end,
    )
    if not preview["can_run"]:
        raise PostingError(preview["reason"] or "Cannot run fee.")

    total_fee = preview["total_fee"]

    # Resolve expense + payable accounts
    if expense_gl_account_id is not None:
        expense_acct = _fetch_account_by_id(
            db, organization_id, expense_gl_account_id
        )
    else:
        expense_acct = _fetch_account_by_number(
            db, organization_id, DEFAULT_EXPENSE_GL
        )
        if expense_acct is None:
            raise PostingError(
                f"Default expense account {DEFAULT_EXPENSE_GL} not found."
            )

    payable_acct = _fetch_account_by_number(
        db, organization_id, DEFAULT_PAYABLE_GL
    )
    if payable_acct is None:
        raise PostingError(
            f"Default payable account {DEFAULT_PAYABLE_GL} not found."
        )

    prop = _fetch_property(db, organization_id, property_id)

    # GL: DR Expense / CR AP
    posting_lines: List[PostingLine] = [
        PostingLine(
            gl_account_id=expense_acct.id,
            property_id=property_id,
            unit_id=None,
            owner_id=None,
            description=f"Management fee {period_start}..{period_end}",
            debit=total_fee,
            credit=Decimal("0"),
        ),
        PostingLine(
            gl_account_id=payable_acct.id,
            property_id=property_id,
            unit_id=None,
            owner_id=None,
            description=f"Management fee {period_start}..{period_end}",
            debit=Decimal("0"),
            credit=total_fee,
        ),
    ]

    # Post
    try:
        txn: GLTransaction = post_transaction(
            db=db,
            organization_id=organization_id,
            transaction_date=period_end,
            transaction_type="BILL",
            memo=notes or f"Management fee {period_start}..{period_end}",
            lines=posting_lines,
            created_by=created_by,
            source_type="management_fee",
            source_id=None,
        )
    except PostingError:
        raise
    except Exception as e:
        raise PostingError(f"Failed to post GL transaction: {e}")

    # Create the Bill row
    try:
        bill = Bill(
            organization_id=organization_id,
            bill_number=None,
            payee_name="Management Fee",
            payee_user_id=None,
            bill_date=period_end,
            due_date=period_end,
            reference_number=None,
            amount=total_fee,
            amount_paid=Decimal("0.00"),
            status="UNPAID",
            property_id=property_id,
            unit_id=None,
            owner_id=None,
            payable_gl_account_id=payable_acct.id,
            remarks=notes or f"Management fee {period_start}..{period_end}",
            source_type="management_fee",
            source_id=None,
            gl_transaction_id=txn.id,
            is_reversed=False,
            is_active=True,
            created_by_id=created_by.id if created_by else None,
        )
        db.add(bill)
        db.flush()

        db.add(
            BillLine(
                organization_id=organization_id,
                bill_id=bill.id,
                gl_account_id=expense_acct.id,
                property_id=property_id,
                unit_id=None,
                description=(
                    f"Management fee {period_start}..{period_end}"
                ),
                amount=total_fee,
            )
        )

        if not bill.bill_number:
            bill.bill_number = f"B-{bill.id:05d}"

        txn.source_id = bill.id
        txn.source_type = "bill"

        # Create the ManagementFeeRun record, linked to the bill
        run = ManagementFeeRun(
            organization_id=organization_id,
            property_id=property_id,
            period_start=period_start,
            period_end=period_end,
            rent_income_total=preview["rent_income_total"],
            other_fee_income_total=preview["other_fee_income_total"],
            rent_fee_pct=preview["rent_fee_pct"],
            other_fee_pct=preview["other_fee_pct"],
            rent_fee_amount=preview["rent_fee_amount"],
            other_fee_amount=preview["other_fee_amount"],
            total_fee=total_fee,
            expense_gl_account_id=expense_acct.id,
            cash_gl_account_id=payable_acct.id,   # store AP here (the credit side)
            gl_transaction_id=txn.id,
            notes=notes,
            is_reversed=False,
            is_active=True,
            created_by_id=created_by.id if created_by else None,
        )
        db.add(run)
        db.flush()

        db.commit()
        db.refresh(run)
        db.refresh(bill)
        db.refresh(txn)
    except Exception as e:
        db.rollback()
        raise PostingError(f"Failed to save management fee: {e}")

    try:
        log_action(
            db=db,
            user=created_by,
            entity_type="management_fee_run",
            entity_id=run.id,
            action="create",
            field_name="total_fee",
            old_value=None,
            new_value=f"{total_fee} via bill #{bill.id} / GL txn #{txn.id}",
        )
    except Exception:
        pass

    return run


# ============================================================
# Reverse
# ============================================================

def reverse_management_fee_run(
    db: Session,
    *,
    original: ManagementFeeRun,
    reversal_date: date,
    memo: Optional[str],
    created_by: User,
) -> ManagementFeeRun:
    from app.services.gl_posting import reverse_transaction

    if original.is_reversed:
        raise PostingError("This management fee run is already reversed.")
    if original.gl_transaction_id is None:
        raise PostingError("This run has no GL transaction.")

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
        memo=memo or f"Reversal of management fee #{original.id}",
    )

    original.is_reversed = True
    db.flush()

    try:
        mirror = ManagementFeeRun(
            organization_id=original.organization_id,
            property_id=original.property_id,
            period_start=original.period_start,
            period_end=original.period_end,
            rent_income_total=original.rent_income_total,
            other_fee_income_total=original.other_fee_income_total,
            rent_fee_pct=original.rent_fee_pct,
            other_fee_pct=original.other_fee_pct,
            rent_fee_amount=original.rent_fee_amount,
            other_fee_amount=original.other_fee_amount,
            total_fee=original.total_fee,
            expense_gl_account_id=original.expense_gl_account_id,
            cash_gl_account_id=original.cash_gl_account_id,
            gl_transaction_id=reversed_txn.id,
            notes=memo or f"Reversal of management fee #{original.id}",
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
        raise PostingError(f"Failed to save reversal: {e}")

    return mirror