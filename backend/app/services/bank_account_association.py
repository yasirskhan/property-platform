"""Org-scoped, read-only BankAccount -> GLAccount configuration inventory.

This report reflects ONLY the recorded bank-to-GL mapping. It does not
assert property-to-bank associations, cleared balances, bank feed/statement
activity, or the validity of stored routing/account-number credentials.
"""
from __future__ import annotations

from typing import Mapping

from sqlalchemy.orm import Session

from app.models.bank_account import BankAccount
from app.models.gl_account import GLAccount
from app.models.user import User, UserRole
from app.services.menu_resolver import permission_allows_user
from app.services.report_delivery import (
    ReportDeliveryError, ReportPayload, _bool_param, _int_param,
)

HEADERS = (
    "Bank ID", "Bank Display Name", "Bank Type", "Bank Record Status",
    "GL Account Number", "GL Account Name", "GL Account Status",
    "Mapping Status",
)


def build_bank_account_association(
    db: Session, *, organization_id: int, current_user: User,
    parameters: Mapping[str, object],
) -> ReportPayload:
    if set(parameters) - {"bank_id", "include_inactive"}:
        raise ReportDeliveryError("Unsupported bank association parameter")
    if (
        current_user.organization_id != organization_id
        or not current_user.is_active
        or current_user.deleted_at is not None
        or current_user.role != UserRole.ADMIN
    ):
        raise ReportDeliveryError("Bank association permission required")
    for key in ("REPORTING.ALL", "ACCOUNTING.BANK_ACCOUNTS", "ACCOUNTING.GL_ACCOUNTS"):
        if not permission_allows_user(db, user=current_user, menu_key=key):
            raise ReportDeliveryError("Bank association permission required")

    bank_id = _int_param(parameters, "bank_id")
    include_inactive = _bool_param(parameters, "include_inactive", False)
    banks = db.query(BankAccount).filter(
        BankAccount.organization_id == organization_id,
    )
    if not include_inactive:
        banks = banks.filter(
            BankAccount.is_active.is_(True),
            BankAccount.deleted_at.is_(None),
        )
    if bank_id is not None:
        banks = banks.filter(BankAccount.id == bank_id)
        if banks.first() is None:
            # No distinction between an unknown and another org's bank ID.
            raise ReportDeliveryError("Bank account not found")
    result = []
    for bank in banks.order_by(BankAccount.name.asc(), BankAccount.id.asc()).all():
        # Do not traverse the mapped relationship: malformed foreign-org
        # GL links must never reveal another organization's ledger metadata.
        gl = db.query(GLAccount).filter(
            GLAccount.id == bank.gl_account_id,
            GLAccount.organization_id == organization_id,
        ).first()
        if gl is None:
            number = name = gl_status = ""
            mapping = "UNRESOLVED"
        else:
            number = gl.gl_number
            name = gl.name
            gl_status = "ACTIVE" if gl.is_active and gl.deleted_at is None else "INACTIVE"
            mapping = "MAPPED_ASSET" if gl.account_type == "ASSET" else "REVIEW_NON_ASSET"
        bank_status = "ACTIVE" if bank.is_active and bank.deleted_at is None else "INACTIVE"
        result.append((
            bank.id, bank.name, bank.account_type, bank_status,
            number, name, gl_status, mapping,
        ))
    return ReportPayload(
        title="Recorded bank-to-GL associations (no bank numbers or property mappings)",
        filename="bank-gl-associations.csv",
        headers=HEADERS,
        rows=tuple(result),
    )
