"""Backend-generated report datasets used by export and email delivery."""
from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Mapping

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.gl_account import GLAccount
from app.models.gl_entry import GLEntry
from app.models.gl_transaction import GLTransaction
from app.models.owner_statement import OwnerStatement


class ReportDeliveryError(ValueError):
    pass


@dataclass(frozen=True)
class ReportPayload:
    title: str
    filename: str
    headers: tuple[str, ...]
    rows: tuple[tuple[object, ...], ...]


REPORT_PERMISSIONS: dict[str, str] = {
    "accounting.chart_of_accounts": "ACCOUNTING.GL_ACCOUNTS",
    "accounting.general_ledger": "ACCOUNTING.GL_ACCOUNTS",
    "accounting.trial_balance": "ACCOUNTING.GL_ACCOUNTS",
    "owner.statement": "ACCOUNTING.OWNER_STATEMENTS",
    "mailing.labels": "PROPERTIES.ALL",
    "tenant.delinquency": "LEASING",
    "tenant.security_deposit_funds_detail": "ACCOUNTING.GL_ACCOUNTS",
    "tenant.directory": "LEASING",
    "tenant.ledger": "LEASING",
}


def _date_param(parameters: Mapping[str, object], key: str) -> date | None:
    raw = parameters.get(key)
    if raw in (None, ""):
        return None
    try:
        return date.fromisoformat(str(raw))
    except ValueError as exc:
        raise ReportDeliveryError(f"{key} must be YYYY-MM-DD") from exc


def _int_param(parameters: Mapping[str, object], key: str, *, required: bool = False) -> int | None:
    raw = parameters.get(key)
    if raw in (None, ""):
        if required:
            raise ReportDeliveryError(f"{key} is required")
        return None
    try:
        value = int(str(raw))
    except (TypeError, ValueError) as exc:
        raise ReportDeliveryError(f"{key} must be an integer") from exc
    if value <= 0:
        raise ReportDeliveryError(f"{key} must be greater than zero")
    return value


def _bool_param(parameters: Mapping[str, object], key: str, default: bool = False) -> bool:
    raw = parameters.get(key)
    if raw in (None, ""):
        return default
    if isinstance(raw, bool):
        return raw
    value = str(raw).strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise ReportDeliveryError(f"{key} must be true or false")


def _chart_of_accounts(db: Session, *, organization_id: int, parameters: Mapping[str, object]) -> ReportPayload:
    include_inactive = _bool_param(parameters, "include_inactive", False)
    query = db.query(GLAccount).filter(GLAccount.organization_id == organization_id)
    if not include_inactive:
        query = query.filter(GLAccount.is_active.is_(True))
    accounts = query.order_by(GLAccount.gl_number.asc(), GLAccount.id.asc()).all()
    return ReportPayload(
        title="Chart of Accounts",
        filename="chart-of-accounts.csv",
        headers=("GL Number", "Account Name", "Type", "Active", "Subject to Management Fees", "Cash Flow"),
        rows=tuple(
            (
                account.gl_number,
                account.name,
                account.account_type,
                "Yes" if account.is_active else "No",
                "Yes" if account.subject_to_mgmt_fees else "No",
                "Yes" if account.include_on_cash_flow else "No",
            )
            for account in accounts
        ),
    )


def _trial_balance(db: Session, *, organization_id: int, parameters: Mapping[str, object]) -> ReportPayload:
    as_of = _date_param(parameters, "as_of")
    include_zero = _bool_param(parameters, "include_zero", False)
    query = (
        db.query(
            GLEntry.gl_account_id,
            func.coalesce(func.sum(GLEntry.debit), 0).label("debits"),
            func.coalesce(func.sum(GLEntry.credit), 0).label("credits"),
        )
        .join(GLTransaction, GLTransaction.id == GLEntry.transaction_id)
        .filter(GLEntry.organization_id == organization_id)
    )
    if as_of is not None:
        query = query.filter(GLTransaction.transaction_date <= as_of)
    totals = {
        row.gl_account_id: (Decimal(row.debits or 0), Decimal(row.credits or 0))
        for row in query.group_by(GLEntry.gl_account_id).all()
    }
    accounts = (
        db.query(GLAccount)
        .filter(
            GLAccount.organization_id == organization_id,
            GLAccount.is_active.is_(True),
        )
        .order_by(GLAccount.gl_number.asc(), GLAccount.id.asc())
        .all()
    )
    rows: list[tuple[object, ...]] = []
    for account in accounts:
        debit, credit = totals.get(account.id, (Decimal("0"), Decimal("0")))
        if not include_zero and debit == 0 and credit == 0:
            continue
        rows.append((account.gl_number, account.name, account.account_type, debit, credit))
    label = (as_of or date.today()).isoformat()
    return ReportPayload(
        title=f"Trial Balance as of {label}",
        filename=f"trial-balance-{label}.csv",
        headers=("GL Number", "Account Name", "Type", "Debit", "Credit"),
        rows=tuple(rows),
    )


def _general_ledger(db: Session, *, organization_id: int, parameters: Mapping[str, object]) -> ReportPayload:
    account_id = _int_param(parameters, "account_id", required=True)
    assert account_id is not None
    account = (
        db.query(GLAccount)
        .filter(
            GLAccount.id == account_id,
            GLAccount.organization_id == organization_id,
        )
        .first()
    )
    if account is None:
        raise ReportDeliveryError("GL account not found")

    date_from = _date_param(parameters, "date_from")
    date_to = _date_param(parameters, "date_to")
    if date_from and date_to and date_from > date_to:
        raise ReportDeliveryError("date_from cannot be after date_to")
    property_id = _int_param(parameters, "property_id")

    opening = Decimal("0")
    if date_from is not None:
        opening_debit, opening_credit = (
            db.query(
                func.coalesce(func.sum(GLEntry.debit), 0),
                func.coalesce(func.sum(GLEntry.credit), 0),
            )
            .join(GLTransaction, GLTransaction.id == GLEntry.transaction_id)
            .filter(
                GLEntry.organization_id == organization_id,
                GLEntry.gl_account_id == account_id,
                GLTransaction.transaction_date < date_from,
            )
            .one()
        )
        opening = Decimal(opening_debit or 0) - Decimal(opening_credit or 0)

    query = (
        db.query(GLEntry, GLTransaction)
        .join(GLTransaction, GLTransaction.id == GLEntry.transaction_id)
        .filter(
            GLEntry.organization_id == organization_id,
            GLEntry.gl_account_id == account_id,
        )
    )
    if date_from is not None:
        query = query.filter(GLTransaction.transaction_date >= date_from)
    if date_to is not None:
        query = query.filter(GLTransaction.transaction_date <= date_to)
    if property_id is not None:
        query = query.filter(GLEntry.property_id == property_id)

    running = opening
    rows: list[tuple[object, ...]] = []
    for entry, transaction in query.order_by(
        GLTransaction.transaction_date.asc(),
        GLTransaction.id.asc(),
        GLEntry.id.asc(),
    ).all():
        debit = Decimal(entry.debit or 0)
        credit = Decimal(entry.credit or 0)
        running = running + debit - credit
        rows.append(
            (
                transaction.transaction_date,
                transaction.transaction_type,
                transaction.reference_number or "",
                entry.description or transaction.memo or "",
                entry.property_id or "",
                debit,
                credit,
                running,
            )
        )

    return ReportPayload(
        title=f"General Ledger - {account.gl_number} {account.name}",
        filename=f"general-ledger-{account.gl_number}.csv",
        headers=("Date", "Type", "Reference", "Description", "Property ID", "Debit", "Credit", "Balance"),
        rows=tuple(rows),
    )


def _owner_statement(db: Session, *, organization_id: int, parameters: Mapping[str, object]) -> ReportPayload:
    statement_id = _int_param(parameters, "statement_id", required=True)
    assert statement_id is not None
    statement = (
        db.query(OwnerStatement)
        .filter(
            OwnerStatement.id == statement_id,
            OwnerStatement.organization_id == organization_id,
            OwnerStatement.is_active.is_(True),
        )
        .first()
    )
    if statement is None:
        raise ReportDeliveryError("Owner statement not found")
    try:
        blocks = json.loads(statement.property_data or "[]")
    except json.JSONDecodeError:
        blocks = []

    rows: list[tuple[object, ...]] = []
    for block in blocks if isinstance(blocks, list) else []:
        property_name = str(block.get("property_name") or "")
        transactions = block.get("transactions") or []
        for transaction in transactions if isinstance(transactions, list) else []:
            rows.append(
                (
                    property_name,
                    transaction.get("date") or "",
                    transaction.get("description") or "",
                    transaction.get("reference") or "",
                    transaction.get("income") or "0.00",
                    transaction.get("expense") or "0.00",
                    transaction.get("running_balance") or "0.00",
                )
            )
    return ReportPayload(
        title=f"Owner Statement {statement.period_start} to {statement.period_end}",
        filename=f"owner-statement-{statement.id}.csv",
        headers=("Property", "Date", "Description", "Reference", "Income", "Expense", "Running Balance"),
        rows=tuple(rows),
    )


_BUILDERS = {
    "accounting.chart_of_accounts": _chart_of_accounts,
    "accounting.general_ledger": _general_ledger,
    "accounting.trial_balance": _trial_balance,
    "owner.statement": _owner_statement,
}


def build_report_payload(
    db: Session,
    *,
    organization_id: int,
    report_key: str,
    parameters: Mapping[str, object],
    current_user: object | None = None,
) -> ReportPayload:
    if report_key == "mailing.labels":
        if current_user is None:
            raise ReportDeliveryError("Authenticated label report access required")
        from app.services.label_report import build_label_report
        return build_label_report(
            db, organization_id=organization_id, current_user=current_user,
            parameters=parameters,
        )
    if report_key == "tenant.delinquency":
        if current_user is None:
            raise ReportDeliveryError("Authenticated delinquency report access required")
        from app.services.tenant_delinquency import build_delinquency_report
        return build_delinquency_report(
            db, organization_id=organization_id, current_user=current_user,
            parameters=parameters,
        )
    if report_key == "tenant.security_deposit_funds_detail":
        if current_user is None:
            raise ReportDeliveryError("Authenticated deposit liability report access required")
        from app.services.security_deposit_funds import build_security_deposit_funds_report
        return build_security_deposit_funds_report(
            db, organization_id=organization_id, current_user=current_user,
            parameters=parameters,
        )
    if report_key == "tenant.directory":
        if current_user is None:
            raise ReportDeliveryError("Authenticated tenant directory access required")
        from app.services.tenant_directory import build_tenant_directory
        return build_tenant_directory(
            db, organization_id=organization_id, current_user=current_user,
            parameters=parameters,
        )
    if report_key == "tenant.ledger":
        if current_user is None:
            raise ReportDeliveryError("Authenticated tenant ledger access required")
        from app.services.tenant_ledger import build_tenant_ledger
        return build_tenant_ledger(
            db, organization_id=organization_id, current_user=current_user,
            parameters=parameters,
        )
    builder = _BUILDERS.get(report_key)
    if builder is None:
        raise ReportDeliveryError("Report is not available for delivery")
    return builder(db, organization_id=organization_id, parameters=parameters)


def _csv_cell(value: object) -> object:
    if value is None:
        return ""
    if isinstance(value, (Decimal, date)):
        return str(value)
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def report_csv_bytes(payload: ReportPayload) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(payload.headers)
    for row in payload.rows:
        writer.writerow([_csv_cell(value) for value in row])
    return stream.getvalue().encode("utf-8-sig")
