"""Explicit draft HOA proposals; no issuance, owner liability, Charges or ledger posting."""
from __future__ import annotations

from calendar import monthrange
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.hoa_assessment import HOAAssessmentProposal
from app.models.hoa_member_assessment import HOAAssessmentDecision
from app.models.hoa_association import HOAPropertyMembership
from app.models.property import Property
from app.models.user import User
from app.routers.auth import get_current_user
from app.routers.hoa_associations import _access, _association, _visible
from app.schemas.hoa_assessment import (
    HOAAssessmentProposalIn, HOAAssessmentProposalOut,
    HOAAssessmentPreviewOccurrence, HOAAssessmentPreviewOut,
)
from app.services.audit import append_audit_log
from app.services.hoa_payer_cleanup import archive_payer_drafts

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
    if db.query(HOAAssessmentDecision.id).filter(
        HOAAssessmentDecision.organization_id == org_id,
        HOAAssessmentDecision.proposal_id == row.id,
    ).first() is not None:
        raise HTTPException(status_code=409, detail="Board-decided assessment cannot be edited; create a new proposal.")
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
    if db.query(HOAAssessmentDecision.id).filter(
        HOAAssessmentDecision.organization_id == org_id,
        HOAAssessmentDecision.proposal_id == row.id,
    ).first() is not None:
        raise HTTPException(status_code=409, detail="Board-decided assessment is immutable; corrections use the member ledger reversal.")
    archive_payer_drafts(
        db, organization_id=org_id, association_id=association.id,
        property_id=property_id, proposal_id=row.id,
        actor_id=current_user.id, action="assessment_draft_archived",
    )
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


def _proposed_calendar(
    proposal: HOAAssessmentProposal, date_from: date, date_to: date,
) -> list[HOAAssessmentPreviewOccurrence]:
    """Calculate a bounded, read-only schedule anchored to the original day.

    Preserve end-of-month anchors (Jan 31 -> Feb 28 -> Mar 31), and do
    not drift a monthly schedule after shorter months. No legal due date,
    payer, approval, Charge, RentInvoice or GL instruction is created.
    """
    if date_to < date_from or (date_to - date_from).days > 366 * 5:
        raise HTTPException(status_code=422, detail="Preview range must be 0-5 years.")
    anchor = proposal.proposed_first_on
    months = {"MONTHLY": 1, "QUARTERLY": 3, "ANNUAL": 12}
    if proposal.frequency == "ONE_TIME":
        return [
            HOAAssessmentPreviewOccurrence(
                proposed_on=anchor, proposed_amount=proposal.proposed_amount,
            )
        ] if date_from <= anchor <= date_to and (
            proposal.proposed_through is None or anchor <= proposal.proposed_through
        ) else []
    step = months.get(proposal.frequency)
    if step is None:
        raise HTTPException(status_code=422, detail="Unrecognized proposal recurrence.")
    origin_month = anchor.year * 12 + anchor.month - 1
    starting_month = date_from.year * 12 + date_from.month - 1
    # Skip far-past periods without iterating unbounded historical dates.
    first_index = max(0, (starting_month - origin_month) // step - 1)
    anchor_at_month_end = anchor.day == monthrange(anchor.year, anchor.month)[1]
    occurrences = []
    for index in range(first_index, first_index + 64):
        month_number = origin_month + index * step
        year, zero_month = divmod(month_number, 12)
        if year > 9999:
            break
        month = zero_month + 1
        final_day = monthrange(year, month)[1]
        occurrence = date(
            year, month, final_day if anchor_at_month_end else min(anchor.day, final_day),
        )
        if occurrence > date_to or (
            proposal.proposed_through is not None and occurrence > proposal.proposed_through
        ):
            break
        if occurrence >= anchor and occurrence >= date_from:
            occurrences.append(HOAAssessmentPreviewOccurrence(
                proposed_on=occurrence, proposed_amount=proposal.proposed_amount,
            ))
            if len(occurrences) > 62:
                raise HTTPException(status_code=422, detail="Preview has too many periods.")
    return occurrences


@router.get(
    "/{association_id}/draft-assessments/{proposal_id}/preview",
    response_model=HOAAssessmentPreviewOut,
)
def preview_proposal(
    association_id: int, proposal_id: int, response: Response,
    property_id: int = Query(ge=1),
    date_from: date = Query(),
    date_to: date = Query(),
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org_id, association = _scope(
        db, actor=current_user, association_id=association_id,
        property_id=property_id, write=False,
    )
    row = _record(
        db, org_id=org_id, association_id=association.id,
        property_id=property_id, proposal_id=proposal_id,
    )
    entries = _proposed_calendar(row, date_from, date_to)
    response.headers["Cache-Control"] = "no-store"
    return HOAAssessmentPreviewOut(
        proposal_id=row.id, property_id=property_id, frequency=row.frequency,
        occurrences=entries,
        proposed_total=sum((e.proposed_amount for e in entries), Decimal("0.00")),
    )
