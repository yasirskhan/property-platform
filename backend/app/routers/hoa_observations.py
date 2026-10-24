"""Staff-recorded HOA observations; no violation ruling, notice, fine or GL."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.hoa_observation import HOAObservation
from app.models.user import User
from app.routers.auth import get_current_user
from app.routers.hoa_assessments import _scope
from app.schemas.hoa_observation import HOAObservationIn, HOAObservationOut
from app.services.audit import append_audit_log

router = APIRouter(prefix="/api/hoa/associations", tags=["HOA staff observations"])


def _record(db: Session, *, org_id: int, association_id: int, property_id: int, note_id: int):
    row = db.query(HOAObservation).filter(
        HOAObservation.id == note_id,
        HOAObservation.organization_id == org_id,
        HOAObservation.association_id == association_id,
        HOAObservation.property_id == property_id,
        HOAObservation.is_active.is_(True),
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Staff observation not found.")
    return row


def _out(row: HOAObservation) -> HOAObservationOut:
    return HOAObservationOut(
        id=row.id, association_id=row.association_id,
        property_id=row.property_id, summary=row.summary,
        observed_on=row.observed_on, details=row.details,
        updated_at=row.updated_at,
    )


@router.get("/{association_id}/observations", response_model=list[HOAObservationOut])
def list_observations(
    association_id: int, response: Response, property_id: int = Query(ge=1),
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org_id, association = _scope(
        db, actor=current_user, association_id=association_id,
        property_id=property_id, write=False,
    )
    response.headers["Cache-Control"] = "no-store"
    rows = db.query(HOAObservation).filter(
        HOAObservation.organization_id == org_id,
        HOAObservation.association_id == association.id,
        HOAObservation.property_id == property_id,
        HOAObservation.is_active.is_(True),
    ).order_by(HOAObservation.id.asc()).limit(201).all()
    if len(rows) > 200:
        raise HTTPException(status_code=422, detail="Too many staff observations for this property.")
    return [_out(row) for row in rows]


@router.post("/{association_id}/observations", response_model=HOAObservationOut, status_code=201)
def create_observation(
    association_id: int, payload: HOAObservationIn,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org_id, association = _scope(
        db, actor=current_user, association_id=association_id,
        property_id=payload.property_id, write=True,
    )
    count = db.query(HOAObservation.id).filter(
        HOAObservation.organization_id == org_id,
        HOAObservation.association_id == association.id,
        HOAObservation.property_id == payload.property_id,
        HOAObservation.is_active.is_(True),
    ).limit(201).all()
    if len(count) >= 200:
        raise HTTPException(status_code=422, detail="Too many staff observations for this property.")
    row = HOAObservation(
        organization_id=org_id, association_id=association.id,
        created_by_id=current_user.id, updated_by_id=current_user.id,
        **payload.model_dump(),
    )
    db.add(row)
    try:
        db.flush()
        append_audit_log(
            db, organization_id=org_id, user_id=current_user.id,
            entity_type="hoa_observation", entity_id=row.id,
            action="staff_recorded",
            new_value={"association_id": association.id, "property_id": row.property_id},
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Observation changed concurrently.") from exc
    db.refresh(row)
    return _out(row)


@router.put("/{association_id}/observations/{note_id}", response_model=HOAObservationOut)
def update_observation(
    association_id: int, note_id: int, payload: HOAObservationIn,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org_id, association = _scope(
        db, actor=current_user, association_id=association_id,
        property_id=payload.property_id, write=True,
    )
    row = _record(db, org_id=org_id, association_id=association.id,
                  property_id=payload.property_id, note_id=note_id)
    for key, value in payload.model_dump().items():
        setattr(row, key, value)
    row.updated_by_id = current_user.id
    db.flush()
    append_audit_log(
        db, organization_id=org_id, user_id=current_user.id,
        entity_type="hoa_observation", entity_id=row.id,
        action="staff_updated",
        new_value={"association_id": association.id, "property_id": row.property_id},
    )
    db.commit()
    db.refresh(row)
    return _out(row)


@router.delete("/{association_id}/observations/{note_id}", status_code=204)
def archive_observation(
    association_id: int, note_id: int, property_id: int,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org_id, association = _scope(
        db, actor=current_user, association_id=association_id,
        property_id=property_id, write=True,
    )
    row = _record(db, org_id=org_id, association_id=association.id,
                  property_id=property_id, note_id=note_id)
    row.is_active = False
    row.updated_by_id = current_user.id
    db.flush()
    append_audit_log(
        db, organization_id=org_id, user_id=current_user.id,
        entity_type="hoa_observation", entity_id=row.id,
        action="staff_archived",
        new_value={"association_id": association.id, "property_id": property_id},
    )
    db.commit()
    return Response(status_code=204, headers={"Cache-Control": "no-store"})
