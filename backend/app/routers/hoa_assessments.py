"""Explicit draft HOA proposals; no issuance, owner liability, Charges or ledger posting."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.hoa_assessment import HOAAssessmentProposal
from app.models.hoa_association import HOAPropertyMembership
from app.models.property import Property
from app.models.user import User
from app.routers.auth import get_current_user
from app.routers.hoa_associations import _access, _association, _visible
from app.schemas.hoa_assessment import HOAAssessmentProposalIn, HOAAssessmentProposalOut
from app.services.audit import append_audit_log

router = APIRouter(prefix="/api/hoa/associations", tags=["HOA staff assessment proposals"])


def _scope(db: Session, *, actor: User, association_id: int, property_id: int, write: bool):
    org_id = _access(db, actor, write=write)
    association = _association(db, org_id=org_id, association_id=association_id)
    property_found = _visible(db, org_id=org_id, actor=actor).filter(
        Property.id == property_id,
    ).first()
    if property_found is None:
        raise HTTPException(status_code=404, detail="Association property not found.")
    linked = db.query(HOAPropertyMembership.id).filter(
        HOAPropertyMembership.organization_id == org_id,
        HOAPropertyMembership.association_id == association.id,
        HOAPropertyMembership.property_id == property_found.id,
    ).first()
    if linked is None:
        raise HTTPException(status_code=404, detail="Association property not found.")
    return org_id, association


def _record(db: Session, *, org_id: int, association_id: int, property_id: int, proposal_id: int):
    row = db.query(HOAAssessmentProposal).filter(
        HOAAssessmentProposal.id == proposal_id,
        HOAAssessmentProposal.organization_id == org_id,
        HOAAssessmentProposal.association_id == association_id,
        HOAAssessmentProposal.property_id == property_id,
        HOAAssessmentProposal.is_active.is_(True),
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Draft proposal not found.")
    return row


def _out(row: HOAAssessmentProposal) -> HOAAssessmentProposalOut:
    return HOAAssessmentProposalOut(
        id=row.id, association_id=row.association_id,
        property_id=row.property_id, title=row.title,
        assessment_type=row.assessment_type, frequency=row.frequency,
        proposed_amount=row.proposed_amount,
        proposed_first_on=row.proposed_first_on,
        proposed_through=row.proposed_through,
        updated_at=row.updated_at,
    )


@router.get("/{association_id}/draft-assessments", response_model=list[HOAAssessmentProposalOut])
def list_proposals(
    association_id: int, response: Response,
    property_id: int = Query(ge=1),
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org_id, association = _scope(
        db, actor=current_user, association_id=association_id,
        property_id=property_id, write=False,
    )
    response.headers["Cache-Control"] = "no-store"
    rows = db.query(HOAAssessmentProposal).filter(
        HOAAssessmentProposal.organization_id == org_id,
        HOAAssessmentProposal.association_id == association.id,
        HOAAssessmentProposal.property_id == property_id,
        HOAAssessmentProposal.is_active.is_(True),
    ).order_by(HOAAssessmentProposal.id.asc()).limit(201).all()
    if len(rows) > 200:
        raise HTTPException(status_code=422, detail="Too many draft proposals for one property.")
    return [_out(row) for row in rows]


@router.post("/{association_id}/draft-assessments", response_model=HOAAssessmentProposalOut, status_code=201)
def create_proposal(
    association_id: int, payload: HOAAssessmentProposalIn,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org_id, association = _scope(
        db, actor=current_user, association_id=association_id,
        property_id=payload.property_id, write=True,
    )
    count = db.query(HOAAssessmentProposal.id).filter(
        HOAAssessmentProposal.organization_id == org_id,
        HOAAssessmentProposal.association_id == association.id,
        HOAAssessmentProposal.property_id == payload.property_id,
        HOAAssessmentProposal.is_active.is_(True),
    ).limit(201).all()
    if len(count) >= 200:
        raise HTTPException(status_code=422, detail="Too many draft proposals for one property.")
    row = HOAAssessmentProposal(
        organization_id=org_id, association_id=association.id,
        created_by_id=current_user.id,
        **payload.model_dump(),
        updated_by_id=current_user.id,
    )
    db.add(row)
    try:
        db.flush()
        append_audit_log(
            db, organization_id=org_id, user_id=current_user.id,
            entity_type="hoa_assessment_proposal", entity_id=row.id,
            action="draft_created",
            new_value={"association_id": association.id, "property_id": row.property_id,
                       "kind": row.assessment_type},
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Proposal changed concurrently.") from exc
    db.refresh(row)
    return _out(row)


@router.put("/{association_id}/draft-assessments/{proposal_id}", response_model=HOAAssessmentProposalOut)
def update_proposal(
    association_id: int, proposal_id: int, payload: HOAAssessmentProposalIn,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org_id, association = _scope(
        db, actor=current_user, association_id=association_id,
        property_id=payload.property_id, write=True,
    )
    row = _record(db, org_id=org_id, association_id=association.id,
                  property_id=payload.property_id, proposal_id=proposal_id)
    for key, value in payload.model_dump().items():
        setattr(row, key, value)
    row.updated_by_id = current_user.id
    db.flush()
    append_audit_log(
        db, organization_id=org_id, user_id=current_user.id,
        entity_type="hoa_assessment_proposal", entity_id=row.id,
        action="draft_updated",
        new_value={"association_id": association.id, "property_id": row.property_id,
                   "kind": row.assessment_type},
    )
    db.commit()
    db.refresh(row)
    return _out(row)


@router.delete("/{association_id}/draft-assessments/{proposal_id}", status_code=204)
def archive_proposal(
    association_id: int, proposal_id: int, property_id: int,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org_id, association = _scope(
        db, actor=current_user, association_id=association_id,
        property_id=property_id, write=True,
    )
    row = _record(db, org_id=org_id, association_id=association.id,
                  property_id=property_id, proposal_id=proposal_id)
    row.is_active = False
    row.updated_by_id = current_user.id
    db.flush()
    append_audit_log(
        db, organization_id=org_id, user_id=current_user.id,
        entity_type="hoa_assessment_proposal", entity_id=row.id,
        action="draft_archived",
        new_value={"association_id": association.id, "property_id": property_id},
    )
    db.commit()
    return Response(status_code=204, headers={"Cache-Control": "no-store"})
