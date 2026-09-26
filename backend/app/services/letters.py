"""Text-only mail merge; tenant and property scoping are checked at every render."""
from __future__ import annotations

import re

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.lease import Lease, LeaseStatus
from app.models.letter_template import LetterTemplate
from app.models.property import Property, PropertyAssignment, Unit
from app.models.user import Organization, User, UserRole
from app.services.menu_resolver import permission_allows_user

ALLOWED_TAGS = frozenset({
    "tenant_name", "tenant_email", "property_name", "property_address",
    "unit_number", "lease_start", "lease_end", "monthly_rent",
    "organization_name",
})
TOKEN = re.compile(r"{{\s*([a-z_]+)\s*}}")
ANY_BRACE = re.compile(r"{{|}}")
HTML_LIKE = re.compile(r"<\s*/?\s*[a-zA-Z!][^>]*>")
CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
MAX_BODY = 12000


def require_letters_access(db: Session, user: User) -> int:
    role = user.role.value if hasattr(user.role, "value") else str(user.role or "")
    if (user.organization_id is None or role not in {"ADMIN", "MANAGER"}
            or not user.is_active or user.deleted_at is not None
            or not permission_allows_user(db, user=user, menu_key="REPORTING.ALL")
            or not permission_allows_user(db, user=user, menu_key="LEASING")):
        raise HTTPException(status_code=403, detail="Letters permission required.")
    return int(user.organization_id)


def validate_letter(subject: str, body: str) -> None:
    for value in (subject, body):
        if not value.strip() or len(value) > MAX_BODY or CONTROL.search(value):
            raise HTTPException(status_code=422, detail="Invalid letter text.")
        if HTML_LIKE.search(value) or "<" in value or ">" in value:
            raise HTTPException(status_code=422, detail="Letters must use plain text.")
        if any(tag not in ALLOWED_TAGS for tag in TOKEN.findall(value)):
            raise HTTPException(status_code=422, detail="Unsupported merge tag.")
        if ANY_BRACE.search(TOKEN.sub("", value)):
            raise HTTPException(status_code=422, detail="Malformed merge tag.")


def scoped_letter(db: Session, *, user: User, letter_id: int) -> LetterTemplate:
    org = require_letters_access(db, user)
    row = db.query(LetterTemplate).filter(
        LetterTemplate.id == letter_id,
        LetterTemplate.organization_id == org,
        LetterTemplate.is_active.is_(True),
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Letter not found.")
    return row


def tenant_context(db: Session, *, user: User, lease_id: int) -> tuple[dict[str, str], User, int]:
    org = require_letters_access(db, user)
    data = (
        db.query(Lease, Unit, Property, User, Organization)
        .join(Unit, Unit.id == Lease.unit_id)
        .join(Property, Property.id == Unit.property_id)
        .join(User, User.id == Lease.tenant_id)
        .join(Organization, Organization.id == Property.organization_id)
        .filter(
            Lease.id == lease_id, Lease.status == LeaseStatus.ACTIVE,
            Unit.is_active.is_(True), Unit.deleted_at.is_(None),
            Property.organization_id == org, Property.is_active.is_(True),
            Property.deleted_at.is_(None), User.organization_id == org,
            User.role == UserRole.TENANT, User.is_active.is_(True),
            User.deleted_at.is_(None),
        ).first()
    )
    if data is None:
        raise HTTPException(status_code=404, detail="Active lease not found.")
    lease, unit, prop, tenant, organization = data
    role = user.role.value if hasattr(user.role, "value") else str(user.role or "")
    if role == "MANAGER" and not db.query(PropertyAssignment.id).filter(
        PropertyAssignment.property_id == prop.id,
        PropertyAssignment.user_id == user.id,
        PropertyAssignment.is_active.is_(True),
        PropertyAssignment.deleted_at.is_(None),
    ).first():
        raise HTTPException(status_code=404, detail="Active lease not found.")
    addr = ", ".join(part for part in (
        prop.address_line1, prop.address_line2, prop.city, prop.state,
        prop.zip_code, prop.country,
    ) if part)
    values = {
        "tenant_name": f"{tenant.first_name} {tenant.last_name}".strip(),
        "tenant_email": tenant.email,
        "property_name": prop.name,
        "property_address": addr,
        "unit_number": unit.unit_number,
        "lease_start": lease.start_date.isoformat(),
        "lease_end": lease.end_date.isoformat(),
        "monthly_rent": f"{lease.monthly_rent:.2f}",
        "organization_name": organization.name,
    }
    return values, tenant, prop.id


def render_plain(text: str, values: dict[str, str]) -> str:
    validate_letter("Letter", text)
    return TOKEN.sub(lambda match: values[match.group(1)], text)


def render_for_lease(db: Session, *, user: User, row: LetterTemplate, lease_id: int):
    values, tenant, property_id = tenant_context(db, user=user, lease_id=lease_id)
    validate_letter(row.subject, row.body)
    from app.schemas.letter import LetterPreviewOut
    return LetterPreviewOut(
        title=row.title, category=row.category,
        subject=render_plain(row.subject, values),
        body=render_plain(row.body, values),
        recipient_email=tenant.email, tenant_id=tenant.id,
        lease_id=lease_id, property_id=property_id,
        legal_notice_review_required=row.category == "THREE_DAY_NOTICE",
    )
