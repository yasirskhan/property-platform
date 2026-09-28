"""Organization-scoped HOA roster only; never an assessment or official HOA certification."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.hoa_association import HOAAssociation, HOAPropertyMembership
from app.models.property import Property, PropertyAssignment
from app.models.user import User, UserRole
from app.routers.auth import get_current_user
from app.schemas.hoa_association import HOAAssociationIn, HOAAssociationOut
from app.services.audit import append_audit_log
from app.services.customer_features import resolve_customer_features
from app.services.menu_resolver import permission_allows_user

router = APIRouter(prefix="/api/hoa/associations", tags=["HOA association inventory"])
# Existing compliance capability, no new unrelated per-field flag.
FEATURE_KEY = "release.properties.compliance"


def _access(db: Session, actor: User, *, write: bool = False) -> int:
    if (
        actor.organization_id is None or not actor.is_active or actor.deleted_at is not None
        or actor.role not in {UserRole.ADMIN, UserRole.OWNER, UserRole.MANAGER}
        or (write and actor.role not in {UserRole.ADMIN, UserRole.OWNER})
        or not permission_allows_user(db, user=actor, menu_key="PROPERTIES.ALL")
    ):
        raise HTTPException(status_code=403, detail="HOA property permission required.")
    decision = next(
        (x for x in resolve_customer_features(db, user=actor) if x.key == FEATURE_KEY), None
    )
    if decision is None or not decision.allowed:
        raise HTTPException(status_code=404, detail="HOA inventory unavailable.")
    return int(actor.organization_id)


def _visible(db: Session, *, org_id: int, actor: User):
    query = db.query(Property).filter(
        Property.organization_id == org_id,
        Property.is_active.is_(True),
        Property.deleted_at.is_(None),
    )
    if actor.role == UserRole.MANAGER:
        assigned = db.query(PropertyAssignment.property_id).filter(
            PropertyAssignment.user_id == actor.id,
            PropertyAssignment.is_active.is_(True),
            PropertyAssignment.deleted_at.is_(None),
        )
        query = query.filter(Property.id.in_(assigned))
    return query


def _association(db: Session, *, org_id: int, association_id: int) -> HOAAssociation:
    row = db.query(HOAAssociation).filter(
        HOAAssociation.id == association_id,
        HOAAssociation.organization_id == org_id,
        HOAAssociation.is_active.is_(True),
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Association not found.")
    return row


def _members(db: Session, *, org_id: int, actor: User, association_id: int) -> list[Property]:
    return _visible(db, org_id=org_id, actor=actor).join(
        HOAPropertyMembership, HOAPropertyMembership.property_id == Property.id,
    ).filter(
        HOAPropertyMembership.organization_id == org_id,
        HOAPropertyMembership.association_id == association_id,
    ).order_by(Property.name.asc(), Property.id.asc()).all()


def _out(row: HOAAssociation, members: list[Property]) -> HOAAssociationOut:
    return HOAAssociationOut(
        id=row.id, name=row.name, property_ids=[p.id for p in members],
        updated_at=row.updated_at,
    )


@router.get("", response_model=list[HOAAssociationOut])
def list_associations(
    response: Response, db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = _access(db, current_user)
    response.headers["Cache-Control"] = "no-store"
    rows = db.query(HOAAssociation).filter(
        HOAAssociation.organization_id == org_id, HOAAssociation.is_active.is_(True),
    ).order_by(HOAAssociation.name, HOAAssociation.id).limit(501).all()
    result = []
    for row in rows:
        members = _members(db, org_id=org_id, actor=current_user, association_id=row.id)
        if current_user.role == UserRole.MANAGER and not members:
            continue
        result.append(_out(row, members))
    return result


@router.get("/{association_id}", response_model=HOAAssociationOut)
def get_association(
    association_id: int, response: Response, db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = _access(db, current_user)
    row = _association(db, org_id=org_id, association_id=association_id)
    members = _members(db, org_id=org_id, actor=current_user, association_id=row.id)
    if current_user.role == UserRole.MANAGER and not members:
        raise HTTPException(status_code=404, detail="Association not found.")
    response.headers["Cache-Control"] = "no-store"
    return _out(row, members)


def _save(db: Session, *, actor: User, payload: HOAAssociationIn,
          association_id: int | None = None) -> HOAAssociationOut:
    org_id = _access(db, actor, write=True)
    wanted = set(payload.property_ids)
    found = {p.id for p in _visible(db, org_id=org_id, actor=actor).filter(
        Property.id.in_(wanted)
    ).all()} if wanted else set()
    if wanted != found:
        raise HTTPException(status_code=404, detail="Property not found.")
    key = payload.name.casefold()
    duplicate = db.query(HOAAssociation.id).filter(
        HOAAssociation.organization_id == org_id, HOAAssociation.name_key == key,
    )
    if association_id is not None:
        duplicate = duplicate.filter(HOAAssociation.id != association_id)
    if duplicate.first() is not None:
        raise HTTPException(status_code=409, detail="Association name already exists.")
    created = association_id is None
    row = (
        HOAAssociation(organization_id=org_id, created_by_id=actor.id)
        if created else _association(db, org_id=org_id, association_id=association_id)
    )
    if created:
        db.add(row)
    row.name, row.name_key, row.updated_by_id = payload.name, key, actor.id
    try:
        db.flush()
        current = db.query(HOAPropertyMembership).filter(
            HOAPropertyMembership.organization_id == org_id,
            HOAPropertyMembership.association_id == row.id,
        ).all()
        current_ids = {m.property_id for m in current}
        for m in current:
            if m.property_id not in wanted:
                db.delete(m)
        for property_id in sorted(wanted - current_ids):
            db.add(HOAPropertyMembership(
                organization_id=org_id, association_id=row.id, property_id=property_id,
            ))
        db.flush()
        append_audit_log(
            db, organization_id=org_id, user_id=actor.id,
            entity_type="hoa_association", entity_id=row.id,
            action="created" if created else "updated",
            new_value={"property_ids": sorted(wanted)},
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Association update conflicts with an existing record.") from exc
    db.refresh(row)
    return _out(row, _members(db, org_id=org_id, actor=actor, association_id=row.id))


@router.post("", response_model=HOAAssociationOut, status_code=201)
def create_association(
    payload: HOAAssociationIn, db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _save(db, actor=current_user, payload=payload)


@router.put("/{association_id}", response_model=HOAAssociationOut)
def update_association(
    association_id: int, payload: HOAAssociationIn, db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _save(db, actor=current_user, payload=payload, association_id=association_id)


@router.delete("/{association_id}", status_code=204)
def archive_association(
    association_id: int, db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = _access(db, current_user, write=True)
    row = _association(db, org_id=org_id, association_id=association_id)
    row.is_active = False
    row.updated_by_id = current_user.id
    db.flush()
    append_audit_log(
        db, organization_id=org_id, user_id=current_user.id,
        entity_type="hoa_association", entity_id=row.id,
        action="archived",
    )
    db.commit()
    return Response(status_code=204, headers={"Cache-Control": "no-store"})
