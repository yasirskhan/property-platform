"""Current recorded vendor-user contact directory, not a payable ledger.

User.role VENDOR is a registered vendor contact. VENDOR_CREW and free-text
Bill.payee_name are separate concepts. Manager /users listing is crew-only:
the report must not widen that existing user-detail permission boundary.
"""
from __future__ import annotations

from typing import Mapping

from sqlalchemy.orm import Session

from app.models.user import User, UserRole
from app.services.menu_resolver import permission_allows_user
from app.services.report_delivery import ReportDeliveryError, ReportPayload


HEADERS = ("Vendor User ID", "Recorded Name", "Email", "Phone (recorded)")


def _role(user: User) -> str:
    role = user.role.value if hasattr(user.role, "value") else user.role
    return str(role or "").upper()


def build_vendor_directory(
    db: Session, *, organization_id: int, current_user: User,
    parameters: Mapping[str, object],
) -> ReportPayload:
    if parameters:
        raise ReportDeliveryError("Unsupported vendor directory parameter")
    if (current_user.organization_id != organization_id
            or not current_user.is_active or current_user.deleted_at is not None
            or _role(current_user) not in {"ADMIN", "OWNER"}):
        raise ReportDeliveryError("Vendor directory permission required")
    for menu_key in ("REPORTING.ALL", "PEOPLE.VENDORS"):
        if not permission_allows_user(db, user=current_user, menu_key=menu_key):
            raise ReportDeliveryError("Vendor directory permission required")
    contacts = db.query(User).filter(
        User.organization_id == organization_id,
        User.role == UserRole.VENDOR,
        User.is_active.is_(True),
        User.deleted_at.is_(None),
    ).order_by(User.last_name.asc(), User.first_name.asc(), User.id.asc()).all()
    rows = tuple((
        person.id, f"{person.first_name} {person.last_name}".strip(),
        person.email, person.phone or "",
    ) for person in contacts)
    return ReportPayload(
        title="Current recorded vendor contacts (no bill-payee inference, address or taxpayer data)",
        filename="vendor-contact-directory.csv", headers=HEADERS, rows=rows,
    )
