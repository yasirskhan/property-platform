"""Staff-only compliance evidence index: never eligibility, certification or approval."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Response, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.affordable_evidence import AffordableEvidence
from app.models.user import User
from app.routers.auth import get_current_user
from app.routers.affordable_programs import _property, _item
from app.schemas.affordable_evidence import AffordableEvidenceIn, AffordableEvidenceOut
from app.services.audit import append_audit_log

router = APIRouter(prefix="/api/properties", tags=["Affordable evidence readiness"])
CATEGORIES = ("AGENCY_GUIDANCE", "PROGRAM_AGREEMENT", "PROPERTY_RECORD_INDEX", "INSPECTION_COORDINATION")


@router.get("/{property_id}/affordable-programs/{program_id}/evidence",
            response_model=list[AffordableEvidenceOut])
def list_evidence(
    property_id: int, program_id: int, response: Response,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    prop = _property(db, property_id=property_id, actor=current_user, write=False)
    program = _item(db, org_id=prop.organization_id, prop_id=prop.id, item_id=program_id)
    response.headers["Cache-Control"] = "no-store"
    records = db.query(AffordableEvidence).filter(
        AffordableEvidence.organization_id == prop.organization_id,
        AffordableEvidence.program_id == program.id,
    ).all()
    saved = {row.category: row for row in records}
    return [
        AffordableEvidenceOut(
            category=key,
            status=saved[key].status if key in saved else "NOT_RECORDED",
            staff_follow_up_on=saved[key].staff_follow_up_on if key in saved else None,
            updated_at=saved[key].updated_at if key in saved else None,
        )
        for key in CATEGORIES
    ]


@router.put("/{property_id}/affordable-programs/{program_id}/evidence",
            response_model=AffordableEvidenceOut)
def save_evidence(
    property_id: int, program_id: int, payload: AffordableEvidenceIn,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    prop = _property(db, property_id=property_id, actor=current_user, write=True)
    program = _item(db, org_id=prop.organization_id, prop_id=prop.id, item_id=program_id)
    # Fixed enum-only values: no unencrypted document bodies, household details,
    # self-certification, legal deadline or arbitrary user-entered reference.
    row = db.query(AffordableEvidence).filter(
        AffordableEvidence.organization_id == prop.organization_id,
        AffordableEvidence.program_id == program.id,
        AffordableEvidence.category == payload.category,
    ).first()
    created = row is None
    if row is None:
        row = AffordableEvidence(
            organization_id=prop.organization_id, program_id=program.id,
            category=payload.category,
        )
        db.add(row)
    previous = None if created else row.status
    row.status = payload.status
    row.staff_follow_up_on = payload.staff_follow_up_on
    row.updated_by_id = current_user.id
    try:
        db.flush()
        append_audit_log(
            db, organization_id=prop.organization_id, user_id=current_user.id,
            entity_type="affordable_evidence", entity_id=row.id,
            action="created" if created else "updated",
            old_value=None if created else {"status": previous},
            new_value={"program_id": program.id, "category": payload.category,
                       "status": payload.status},
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Evidence readiness was updated concurrently.") from exc
    db.refresh(row)
    return AffordableEvidenceOut.model_validate(row)
