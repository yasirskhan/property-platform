"""Posted accrual balance sheet assembled from verified Account Totals.

No asset appraisal, tenant payments, historical balance-field inference or
CASH basis translation. Income less expense is shown separately as unclosed
posted earnings; if the posted double entry does not balance, refuse to
present a purported balanced statement.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Mapping

from sqlalchemy.orm import Session

from app.models.user import User
from app.services.account_totals import build_account_totals
from app.services.report_delivery import ReportDeliveryError, ReportPayload, _date_param

HEADERS = ("Section", "GL Number", "Recorded Account", "Posted Natural Balance")


def build_balance_sheet(
    db: Session, *, organization_id: int, current_user: User,
    parameters: Mapping[str, object],
) -> ReportPayload:
    if set(parameters) - {"as_of"}:
        raise ReportDeliveryError("Unsupported balance sheet parameter")
    as_of = _date_param(parameters, "as_of")
    if as_of is None:
        raise ReportDeliveryError("as_of is required for a balance sheet")
    # Reuse existing verified account scoping/permissions, archived
    # posted-account inclusion and ACCRUAL-only basis refusal.
    source = build_account_totals(
        db, organization_id=organization_id, current_user=current_user,
        parameters={"as_of": as_of.isoformat()},
    )
    asset_total = Decimal("0")
    liability_total = Decimal("0")
    equity_total = Decimal("0")
    posted_income = Decimal("0")
    posted_expense = Decimal("0")
    sections: dict[str, list[tuple[object, ...]]] = {
        "ASSET": [], "LIABILITY": [], "EQUITY": [],
    }
    for gl_number, name, kind, _debit, _credit, net_debit in source.rows:
        net = Decimal(net_debit)
        if kind == "ASSET":
            amount = net
            asset_total += amount
        elif kind == "LIABILITY":
            amount = -net
            liability_total += amount
        elif kind == "EQUITY":
            amount = -net
            equity_total += amount
        elif kind == "INCOME":
            posted_income += -net
            continue
        elif kind == "EXPENSE":
            posted_expense += net
            continue
        else:
            raise ReportDeliveryError("Unrecognized posted GL account type")
        if amount != 0:
            sections[kind].append((kind, gl_number, name, amount))
    earnings = posted_income - posted_expense
    funding = liability_total + equity_total + earnings
    discrepancy = asset_total - funding
    if discrepancy != 0:
        raise ReportDeliveryError(
            "Posted GL account balances do not reconcile; balance sheet unavailable"
        )
    rows = tuple(
        [
            *sections["ASSET"],
            ("TOTAL ASSETS", "", "", asset_total),
            *sections["LIABILITY"],
            ("TOTAL LIABILITIES", "", "", liability_total),
            *sections["EQUITY"],
            ("TOTAL POSTED EQUITY", "", "", equity_total),
            ("UNCLOSED POSTED EARNINGS", "", "Income minus expense", earnings),
            ("TOTAL LIABILITIES + EQUITY + EARNINGS", "", "", funding),
            ("BALANCE CHECK", "", "Assets less liabilities/equity/earnings", discrepancy),
        ]
    )
    return ReportPayload(
        title=f"Posted accrual balance sheet as of {as_of.isoformat()} (unaudited)",
        filename=f"balance-sheet-{as_of.isoformat()}.csv",
        headers=HEADERS, rows=rows,
    )
