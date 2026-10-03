"""Persist HOA staff planning occurrences, without creating a legal or accounting debt.

This module has NO imports of billing/posting services. Actual issuance
will require a separate authenticated authority, payer and GL contract.
"""
from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.hoa_planned_occurrence import HOAPlannedOccurrence
from app.models.hoa_member_assessment import HOAMemberAssessmentCharge
from app.models.hoa_payer_draft import HOAPayerDraft
from app.models.user import User
from app.routers.auth import get_current_user
from app.routers.hoa_assessments import _proposed_calendar, _record
from app.routers.hoa_associations import _contact_scope
from app.routers.hoa_board import _link
from app.schemas.hoa_planned_occurrence import (
    HOAPlanGenerationIn, HOAPlanGenerationOut, HOAPlannedOccurrenceOut,
)
from app.services.audit import append_audit_log

router = APIRouter(prefix="/api/hoa/associations", tags=["HOA unissued planning history"])


def _scope(db: Session, actor: User, association_id: int, property_id: int, proposal_id: int,
           *, write: bool):
    org, association = _contact_scope(
        db, actor=actor, association_id=association_id, property_id=property_id, write=write,
    )
    proposal = _record(
        db, org_id=org, association_id=association.id,
        property_id=property_id, proposal_id=proposal_id,
    )
    return org, association, proposal


def _payer(db: Session, org: int, association_id: int, property_id: int, proposal_id: int):
    row = db.query(HOAPayerDraft).filter(
        HOAPayerDraft.organization_id == org,
        HOAPayerDraft.association_id == association_id,
        HOAPayerDraft.property_id == property_id,
        HOAPayerDraft.proposal_id == proposal_id,
        HOAPayerDraft.is_active.is_(True),
    ).first()
    if row is None:
        raise HTTPException(status_code=409, detail="Active staff payer suggestion required.")
    # Recheck the live, same-scope contact link: no stale archived or foreign contact.
    _link(db, org, association_id, property_id, row.contact_link_id)
    return row


def _rows(db: Session, org: int, association_id: int, property_id: int, proposal_id: int):
    return db.query(HOAPlannedOccurrence).filter(
        HOAPlannedOccurrence.organization_id == org,
        HOAPlannedOccurrence.association_id == association_id,
        HOAPlannedOccurrence.property_id == property_id,
        HOAPlannedOccurrence.proposal_id == proposal_id,
    ).order_by(HOAPlannedOccurrence.proposed_on, HOAPlannedOccurrence.id)


def _out(row: HOAPlannedOccurrence, *, issued: bool = False) -> HOAPlannedOccurrenceOut:
    return HOAPlannedOccurrenceOut(
        id=row.id, proposal_id=row.proposal_id, property_id=row.property_id,
        payer_draft_id=row.payer_draft_id, proposed_on=row.proposed_on,
        proposed_amount=row.proposed_amount, proposal_revision_at=row.proposal_revision_at,
        status=row.status, created_at=row.created_at, voided_at=row.voided_at,
        is_issued=issued, is_receivable=issued, gl_posting_enabled=issued,
    )


@router.get("/{association_id}/draft-assessments/{proposal_id}/planned-occurrences",
            response_model=list[HOAPlannedOccurrenceOut])
def list_occurrences(
    association_id: int, proposal_id: int, response: Response,
    property_id: int = Query(ge=1),
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org, assoc, _ = _scope(db, current_user, association_id, property_id, proposal_id, write=False)
    rows = _rows(db, org, assoc.id, property_id, proposal_id).limit(501).all()
    if len(rows) > 500:
        raise HTTPException(status_code=422, detail="Too many historical planning records.")
    ids = [row.id for row in rows]
    issued_ids = {ident for (ident,) in db.query(HOAMemberAssessmentCharge.occurrence_id).filter(
        HOAMemberAssessmentCharge.organization_id == org,
        HOAMemberAssessmentCharge.association_id == assoc.id,
        HOAMemberAssessmentCharge.property_id == property_id,
        HOAMemberAssessmentCharge.occurrence_id.in_(ids),
    ).all()} if ids else set()
    response.headers["Cache-Control"] = "no-store"
    return [_out(row, issued=row.id in issued_ids) for row in rows]


@router.post("/{association_id}/draft-assessments/{proposal_id}/planned-occurrences/generate",
             response_model=HOAPlanGenerationOut)
def generate_occurrences(
    association_id: int, proposal_id: int, payload: HOAPlanGenerationIn,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org, assoc, proposal = _scope(
        db, current_user, association_id, payload.property_id, proposal_id, write=True,
    )
    payer = _payer(db, org, assoc.id, payload.property_id, proposal.id)
    suggested = _proposed_calendar(proposal, payload.date_from, payload.date_to)
    if not suggested:
        return HOAPlanGenerationOut(rows=[], new_count=0, existing_count=0)
    # The two-level uniqueness ensures replay cannot duplicate a period, including
    # a previously VOIDED period, even after a proposal amount revision.
    dates = [entry.proposed_on for entry in suggested]
    existing = {
        row.proposed_on: row for row in _rows(
            db, org, assoc.id, payload.property_id, proposal.id,
        ).filter(HOAPlannedOccurrence.proposed_on.in_(dates)).all()
    }
    if len(existing) != len(set(existing)):
        raise HTTPException(status_code=409, detail="Planning history conflict.")
    new_rows = []
    for occurrence in suggested:
        if occurrence.proposed_on in existing:
            continue
        item = HOAPlannedOccurrence(
            organization_id=org, association_id=assoc.id, property_id=payload.property_id,
            proposal_id=proposal.id, payer_draft_id=payer.id,
            proposed_on=occurrence.proposed_on, proposed_amount=occurrence.proposed_amount,
            proposal_revision_at=proposal.updated_at, status="PLANNED",
            created_by_id=current_user.id,
        )
        db.add(item)
        new_rows.append(item)
    try:
        db.flush()
        for row in new_rows:
            append_audit_log(
                db, organization_id=org, user_id=current_user.id,
                entity_type="hoa_planned_occurrence", entity_id=row.id,
                action="staff_plan_generated",
                new_value={"association_id": assoc.id, "property_id": payload.property_id,
                           "proposal_id": proposal.id, "proposed_on": row.proposed_on.isoformat()},
            )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Concurrent schedule generation; refresh history.") from exc
    for row in new_rows:
        db.refresh(row)
        existing[row.proposed_on] = row
    return HOAPlanGenerationOut(
        rows=[_out(existing[day]) for day in dates],
        new_count=len(new_rows), existing_count=len(suggested) - len(new_rows),
    )


@router.post("/{association_id}/draft-assessments/{proposal_id}/planned-occurrences/{occurrence_id}/void",
             response_model=HOAPlannedOccurrenceOut)
def void_occurrence(
    association_id: int, proposal_id: int, occurrence_id: int,
    property_id: int = Query(ge=1),
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org, assoc, proposal = _scope(
        db, current_user, association_id, property_id, proposal_id, write=True,
    )
    row = _rows(db, org, assoc.id, property_id, proposal.id).filter(
        HOAPlannedOccurrence.id == occurrence_id,
    ).with_for_update().first()
    if row is None:
        raise HTTPException(status_code=404, detail="Planning record not found.")
    if row.status != "PLANNED":
        raise HTTPException(status_code=409, detail="Planning record already voided.")
    # A posted member receivable must never become a voided planning
    # record. Coordinate with issue_assessment's occurrence row lock.
    issued = db.query(HOAMemberAssessmentCharge.id).filter(
        HOAMemberAssessmentCharge.organization_id == org,
        HOAMemberAssessmentCharge.association_id == assoc.id,
        HOAMemberAssessmentCharge.property_id == property_id,
        HOAMemberAssessmentCharge.occurrence_id == row.id,
    ).first()
    if issued is not None:
        raise HTTPException(status_code=409, detail="Issued member assessments cannot be voided.")
    row.status = "VOIDED"
    row.voided_at = datetime.utcnow()
    row.voided_by_id = current_user.id
    db.flush()
    append_audit_log(
        db, organization_id=org, user_id=current_user.id,
        entity_type="hoa_planned_occurrence", entity_id=row.id,
        action="staff_plan_voided",
        new_value={"association_id": assoc.id, "property_id": property_id,
                   "proposal_id": proposal.id, "proposed_on": row.proposed_on.isoformat()},
    )
    db.commit()
    db.refresh(row)
    return _out(row)
