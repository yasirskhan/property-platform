"""Summary of already authorized current positive standalone tenant Charges.

The detailed unpaid charge service owns all actor, organization, property,
tenant, record-status and menu-permission checks. Summarize its identical
data; never independently reconstruct invoices or double-count payments.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Mapping

from sqlalchemy.orm import Session

from app.models.user import User
from app.services.report_delivery import ReportPayload
from app.services.tenant_unpaid_charges import build_tenant_unpaid_charges

HEADERS = (
    "Tenant", "Property", "Unpaid Charges", "Charge Amount",
    "Recorded Paid", "Outstanding", "Tenant ID", "Property ID",
)


def build_tenant_unpaid_summary(
    db: Session, *, organization_id: int, current_user: User,
    parameters: Mapping[str, object],
) -> ReportPayload:
    detail = build_tenant_unpaid_charges(
        db, organization_id=organization_id,
        current_user=current_user, parameters=parameters,
    )
    grouped: dict[tuple[int, int | str], list[object]] = {}
    for row in detail.rows:
        tenant_id, property_id = int(row[9]), row[10]
        key = (tenant_id, property_id)
        item = grouped.get(key)
        if item is None:
            item = [row[1], row[2], 0, Decimal(0), Decimal(0), Decimal(0),
                    tenant_id, property_id]
            grouped[key] = item
        item[2] += 1
        item[3] += Decimal(row[6])
        item[4] += Decimal(row[7])
        item[5] += Decimal(row[8])
    rows = tuple(
        tuple(item)
        for item in sorted(
            grouped.values(),
            key=lambda item: (str(item[0]).casefold(), int(item[6]),
                              str(item[1]).casefold(), str(item[7])),
        )
    )
    return ReportPayload(
        title=f"Tenant unpaid standalone charges summary as of {date.today().isoformat()}",
        filename=f"tenant-unpaid-charges-summary-{date.today().isoformat()}.csv",
        headers=HEADERS,
        rows=rows,
    )
