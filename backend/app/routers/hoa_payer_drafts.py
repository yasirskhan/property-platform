"""Staff-only suggested HOA dues payer. No legal liability or tenant charge."""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.hoa_payer_draft import HOAPayerDraft
from app.models.user import User
from app.routers.auth import get_current_user
from app.routers.hoa_associations import _contact_scope
from app.routers.hoa_assessments import _record
from app.routers.hoa_board import _link
from app.schemas.hoa_payer_draft import HOAPayerDraftIn, HOAPayerDraftOut
from app.services.audit import append_audit_log

router = APIRouter(prefix="/api/hoa/associations", tags=["HOA payer planning only"])


def _row(db: Session, org: int, assoc: int, prop: int, proposal: int):
    return db.query(HOAPayerDraft).filter(
        HOAPayerDraft.organization_id == org,
        HOAPayerDraft.association_id == assoc,
        HOAPayerDraft.property_id == prop,
        HOAPayerDraft.proposal_id == proposal,
    ).first()


def _out(row: HOAPayerDraft, name: str) -> HOAPayerDraftOut:
    return HOAPayerDraftOut(
        id=row.id, proposal_id=row.proposal_id,
        property_id=row.property_id, contact_link_id=row.contact_link_id,
        contact_name=name,
    )


def _audit(db: Session, user: User, row: HOAPayerDraft, action: str) -> None:
    append_audit_log(
        db, organization_id=row.organization_id, user_id=user.id,
        entity_type="hoa_payer_draft", entity_id=row.id, action=action,
        new_value={"association_id": row.association_id,
                   "property_id": row.property_id,
                   "proposal_id": row.proposal_id},
    )


@router.get("/{association_id}/draft-assessments/{proposal_id}/payer-draft",
            response_model=HOAPayerDraftOut | None)
def get_payer_draft(
    association_id: int, proposal_id: int, response: Response,
    property_id: int = Query(ge=1),
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org, assoc = _contact_scope(
        db, actor=current_user, association_id=association_id,
        property_id=property_id, write=False,
    )
    _record(db, org_id=org, association_id=assoc.id,
            property_id=property_id, proposal_id=proposal_id)
    response.headers["Cache-Control"] = "no-store"
    row = _row(db, org, assoc.id, property_id, proposal_id)
    if row is None or not row.is_active:
        return None
    try:
        _link(db, org, assoc.id, property_id, row.contact_link_id)
    except HTTPException:
        return None
    _, contact = _link(db, org, assoc.id, property_id, row.contact_link_id)
    return _out(row, contact)


@router.put("/{association_id}/draft-assessments/{proposal_id}/payer-draft",
            response_model=HOAPayerDraftOut)
def set_payer_draft(
    association_id: int, proposal_id: int, payload: HOAPayerDraftIn,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org, assoc = _contact_scope(
        db, actor=current_user, association_id=association_id,
        property_id=payload.property_id, write=True,
    )
    _record(db, org_id=org, association_id=assoc.id,
            property_id=payload.property_id, proposal_id=proposal_id)
    _, contact = _link(db, org, assoc.id, payload.property_id,
                       payload.contact_link_id)
    row = _row(db, org, assoc.id, payload.property_id, proposal_id)
    if row is not None and not row.is_active:
        raise HTTPException(status_code=409, detail="Archived payer draft cannot be resurrected.")
    created = row is None
    if created:
        row = HOAPayerDraft(
            organization_id=org, association_id=assoc.id,
            property_id=payload.property_id, proposal_id=proposal_id,
            created_by_id=current_user.id,
        )
        db.add(row)
    row.contact_link_id = payload.contact_link_id
    row.updated_by_id = current_user.id
    try:
        db.flush()
        _audit(db, current_user, row,
               "staff_payer_suggested" if created else "staff_payer_revised")
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Payer draft changed concurrently.") from exc
    db.refresh(row)
    return _out(row, contact)


@router.delete("/{association_id}/draft-assessments/{proposal_id}/payer-draft",
               status_code=204)
def archive_payer_draft(
    association_id: int, proposal_id: int, property_id: int = Query(ge=1),
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org, assoc = _contact_scope(
        db, actor=current_user, association_id=association_id,
        property_id=property_id, write=True,
    )
    _record(db, org_id=org, association_id=assoc.id,
            property_id=property_id, proposal_id=proposal_id)
    row = _row(db, org, assoc.id, property_id, proposal_id)
    if row is None or not row.is_active:
        raise HTTPException(status_code=404, detail="Payer draft not found.")
    row.is_active = False
    row.updated_by_id = current_user.id
    db.flush()
    _audit(db, current_user, row, "staff_payer_archived")
    db.commit()
    return Response(status_code=204, headers={"Cache-Control": "no-store"})
