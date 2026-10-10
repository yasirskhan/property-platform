"""Recorded LIHTC BINs per program, never an IRS Form 8609 submission."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.affordable_building import AffordableBuilding
from app.models.user import User
from app.routers.auth import get_current_user
from app.routers.affordable_programs import _property, _item
from app.schemas.affordable_building import AffordableBuildingIn, AffordableBuildingOut
from app.services.audit import append_audit_log

router = APIRouter(prefix="/api/properties", tags=["LIHTC recorded buildings"])


def _lihtc(db: Session, *, property_id: int, program_id: int, actor: User, write: bool):
    prop = _property(db, property_id=property_id, actor=actor, write=write)
    program = _item(db, org_id=prop.organization_id, prop_id=prop.id, item_id=program_id)
    if program.program_type != "LIHTC":
        raise HTTPException(status_code=404, detail="LIHTC program not found.")
    return prop, program


@router.get("/{property_id}/affordable-programs/{program_id}/buildings",
            response_model=list[AffordableBuildingOut])
def list_buildings(
    property_id: int, program_id: int, response: Response,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    prop, program = _lihtc(db, property_id=property_id, program_id=program_id,
                           actor=current_user, write=False)
    response.headers["Cache-Control"] = "no-store"
    rows = db.query(AffordableBuilding).filter(
        AffordableBuilding.organization_id == prop.organization_id,
        AffordableBuilding.property_id == prop.id,
        AffordableBuilding.program_id == program.id,
        AffordableBuilding.is_active.is_(True),
    ).order_by(AffordableBuilding.agency_bin).limit(101).all()
    if len(rows) > 100:
        raise HTTPException(status_code=422, detail="Recorded building list exceeds preview limit.")
    return rows


@router.post("/{property_id}/affordable-programs/{program_id}/buildings",
             response_model=AffordableBuildingOut, status_code=201)
def record_building(
    property_id: int, program_id: int, payload: AffordableBuildingIn,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    prop, program = _lihtc(db, property_id=property_id, program_id=program_id,
                           actor=current_user, write=True)
    row = db.query(AffordableBuilding).filter(
        AffordableBuilding.organization_id == prop.organization_id,
        AffordableBuilding.program_id == program.id,
        AffordableBuilding.agency_bin == payload.agency_bin,
    ).first()
    if row is not None and row.is_active:
        raise HTTPException(status_code=409, detail="Building BIN already recorded for this program.")
    restored = row is not None
    if row is None:
        row = AffordableBuilding(
            organization_id=prop.organization_id, property_id=prop.id,
            program_id=program.id, agency_bin=payload.agency_bin,
            recorded_by_id=current_user.id,
        )
        db.add(row)
    row.building_label = payload.building_label
    row.is_active = True
    row.updated_by_id = current_user.id
    try:
        db.flush()
        append_audit_log(
            db, organization_id=prop.organization_id, user_id=current_user.id,
            entity_type="affordable_lihtc_building", entity_id=row.id,
            action="restored" if restored else "recorded",
            new_value={"program_id": program.id, "building_id": row.id},
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Building BIN already recorded for this program.") from exc
    db.refresh(row)
    return row


@router.delete("/{property_id}/affordable-programs/{program_id}/buildings/{building_id}",
               status_code=204)
def archive_building(
    property_id: int, program_id: int, building_id: int,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    prop, program = _lihtc(db, property_id=property_id, program_id=program_id,
                           actor=current_user, write=True)
    row = db.query(AffordableBuilding).filter(
        AffordableBuilding.id == building_id,
        AffordableBuilding.organization_id == prop.organization_id,
        AffordableBuilding.property_id == prop.id,
        AffordableBuilding.program_id == program.id,
        AffordableBuilding.is_active.is_(True),
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Recorded building not found.")
    row.is_active = False
    row.updated_by_id = current_user.id
    db.flush()
    append_audit_log(
        db, organization_id=prop.organization_id, user_id=current_user.id,
        entity_type="affordable_lihtc_building", entity_id=row.id,
        action="archived", new_value={"program_id": program.id, "building_id": row.id},
    )
    db.commit()
    return Response(status_code=204)
