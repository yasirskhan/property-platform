"""Phase 4.8: staff-only commercial lease commencement index.

Recorded dates are not a verified contract, due date, rent schedule, CAM
allocation, legal notice, invoice or ledger instruction.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.commercial_lease_abstract import CommercialLeaseAbstract
from app.models.entity_attachment import EntityAttachment
from app.models.lease import Lease
from app.models.property import Property, PropertyType, Unit
from app.models.user import User, UserRole
from app.routers import affordable_programs
from app.routers.auth import get_current_user
from app.schemas.commercial_lease_abstract import (
    CommercialLeaseAbstractIn, CommercialLeaseAbstractOut,
    CommercialLeaseAbstractUpdate, CommercialLeaseCandidateOut,
    CommercialLeaseSourceOut,
)
from app.services.audit import append_audit_log
from app.services.menu_resolver import permission_allows_user
from app.services.customer_features import resolve_customer_features

router = APIRouter(prefix="/api/properties", tags=["Commercial lease staff references"])
ATTACHMENTS_FEATURE_KEY = "release.documents.attachments"


def _property(db: Session, property_id: int, actor: User, *, write: bool = False) -> Property:
    prop = affordable_programs._property(
        db, property_id=property_id, actor=actor, write=write,
    )
    if not permission_allows_user(db, user=actor, menu_key="LEASING"):
        raise HTTPException(status_code=403, detail="Leasing permission required.")
    if prop.property_type != PropertyType.COMMERCIAL:
        raise HTTPException(status_code=404, detail="Commercial property not found.")
    return prop


def _eligible_leases(db: Session, prop: Property):
    return db.query(Lease, Unit).join(
        Unit, Unit.id == Lease.unit_id,
    ).join(User, User.id == Lease.tenant_id).filter(
        Unit.property_id == prop.id,
        Unit.is_active.is_(True), Unit.deleted_at.is_(None),
        User.organization_id == prop.organization_id,
        User.role == UserRole.TENANT,
        User.is_active.is_(True), User.deleted_at.is_(None),
    )


def _lease(db: Session, prop: Property, lease_id: int) -> tuple[Lease, Unit]:
    found = _eligible_leases(db, prop).filter(Lease.id == lease_id).first()
    if found is None:
        raise HTTPException(status_code=404, detail="Recorded lease not found.")
    return found


def _item(db: Session, prop: Property, item_id: int) -> CommercialLeaseAbstract:
    item = db.query(CommercialLeaseAbstract).filter(
        CommercialLeaseAbstract.id == item_id,
        CommercialLeaseAbstract.organization_id == prop.organization_id,
        CommercialLeaseAbstract.property_id == prop.id,
        CommercialLeaseAbstract.is_active.is_(True),
    ).first()
    if item is None:
        raise HTTPException(status_code=404, detail="Commercial reference not found.")
    return item


def _candidate(lease: Lease, unit: Unit) -> CommercialLeaseCandidateOut:
    status = lease.status.value if hasattr(lease.status, "value") else str(lease.status)
    return CommercialLeaseCandidateOut(
        lease_id=lease.id, unit_id=unit.id, unit_number=unit.unit_number,
        lease_start_on=lease.start_date, lease_end_on=lease.end_date,
        lease_status=status,
    )


def _attachment_gate(db: Session, actor: User) -> None:
    decision = next(
        (item for item in resolve_customer_features(db, user=actor)
         if item.key == ATTACHMENTS_FEATURE_KEY), None,
    )
    if decision is None or not decision.allowed:
        raise HTTPException(status_code=404, detail="Commercial lease source documents unavailable.")


def _source_attachment(
    db: Session, *, prop: Property, lease: Lease, attachment_id: int,
    actor: User,
) -> EntityAttachment:
    _attachment_gate(db, actor)
    row = db.query(EntityAttachment).filter(
        EntityAttachment.id == attachment_id,
        EntityAttachment.organization_id == prop.organization_id,
        EntityAttachment.entity_type == "leases",
        EntityAttachment.entity_id == lease.id,
        EntityAttachment.is_active.is_(True),
        EntityAttachment.deleted_at.is_(None),
        EntityAttachment.share_with_tenants.is_(False),
        EntityAttachment.share_with_owners.is_(False),
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Private lease source document not found.")
    return row


def _out(
    item: CommercialLeaseAbstract, lease: Lease, unit: Unit,
    source: EntityAttachment | None = None,
) -> CommercialLeaseAbstractOut:
    return CommercialLeaseAbstractOut(
        id=item.id, property_id=item.property_id,
        rent_commencement_on=item.rent_commencement_on,
        source_attachment_id=source.id if source else None,
        source_filename=source.original_name if source else None,
        source_status="STAFF_LINKED_UNVERIFIED" if source else None,
        recorded_at=item.updated_at, **_candidate(lease, unit).model_dump(),
    )


def _audit(db: Session, *, row: CommercialLeaseAbstract, actor: User, action: str) -> None:
    append_audit_log(
        db, organization_id=row.organization_id, user_id=actor.id,
        entity_type="commercial_lease_abstract", entity_id=row.id, action=action,
        new_value={"property_id": row.property_id, "lease_id": row.lease_id,
                   "source_document_linked": row.source_attachment_id is not None},
    )


@router.get("/{property_id}/commercial-lease-abstracts/candidates",
            response_model=list[CommercialLeaseCandidateOut])
def list_candidates(
    property_id: int, response: Response,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    prop = _property(db, property_id, current_user)
    rows = _eligible_leases(db, prop).order_by(Lease.id).limit(251).all()
    if len(rows) > 250:
        raise HTTPException(status_code=409, detail="Too many recorded leases for this selector.")
    response.headers["Cache-Control"] = "no-store"
    return [_candidate(lease, unit) for lease, unit in rows]


@router.get("/{property_id}/commercial-lease-abstracts/source-candidates",
            response_model=list[CommercialLeaseSourceOut])
def list_source_candidates(
    property_id: int, response: Response, lease_id: int = Query(ge=1),
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    prop = _property(db, property_id, current_user)
    lease, _unit = _lease(db, prop, lease_id)
    _attachment_gate(db, current_user)
    rows = db.query(EntityAttachment).filter(
        EntityAttachment.organization_id == prop.organization_id,
        EntityAttachment.entity_type == "leases",
        EntityAttachment.entity_id == lease.id,
        EntityAttachment.is_active.is_(True),
        EntityAttachment.deleted_at.is_(None),
        EntityAttachment.share_with_tenants.is_(False),
        EntityAttachment.share_with_owners.is_(False),
    ).order_by(EntityAttachment.created_at.desc(), EntityAttachment.id.desc()).limit(101).all()
    if len(rows) > 100:
        raise HTTPException(status_code=422, detail="Too many private lease source documents.")
    response.headers["Cache-Control"] = "no-store"
    return [
        CommercialLeaseSourceOut(
            id=row.id, filename=row.original_name,
            content_type=row.content_type, size_bytes=row.size_bytes,
        )
        for row in rows
    ]


@router.get("/{property_id}/commercial-lease-abstracts",
            response_model=list[CommercialLeaseAbstractOut])
def list_abstracts(
    property_id: int, response: Response,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    prop = _property(db, property_id, current_user)
    rows = db.query(CommercialLeaseAbstract, Lease, Unit).join(
        Lease, Lease.id == CommercialLeaseAbstract.lease_id,
    ).join(Unit, Unit.id == Lease.unit_id).join(
        User, User.id == Lease.tenant_id,
    ).filter(
        CommercialLeaseAbstract.organization_id == prop.organization_id,
        CommercialLeaseAbstract.property_id == prop.id,
        CommercialLeaseAbstract.is_active.is_(True),
        Unit.property_id == prop.id,
        Unit.is_active.is_(True), Unit.deleted_at.is_(None),
        User.organization_id == prop.organization_id,
        User.role == UserRole.TENANT,
        User.is_active.is_(True), User.deleted_at.is_(None),
    ).order_by(CommercialLeaseAbstract.id).limit(251).all()
    if len(rows) > 250:
        raise HTTPException(status_code=409, detail="Too many commercial references.")
    response.headers["Cache-Control"] = "no-store"
    result = []
    for row, lease, unit in rows:
        source = None
        if row.source_attachment_id is not None:
            source = _source_attachment(
                db, prop=prop, lease=lease,
                attachment_id=row.source_attachment_id, actor=current_user,
            )
        result.append(_out(row, lease, unit, source))
    return result


@router.post("/{property_id}/commercial-lease-abstracts",
             response_model=CommercialLeaseAbstractOut, status_code=201)
def record_abstract(
    property_id: int, payload: CommercialLeaseAbstractIn,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    prop = _property(db, property_id, current_user, write=True)
    lease, unit = _lease(db, prop, payload.lease_id)
    source = (_source_attachment(db, prop=prop, lease=lease,
                                 attachment_id=payload.source_attachment_id,
                                 actor=current_user)
              if payload.source_attachment_id is not None else None)
    row = db.query(CommercialLeaseAbstract).filter(
        CommercialLeaseAbstract.organization_id == prop.organization_id,
        CommercialLeaseAbstract.lease_id == lease.id,
    ).first()
    if row is not None and (row.is_active or row.property_id != prop.id):
        raise HTTPException(status_code=409, detail="Lease reference already recorded.")
    action = "rerecorded" if row is not None else "created"
    if row is None:
        row = CommercialLeaseAbstract(
            organization_id=prop.organization_id, property_id=prop.id,
            lease_id=lease.id, created_by_id=current_user.id,
        )
        db.add(row)
    row.is_active = True
    row.rent_commencement_on = payload.rent_commencement_on
    row.source_attachment_id = source.id if source else None
    row.updated_by_id = current_user.id
    try:
        db.flush()
        _audit(db, row=row, actor=current_user, action=action)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Lease reference already recorded.") from exc
    db.refresh(row)
    return _out(row, lease, unit, source)


@router.put("/{property_id}/commercial-lease-abstracts/{item_id}",
            response_model=CommercialLeaseAbstractOut)
def update_abstract(
    property_id: int, item_id: int, payload: CommercialLeaseAbstractUpdate,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    prop = _property(db, property_id, current_user, write=True)
    row = _item(db, prop, item_id)
    lease, unit = _lease(db, prop, row.lease_id)
    if not ({"rent_commencement_on", "source_attachment_id"} & payload.model_fields_set):
        raise HTTPException(status_code=400, detail="Supply a recorded date/source change or explicit null.")
    source = None
    if "source_attachment_id" in payload.model_fields_set:
        if payload.source_attachment_id is not None:
            source = _source_attachment(
                db, prop=prop, lease=lease,
                attachment_id=payload.source_attachment_id, actor=current_user,
            )
        row.source_attachment_id = source.id if source else None
    elif row.source_attachment_id is not None:
        source = _source_attachment(
            db, prop=prop, lease=lease,
            attachment_id=row.source_attachment_id, actor=current_user,
        )
    if "rent_commencement_on" in payload.model_fields_set:
        row.rent_commencement_on = payload.rent_commencement_on
    row.updated_by_id = current_user.id
    db.flush()
    _audit(db, row=row, actor=current_user, action="updated")
    db.commit()
    db.refresh(row)
    return _out(row, lease, unit, source)


@router.delete("/{property_id}/commercial-lease-abstracts/{item_id}", status_code=204)
def archive_abstract(
    property_id: int, item_id: int,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    prop = _property(db, property_id, current_user, write=True)
    row = _item(db, prop, item_id)
    _lease(db, prop, row.lease_id)
    row.is_active = False
    row.updated_by_id = current_user.id
    db.flush()
    _audit(db, row=row, actor=current_user, action="archived")
    db.commit()
    return Response(status_code=204)
