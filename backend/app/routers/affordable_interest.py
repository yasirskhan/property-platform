"""Staff-recorded links to existing CRM prospects; NOT a ranked official waitlist."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.affordable_interest import AffordableInterest
from app.models.contact import Contact
from app.models.prospect import Prospect
from app.models.user import User
from app.routers.auth import get_current_user
from app.routers.affordable_programs import _property, _item
from app.routers.prospects import _access as crm_access, _row as crm_prospect
from app.schemas.affordable_interest import AffordableInterestIn, AffordableInterestOut
from app.services.audit import append_audit_log

router = APIRouter(prefix="/api/properties", tags=["Affordable prospect interest"])


def _scope(db: Session, *, property_id: int, program_id: int, actor: User, write: bool):
    prop = _property(db, property_id=property_id, actor=actor, write=write)
    crm_org = crm_access(db, actor)
    if crm_org != prop.organization_id:
        raise HTTPException(status_code=403, detail="CRM permission required.")
    program = _item(db, org_id=prop.organization_id, prop_id=prop.id, item_id=program_id)
    return prop, program


def _prospect(db: Session, *, actor: User, org_id: int, property_id: int, prospect_id: int) -> Prospect:
    prospect = crm_prospect(db, org_id, actor, prospect_id)
    if prospect.property_id != property_id:
        raise HTTPException(status_code=404, detail="Prospect not found.")
    return prospect


def _row_out(row: AffordableInterest, contact_name: str) -> AffordableInterestOut:
    return AffordableInterestOut(
        id=row.id, program_id=row.program_id, prospect_id=row.prospect_id,
        contact_name=contact_name, recorded_at=row.recorded_at,
    )


@router.get("/{property_id}/affordable-programs/{program_id}/interest", response_model=list[AffordableInterestOut])
def list_interest(
    property_id: int, program_id: int, response: Response,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    prop, program = _scope(db, property_id=property_id, program_id=program_id,
                           actor=current_user, write=False)
    response.headers["Cache-Control"] = "no-store"
    # Join the current authorized property+prospect+contact relationships; a
    # stale or archived CRM entry must not leak a name through this table.
    rows = (
        db.query(AffordableInterest, Contact.display_name)
        .join(Prospect, Prospect.id == AffordableInterest.prospect_id)
        .join(Contact, Contact.id == Prospect.contact_id)
        .filter(
            AffordableInterest.organization_id == prop.organization_id,
            AffordableInterest.program_id == program.id,
            AffordableInterest.is_active.is_(True),
            Prospect.organization_id == prop.organization_id,
            Prospect.property_id == prop.id,
            Prospect.is_active.is_(True),
            Contact.organization_id == prop.organization_id,
            Contact.is_active.is_(True),
            Contact.deleted_at.is_(None),
        )
        .order_by(AffordableInterest.id)
        .limit(201)
        .all()
    )
    if len(rows) > 200:
        raise HTTPException(status_code=422, detail="Interest list is too large for preview.")
    return [_row_out(row, name) for row, name in rows]


@router.post("/{property_id}/affordable-programs/{program_id}/interest", response_model=AffordableInterestOut, status_code=201)
def record_interest(
    property_id: int, program_id: int, payload: AffordableInterestIn,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    prop, program = _scope(db, property_id=property_id, program_id=program_id,
                           actor=current_user, write=True)
    prospect = _prospect(
        db, actor=current_user, org_id=prop.organization_id,
        property_id=prop.id, prospect_id=payload.prospect_id,
    )
    current = db.query(AffordableInterest).filter(
        AffordableInterest.organization_id == prop.organization_id,
        AffordableInterest.program_id == program.id,
        AffordableInterest.prospect_id == prospect.id,
    ).first()
    if current is not None:
        raise HTTPException(status_code=409, detail="Prospect interest already recorded for program.")
    row = AffordableInterest(
        organization_id=prop.organization_id, program_id=program.id,
        prospect_id=prospect.id, recorded_by_id=current_user.id,
        updated_by_id=current_user.id,
    )
    db.add(row)
    try:
        db.flush()
        append_audit_log(
            db, organization_id=prop.organization_id, user_id=current_user.id,
            entity_type="affordable_program_interest", entity_id=row.id,
            action="recorded", new_value={"program_id": program.id, "prospect_id": prospect.id},
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Prospect interest already recorded for program.") from exc
    db.refresh(row)
    # Current CRM scope is rechecked on each call, never rely on the submitted
    # contact name or an id from a foreign property.
    contact = db.query(Contact).filter(
        Contact.id == prospect.contact_id, Contact.organization_id == prop.organization_id,
        Contact.is_active.is_(True), Contact.deleted_at.is_(None),
    ).first()
    if contact is None:
        raise HTTPException(status_code=404, detail="Contact not found.")
    return _row_out(row, contact.display_name)


@router.delete("/{property_id}/affordable-programs/{program_id}/interest/{interest_id}", status_code=204)
def archive_interest(
    property_id: int, program_id: int, interest_id: int,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    prop, program = _scope(db, property_id=property_id, program_id=program_id,
                           actor=current_user, write=True)
    row = db.query(AffordableInterest).filter(
        AffordableInterest.id == interest_id,
        AffordableInterest.organization_id == prop.organization_id,
        AffordableInterest.program_id == program.id,
        AffordableInterest.is_active.is_(True),
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Interest record not found.")
    _prospect(db, actor=current_user, org_id=prop.organization_id,
              property_id=prop.id, prospect_id=row.prospect_id)
    row.is_active = False
    row.updated_by_id = current_user.id
    db.flush()
    append_audit_log(
        db, organization_id=prop.organization_id, user_id=current_user.id,
        entity_type="affordable_program_interest", entity_id=row.id,
        action="archived", new_value={"program_id": program.id, "prospect_id": row.prospect_id},
    )
    db.commit()
    return Response(status_code=204)
