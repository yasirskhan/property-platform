"""Read-only current-record unit-vacancy candidates, not physical occupancy.

Reuse the verified rent roll's current lease eligibility/conflict checks and
unit directory's editable inventory flags. Never infer that an empty current
lease association proves the actual unit is vacant.
"""
from __future__ import annotations

from datetime import date
from typing import Mapping

from sqlalchemy.orm import Session

from app.models.user import User
from app.services.rent_roll import build_rent_roll
from app.services.unit_directory import build_unit_directory
from app.services.report_delivery import ReportDeliveryError, ReportPayload


HEADERS = (
    "Property", "Unit", "Current Recorded Lease Association",
    "Available Flag (recorded, not verified vacancy)",
    "Listed Flag (recorded)", "Available From (recorded)",
    "Current Config Market Rent", "Property ID", "Unit ID",
)


def build_unit_vacancy_detail(
    db: Session, *, organization_id: int, current_user: User,
    parameters: Mapping[str, object],
) -> ReportPayload:
    """A candidate is a visible unit without an eligible current ACTIVE lease."""
    if set(parameters) - {"property_id"}:
        raise ReportDeliveryError("Unsupported unit vacancy detail parameter")

    # Each service enforces its own live admin/manager/org/assignment/permission
    # rules. Rent roll additionally rechecks LEASING, overlapping leases and
    # cross-org tenant links; unit directory additionally checks PROPERTIES.UNITS.
    # Do not bypass either layer when building this composition.
    roll = build_rent_roll(
        db, organization_id=organization_id, current_user=current_user,
        parameters=parameters,
    )
    directory = build_unit_directory(
        db, organization_id=organization_id, current_user=current_user,
        parameters=parameters,
    )
    by_unit_id = {row[-1]: row for row in directory.rows}
    rows = []
    for row in roll.rows:
        association = row[2]
        if association == "CURRENT RECORDED LEASE":
            continue
        if association != "NO ELIGIBLE CURRENT LEASE (vacancy not verified)":
            # Fail closed if verified rent-roll semantics change.
            raise ReportDeliveryError("Unrecognized current lease association")
        inventory = by_unit_id.get(row[10])
        if inventory is None or inventory[12] != row[9]:
            raise ReportDeliveryError("Unit inventory scope changed")
        rows.append((
            row[0], row[1], association,
            inventory[9], inventory[10], inventory[11],
            inventory[5], row[9], row[10],
        ))
    today = date.today().isoformat()
    return ReportPayload(
        title=(
            f"Units with no eligible current recorded lease as of {today} "
            "(physical vacancy NOT verified; available/listed are editable settings)"
        ),
        filename=f"unit-vacancy-candidates-current-{today}.csv",
        headers=HEADERS, rows=tuple(rows),
    )
