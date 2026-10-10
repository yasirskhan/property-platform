"""Bounded, two-step CSV import/export for independent non-login Contacts.

No User/Vendor creation, no tax data, no implicit merge/overwrite or
cross-org target IDs. Only the explicit ContactCreate schema is accepted.
"""
from __future__ import annotations

import csv
from hashlib import sha256
import io

from pydantic import ValidationError
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.contact import Contact
from app.models.user import Organization
from app.schemas.contact import ContactCreate
from app.services.audit import append_audit_log
from app.services.report_delivery import ReportPayload, report_csv_bytes


class ContactTransferError(ValueError):
    pass


COLUMNS = (
    "display_name", "contact_type", "company_name", "email", "phone",
    "job_title", "address_line1", "address_line2", "city", "state",
    "postal_code", "country",
)
MAX_ROWS = 200
MAX_BYTES = 131072
MAX_EXPORT = 1000


def _parse(csv_text: str) -> list[ContactCreate]:
    if not csv_text or len(csv_text.encode("utf-8")) > MAX_BYTES or "\x00" in csv_text:
        raise ContactTransferError("CSV must be UTF-8, nonempty and at most 128 KiB.")
    if csv_text.startswith("\ufeff"):
        csv_text = csv_text[1:]
    try:
        reader = csv.reader(io.StringIO(csv_text, newline=""), strict=True)
        header = next(reader, None)
        if header is None or not header or len(header) != len(set(header)):
            raise ContactTransferError("CSV header is missing or contains duplicate columns.")
        if "display_name" not in header or set(header) - set(COLUMNS):
            raise ContactTransferError("CSV must contain display_name and only the documented contact fields.")
        rows = []
        for number, cells in enumerate(reader, start=2):
            if not cells or all(not cell.strip() for cell in cells):
                continue
            if len(rows) >= MAX_ROWS:
                raise ContactTransferError("Import limit is 200 contacts per batch.")
            if len(cells) != len(header):
                raise ContactTransferError(f"CSV row {number} has an incorrect number of columns.")
            fields = dict(zip(header, cells))
            fields = {key: (value.strip() or None) for key, value in fields.items()}
            if fields.get("contact_type") is None:
                fields["contact_type"] = "PERSON"
            try:
                row = ContactCreate.model_validate(fields)
            except ValidationError as exc:
                # Never mirror a free-text payload or Pydantic input_value in errors.
                raise ContactTransferError(f"CSV row {number} has invalid contact fields.") from exc
            rows.append(row)
    except (csv.Error, UnicodeError) as exc:
        raise ContactTransferError("Invalid CSV document.") from exc
    if not rows:
        raise ContactTransferError("CSV contains no contact records.")
    return rows


def _dedup_key(row: ContactCreate) -> tuple[str, ...]:
    if row.email:
        return ("email", str(row.email).casefold())
    return ("name", row.display_name.casefold(), (row.company_name or "").casefold())


def _existing(db: Session, *, organization_id: int, row: ContactCreate) -> bool:
    if row.email:
        return db.query(Contact.id).filter(
            Contact.organization_id == organization_id,
            func.lower(Contact.email) == str(row.email).casefold(),
        ).first() is not None
    return db.query(Contact.id).filter(
        Contact.organization_id == organization_id,
        func.lower(Contact.display_name) == row.display_name.casefold(),
        func.lower(func.coalesce(Contact.company_name, "")) == (row.company_name or "").casefold(),
        Contact.email.is_(None),
    ).first() is not None


def _analyze(db: Session, *, organization_id: int, csv_text: str) -> tuple[list[ContactCreate], list[int]]:
    rows = _parse(csv_text)
    seen = set()
    conflicts: list[int] = []
    for number, row in enumerate(rows, start=2):
        key = _dedup_key(row)
        if key in seen or _existing(db, organization_id=organization_id, row=row):
            conflicts.append(number)
        seen.add(key)
    return rows, conflicts


def _digest(organization_id: int, csv_text: str) -> str:
    return sha256(f"{organization_id}:".encode("ascii") + csv_text.encode("utf-8")).hexdigest()


def analyze_import(db: Session, *, organization_id: int, csv_text: str) -> dict:
    rows, conflicts = _analyze(db, organization_id=organization_id, csv_text=csv_text)
    return {
        "total": len(rows),
        "create_count": len(rows) - len(conflicts),
        "conflict_rows": conflicts[:MAX_ROWS],
        "preview_digest": _digest(organization_id, csv_text),
        "can_commit": not conflicts,
        "note": "Preview only; no contacts or accounts changed. Conflicts require a corrected CSV.",
    }


def commit_import(
    db: Session, *, organization_id: int, actor_id: int,
    csv_text: str, preview_digest: str,
) -> dict[str, int]:
    if not preview_digest or _digest(organization_id, csv_text) != preview_digest:
        raise ContactTransferError("CSV changed since preview. Preview again.")
    # Serialize concurrent imports of the same organization in PostgreSQL.
    org = db.query(Organization.id).filter(
        Organization.id == organization_id,
    ).with_for_update().first()
    if org is None:
        raise ContactTransferError("Organization not found.")
    rows, conflicts = _analyze(db, organization_id=organization_id, csv_text=csv_text)
    if conflicts:
        raise ContactTransferError("Contacts changed since preview or duplicate entries exist. Preview again.")
    try:
        for row in rows:
            db.add(Contact(
                organization_id=organization_id, created_by_id=actor_id,
                updated_by_id=actor_id, **row.model_dump(),
            ))
        db.flush()
        append_audit_log(
            db, organization_id=organization_id, user_id=actor_id,
            entity_type="contact_import", entity_id=organization_id,
            action="imported", new_value={"count": len(rows)},
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {"created": len(rows)}


def export_contacts(db: Session, *, organization_id: int) -> bytes:
    rows = db.query(Contact).filter(
        Contact.organization_id == organization_id,
        Contact.is_active.is_(True), Contact.deleted_at.is_(None),
    ).order_by(Contact.display_name.asc(), Contact.id.asc()).limit(MAX_EXPORT + 1).all()
    if len(rows) > MAX_EXPORT:
        raise ContactTransferError("Too many contacts to export at once (limit 1000).")
    return report_csv_bytes(ReportPayload(
        title="Active contact directory", filename="contacts-export.csv",
        headers=COLUMNS,
        rows=tuple(tuple(getattr(row, key) for key in COLUMNS) for row in rows),
    ))
