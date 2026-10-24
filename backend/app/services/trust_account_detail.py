"""Scoped posted trust bank GL lines, tagged only when references belong to org.

Reuses verified trust-bank mapping and admin/permission safeguards. A recorded
owner/property reference is not proof that an entry belongs to that beneficiary.
No bank statements, bank-feed imports, ACH credentials or private account numbers.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Mapping

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.models.bank_account import BankAccount
from app.models.gl_entry import GLEntry
from app.models.gl_transaction import GLTransaction
from app.models.property import Property
from app.models.user import User, UserRole
from app.services.cash_flow import _account_totals
from app.services.report_delivery import (
    ReportDeliveryError, ReportPayload, _date_param, _int_param,
)
from app.services.trust_account_balance import build_trust_account_balance

HEADERS = (
    "Posted Date", "GL Entry ID", "Transaction ID", "Transaction Type",
    "Recorded Reference", "Property ID", "Owner ID", "Debit To Trust GL",
    "Credit From Trust GL", "Running Posted Book Balance", "Recorded Tag Scope",
)


def build_trust_account_detail(
    db: Session, *, organization_id: int, current_user: User,
    parameters: Mapping[str, object],
) -> ReportPayload:
    if set(parameters) - {"bank_id", "date_from", "date_to"}:
        raise ReportDeliveryError("Unsupported trust account detail parameter")
    bank_id = _int_param(parameters, "bank_id", required=True)
    start = _date_param(parameters, "date_from")
    finish = _date_param(parameters, "date_to")
    if start is None or finish is None:
        raise ReportDeliveryError("date_from and date_to are required")
    if start > finish:
        raise ReportDeliveryError("date_from cannot be after date_to")

    # The verified snapshot validates active-org ADMIN/REPORTING.ALL,
    # BANK_ACCOUNTS and GL_ACCOUNTS, bank ownership, same-org ASSET GL,
    # and uniqueness of bank-to-cash-GL mapping. Reuse, do not bypass.
    snapshot = build_trust_account_balance(
        db, organization_id=organization_id, current_user=current_user,
        parameters={"as_of": finish.isoformat(), "bank_id": bank_id},
    )
    bank = db.query(BankAccount).filter(
        BankAccount.id == bank_id,
        BankAccount.organization_id == organization_id,
    ).first()
    if bank is None:
        raise ReportDeliveryError("Bank account not found")
    bank_name = snapshot.rows[0][1]
    gl_number = snapshot.rows[0][4]
    opened = _account_totals(
        db, organization_id=organization_id,
        gl_ids=(bank.gl_account_id,), before_date=start,
    ).get(bank.gl_account_id, (Decimal("0"), Decimal("0")))
    running = opened[0] - opened[1]

    # Explicit outer-join organization checks prevent a malformed owner/
    # property pointer on an org-owned posting leaking foreign entity IDs.
    query = (
        db.query(GLEntry, GLTransaction, Property.id, User.id)
        .join(GLTransaction, GLTransaction.id == GLEntry.transaction_id)
        .outerjoin(
            Property, and_(
                Property.id == GLEntry.property_id,
                Property.organization_id == organization_id,
            ),
        )
        .outerjoin(
            User, and_(
                User.id == GLEntry.owner_id,
                User.organization_id == organization_id,
                User.role == UserRole.OWNER,
            ),
        )
        .filter(
            GLEntry.organization_id == organization_id,
            GLTransaction.organization_id == organization_id,
            GLEntry.gl_account_id == bank.gl_account_id,
            GLTransaction.transaction_date >= start,
            GLTransaction.transaction_date <= finish,
        )
        .order_by(
            GLTransaction.transaction_date.asc(),
            GLTransaction.id.asc(), GLEntry.id.asc(),
        )
    )
    rows: list[tuple[object, ...]] = [
        ("OPENING", "", "", "", "", "", "", "", "", running, ""),
    ]
    for entry, transaction, property_id, owner_id in query.all():
        debit, credit = Decimal(entry.debit or 0), Decimal(entry.credit or 0)
        running += debit - credit
        scope = []
        if entry.property_id is None:
            scope.append("PROPERTY UNALLOCATED")
        elif property_id is None:
            scope.append("PROPERTY TAG UNVERIFIED")
        else:
            scope.append("PROPERTY TAG RECORDED")
        if entry.owner_id is None:
            scope.append("OWNER UNALLOCATED")
        elif owner_id is None:
            scope.append("OWNER TAG UNVERIFIED")
        else:
            scope.append("OWNER TAG RECORDED")
        rows.append((
            transaction.transaction_date, entry.id, transaction.id,
            transaction.transaction_type, transaction.reference_number or "",
            property_id if property_id is not None else "",
            owner_id if owner_id is not None else "",
            debit, credit, running, "; ".join(scope),
        ))
    rows.append(("CLOSING", "", "", "", "", "", "", "", "", running, ""))
    return ReportPayload(
        title=(
            f"Posted trust GL BOOK detail for {bank_name} / {gl_number}, "
            f"{start.isoformat()} through {finish.isoformat()} "
            "(unaudited; recorded tags do not prove ownership; "
            "not cleared bank activity, reconciliation or available owner funds)"
        ),
        filename=(
            f"trust-bank-book-detail-{bank_id}-"
            f"{start.isoformat()}-{finish.isoformat()}.csv"
        ),
        headers=HEADERS,
        rows=tuple(rows),
    )
