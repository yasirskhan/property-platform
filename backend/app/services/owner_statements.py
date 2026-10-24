# ============================================================
# owner_statements.py
# ------------------------------------------------------------
# Owner Statement engine.
#
# AppFolio parity:
#   * One statement per owner per period
#   * One section per property the owner has a stake in
#   * Beginning cash, transaction list, ending cash
#   * Numbers are FROZEN once generated (snapshot model)
#
# Where the numbers come from:
#   * property_owners (ownership splits) + Property.owner_id (primary)
#   * gl_entries scoped by property_id in the period
#   * Beginning cash = sum of activity on cash GL accounts (11xx)
#     BEFORE period_start, for the property
#   * Transactions = GL activity in the period on the property
#     that touches a cash or income/expense account. We show
#     cash-moving entries (debits/credits to cash accounts) as
#     the primary lines because that is what owners care about.
#   * Ending cash = beginning cash + net cash movement in period
#
# Snapshot: once generated, the JSON `property_data` is frozen.
# Later GL corrections do NOT rewrite the statement.
# ============================================================

from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.audit import log_action
from app.models.gl_account import GLAccount
from app.models.gl_entry import GLEntry
from app.models.gl_transaction import GLTransaction
from app.models.owner_statement import OwnerStatement
from app.models.property import Property, PropertyOwner
from app.models.user import User
from app.services.gl_posting import PostingError


# ============================================================
# Helpers
# ============================================================

def _money_str(v: Decimal) -> str:
    return f"{Decimal(v).quantize(Decimal('0.01'))}"


def _properties_for_owner(
    db: Session, organization_id: int, owner_id: int
) -> List[tuple[Property, Decimal]]:
    """
    Return every property the owner has a stake in, along with
    their ownership_pct for that property.

    Combines:
      * Property.owner_id (primary) — pct from ownership_pct
      * property_owners (split) — pct from that row

    Deduplicates by property_id; prefers the ownership_pct from
    property_owners when both exist.
    """
    seen: dict[int, tuple[Property, Decimal]] = {}

    # Primary ownership
    primary = (
        db.query(Property)
        .filter(
            Property.organization_id == organization_id,
            Property.owner_id == owner_id,
        )
        .all()
    )
    for p in primary:
        pct = Decimal(p.ownership_pct or 100)
        seen[p.id] = (p, pct)

    # Split ownership
    split_rows = (
        db.query(PropertyOwner)
        .filter(
            PropertyOwner.organization_id == organization_id,
            PropertyOwner.user_id == owner_id,
            PropertyOwner.is_active.is_(True),
        )
        .all()
    )
    for row in split_rows:
        prop = (
            db.query(Property)
            .filter(Property.id == row.property_id)
            .first()
        )
        if prop is None:
            continue
        seen[prop.id] = (prop, Decimal(row.ownership_pct or 0))

    return list(seen.values())


def _cash_account_ids(db: Session, organization_id: int) -> List[int]:
    """All asset-type GL accounts whose gl_number starts with '11'."""
    rows = (
        db.query(GLAccount.id)
        .filter(
            GLAccount.organization_id == organization_id,
            GLAccount.account_type == "ASSET",
            GLAccount.gl_number.like("11%"),
        )
        .all()
    )
    return [r[0] for r in rows]


def _cash_activity_for_property(
    db: Session,
    organization_id: int,
    property_id: int,
    cash_account_ids: List[int],
    before: Optional[date] = None,
    on_or_after: Optional[date] = None,
    on_or_before: Optional[date] = None,
) -> Decimal:
    """Sum of (debit - credit) on cash accounts for this property."""
    q = (
        db.query(
            func.coalesce(func.sum(GLEntry.debit), 0),
            func.coalesce(func.sum(GLEntry.credit), 0),
        )
        .join(GLTransaction, GLTransaction.id == GLEntry.transaction_id)
        .filter(
            GLEntry.organization_id == organization_id,
            GLEntry.property_id == property_id,
            GLEntry.gl_account_id.in_(cash_account_ids),
        )
    )
    if before is not None:
        q = q.filter(GLTransaction.transaction_date < before)
    if on_or_after is not None:
        q = q.filter(GLTransaction.transaction_date >= on_or_after)
    if on_or_before is not None:
        q = q.filter(GLTransaction.transaction_date <= on_or_before)

    debit_total, credit_total = q.one()
    return Decimal(debit_total or 0) - Decimal(credit_total or 0)


def _liability_balance_for_property(
    db: Session,
    organization_id: int,
    property_id: int,
    gl_number: str,
    *,
    on_or_before: date,
) -> Decimal:
    """Natural liability balance (credits - debits) for a property."""
    account_ids = [
        row[0]
        for row in (
            db.query(GLAccount.id)
            .filter(
                GLAccount.organization_id == organization_id,
                GLAccount.gl_number == gl_number,
            )
            .all()
        )
    ]
    if not account_ids:
        return Decimal("0")

    debit_total, credit_total = (
        db.query(
            func.coalesce(func.sum(GLEntry.debit), 0),
            func.coalesce(func.sum(GLEntry.credit), 0),
        )
        .join(GLTransaction, GLTransaction.id == GLEntry.transaction_id)
        .filter(
            GLEntry.organization_id == organization_id,
            GLEntry.property_id == property_id,
            GLEntry.gl_account_id.in_(account_ids),
            GLTransaction.transaction_date <= on_or_before,
        )
        .one()
    )
    return Decimal(credit_total or 0) - Decimal(debit_total or 0)


def _transactions_for_property(
    db: Session,
    organization_id: int,
    property_id: int,
    cash_account_ids: List[int],
    period_start: date,
    period_end: date,
    beginning_cash: Decimal = Decimal("0"),
) -> List[dict]:
    """
    All GL transactions in the period that touch the property.
    Each row is a transaction header with its total cash movement
    and total income/expense movement, for display on the statement.
    """
    # Gather transactions that touch this property in the period
    txn_ids = [
        r[0]
        for r in (
            db.query(GLEntry.transaction_id)
            .join(
                GLTransaction, GLTransaction.id == GLEntry.transaction_id
            )
            .filter(
                GLEntry.organization_id == organization_id,
                GLEntry.property_id == property_id,
                GLTransaction.transaction_date >= period_start,
                GLTransaction.transaction_date <= period_end,
            )
            .distinct()
            .all()
        )
    ]
    if not txn_ids:
        return []

    rows = (
        db.query(GLEntry, GLTransaction, GLAccount)
        .join(GLTransaction, GLTransaction.id == GLEntry.transaction_id)
        .join(GLAccount, GLAccount.id == GLEntry.gl_account_id)
        .filter(
            GLEntry.transaction_id.in_(txn_ids),
            GLEntry.property_id == property_id,
        )
        .order_by(
            GLTransaction.transaction_date.asc(),
            GLTransaction.id.asc(),
            GLEntry.id.asc(),
        )
        .all()
    )

    # Group entries by transaction id
    grouped: dict[int, dict] = {}
    for entry, txn, acct in rows:
        key = txn.id
        if key not in grouped:
            grouped[key] = {
                "txn": txn,
                "debit": Decimal("0"),
                "credit": Decimal("0"),
                "cash_movement": Decimal("0"),
                "income": Decimal("0"),
                "expense": Decimal("0"),
            }
        d = Decimal(entry.debit or 0)
        c = Decimal(entry.credit or 0)
        grouped[key]["debit"] += d
        grouped[key]["credit"] += c
        if acct.id in cash_account_ids:
            grouped[key]["cash_movement"] += d - c
        if acct.account_type == "INCOME":
            grouped[key]["income"] += c - d
        if acct.account_type == "EXPENSE":
            grouped[key]["expense"] += d - c

    result: List[dict] = []
    running = Decimal(beginning_cash)
    for key in sorted(grouped.keys()):
        g = grouped[key]
        txn = g["txn"]
        running += g["cash_movement"]
        result.append(
            {
                "gl_transaction_id": txn.id,
                "date": txn.transaction_date.isoformat(),
                "description": txn.memo or txn.transaction_type,
                "reference": txn.reference_number,
                "income": _money_str(g["income"]),
                "expense": _money_str(g["expense"]),
                "cash_movement": _money_str(g["cash_movement"]),
                "running_balance": _money_str(running),
            }
        )
    return result


# ============================================================
# Preview — compute without saving
# ============================================================

def preview_owner_statement(
    db: Session,
    *,
    organization_id: int,
    owner_id: int,
    period_start: date,
    period_end: date,
) -> dict:
    owner = (
        db.query(User)
        .filter(
            User.id == owner_id,
            User.organization_id == organization_id,
        )
        .first()
    )
    if owner is None:
        raise PostingError(
            f"Owner {owner_id} not found in your organization."
        )

    cash_ids = _cash_account_ids(db, organization_id)
    if not cash_ids:
        return {
            "owner_id": owner_id,
            "owner_email": owner.email,
            "owner_name": getattr(owner, "full_name", None) or owner.email,
            "period_start": period_start,
            "period_end": period_end,
            "total_beginning_cash": Decimal("0"),
            "total_ending_cash": Decimal("0"),
            "total_income": Decimal("0"),
            "total_expense": Decimal("0"),
            "total_net": Decimal("0"),
            "properties": [],
            "can_generate": False,
            "reason": "No cash GL accounts configured.",
        }

    props = _properties_for_owner(db, organization_id, owner_id)

    total_beginning = Decimal("0")
    total_ending = Decimal("0")
    total_income = Decimal("0")
    total_expense = Decimal("0")
    total_required_reserves = Decimal("0")
    total_prepaid_rent = Decimal("0")
    total_available_cash = Decimal("0")

    property_blocks: List[dict] = []

    for prop, ownership_pct in props:
        beginning_cash = _cash_activity_for_property(
            db,
            organization_id,
            prop.id,
            cash_ids,
            before=period_start,
        )
        ending_cash = _cash_activity_for_property(
            db,
            organization_id,
            prop.id,
            cash_ids,
            on_or_before=period_end,
        )
        txns = _transactions_for_property(
            db,
            organization_id,
            prop.id,
            cash_ids,
            period_start,
            period_end,
            beginning_cash=beginning_cash,
        )

        income = sum(Decimal(t["income"]) for t in txns)
        expense = sum(Decimal(t["expense"]) for t in txns)
        net = ending_cash - beginning_cash
        required_reserves = Decimal(prop.required_reserve_amount or 0)
        prepaid_rent = _liability_balance_for_property(
            db,
            organization_id,
            prop.id,
            "2300",
            on_or_before=period_end,
        )
        available_cash = ending_cash - required_reserves - prepaid_rent

        # Owner gets their share. We still SHOW the full
        # property numbers and the ownership_pct so the owner
        # can see the split. This matches AppFolio.
        total_beginning += beginning_cash
        total_ending += ending_cash
        total_income += income
        total_expense += expense
        total_required_reserves += required_reserves
        total_prepaid_rent += prepaid_rent
        total_available_cash += available_cash

        property_blocks.append(
            {
                "property_id": prop.id,
                "property_name": prop.name,
                "ownership_pct": _money_str(ownership_pct),
                "beginning_cash": _money_str(beginning_cash),
                "ending_cash": _money_str(ending_cash),
                "income": _money_str(income),
                "expense": _money_str(expense),
                "net": _money_str(net),
                "required_reserves": _money_str(required_reserves),
                "prepaid_rent": _money_str(prepaid_rent),
                "available_cash": _money_str(available_cash),
                "transactions": txns,
            }
        )

    total_net = total_ending - total_beginning

    return {
        "owner_id": owner_id,
        "owner_email": owner.email,
        "owner_name": getattr(owner, "full_name", None) or owner.email,
        "period_start": period_start,
        "period_end": period_end,
        "total_beginning_cash": total_beginning,
        "total_ending_cash": total_ending,
        "total_income": total_income,
        "total_expense": total_expense,
        "total_net": total_net,
        "total_required_reserves": total_required_reserves,
        "total_prepaid_rent": total_prepaid_rent,
        "total_available_cash": total_available_cash,
        "properties": property_blocks,
        "can_generate": True,
        "reason": None,
    }


# ============================================================
# Generate — compute + freeze
# ============================================================

def generate_owner_statement(
    db: Session,
    *,
    organization_id: int,
    owner_id: int,
    period_start: date,
    period_end: date,
    notes: Optional[str],
    created_by: User,
) -> OwnerStatement:
    preview = preview_owner_statement(
        db,
        organization_id=organization_id,
        owner_id=owner_id,
        period_start=period_start,
        period_end=period_end,
    )
    if not preview["can_generate"]:
        raise PostingError(preview["reason"] or "Cannot generate statement.")

    try:
        stmt = OwnerStatement(
            organization_id=organization_id,
            owner_id=owner_id,
            period_start=period_start,
            period_end=period_end,
            generated_at=datetime.utcnow(),
            total_beginning_cash=preview["total_beginning_cash"],
            total_ending_cash=preview["total_ending_cash"],
            total_income=preview["total_income"],
            total_expense=preview["total_expense"],
            total_net=preview["total_net"],
            property_data=json.dumps(preview["properties"]),
            notes=notes,
            is_active=True,
            generated_by_id=created_by.id if created_by else None,
        )
        db.add(stmt)
        db.commit()
        db.refresh(stmt)
    except Exception as e:
        db.rollback()
        raise PostingError(f"Failed to save owner statement: {e}")

    try:
        log_action(
            db=db,
            user=created_by,
            entity_type="owner_statement",
            entity_id=stmt.id,
            action="create",
            field_name="period",
            old_value=None,
            new_value=f"{period_start}..{period_end}",
        )
    except Exception:
        pass

    return stmt