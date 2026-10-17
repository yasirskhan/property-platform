"""Property-scoped staff ARC interest; no approval, legal filing, permit or fee."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.core.database import get_db
from app.models.hoa_arc_intake import HOAARCIntake
from app.models.user import User
from app.routers.auth import get_current_user
from app.routers.hoa_assessments import _scope
from app.schemas.hoa_arc_intake import HOAARCIntakeIn, HOAARCIntakeOut
from app.services.audit import append_audit_log
from app.services.hoa_arc_application_cleanup import archive_arc_applications

router = APIRouter(prefix="/api/hoa/associations", tags=["HOA staff architectural intake"])


def _row(db: Session, org_id: int, assoc_id: int, prop_id: int, intake_id: int) -> HOAARCIntake:
    row = db.query(HOAARCIntake).filter(
        HOAARCIntake.id == intake_id,
        HOAARCIntake.organization_id == org_id,
        HOAARCIntake.association_id == assoc_id,
        HOAARCIntake.property_id == prop_id,
        HOAARCIntake.is_active.is_(True),
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="ARC staff intake not found.")
    return row


def _out(row: HOAARCIntake) -> HOAARCIntakeOut:
    return HOAARCIntakeOut(
        id=row.id, association_id=row.association_id, property_id=row.property_id,
        project_title=row.project_title, staff_noted_on=row.staff_noted_on,
        staff_description=row.staff_description, updated_at=row.updated_at,
    )


@router.get("/{association_id}/arc-intakes", response_model=list[HOAARCIntakeOut])
def list_arc_intakes(
    association_id: int, response: Response, property_id: int = Query(ge=1),
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org_id, assoc = _scope(
        db, actor=current_user, association_id=association_id,
        property_id=property_id, write=False,
    )
    response.headers["Cache-Control"] = "no-store"
    rows = db.query(HOAARCIntake).filter(
        HOAARCIntake.organization_id == org_id,
        HOAARCIntake.association_id == assoc.id,
        HOAARCIntake.property_id == property_id,
        HOAARCIntake.is_active.is_(True),
    ).order_by(HOAARCIntake.id.asc()).limit(201).all()
    if len(rows) > 200:
        raise HTTPException(status_code=422, detail="Too many staff ARC intake records.")
    return [_out(row) for row in rows]


@router.post("/{association_id}/arc-intakes", response_model=HOAARCIntakeOut, status_code=201)
def create_arc_intake(
    association_id: int, payload: HOAARCIntakeIn,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org_id, assoc = _scope(
        db, actor=current_user, association_id=association_id,
        property_id=payload.property_id, write=True,
    )
    found = db.query(HOAARCIntake.id).filter(
        HOAARCIntake.organization_id == org_id,
        HOAARCIntake.association_id == assoc.id,
        HOAARCIntake.property_id == payload.property_id,
        HOAARCIntake.is_active.is_(True),
    ).limit(200).all()
    if len(found) >= 200:
        raise HTTPException(status_code=422, detail="Too many staff ARC intake records.")
    row = HOAARCIntake(
        organization_id=org_id, association_id=assoc.id,
        created_by_id=current_user.id, updated_by_id=current_user.id,
        **payload.model_dump(),
    )
    db.add(row)
    try:
        db.flush()
        append_audit_log(
            db, organization_id=org_id, user_id=current_user.id,
            entity_type="hoa_arc_intake", entity_id=row.id, action="staff_intake_recorded",
            new_value={"association_id": assoc.id, "property_id": row.property_id},
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="ARC staff intake changed concurrently.") from exc
    db.refresh(row)
    return _out(row)


@router.put("/{association_id}/arc-intakes/{intake_id}", response_model=HOAARCIntakeOut)
def update_arc_intake(
    association_id: int, intake_id: int, payload: HOAARCIntakeIn,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org_id, assoc = _scope(
        db, actor=current_user, association_id=association_id,
        property_id=payload.property_id, write=True,
    )
    row = _row(db, org_id, assoc.id, payload.property_id, intake_id)
    row.project_title = payload.project_title
    row.staff_noted_on = payload.staff_noted_on
    row.staff_description = payload.staff_description
    row.updated_by_id = current_user.id
    db.flush()
    append_audit_log(
        db, organization_id=org_id, user_id=current_user.id,
        entity_type="hoa_arc_intake", entity_id=row.id, action="staff_intake_updated",
        new_value={"association_id": assoc.id, "property_id": row.property_id},
    )
    db.commit()
    db.refresh(row)
    return _out(row)


@router.delete("/{association_id}/arc-intakes/{intake_id}", status_code=204)
def archive_arc_intake(
    association_id: int, intake_id: int, property_id: int,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org_id, assoc = _scope(
        db, actor=current_user, association_id=association_id,
        property_id=property_id, write=True,
    )
    row = _row(db, org_id, assoc.id, property_id, intake_id)
    row.is_active = False
    row.updated_by_id = current_user.id
    archive_arc_applications(
        db, organization_id=org_id, association_id=assoc.id,
        property_id=property_id, intake_id=row.id,
        actor_id=current_user.id, action="arc_intake_archived",
    )
    db.flush()
    append_audit_log(
        db, organization_id=org_id, user_id=current_user.id,
        entity_type="hoa_arc_intake", entity_id=row.id, action="staff_intake_archived",
        new_value={"association_id": assoc.id, "property_id": row.property_id},
    )
    db.commit()
    return Response(status_code=204, headers={"Cache-Control": "no-store"})
