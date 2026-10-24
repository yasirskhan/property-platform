"""Restricted per-building Form 8609 reference status. No IRS filing, document or credit."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.affordable_building import AffordableBuilding
from app.models.affordable_8609_readiness import Affordable8609Readiness
from app.models.user import User
from app.routers.auth import get_current_user
from app.routers.affordable_buildings import _lihtc
from app.schemas.affordable_8609_readiness import Affordable8609ReadinessIn, Affordable8609ReadinessOut
from app.services.audit import append_audit_log

router = APIRouter(prefix="/api/properties", tags=["LIHTC Form 8609 readiness"])


def _building(db: Session, *, property_id: int, program_id: int,
              building_id: int, user: User, write: bool) -> tuple[object, AffordableBuilding]:
    prop, program = _lihtc(db, property_id=property_id, program_id=program_id,
                           actor=user, write=write)
    building = db.query(AffordableBuilding).filter(
        AffordableBuilding.id == building_id,
        AffordableBuilding.organization_id == prop.organization_id,
        AffordableBuilding.property_id == prop.id,
        AffordableBuilding.program_id == program.id,
        AffordableBuilding.is_active.is_(True),
    ).first()
    if building is None:
        raise HTTPException(status_code=404, detail="Recorded LIHTC building not found.")
    return prop, building


@router.get("/{property_id}/affordable-programs/{program_id}/buildings/{building_id}/8609-readiness",
            response_model=Affordable8609ReadinessOut)
def get_readiness(
    property_id: int, program_id: int, building_id: int, response: Response,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    prop, building = _building(db, property_id=property_id, program_id=program_id,
                               building_id=building_id, user=current_user, write=False)
    response.headers["Cache-Control"] = "no-store"
    row = db.query(Affordable8609Readiness).filter(
        Affordable8609Readiness.organization_id == prop.organization_id,
        Affordable8609Readiness.property_id == prop.id,
        Affordable8609Readiness.program_id == program_id,
        Affordable8609Readiness.building_id == building.id,
    ).first()
    return Affordable8609ReadinessOut(
        building_id=building.id, status=row.status if row else "NOT_RECORDED",
        updated_at=row.updated_at if row else None,
    )


@router.put("/{property_id}/affordable-programs/{program_id}/buildings/{building_id}/8609-readiness",
            response_model=Affordable8609ReadinessOut)
def save_readiness(
    property_id: int, program_id: int, building_id: int,
    payload: Affordable8609ReadinessIn,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    prop, building = _building(db, property_id=property_id, program_id=program_id,
                               building_id=building_id, user=current_user, write=True)
    row = db.query(Affordable8609Readiness).filter(
        Affordable8609Readiness.organization_id == prop.organization_id,
        Affordable8609Readiness.property_id == prop.id,
        Affordable8609Readiness.program_id == program_id,
        Affordable8609Readiness.building_id == building.id,
    ).first()
    previous = row.status if row else "NOT_RECORDED"
    created = row is None
    if row is None:
        row = Affordable8609Readiness(
            organization_id=prop.organization_id, property_id=prop.id,
            program_id=program_id, building_id=building.id,
        )
        db.add(row)
    row.status = payload.status
    row.updated_by_id = current_user.id
    try:
        db.flush()
        append_audit_log(
            db, user_id=current_user.id, organization_id=prop.organization_id,
            entity_type="affordable_8609_readiness", entity_id=row.id,
            action="recorded" if created else "updated",
            old_value=None if created else {"status": previous},
            new_value={"building_id": building.id, "status": payload.status},
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Form 8609 readiness changed concurrently.") from exc
    db.refresh(row)
    return Affordable8609ReadinessOut.model_validate(row)
