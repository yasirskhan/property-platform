# ============================================================
# owner_ledger.py
# ------------------------------------------------------------
# The owner SUB-LEDGER.
#
# AppFolio parity: this is the "third leg" of the trust account
# three-way reconciliation. The three numbers that must agree:
#
#   1. Bank statement balance
#   2. Trust GL cash balance (e.g. 1150 Rental Trust)
#   3. Sum of every owner sub-ledger balance
#
# This module computes #3. It combines all GL activity scoped
# by owner_id across every property that owner owns (via the
# primary owner_id and the property_owners join table).
#
# What counts as an "owner balance":
#   * Income GL lines tagged to the owner (increase what they're owed)
#   * Expense GL lines tagged to the owner (reduce what they're owed)
#   * Owner-contribution receipts (decrease what they're owed)
#   * Owner draws / distributions (decrease what they're owed)
#
# The balance is derived entirely from GL entries with
# owner_id set, so it will always reconcile to the trust cash
# when the postings are correct.
# ============================================================

from __future__ import annotations

from decimal import Decimal
from typing import Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.gl_account import GLAccount
from app.models.gl_entry import GLEntry
from app.models.gl_transaction import GLTransaction
from app.models.property import Property, PropertyOwner
from app.models.user import User


# ============================================================
# Shape returned by get_owner_subledger
# ============================================================

def _compute_owner_balance_row(
    db: Session, organization_id: int, owner_id: int
) -> Dict:
    """
    Compute one owner's sub-ledger balance by summing all GL
    activity tagged with their owner_id, using the natural sign
    of each account type:
        INCOME     -> credit increases owner's owed
        EXPENSE    -> debit decreases owner's owed
        ASSET      -> debit increases owner's owed
        LIABILITY  -> credit increases owner's owed
        EQUITY     -> credit increases owner's owed

    We express the balance as: owner's net position (positive =
    the trust owes the owner; negative = the owner owes the trust).

    Company-level entries (owner_id is NULL) are NOT included.
    """
    # Sum by account type, with the correct sign.
    rows = (
        db.query(
            GLAccount.account_type,
            func.coalesce(func.sum(GLEntry.debit), 0).label("debits"),
            func.coalesce(func.sum(GLEntry.credit), 0).label("credits"),
        )
        .join(GLEntry, GLEntry.gl_account_id == GLAccount.id)
        .join(
            GLTransaction,
            GLTransaction.id == GLEntry.transaction_id,
        )
        .filter(
            GLEntry.organization_id == organization_id,
            GLEntry.owner_id == owner_id,
        )
        .group_by(GLAccount.account_type)
        .all()
    )

    total = Decimal("0")
    by_type: Dict[str, Decimal] = {}
    for account_type, debits, credits in rows:
        d = Decimal(debits or 0)
        c = Decimal(credits or 0)
        at = (account_type or "").upper()

        if at == "INCOME":
            # Income earned -> owner is owed.  net = credit - debit
            net = c - d
        elif at == "EXPENSE":
            # Expense paid -> reduces what owner is owed.
            net = -(d - c)
        elif at == "ASSET":
            # Assets purchased for the owner increase owner equity.
            net = d - c
        elif at == "LIABILITY":
            # Liability in owner's name -> reduces owner's net.
            net = -(c - d)
        elif at == "EQUITY":
            net = c - d
        else:
            net = Decimal("0")

        by_type[at] = by_type.get(at, Decimal("0")) + net
        total += net

    # Count the GL entries that make up this balance so we can
    # show the user something meaningful.
    entry_count = (
        db.query(func.count(GLEntry.id))
        .filter(
            GLEntry.organization_id == organization_id,
            GLEntry.owner_id == owner_id,
        )
        .scalar()
        or 0
    )

    return {
        "owner_id": owner_id,
        "balance": total,
        "by_account_type": by_type,
        "entry_count": int(entry_count),
    }


# ============================================================
# Public: get one owner's sub-ledger
# ============================================================

def get_owner_subledger(
    db: Session,
    *,
    organization_id: int,
    owner_id: int,
) -> Optional[Dict]:
    """
    Return the sub-ledger summary for one owner.

    Includes:
      - owner metadata (email, name)
      - the properties this owner is attached to (primary + splits)
      - total balance and per-account-type breakdown
      - GL entry count contributing to the balance

    Returns None if the owner doesn't exist in the org.
    """
    owner = (
        db.query(User)
        .filter(
            User.id == owner_id,
            User.organization_id == organization_id,
        )
        .first()
    )
    if owner is None:
        return None

    # Properties this owner is attached to (primary + join table)
    primary_props = (
        db.query(Property)
        .filter(
            Property.organization_id == organization_id,
            Property.owner_id == owner_id,
        )
        .all()
    )
    split_props = (
        db.query(Property)
        .join(PropertyOwner, PropertyOwner.property_id == Property.id)
        .filter(
            PropertyOwner.organization_id == organization_id,
            PropertyOwner.user_id == owner_id,
            PropertyOwner.is_active.is_(True),
        )
        .all()
    )
    # Deduplicate by id
    props_by_id = {p.id: p for p in primary_props}
    for p in split_props:
        props_by_id.setdefault(p.id, p)
    properties = list(props_by_id.values())

    balance_row = _compute_owner_balance_row(db, organization_id, owner_id)

    return {
        "owner_id": owner.id,
        "owner_email": owner.email,
        "owner_name": (
            owner.full_name
            if getattr(owner, "full_name", None)
            else owner.email
        ),
        "properties": [
            {
                "id": p.id,
                "name": p.name,
                "ownership_pct": float(p.ownership_pct or 0),
            }
            for p in properties
        ],
        "balance": balance_row["balance"],
        "by_account_type": balance_row["by_account_type"],
        "entry_count": balance_row["entry_count"],
    }


# ============================================================
# Public: totals across every owner (the third leg)
# ============================================================

def get_all_owner_subledger_totals(
    db: Session,
    *,
    organization_id: int,
) -> Dict:
    """
    Sum every owner's sub-ledger balance into one number.

    This is the third leg of the 3-way reconciliation. It should
    equal the trust cash GL balance when everything is posted
    correctly.
    """
    # Every owner in the org (role == OWNER)
    owners = (
        db.query(User)
        .filter(
            User.organization_id == organization_id,
            User.role == "OWNER",
        )
        .all()
    )

    total = Decimal("0")
    per_owner: List[Dict] = []
    for owner in owners:
        row = _compute_owner_balance_row(db, organization_id, owner.id)
        total += row["balance"]
        per_owner.append(
            {
                "owner_id": owner.id,
                "owner_email": owner.email,
                "balance": row["balance"],
                "entry_count": row["entry_count"],
            }
        )

    return {
        "total": total,
        "owner_count": len(per_owner),
        "per_owner": per_owner,
    }


# ============================================================
# Public: the raw third-leg number for the 3-way reconciliation
# ============================================================

def get_owner_subledger_total(
    db: Session,
    *,
    organization_id: int,
) -> Decimal:
    """Convenience: just the sum, no details. Used by diagnostics."""
    return get_all_owner_subledger_totals(
        db, organization_id=organization_id
    )["total"]