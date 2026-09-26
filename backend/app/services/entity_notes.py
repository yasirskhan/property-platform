"""Authorization and target resolution for universal entity notes."""
from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

import init_db  # noqa: F401
from app.core.database import Base
from app.models.property import Property, PropertyAssignment, Unit
from app.models.user import User
from app.services.menu_resolver import permission_allows_user


_FORBIDDEN_TABLES = {
    "audit_log",
    "entity_notes",
    "entity_attachments",
    "tax_profiles",  # Tax identifiers must never use generic notes/unencrypted attachments.
    "platform_users",
    "release_gates",
    "release_gate_organizations",
    "job_runs",
    "job_dead_letters",
    "fraud_cases",
    "fraud_signals",
}
_FORBIDDEN_PREFIXES = (
    "billing_",
    "subscription_",
    "plans",
    "modules",
    "pricing_",
    "platform_",
)

_ENTITY_PERMISSION_PREFIXES = (
    (("properties", "property_"), "PROPERTIES.ALL"),
    (("units",), "PROPERTIES.UNITS"),
    (("leases", "rent_invoices", "payments"), "LEASING"),
    (("work_orders", "work_order_updates"), "MAINTENANCE.WORK_ORDERS"),
    (("receipts", "receipt_lines"), "ACCOUNTING.RECEIVABLES"),
    (("bills", "bill_lines", "recurring_bills", "recurring_bill_lines", "vendor_credits", "vendor_credit_lines", "checks", "check_bill_allocations"), "ACCOUNTING.PAYABLES"),
    (("charges",), "ACCOUNTING.CHARGES"),
    (("deposits", "deposit_lines"), "ACCOUNTING.DEPOSITS"),
    (("bank_", "owner_ach_accounts"), "ACCOUNTING.BANK_ACCOUNTS"),
    (("gl_accounts", "gl_account_posting_restrictions"), "ACCOUNTING.GL_ACCOUNTS"),
    (("gl_transactions", "gl_entries", "recurring_journal_entries", "recurring_journal_entry_lines"), "ACCOUNTING.JOURNAL_ENTRIES"),
    (("management_fee_runs", "owner_payouts"), "ACCOUNTING.MANAGEMENT_FEES"),
    (("owner_statements", "owner_packet_settings"), "ACCOUNTING.OWNER_STATEMENTS"),
)


def _role(user: User) -> str:
    value = user.role.value if hasattr(user.role, "value") else user.role
    return str(value or "").upper()


def _model_for_table(entity_type: str):
    clean = entity_type.strip().lower()
    if (
        not clean
        or clean in _FORBIDDEN_TABLES
        or any(clean.startswith(prefix) for prefix in _FORBIDDEN_PREFIXES)
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entity type not available for notes.")

    for mapper in Base.registry.mappers:
        if mapper.local_table.name == clean:
            return clean, mapper.class_
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entity type not found.")


def _permission_for(entity_type: str) -> str | None:
    for names, permission in _ENTITY_PERMISSION_PREFIXES:
        for name in names:
            if entity_type == name or (name.endswith("_") and entity_type.startswith(name)):
                return permission
    return None


def _row(db: Session, table: str, entity_id: int):
    _, model = _model_for_table(table)
    obj = db.query(model).filter(model.id == entity_id).first()
    if obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entity not found.")
    return obj


def _property_id_for_target(db: Session, entity_type: str, obj) -> int | None:
    if entity_type == "properties":
        return int(obj.id)
    value = getattr(obj, "property_id", None)
    if value is not None:
        return int(value)

    unit_id = getattr(obj, "unit_id", None)
    if unit_id is not None:
        unit = db.query(Unit).filter(Unit.id == unit_id).first()
        return int(unit.property_id) if unit else None

    lease_id = getattr(obj, "lease_id", None)
    if lease_id is not None:
        lease = _row(db, "leases", int(lease_id))
        unit = db.query(Unit).filter(Unit.id == lease.unit_id).first()
        return int(unit.property_id) if unit else None

    invoice_id = getattr(obj, "invoice_id", None)
    if invoice_id is not None:
        invoice = _row(db, "rent_invoices", int(invoice_id))
        lease = _row(db, "leases", int(invoice.lease_id))
        unit = db.query(Unit).filter(Unit.id == lease.unit_id).first()
        return int(unit.property_id) if unit else None

    return None


_REFERENCE_KEYS = (
    ("receipt_id", "receipts"),
    ("bill_id", "bills"),
    ("deposit_id", "deposits"),
    ("transaction_id", "gl_transactions"),
    ("bank_account_id", "bank_accounts"),
    ("owner_statement_id", "owner_statements"),
    ("work_order_id", "work_orders"),
    ("subscription_id", "subscriptions"),
)


def _organization_id_for_target(
    db: Session,
    entity_type: str,
    obj,
    *,
    visited: set[tuple[str, int]] | None = None,
) -> int:
    visited = visited or set()
    key = (entity_type, int(obj.id))
    if key in visited:
        raise HTTPException(status_code=400, detail="Unable to resolve entity organization.")
    visited.add(key)

    organization_id = getattr(obj, "organization_id", None)
    if organization_id is not None:
        return int(organization_id)
    if entity_type == "organizations":
        return int(obj.id)

    property_id = _property_id_for_target(db, entity_type, obj)
    if property_id is not None:
        prop = db.query(Property).filter(Property.id == property_id).first()
        if prop is None:
            raise HTTPException(status_code=404, detail="Related property not found.")
        return int(prop.organization_id)

    for attr, parent_table in _REFERENCE_KEYS:
        parent_id = getattr(obj, attr, None)
        if parent_id is not None:
            parent = _row(db, parent_table, int(parent_id))
            return _organization_id_for_target(
                db,
                parent_table,
                parent,
                visited=visited,
            )

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="This entity type does not expose an organization scope for notes.",
    )


def resolve_note_target(
    db: Session,
    *,
    current_user: User,
    entity_type: str,
    entity_id: int,
):
    if current_user.organization_id is None:
        raise HTTPException(status_code=400, detail="User has no organization.")

    clean, _ = _model_for_table(entity_type)
    obj = _row(db, clean, entity_id)
    target_org_id = _organization_id_for_target(db, clean, obj)
    if target_org_id != current_user.organization_id:
        raise HTTPException(status_code=403, detail="Entity belongs to another organization.")

    role = _role(current_user)
    if role not in {"ADMIN", "OWNER", "MANAGER", "CREW"}:
        raise HTTPException(status_code=403, detail="Staff access required for internal notes.")

    permission = _permission_for(clean)
    if permission is not None and not permission_allows_user(
        db,
        user=current_user,
        menu_key=permission,
    ):
        raise HTTPException(status_code=403, detail="Entity permission required.")

    property_id = _property_id_for_target(db, clean, obj)
    if property_id is not None and role in {"MANAGER", "CREW"}:
        assigned = (
            db.query(PropertyAssignment)
            .filter(
                PropertyAssignment.property_id == property_id,
                PropertyAssignment.user_id == current_user.id,
                PropertyAssignment.is_active.is_(True),
            )
            .first()
        )
        if assigned is None:
            raise HTTPException(status_code=403, detail="Not assigned to this property.")

    if permission is None and role not in {"ADMIN", "OWNER"}:
        raise HTTPException(
            status_code=403,
            detail="This entity type requires administrator or owner access for notes.",
        )

    return clean, obj, target_org_id
