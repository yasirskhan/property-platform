# ============================================================
# deposit_posting.py
# ------------------------------------------------------------
# Bank Deposit service.
#
# Deposits group already-posted receipts. They do NOT create GL
# transactions. deposit_lines remains the source of truth for
# receipt membership.
# ============================================================
from __future__ import annotations

import re
from decimal import Decimal
from typing import List

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.audit import log_action
from app.models.deposit import Deposit
from app.models.deposit_line import DepositLine
from app.models.gl_account import GLAccount
from app.models.receipt import Receipt
from app.models.user import User
from app.services.gl_posting import PostingError

_AUTO_NUMBER_RE = re.compile(r"^D-\d{5}$")


def _validate_bank_account(
    db: Session, *, organization_id: int, bank_gl_account_id: int
) -> GLAccount:
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
        raise PostingError(f"Bank GL account {bank_acct.name} is inactive.")
    return bank_acct


def _load_receipts(
    db: Session,
    *,
    organization_id: int,
    receipt_ids: List[int],
    editing_deposit_id: int | None = None,
) -> list[Receipt]:
    if not receipt_ids:
        raise PostingError("A deposit must include at least one receipt.")

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
        raise PostingError(f"Receipt(s) not found in your org: {sorted(missing)}")

    for receipt in receipts:
        if receipt.is_reversed:
            raise PostingError(
                f"Receipt #{receipt.id} is reversed and cannot be deposited."
            )
        if not receipt.is_active:
            raise PostingError(f"Receipt #{receipt.id} is inactive.")

    already_q = db.query(DepositLine.receipt_id).filter(
        DepositLine.organization_id == organization_id,
        DepositLine.receipt_id.in_(receipt_ids),
    )
    if editing_deposit_id is not None:
        already_q = already_q.filter(DepositLine.deposit_id != editing_deposit_id)
    already = already_q.all()
    if already:
        ids = sorted(rid for (rid,) in already)
        raise PostingError(f"Receipt(s) already deposited: {ids}")
    return receipts


def _next_bank_sequence(
    db: Session, *, organization_id: int, bank_gl_account_id: int
) -> int:
    current = (
        db.query(func.max(Deposit.bank_sequence))
        .filter(
            Deposit.organization_id == organization_id,
            Deposit.bank_gl_account_id == bank_gl_account_id,
        )
        .scalar()
    )
    return int(current or 0) + 1


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
    _validate_bank_account(
        db,
        organization_id=organization_id,
        bank_gl_account_id=bank_gl_account_id,
    )
    receipts = _load_receipts(
        db, organization_id=organization_id, receipt_ids=receipt_ids
    )
    total = sum((Decimal(r.amount or 0) for r in receipts), Decimal("0"))
    sequence = _next_bank_sequence(
        db,
        organization_id=organization_id,
        bank_gl_account_id=bank_gl_account_id,
    )
    try:
        deposit = Deposit(
            organization_id=organization_id,
            bank_gl_account_id=bank_gl_account_id,
            bank_sequence=sequence,
            deposit_date=deposit_date,
            deposit_number=deposit_number or f"D-{sequence:05d}",
            description=description,
            total=total,
            notes=notes,
            is_active=True,
            created_by_id=created_by.id if created_by else None,
        )
        db.add(deposit)
        db.flush()
        for rid in receipt_ids:
            db.add(
                DepositLine(
                    organization_id=organization_id,
                    deposit_id=deposit.id,
                    receipt_id=rid,
                )
            )
        db.commit()
        db.refresh(deposit)
    except Exception as exc:
        db.rollback()
        raise PostingError(f"Failed to save deposit: {exc}")

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


def edit_deposit(
    db: Session,
    *,
    deposit: Deposit,
    deposit_date=None,
    deposit_number=None,
    description=None,
    notes=None,
    receipt_ids: List[int] | None = None,
    fields_set: set[str] | None = None,
    edited_by: User,
) -> Deposit:
    """Edit grouping metadata and/or receipt membership without GL writes."""
    fields_set = fields_set or set()
    receipts = None
    if receipt_ids is not None:
        receipts = _load_receipts(
            db,
            organization_id=deposit.organization_id,
            receipt_ids=receipt_ids,
            editing_deposit_id=deposit.id,
        )

    old_total = Decimal(deposit.total or 0)
    try:
        if "deposit_date" in fields_set and deposit_date is not None:
            deposit.deposit_date = deposit_date
        if "deposit_number" in fields_set:
            deposit.deposit_number = deposit_number or f"D-{deposit.bank_sequence:05d}"
        if "description" in fields_set:
            deposit.description = description
        if "notes" in fields_set:
            deposit.notes = notes
        if receipts is not None:
            db.query(DepositLine).filter(
                DepositLine.organization_id == deposit.organization_id,
                DepositLine.deposit_id == deposit.id,
            ).delete(synchronize_session=False)
            for rid in receipt_ids or []:
                db.add(
                    DepositLine(
                        organization_id=deposit.organization_id,
                        deposit_id=deposit.id,
                        receipt_id=rid,
                    )
                )
            deposit.total = sum(
                (Decimal(r.amount or 0) for r in receipts), Decimal("0")
            )
        db.commit()
        db.refresh(deposit)
    except Exception as exc:
        db.rollback()
        raise PostingError(f"Failed to edit deposit: {exc}")

    try:
        log_action(
            db=db,
            user=edited_by,
            entity_type="deposit",
            entity_id=deposit.id,
            action="update",
            field_name="total",
            old_value=str(old_total),
            new_value=str(deposit.total),
        )
    except Exception:
        pass
    return deposit


def list_undeposited_receipts(
    db: Session,
    *,
    organization_id: int,
    bank_gl_account_id: int | None = None,
) -> List[Receipt]:
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
