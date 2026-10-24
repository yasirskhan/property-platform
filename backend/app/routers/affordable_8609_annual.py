"""Scoped annual Form 8609-A staff references, never IRS filing or compliance determination."""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.affordable_8609_annual import Affordable8609Annual
from app.models.user import User
from app.routers.auth import get_current_user
from app.routers.affordable_8609_readiness import _building
from app.schemas.affordable_8609_annual import (
    AllocationCategory, Affordable8609AnnualIn, Affordable8609AnnualOut,
)
from app.services.audit import append_audit_log

router = APIRouter(prefix="/api/properties", tags=["Annual LIHTC Form 8609-A reference"])
CATEGORIES: tuple[AllocationCategory, ...] = (
    "BUILDING_OR_ACQUISITION", "REHABILITATION",
)


@router.get("/{property_id}/affordable-programs/{program_id}/buildings/{building_id}/8609-annual",
            response_model=list[Affordable8609AnnualOut])
def list_annual(
    property_id: int, program_id: int, building_id: int, response: Response,
    tax_year: int = Query(..., ge=1987, le=2100),
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    prop, building = _building(db, property_id=property_id, program_id=program_id,
                               building_id=building_id, user=current_user, write=False)
    response.headers["Cache-Control"] = "no-store"
    items = db.query(Affordable8609Annual).filter(
        Affordable8609Annual.organization_id == prop.organization_id,
        Affordable8609Annual.property_id == prop.id,
        Affordable8609Annual.program_id == program_id,
        Affordable8609Annual.building_id == building.id,
        Affordable8609Annual.tax_year == tax_year,
    ).all()
    saved = {item.allocation_category: item for item in items}
    return [
        Affordable8609AnnualOut(
            building_id=building.id, tax_year=tax_year, allocation_category=category,
            status=saved[category].status if category in saved else "NOT_RECORDED",
            updated_at=saved[category].updated_at if category in saved else None,
        )
        for category in CATEGORIES
    ]


@router.put("/{property_id}/affordable-programs/{program_id}/buildings/{building_id}/8609-annual",
            response_model=Affordable8609AnnualOut)
def save_annual(
    property_id: int, program_id: int, building_id: int,
    payload: Affordable8609AnnualIn,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    prop, building = _building(db, property_id=property_id, program_id=program_id,
                               building_id=building_id, user=current_user, write=True)
    row = db.query(Affordable8609Annual).filter(
        Affordable8609Annual.organization_id == prop.organization_id,
        Affordable8609Annual.property_id == prop.id,
        Affordable8609Annual.program_id == program_id,
        Affordable8609Annual.building_id == building.id,
        Affordable8609Annual.tax_year == payload.tax_year,
        Affordable8609Annual.allocation_category == payload.allocation_category,
    ).first()
    created = row is None
    previous = row.status if row else "NOT_RECORDED"
    if row is None:
        row = Affordable8609Annual(
            organization_id=prop.organization_id, property_id=prop.id,
            program_id=program_id, building_id=building.id,
            tax_year=payload.tax_year, allocation_category=payload.allocation_category,
        )
        db.add(row)
    row.status = payload.status
    row.updated_by_id = current_user.id
    try:
        db.flush()
        append_audit_log(
            db, organization_id=prop.organization_id, user_id=current_user.id,
            entity_type="affordable_8609_annual", entity_id=row.id,
            action="recorded" if created else "updated",
            old_value=None if created else {"status": previous},
            new_value={"building_id": building.id, "tax_year": payload.tax_year,
                       "allocation_category": payload.allocation_category,
                       "status": payload.status},
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Annual 8609-A reference changed concurrently.") from exc
    db.refresh(row)
    return Affordable8609AnnualOut.model_validate(row)
