"""Org/assignment-scoped explicit budgets vs posted GL movements.

This is an ACCRUAL journal comparison, not a cash-basis statement. Budget
lines are user-entered targets; the ledger is read-only and both the
original posting and any later posted reversal contribute their signs.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Mapping

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.gl_account import GLAccount
from app.models.gl_entry import GLEntry
from app.models.gl_transaction import GLTransaction
from app.models.property import Property, PropertyAssignment
from app.models.property_budget import PropertyBudgetLine
from app.models.user import User, UserRole
from app.schemas.property_budget import PropertyBudgetOut, PropertyBudgetUpsertIn
from app.services.audit import append_audit_log
from app.services.menu_resolver import permission_allows_user
from app.services.report_delivery import ReportDeliveryError, ReportPayload, _int_param
from app.services.reporting_basis import get_accounting_basis


def _role(user: User) -> str:
    val = user.role.value if hasattr(user.role, "value") else user.role
    return str(val or "").upper()


def visible_budget_property(db: Session, *, organization_id: int,
                            current_user: User, property_id: int) -> Property:
    if (current_user.organization_id != organization_id
            or not current_user.is_active or current_user.deleted_at is not None
            or _role(current_user) not in {"ADMIN", "MANAGER"}):
        raise ReportDeliveryError("Budget report permission required")
    for menu in ("REPORTING.ALL", "PROPERTIES.ALL", "ACCOUNTING.GL_ACCOUNTS"):
        if not permission_allows_user(db, user=current_user, menu_key=menu):
            raise ReportDeliveryError("Budget report permission required")
    query = db.query(Property).filter(
        Property.id == property_id,
        Property.organization_id == organization_id,
        Property.is_active.is_(True), Property.deleted_at.is_(None),
    )
    if _role(current_user) == "MANAGER":
        assigned = db.query(PropertyAssignment.property_id).filter(
            PropertyAssignment.user_id == current_user.id,
            PropertyAssignment.is_active.is_(True),
            PropertyAssignment.deleted_at.is_(None),
        )
        query = query.filter(Property.id.in_(assigned))
    prop = query.first()
    if prop is None:
        raise ReportDeliveryError("Property not found")
    return prop


def _account(db: Session, *, organization_id: int, gl_account_id: int) -> GLAccount:
    acct = db.query(GLAccount).filter(
        GLAccount.id == gl_account_id,
        GLAccount.organization_id == organization_id,
        GLAccount.is_active.is_(True),
        GLAccount.deleted_at.is_(None),
        GLAccount.account_type.in_(("INCOME", "EXPENSE")),
    ).first()
    if acct is None:
        raise ReportDeliveryError("Income or expense GL account not found")
    return acct


def list_property_budget(db: Session, *, current_user: User,
                         property_id: int, calendar_year: int) -> list[PropertyBudgetOut]:
    org_id = current_user.organization_id
    visible_budget_property(db, organization_id=org_id, current_user=current_user,
                            property_id=property_id)
    if not 2000 <= calendar_year <= 2100:
        raise ReportDeliveryError("Budget year is out of range")
    lines = db.query(PropertyBudgetLine).filter(
        PropertyBudgetLine.organization_id == org_id,
        PropertyBudgetLine.property_id == property_id,
        PropertyBudgetLine.calendar_year == calendar_year,
    ).order_by(PropertyBudgetLine.month, PropertyBudgetLine.gl_account_id).all()
    return [PropertyBudgetOut.model_validate(line) for line in lines]


def upsert_property_budget(db: Session, *, current_user: User,
                           payload: PropertyBudgetUpsertIn) -> PropertyBudgetOut:
    org_id = current_user.organization_id
    visible_budget_property(db, organization_id=org_id, current_user=current_user,
                            property_id=payload.property_id)
    if _role(current_user) != "ADMIN":
        raise ReportDeliveryError("Only organization administrators may change budget targets")
    _account(db, organization_id=org_id, gl_account_id=payload.gl_account_id)
    filters = (
        PropertyBudgetLine.organization_id == org_id,
        PropertyBudgetLine.property_id == payload.property_id,
        PropertyBudgetLine.gl_account_id == payload.gl_account_id,
        PropertyBudgetLine.calendar_year == payload.calendar_year,
        PropertyBudgetLine.month == payload.month,
    )
    line = db.query(PropertyBudgetLine).filter(*filters).first()
    created = line is None
    before = None if created else str(line.amount)
    if line is None:
        line = PropertyBudgetLine(
            organization_id=org_id, property_id=payload.property_id,
            gl_account_id=payload.gl_account_id,
            calendar_year=payload.calendar_year, month=payload.month,
            created_by_id=current_user.id,
        )
        db.add(line)
    line.amount = payload.amount
    line.updated_by_id = current_user.id
    db.flush()
    append_audit_log(
        db, organization_id=org_id, user_id=current_user.id,
        entity_type="property_budget", entity_id=line.id,
        action="created" if created else "updated",
        old_value=None if created else {"amount": before},
        new_value={
            "property_id": line.property_id,
            "gl_account_id": line.gl_account_id,
            "year": line.calendar_year, "month": line.month,
            "amount": str(line.amount),
        },
    )
    db.commit()
    db.refresh(line)
    return PropertyBudgetOut.model_validate(line)


def build_budget_comparison(db: Session, *, organization_id: int,
                            current_user: User,
                            parameters: Mapping[str, object]) -> ReportPayload:
    if set(parameters) - {"property_id", "calendar_year"}:
        raise ReportDeliveryError("Unsupported budget report parameter")
    property_id = _int_param(parameters, "property_id", required=True)
    year = _int_param(parameters, "calendar_year", required=True)
    assert property_id is not None and year is not None
    if not 2000 <= year <= 2100:
        raise ReportDeliveryError("Budget year is out of range")
    prop = visible_budget_property(
        db, organization_id=organization_id, current_user=current_user,
        property_id=property_id,
    )
    if get_accounting_basis(db, organization_id=organization_id) != "ACCRUAL":
        raise ReportDeliveryError("Posted GL comparison requires ACCRUAL reporting basis; CASH actuals are not available")
    lines = db.query(PropertyBudgetLine, GLAccount).join(
        GLAccount, GLAccount.id == PropertyBudgetLine.gl_account_id,
    ).filter(
        PropertyBudgetLine.organization_id == organization_id,
        PropertyBudgetLine.property_id == property_id,
        PropertyBudgetLine.calendar_year == year,
        GLAccount.organization_id == organization_id,
        GLAccount.account_type.in_(("INCOME", "EXPENSE")),
    ).order_by(PropertyBudgetLine.month, GLAccount.gl_number, PropertyBudgetLine.id).all()
    if not lines:
        return ReportPayload(
            title=f"Property budget vs posted GL (ACCRUAL), {prop.name}, {year}",
            filename=f"property-budget-comparison-{property_id}-{year}.csv",
            headers=HEADERS, rows=(),
        )
    account_ids = {acct.id for _, acct in lines}
    booked = db.query(GLEntry, GLTransaction).join(
        GLTransaction, GLTransaction.id == GLEntry.transaction_id,
    ).filter(
        GLEntry.organization_id == organization_id,
        GLTransaction.organization_id == organization_id,
        GLEntry.property_id == property_id,
        GLEntry.gl_account_id.in_(account_ids),
        GLTransaction.transaction_date >= date(year, 1, 1),
        GLTransaction.transaction_date < date(year + 1, 1, 1),
    ).all()
    movements: dict[tuple[int, int], Decimal] = {}
    for entry, transaction in booked:
        key = (entry.gl_account_id, transaction.transaction_date.month)
        movements[key] = movements.get(key, Decimal(0)) + (
            Decimal(entry.credit or 0) - Decimal(entry.debit or 0)
        )
    rows: list[tuple[object, ...]] = []
    for budget, account in lines:
        budgeted = Decimal(budget.amount or 0)
        income_sign = 1 if account.account_type == "INCOME" else -1
        actual = movements.get((account.id, budget.month), Decimal(0)) * income_sign
        # Positive means favorable: revenue above budget or expense below budget.
        favorable = (actual - budgeted) * income_sign
        rows.append((
            prop.name, year, budget.month, account.gl_number,
            account.name, account.account_type,
            budgeted, actual, favorable, prop.id, account.id,
        ))
    return ReportPayload(
        title=f"Property budget vs posted GL (ACCRUAL), {prop.name}, {year}",
        filename=f"property-budget-comparison-{property_id}-{year}.csv",
        headers=HEADERS, rows=tuple(rows),
    )


HEADERS = (
    "Property", "Calendar Year", "Month", "GL Number",
    "GL Account", "Type", "Budget", "Posted GL Actual",
    "Favorable Variance", "Property ID", "Account ID",
)
