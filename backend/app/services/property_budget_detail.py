"""Recorded monthly property budget targets only; no inferred GL/cash actuals."""
from __future__ import annotations

from decimal import Decimal
from typing import Mapping

from sqlalchemy.orm import Session

from app.models.gl_account import GLAccount
from app.models.property_budget import PropertyBudgetLine
from app.models.user import User
from app.services.property_budgets import visible_budget_property
from app.services.report_delivery import ReportDeliveryError, ReportPayload, _int_param

MONTHS = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)
HEADERS = (
    "Property", "GL Number", "GL Account", "Type", *MONTHS,
    "Configured Annual Total", "Months Configured", "Property ID", "Account ID",
)


def build_budget_detail(
    db: Session, *, organization_id: int, current_user: User,
    parameters: Mapping[str, object],
) -> ReportPayload:
    if set(parameters) - {"property_id", "calendar_year"}:
        raise ReportDeliveryError("Unsupported budget detail parameter")
    property_id = _int_param(parameters, "property_id", required=True)
    year = _int_param(parameters, "calendar_year", required=True)
    assert property_id is not None and year is not None
    if not 2000 <= year <= 2100:
        raise ReportDeliveryError("Budget year is out of range")
    prop = visible_budget_property(
        db, organization_id=organization_id,
        current_user=current_user, property_id=property_id,
    )
    # The budget-only view works regardless of accounting-basis setting.
    # Do not substitute GL actuals, cash receipts or estimated rents.
    lines = db.query(PropertyBudgetLine, GLAccount).join(
        GLAccount, GLAccount.id == PropertyBudgetLine.gl_account_id,
    ).filter(
        PropertyBudgetLine.organization_id == organization_id,
        PropertyBudgetLine.property_id == property_id,
        PropertyBudgetLine.calendar_year == year,
        GLAccount.organization_id == organization_id,
        GLAccount.account_type.in_(("INCOME", "EXPENSE")),
    ).order_by(GLAccount.gl_number, PropertyBudgetLine.month).all()
    grouped: dict[int, tuple[GLAccount, dict[int, Decimal]]] = {}
    for line, account in lines:
        if account.id not in grouped:
            grouped[account.id] = (account, {})
        grouped[account.id][1][line.month] = Decimal(line.amount)
    rows: list[tuple[object, ...]] = []
    for account, months in sorted(
        grouped.values(), key=lambda item: (item[0].gl_number, item[0].id),
    ):
        monthly = tuple(months.get(i, "") for i in range(1, 13))
        total = sum(months.values(), Decimal(0))
        rows.append((
            prop.name, account.gl_number, account.name,
            account.account_type, *monthly, total, len(months),
            prop.id, account.id,
        ))
    return ReportPayload(
        title=f"Explicit property budget detail, {prop.name}, {year} (unconfigured months blank)",
        filename=f"property-budget-detail-{property_id}-{year}.csv",
        headers=HEADERS, rows=tuple(rows),
    )
