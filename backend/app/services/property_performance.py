"""Property performance from actual posted property-tagged GL journal lines.

All income/expense account activity is included, including reversals.
This is an accrual-basis *recorded GL* report, not NOI, cash, return on
investment, a bank reconciliation, or a historical rent roll.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Mapping

from sqlalchemy.orm import Session

from app.models.gl_account import GLAccount
from app.models.gl_entry import GLEntry
from app.models.gl_transaction import GLTransaction
from app.models.user import User
from app.services.property_budgets import visible_budget_property
from app.services.report_delivery import ReportDeliveryError, ReportPayload, _int_param
from app.services.reporting_basis import get_accounting_basis

HEADERS = (
    "Property", "Calendar Year", "GL Number", "GL Account", "Account Type",
    "Posted Income", "Posted Expense", "Posted Net", "Property ID", "Account ID",
)


def build_property_performance(
    db: Session, *, organization_id: int, current_user: User,
    parameters: Mapping[str, object],
) -> ReportPayload:
    if set(parameters) - {"property_id", "calendar_year"}:
        raise ReportDeliveryError("Unsupported property performance parameter")
    property_id = _int_param(parameters, "property_id", required=True)
    year = _int_param(parameters, "calendar_year", required=True)
    assert property_id is not None and year is not None
    if not 2000 <= year <= 2099:
        raise ReportDeliveryError("Property performance year is out of range")

    prop = visible_budget_property(
        db, organization_id=organization_id, current_user=current_user,
        property_id=property_id,
    )
    if get_accounting_basis(db, organization_id=organization_id) != "ACCRUAL":
        raise ReportDeliveryError("Posted GL performance requires ACCRUAL reporting basis; CASH performance is not available")

    movements = (
        db.query(GLEntry, GLAccount)
        .join(GLTransaction, GLTransaction.id == GLEntry.transaction_id)
        .join(GLAccount, GLAccount.id == GLEntry.gl_account_id)
        .filter(
            GLEntry.organization_id == organization_id,
            GLTransaction.organization_id == organization_id,
            GLAccount.organization_id == organization_id,
            GLEntry.property_id == property_id,
            GLAccount.account_type.in_(("INCOME", "EXPENSE")),
            GLTransaction.transaction_date >= date(year, 1, 1),
            GLTransaction.transaction_date < date(year + 1, 1, 1),
        )
        .order_by(GLAccount.account_type, GLAccount.gl_number, GLEntry.id)
        .all()
    )
    by_account: dict[int, tuple[GLAccount, Decimal]] = {}
    for entry, account in movements:
        credit_minus_debit = Decimal(entry.credit or 0) - Decimal(entry.debit or 0)
        prior = by_account.get(account.id)
        by_account[account.id] = (
            account,
            (prior[1] if prior else Decimal(0)) + credit_minus_debit,
        )

    rows: list[tuple[object, ...]] = []
    income_total = Decimal(0)
    expense_total = Decimal(0)
    for account, credit_minus_debit in by_account.values():
        income = credit_minus_debit if account.account_type == "INCOME" else Decimal(0)
        expense = -credit_minus_debit if account.account_type == "EXPENSE" else Decimal(0)
        income_total += income
        expense_total += expense
        rows.append((
            prop.name, year, account.gl_number, account.name, account.account_type,
            income, expense, income - expense, prop.id, account.id,
        ))
    if rows:
        rows.append((
            prop.name, year, "", "TOTAL PROPERTY-TAGGED GL", "TOTAL",
            income_total, expense_total, income_total - expense_total,
            prop.id, "",
        ))
    return ReportPayload(
        title=f"Posted property GL income/expense (ACCRUAL), {prop.name}, {year}",
        filename=f"property-performance-accrual-{property_id}-{year}.csv",
        headers=HEADERS, rows=tuple(rows),
    )
