"""Twelve complete calendar months of verified posted bank-mapped GL cash.

Each month reuses the existing cash-flow builder and its live organization,
role, menu and mapping checks. Not a classified GAAP cash-flow statement;
internal transfers inflate gross amounts but cancel in net book movement.
"""
from __future__ import annotations

import calendar
from datetime import date
from decimal import Decimal
from typing import Mapping

from sqlalchemy.orm import Session

from app.models.user import User
from app.services.cash_flow import build_cash_flow
from app.services.report_delivery import ReportDeliveryError, ReportPayload

HEADERS = (
    "Month", "Opening Posted Book Cash", "Posted Debits / Inflows",
    "Posted Credits / Outflows", "Net Book Cash Movement",
    "Ending Posted Book Cash",
)


def _end_month(parameters: Mapping[str, object]) -> tuple[int, int]:
    if set(parameters) != {"ending_month"}:
        raise ReportDeliveryError("ending_month is required; unsupported twelve-month parameter")
    raw = parameters.get("ending_month")
    if not isinstance(raw, str) or len(raw) != 7 or raw[4] != "-" or not (
        raw[:4].isdigit() and raw[5:].isdigit()
    ):
        raise ReportDeliveryError("ending_month must be YYYY-MM")
    year, month = int(raw[:4]), int(raw[5:])
    if not 1 <= year <= 9999 or not 1 <= month <= 12:
        raise ReportDeliveryError("Invalid ending month")
    if year == 1 and month < 12:
        # The complete 12-month range would precede supported calendar dates.
        raise ReportDeliveryError("Twelve-month range precedes year 0001")
    return year, month


def build_cash_flow_12_month(
    db: Session, *, organization_id: int, current_user: User,
    parameters: Mapping[str, object],
) -> ReportPayload:
    ending_year, ending_month = _end_month(parameters)
    months = []
    for offset in range(11, -1, -1):
        ordinal_month = ((ending_year - 1) * 12 + ending_month - 1) - offset
        year, zero_month = divmod(ordinal_month, 12)
        year += 1
        month = zero_month + 1
        start = date(year, month, 1)
        finish = date(year, month, calendar.monthrange(year, month)[1])
        months.append((start, finish))

    records = []
    for start, finish in months:
        payload = build_cash_flow(
            db, organization_id=organization_id, current_user=current_user,
            parameters={"date_from": start.isoformat(), "date_to": finish.isoformat()},
        )
        # The underlying report always appends its summarized TOTAL.
        summary = payload.rows[-1]
        if summary[0] != "TOTAL":
            raise ReportDeliveryError("Cash flow summary missing")
        records.append((
            f"{start.year:04d}-{start.month:02d}",
            *(Decimal(value) for value in summary[3:]),
        ))

    first_opening = records[0][1]
    debits = sum((row[2] for row in records), Decimal("0"))
    credits = sum((row[3] for row in records), Decimal("0"))
    ending = records[-1][5]
    # Every successive monthly beginning must equal the previous ending;
    # refuse inconsistent period snapshots rather than silently presenting
    # a purported continuous book-cash rollforward.
    for prior, later in zip(records, records[1:]):
        if prior[5] != later[1]:
            raise ReportDeliveryError("Monthly posted book cash does not reconcile")
    records.append((
        "TOTAL 12 MONTHS", first_opening, debits, credits,
        debits - credits, ending,
    ))
    return ReportPayload(
        title=(
            f"Twelve-month posted GL bank-mapped book cash through "
            f"{ending_year:04d}-{ending_month:02d}; not a classified "
            "cash-flow statement or cleared bank balance; internal "
            "transfers inflate gross movements; unmapped/excluded cash omitted"
        ),
        filename=f"cash-book-twelve-months-{ending_year:04d}-{ending_month:02d}.csv",
        headers=HEADERS,
        rows=tuple(records),
    )
