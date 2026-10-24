"""Read-only trust BANK-TO-GL book cash as of a recorded transaction date.

This is neither an external bank statement nor evidence of a completed
three-way reconciliation or a tenant/owner deposit liability balance.
Physical account/routing numbers remain inaccessible to this report.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Mapping

from sqlalchemy.orm import Session

from app.models.bank_account import BankAccount
from app.models.gl_account import GLAccount
from app.models.user import User, UserRole
from app.services.cash_flow import _account_totals
from app.services.menu_resolver import permission_allows_user
from app.services.report_delivery import ReportDeliveryError, ReportPayload, _date_param, _int_param

HEADERS = (
    "Bank ID", "Bank Display Name", "Bank Type", "Bank Record Status",
    "Mapped Cash GL Number", "GL Record Status", "Posted GL Book Balance",
)


def build_trust_account_balance(
    db: Session, *, organization_id: int, current_user: User,
    parameters: Mapping[str, object],
) -> ReportPayload:
    if set(parameters) - {"as_of", "bank_id"}:
        raise ReportDeliveryError("Unsupported trust account balance parameter")
    if (
        current_user.organization_id != organization_id
        or not current_user.is_active
        or current_user.deleted_at is not None
        or current_user.role != UserRole.ADMIN
    ):
        raise ReportDeliveryError("Trust account balance permission required")
    for key in ("REPORTING.ALL", "ACCOUNTING.BANK_ACCOUNTS", "ACCOUNTING.GL_ACCOUNTS"):
        if not permission_allows_user(db, user=current_user, menu_key=key):
            raise ReportDeliveryError("Trust account balance permission required")

    as_of = _date_param(parameters, "as_of")
    if as_of is None:
        raise ReportDeliveryError("as_of is required")
    requested_bank_id = _int_param(parameters, "bank_id")
    # Include archived bank mappings and GL accounts: dropping past posted
    # balances because the account was closed would falsify historical totals.
    all_banks = db.query(BankAccount).filter(
        BankAccount.organization_id == organization_id,
    ).order_by(BankAccount.name.asc(), BankAccount.id.asc()).all()

    if requested_bank_id is not None and not any(b.id == requested_bank_id for b in all_banks):
        raise ReportDeliveryError("Bank account not found")
    seen: dict[int, int] = {}
    valid: list[tuple[BankAccount, GLAccount]] = []
    for bank in all_banks:
        if bank.account_type not in ("OPERATING", "ESCROW"):
            raise ReportDeliveryError("Trust bank classification needs review")
        # Never use the mapped relationship to fetch foreign-org GL metadata.
        gl = db.query(GLAccount).filter(
            GLAccount.id == bank.gl_account_id,
            GLAccount.organization_id == organization_id,
            GLAccount.account_type == "ASSET",
        ).first()
        if gl is None:
            raise ReportDeliveryError("Bank-to-GL cash mapping needs review")
        if gl.id in seen:
            # Two bank records on one GL cannot have independent book balances.
            raise ReportDeliveryError("Duplicate cash GL mapping needs review")
        seen[gl.id] = bank.id
        if requested_bank_id is None or bank.id == requested_bank_id:
            valid.append((bank, gl))
    if not valid:
        raise ReportDeliveryError("No configured trust bank account found")

    balances = _account_totals(
        db, organization_id=organization_id,
        gl_ids=tuple(gl.id for _, gl in valid), date_to=as_of,
    )
    rows: list[tuple[object, ...]] = []
    total = Decimal("0")
    for bank, gl in valid:
        dr, cr = balances.get(gl.id, (Decimal("0"), Decimal("0")))
        amount = dr - cr
        total += amount
        bank_status = "ACTIVE" if bank.is_active and bank.deleted_at is None else "ARCHIVED"
        gl_status = "ACTIVE" if gl.is_active and gl.deleted_at is None else "ARCHIVED"
        rows.append((
            bank.id, bank.name, bank.account_type, bank_status,
            gl.gl_number, gl_status, amount,
        ))
    rows.append(("TOTAL", "Mapped trust bank book cash", "", "", "", "", total))
    return ReportPayload(
        title=(
            f"Posted GL trust bank BOOK balance as of {as_of.isoformat()} "
            "(unaudited; no bank statement, clearing, owner/tenant liability, "
            "or three-way reconciliation; bank mapping only)"
        ),
        filename=f"trust-bank-book-balance-{as_of.isoformat()}.csv",
        headers=HEADERS, rows=tuple(rows),
    )
