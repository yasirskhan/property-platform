# ============================================================
# receipt_posting.py
# ------------------------------------------------------------
# Turns a Receipt (tenant / owner / other) into a balanced
# GL transaction, then saves the Receipt + ReceiptLine rows.
#
# The ONLY place receipts touch the GL. It calls
# post_transaction() from gl_posting.py. It never writes to
# gl_transactions or gl_entries directly.
#
# Flow:
#   1. Validate the receipt against its type
#   2. Build GL PostingLines (cash + income side)
#   3. Call post_transaction()  -> gets back a GLTransaction
#   4. Save Receipt + ReceiptLine rows, linked to that GL txn
#   5. Return the Receipt
#
# If anything fails, we roll back. Either the whole receipt
# lands (GL + Receipt + lines) or nothing does.
# ============================================================

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import List, Optional

from sqlalchemy.orm import Session

from app.core.audit import log_action
from app.models.gl_account import GLAccount
from app.models.gl_transaction import GLTransaction
from app.models.receipt import Receipt
from app.models.receipt_line import ReceiptLine
from app.models.user import User
from app.schemas.gl_transaction import PostingLine
from app.schemas.receipt import ReceiptCreateIn, ReceiptLineIn
from app.services.gl_posting import PostingError, post_transaction


# ============================================================
# Helper: fetch an org-scoped GL account or raise PostingError
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


# ============================================================
# Helper: build the posting lines for a receipt
# ============================================================

def _build_posting_lines(
    db: Session,
    organization_id: int,
    payload: ReceiptCreateIn,
) -> List[PostingLine]:
    """Return the list of PostingLine objects that, together,
    balance to zero and represent the receipt.

    Money IN = debit cash, credit income.
    """
    # Sanity: the cash account must exist and belong to us.
    _get_account(db, organization_id, payload.cash_gl_account_id)

    lines: List[PostingLine] = []

    # ---- Cash side: one debit line for the total ----
    cash_line = PostingLine(
        gl_account_id=payload.cash_gl_account_id,
        property_id=payload.property_id,
        unit_id=payload.unit_id,
        description=f"{payload.type.title()} receipt",
        debit=Decimal(payload.amount),
        credit=Decimal("0"),
    )
    lines.append(cash_line)

    # ---- Income side ----
    if payload.type == "TENANT":
        if not payload.lines:
            raise PostingError(
                "A TENANT receipt must have at least one line."
            )
        total_credits = Decimal("0")
        for ln in payload.lines:
            if ln.amount_to_pay <= 0:
                # Skip zero lines instead of erroring, so the
                # frontend can send the whole charges table and
                # let us filter.
                continue
            _get_account(db, organization_id, ln.gl_account_id)
            total_credits += Decimal(ln.amount_to_pay)
            lines.append(
                PostingLine(
                    gl_account_id=ln.gl_account_id,
                    property_id=ln.property_id or payload.property_id,
                    unit_id=ln.unit_id or payload.unit_id,
                    description=ln.description or "Tenant payment",
                    debit=Decimal("0"),
                    credit=Decimal(ln.amount_to_pay),
                )
            )
        if total_credits == 0:
            raise PostingError(
                "A TENANT receipt must have at least one non-zero line."
            )
        if total_credits != Decimal(payload.amount):
            raise PostingError(
                f"Tenant receipt lines total {total_credits} but "
                f"receipt amount is {payload.amount}. They must match."
            )

    elif payload.type == "OWNER":
        if payload.income_gl_account_id is None:
            raise PostingError(
                "An OWNER receipt must specify income_gl_account_id."
            )
        _get_account(db, organization_id, payload.income_gl_account_id)
        lines.append(
            PostingLine(
                gl_account_id=payload.income_gl_account_id,
                property_id=payload.property_id,
                unit_id=payload.unit_id,
                description=payload.payer_name or "Owner contribution",
                debit=Decimal("0"),
                credit=Decimal(payload.amount),
            )
        )

    elif payload.type == "OTHER":
        if payload.income_gl_account_id is None:
            raise PostingError(
                "An OTHER receipt must specify income_gl_account_id."
            )
        _get_account(db, organization_id, payload.income_gl_account_id)
        lines.append(
            PostingLine(
                gl_account_id=payload.income_gl_account_id,
                property_id=payload.property_id,
                unit_id=payload.unit_id,
                description=payload.received_from or "Other receipt",
                debit=Decimal("0"),
                credit=Decimal(payload.amount),
            )
        )

    else:
        # Should be unreachable (schema validated), but be safe.
        raise PostingError(f"Unknown receipt type: {payload.type}")

    return lines


# ============================================================
# The public function
# ============================================================

def post_receipt(
    db: Session,
    *,
    organization_id: int,
    payload: ReceiptCreateIn,
    created_by: User,
) -> Receipt:
    """Create a Receipt and post it to the GL in one transaction.

    On success: commits, returns the Receipt (with .lines loaded).
    On failure: rolls back and raises PostingError.
    """
    # ---------------------------------------------------------
    # 1. Build the GL lines
    # ---------------------------------------------------------
    posting_lines = _build_posting_lines(db, organization_id, payload)

    # ---------------------------------------------------------
    # 2. Post to the GL (this commits its own GL transaction)
    # ---------------------------------------------------------
    try:
        txn: GLTransaction = post_transaction(
            db=db,
            organization_id=organization_id,
            transaction_date=payload.receipt_date,
            transaction_type="RECEIPT",
            memo=payload.remarks,
            lines=posting_lines,
            created_by=created_by,
            reference_number=payload.reference_number,
            source_type="receipt",
            source_id=None,  # filled in below after we create the Receipt
        )
    except PostingError:
        raise
    except Exception as e:
        raise PostingError(f"Failed to post GL transaction: {e}")

    # ---------------------------------------------------------
    # 3. Save Receipt + ReceiptLine rows, linked to the GL txn
    # ---------------------------------------------------------
    try:
        receipt = Receipt(
            organization_id=organization_id,
            type=payload.type,
            receipt_date=payload.receipt_date,
            amount=Decimal(payload.amount),
            cash_gl_account_id=payload.cash_gl_account_id,
            tenant_user_id=payload.tenant_user_id,
            owner_user_id=payload.owner_user_id,
            income_gl_account_id=payload.income_gl_account_id,
            payer_name=payload.payer_name,
            received_from=payload.received_from,
            exclude_from_mgmt_fee=payload.exclude_from_mgmt_fee,
            property_id=payload.property_id,
            unit_id=payload.unit_id,
            reference_number=payload.reference_number,
            remarks=payload.remarks,
            notes=payload.notes,
            gl_transaction_id=txn.id,
            is_reversed=False,
            is_active=True,
            created_by_id=created_by.id if created_by else None,
        )
        db.add(receipt)
        db.flush()  # assigns receipt.id

        # If TENANT, save one ReceiptLine per line the frontend
        # sent. For OWNER/OTHER, save one line that mirrors the
        # single income posting.
        if payload.type == "TENANT":
            for ln in payload.lines:
                if ln.amount_to_pay <= 0:
                    continue
                db.add(
                    ReceiptLine(
                        organization_id=organization_id,
                        receipt_id=receipt.id,
                        gl_account_id=ln.gl_account_id,
                        property_id=ln.property_id or payload.property_id,
                        unit_id=ln.unit_id or payload.unit_id,
                        description=ln.description,
                        amount_to_pay=Decimal(ln.amount_to_pay),
                        line_date=ln.line_date or payload.receipt_date,
                        is_prepayment=ln.is_prepayment,
                    )
                )
        else:
            # OWNER or OTHER: a single auto-line on the income side
            db.add(
                ReceiptLine(
                    organization_id=organization_id,
                    receipt_id=receipt.id,
                    gl_account_id=payload.income_gl_account_id,
                    property_id=payload.property_id,
                    unit_id=payload.unit_id,
                    description=(
                        payload.payer_name
                        if payload.type == "OWNER"
                        else payload.received_from
                    ),
                    amount_to_pay=Decimal(payload.amount),
                    line_date=payload.receipt_date,
                    is_prepayment=False,
                )
            )

        # Link the GL transaction back to this receipt (source_id)
        txn.source_id = receipt.id
        txn.source_type = "receipt"

        db.commit()
        db.refresh(receipt)
        db.refresh(txn)

    except Exception as e:
        db.rollback()
        raise PostingError(f"Failed to save receipt: {e}")

    # ---------------------------------------------------------
    # 4. Audit log (best-effort)
    # ---------------------------------------------------------
    try:
        log_action(
            db=db,
            user=created_by,
            entity_type="receipt",
            entity_id=receipt.id,
            action="create",
            field_name=payload.type,
            old_value=None,
            new_value=f"{payload.amount} via GL txn #{txn.id}",
        )
    except Exception:
        pass

    return receipt


# ============================================================
# Reversal
# ============================================================

def reverse_receipt(
    db: Session,
    *,
    original: Receipt,
    reversal_date: date,
    memo: Optional[str],
    created_by: User,
) -> Receipt:
    """Reverse a posted receipt.

    Steps:
      1. Reverse the underlying GL transaction (flips all lines)
      2. Mark original.is_reversed = True
      3. Create a new Receipt row that mirrors the original
         (with debit/credit flipped on the GL side already),
         linked via reversal_of_id.
    """
    from app.services.gl_posting import reverse_transaction

    if original.is_reversed:
        raise PostingError("This receipt has already been reversed.")

    # 1. Reverse the GL transaction
    if original.gl_transaction_id is None:
        raise PostingError(
            "This receipt has no GL transaction; cannot reverse."
        )
    txn = (
        db.query(GLTransaction)
        .filter(GLTransaction.id == original.gl_transaction_id)
        .first()
    )
    if txn is None:
        raise PostingError(
            "Underlying GL transaction not found; cannot reverse."
        )

    reversed_txn = reverse_transaction(
        db=db,
        original=txn,
        reversal_date=reversal_date,
        created_by=created_by,
        memo=memo or f"Reversal of receipt #{original.id}",
    )

    # 2. Mark original
    original.is_reversed = True
    db.flush()

    # 3. Mirror the receipt (with the reversal GL txn attached)
    try:
        mirror = Receipt(
            organization_id=original.organization_id,
            type=original.type,
            receipt_date=reversal_date,
            amount=-Decimal(original.amount) if False else Decimal(original.amount),
            cash_gl_account_id=original.cash_gl_account_id,
            tenant_user_id=original.tenant_user_id,
            owner_user_id=original.owner_user_id,
            income_gl_account_id=original.income_gl_account_id,
            payer_name=original.payer_name,
            received_from=original.received_from,
            exclude_from_mgmt_fee=original.exclude_from_mgmt_fee,
            property_id=original.property_id,
            unit_id=original.unit_id,
            reference_number=original.reference_number,
            remarks=memo or f"Reversal of receipt #{original.id}",
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
        raise PostingError(f"Failed to save reversal receipt: {e}")

    try:
        log_action(
            db=db,
            user=created_by,
            entity_type="receipt",
            entity_id=original.id,
            action="reverse",
            field_name="is_reversed",
            old_value="False",
            new_value=f"True (mirror receipt #{mirror.id})",
        )
    except Exception:
        pass

    return mirror