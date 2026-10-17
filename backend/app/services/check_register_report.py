"""Issued/void bank check register from verified same-org Check and GL records.

An issued check is not a cleared check. Never expose routing/account numbers,
reconstruct bank balances or mutate posted GL.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Mapping

from sqlalchemy.orm import Session

from app.models.bank_account import BankAccount
from app.models.check import Check
from app.models.gl_account import GLAccount
from app.models.gl_transaction import GLTransaction
from app.models.user import User, UserRole
from app.services.menu_resolver import permission_allows_user
from app.services.report_delivery import ReportDeliveryError, ReportPayload, _date_param, _int_param


HEADERS = (
    "Check ID", "Check Date", "Check Number", "Recorded Payee",
    "Bank Display Name", "Recorded Status", "Nominal Check Amount",
    "Original GL Transaction ID", "Verified Void GL Transaction ID",
    "Recorded Void Date",
)


def build_check_register(
    db: Session, *, organization_id: int, current_user: User,
    parameters: Mapping[str, object],
) -> ReportPayload:
    if set(parameters) - {"check_id", "bank_id", "date_from", "date_to", "status"}:
        raise ReportDeliveryError("Unsupported Check Register parameter")
    if (
        current_user.organization_id != organization_id
        or not current_user.is_active or current_user.deleted_at is not None
        or current_user.role != UserRole.ADMIN
    ):
        raise ReportDeliveryError("Check Register permission required")
    for key in ("REPORTING.ALL", "ACCOUNTING.BANK_ACCOUNTS", "ACCOUNTING.PAYABLES"):
        if not permission_allows_user(db, user=current_user, menu_key=key):
            raise ReportDeliveryError("Check Register permission required")

    check_id = _int_param(parameters, "check_id")
    bank_id = _int_param(parameters, "bank_id")
    date_from = _date_param(parameters, "date_from")
    date_to = _date_param(parameters, "date_to")
    if date_from is not None and date_to is not None and date_from > date_to:
        raise ReportDeliveryError("date_from cannot be after date_to")
    status = str(parameters.get("status") or "").strip().upper()
    if status and status not in {"ISSUED", "VOID"}:
        raise ReportDeliveryError("Unsupported check status")
    if bank_id is not None and db.query(BankAccount.id).filter(
        BankAccount.id == bank_id,
        BankAccount.organization_id == organization_id,
    ).first() is None:
        raise ReportDeliveryError("Bank account not found")

    query = db.query(Check).filter(Check.organization_id == organization_id)
    if check_id is not None:
        query = query.filter(Check.id == check_id)
    if bank_id is not None:
        query = query.filter(Check.bank_account_id == bank_id)
    if date_from is not None:
        query = query.filter(Check.check_date >= date_from)
    if date_to is not None:
        query = query.filter(Check.check_date <= date_to)
    if status:
        query = query.filter(Check.status == status)
    checks = query.order_by(Check.check_date.asc(), Check.id.asc()).limit(5001).all()
    if len(checks) > 5000:
        raise ReportDeliveryError("Narrow Check Register filters before exporting")
    if check_id is not None and not checks:
        raise ReportDeliveryError("Check not found")

    rows: list[tuple[object, ...]] = []
    for check in checks:
        amount = Decimal(check.amount or 0)
        if amount <= 0 or check.status not in {"ISSUED", "VOID"}:
            raise ReportDeliveryError("Invalid recorded check status or amount")
        bank = db.query(BankAccount).filter(
            BankAccount.id == check.bank_account_id,
            BankAccount.organization_id == organization_id,
        ).first()
        if bank is None:
            raise ReportDeliveryError("Check bank mapping needs review")
        account = db.query(GLAccount.id).filter(
            GLAccount.id == bank.gl_account_id,
            GLAccount.organization_id == organization_id,
            GLAccount.account_type == "ASSET",
        ).first()
        if account is None:
            raise ReportDeliveryError("Check cash GL mapping needs review")
        issue = db.query(GLTransaction).filter(
            GLTransaction.id == check.gl_transaction_id,
            GLTransaction.organization_id == organization_id,
            GLTransaction.transaction_type == "CHECK",
            GLTransaction.source_type == "check",
            GLTransaction.source_id == check.id,
        ).first()
        if issue is None:
            raise ReportDeliveryError("Check original posting needs review")
        if check.status == "ISSUED":
            if issue.is_reversed or check.void_gl_transaction_id is not None or check.voided_at is not None:
                raise ReportDeliveryError("Issued check and GL reversal status disagree")
            void_id: int | str = ""
            void_date: date | str = ""
        else:
            reversal = db.query(GLTransaction).filter(
                GLTransaction.id == check.void_gl_transaction_id,
                GLTransaction.organization_id == organization_id,
                GLTransaction.transaction_type == "REVERSAL",
                GLTransaction.reversal_of_id == issue.id,
                GLTransaction.source_type == "check_void",
                GLTransaction.source_id == check.id,
            ).first()
            if not issue.is_reversed or reversal is None or check.voided_at is None:
                raise ReportDeliveryError("Void check reversal needs review")
            void_id = reversal.id
            void_date = check.voided_at.date()
        rows.append((
            check.id, check.check_date, check.check_number or "",
            check.payee_name, bank.name, check.status, amount,
            issue.id, void_id, void_date,
        ))
    return ReportPayload(
        title=(
            "Recorded bank check issue/void register; nominal checks only, "
            "NOT verified cleared payments or reconciled bank balances"
        ),
        filename="recorded-check-register.csv",
        headers=HEADERS, rows=tuple(rows),
    )
