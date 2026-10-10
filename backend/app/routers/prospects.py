"""Staff CRM lead tracking for existing contacts and assigned properties.

Not an applicant account, signed guest card, mailing service or lease.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from sqlalchemy import or_, func

from app.core.database import get_db
from app.models.prospect import Prospect
from app.models.contact import Contact
from app.models.property import Property, PropertyAssignment
from app.models.user import User, UserRole
from app.routers.auth import get_current_user
from app.schemas.prospect import ProspectIn, ProspectUpdate, ProspectOut, ProspectList
from app.services.audit import append_audit_log
from app.services.menu_resolver import permission_allows_user

router = APIRouter(prefix="/api/leasing/prospects", tags=["Leasing CRM"])


def _access(db: Session, user: User, *, write: bool = False) -> int:
    roles = {UserRole.ADMIN, UserRole.MANAGER} if write else {UserRole.ADMIN, UserRole.OWNER, UserRole.MANAGER}
    if (user.organization_id is None or not user.is_active or user.deleted_at is not None
        or user.role not in roles
        or not permission_allows_user(db, user=user, menu_key="LEASING.CRM")):
        raise HTTPException(status_code=403, detail="Leasing CRM permission required.")
    return int(user.organization_id)


def _assigned(db: Session, user: User):
    return db.query(PropertyAssignment.property_id).filter(
        PropertyAssignment.user_id == user.id,
        PropertyAssignment.is_active.is_(True),
        PropertyAssignment.deleted_at.is_(None),
    )


def _property(db: Session, user: User, org: int, property_id: int) -> Property:
    row = db.query(Property).filter(
        Property.id == property_id, Property.organization_id == org,
        Property.is_active.is_(True), Property.deleted_at.is_(None),
    ).first()
    if row is None or (user.role == UserRole.MANAGER and
                       not db.query(PropertyAssignment.id).filter(
                           PropertyAssignment.property_id == property_id,
                           PropertyAssignment.user_id == user.id,
                           PropertyAssignment.is_active.is_(True),
                           PropertyAssignment.deleted_at.is_(None),
                       ).first()):
        raise HTTPException(status_code=404, detail="Property not found.")
    return row


def _contact(db: Session, org: int, contact_id: int) -> Contact:
    row = db.query(Contact).filter(
        Contact.id == contact_id, Contact.organization_id == org,
        Contact.is_active.is_(True), Contact.deleted_at.is_(None),
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Contact not found.")
    return row


def _out(row: Prospect, contact: Contact) -> ProspectOut:
    return ProspectOut(
        id=row.id, organization_id=row.organization_id,
        property_id=row.property_id, contact_id=row.contact_id,
        stage=row.stage, source=row.source, next_follow_up=row.next_follow_up,
        is_active=row.is_active, created_at=row.created_at, updated_at=row.updated_at,
        contact_name=contact.display_name, contact_email=contact.email,
    )


def _visible(db: Session, org: int, user: User):
    q = db.query(Prospect).filter(Prospect.organization_id == org, Prospect.is_active.is_(True))
    if user.role == UserRole.MANAGER:
        q = q.filter(Prospect.property_id.in_(_assigned(db, user)))
    return q


def _row(db: Session, org: int, user: User, prospect_id: int) -> Prospect:
    row = _visible(db, org, user).filter(Prospect.id == prospect_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Prospect not found.")
    _property(db, user, org, row.property_id)
    _contact(db, org, row.contact_id)
    return row


@router.get("/source-summary")
def source_summary(
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Per-source staff-recorded pipeline counts, not ad ROI or verified applications."""
    org = _access(db, current_user)
    response.headers["Cache-Control"] = "no-store"
    q = (
        _visible(db, org, current_user)
        .join(Property, Property.id == Prospect.property_id)
        .join(Contact, Contact.id == Prospect.contact_id)
        .filter(
            Property.organization_id == org,
            Property.is_active.is_(True), Property.deleted_at.is_(None),
            Contact.organization_id == org,
            Contact.is_active.is_(True), Contact.deleted_at.is_(None),
        )
    )
    grouped = (
        q.with_entities(Prospect.source, Prospect.stage, func.count(Prospect.id))
        .group_by(Prospect.source, Prospect.stage)
        .order_by(Prospect.source, Prospect.stage)
        .limit(501)
        .all()
    )
    if len(grouped) > 500:
        raise HTTPException(status_code=422, detail="Narrow CRM source breakdown.")
    totals: dict[str, dict[str, object]] = {}
    for source, stage, count in grouped:
        if source not in totals:
            totals[source] = {
                "source": source, "total": 0, "new": 0, "contacted": 0,
                "tour_scheduled": 0, "applied": 0, "closed": 0,
            }
        row = totals[source]
        row["total"] += int(count)
        row[stage.lower()] += int(count)
    return {
        "items": list(totals.values()),
        "total": sum(int(row["total"]) for row in totals.values()),
        "meaning": "Staff-entered stages only; not verified applications, paid conversions or marketing ROI.",
    }


@router.get("", response_model=ProspectList)
def list_prospects(
    response: Response, property_id: int | None = None, stage: str | None = None,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org = _access(db, current_user)
    response.headers["Cache-Control"] = "no-store"
    q = _visible(db, org, current_user)
    if property_id is not None:
        _property(db, current_user, org, property_id)
        q = q.filter(Prospect.property_id == property_id)
    if stage is not None:
        if stage not in {"NEW", "CONTACTED", "TOUR_SCHEDULED", "APPLIED", "CLOSED"}:
            raise HTTPException(status_code=422, detail="Invalid prospect stage.")
        q = q.filter(Prospect.stage == stage)
    rows = q.order_by(Prospect.id.desc()).limit(201).all()
    if len(rows) > 200:
        raise HTTPException(status_code=422, detail="Narrow prospect search.")
    result = []
    for row in rows:
        prop = db.query(Property.id).filter(
            Property.id == row.property_id, Property.organization_id == org,
            Property.is_active.is_(True), Property.deleted_at.is_(None),
        ).first()
        contact = db.query(Contact).filter(
            Contact.id == row.contact_id, Contact.organization_id == org,
            Contact.is_active.is_(True), Contact.deleted_at.is_(None),
        ).first()
        if prop and contact:
            result.append(_out(row, contact))
    return ProspectList(items=result, total=len(result))


@router.post("", response_model=ProspectOut, status_code=201)
def create_prospect(
    payload: ProspectIn, response: Response,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org = _access(db, current_user, write=True)
    _property(db, current_user, org, payload.property_id)
    contact = _contact(db, org, payload.contact_id)
    if db.query(Prospect.id).filter(
        Prospect.organization_id == org, Prospect.property_id == payload.property_id,
        Prospect.contact_id == payload.contact_id, Prospect.is_active.is_(True),
    ).first():
        raise HTTPException(status_code=409, detail="Active prospect already exists for this property and contact.")
    row = Prospect(organization_id=org, created_by_id=current_user.id,
                   updated_by_id=current_user.id, **payload.model_dump())
    db.add(row)
    db.flush()
    append_audit_log(db, user_id=current_user.id, organization_id=org,
                     entity_type="leasing_prospect", entity_id=row.id, action="created",
                     new_value={"property_id": row.property_id, "stage": row.stage})
    db.commit()
    db.refresh(row)
    response.headers["Cache-Control"] = "no-store"
    return _out(row, contact)


@router.patch("/{prospect_id}", response_model=ProspectOut)
def update_prospect(
    prospect_id: int, payload: ProspectUpdate, response: Response,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org = _access(db, current_user, write=True)
    row = _row(db, org, current_user, prospect_id)
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=422, detail="No changes supplied.")
    if "stage" in changes and changes["stage"] is None or "source" in changes and changes["source"] is None:
        raise HTTPException(status_code=422, detail="Stage and source cannot be blank.")
    changed = []
    for key, value in changes.items():
        if getattr(row, key) != value:
            setattr(row, key, value)
            changed.append(key)
    if changed:
        row.updated_by_id = current_user.id
        db.flush()
        append_audit_log(db, user_id=current_user.id, organization_id=org,
                         entity_type="leasing_prospect", entity_id=row.id, action="updated",
                         field_name=",".join(sorted(changed)),
                         new_value={"changed_fields": sorted(changed), "stage": row.stage})
        db.commit()
    db.refresh(row)
    response.headers["Cache-Control"] = "no-store"
    return _out(row, _contact(db, org, row.contact_id))


@router.delete("/{prospect_id}", status_code=204)
def archive_prospect(
    prospect_id: int, db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org = _access(db, current_user, write=True)
    row = _row(db, org, current_user, prospect_id)
    row.is_active = False
    append_audit_log(db, user_id=current_user.id, organization_id=org,
                     entity_type="leasing_prospect", entity_id=row.id, action="archived")
    db.commit()
    return Response(status_code=204, headers={"Cache-Control": "no-store"})
