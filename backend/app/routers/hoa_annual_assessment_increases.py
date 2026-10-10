"""Turn an approved HOA annual budget into an explicit NEW assessment proposal.

The budget does not itself assess a member. The NEW proposal requires
its own association board decision, payer confirmation, planned occurrence
and separately authorized central GL issuance.
"""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.hoa_annual_assessment_increase import HOAAnnualAssessmentIncrease
from app.models.hoa_assessment import HOAAssessmentProposal
from app.models.hoa_member_assessment import HOAAssessmentDecision, HOAMemberAssessmentCharge
from app.models.hoa_payer_draft import HOAPayerDraft
from app.models.user import User
from app.routers.auth import get_current_user
from app.routers.hoa_annual_budgets import _budget
from app.routers.hoa_arc_applications import _contact_link
from app.routers.hoa_arc_board_decisions import _verified_member
from app.routers.hoa_member_assessments import _accountant
from app.schemas.hoa_annual_assessment_increase import (
    HOAIncreaseCreateIn, HOAIncreaseOut, HOAIncreaseSourceOut,
)
from app.services.audit import append_audit_log

router = APIRouter(prefix="/api/hoa/associations", tags=["HOA annual assessment increase"])


def _prior(db: Session, *, org: int, association_id: int, property_id: int,
           charge_id: int, lock: bool = False):
    q = db.query(
        HOAMemberAssessmentCharge, HOAAssessmentDecision, HOAAssessmentProposal,
    ).join(
        HOAAssessmentDecision,
        HOAAssessmentDecision.id == HOAMemberAssessmentCharge.decision_id,
    ).join(
        HOAAssessmentProposal,
        HOAAssessmentProposal.id == HOAAssessmentDecision.proposal_id,
    ).filter(
        HOAMemberAssessmentCharge.id == charge_id,
        HOAMemberAssessmentCharge.organization_id == org,
        HOAMemberAssessmentCharge.association_id == association_id,
        HOAMemberAssessmentCharge.property_id == property_id,
        HOAMemberAssessmentCharge.status.in_(("OPEN", "PAID")),
        HOAAssessmentDecision.organization_id == org,
        HOAAssessmentDecision.association_id == association_id,
        HOAAssessmentDecision.property_id == property_id,
        HOAAssessmentDecision.decision == "APPROVED",
        HOAAssessmentProposal.organization_id == org,
        HOAAssessmentProposal.association_id == association_id,
        HOAAssessmentProposal.property_id == property_id,
        HOAAssessmentProposal.assessment_type == "RECURRING",
        HOAAssessmentProposal.is_active.is_(True),
    )
    found = (q.with_for_update() if lock else q).first()
    if found is None:
        raise HTTPException(status_code=404, detail="Eligible posted recurring assessment not found.")
    return found


def _out(row: HOAAnnualAssessmentIncrease) -> HOAIncreaseOut:
    return HOAIncreaseOut(
        id=row.id, budget_id=row.budget_id,
        source_charge_id=row.source_charge_id,
        proposal_id=row.proposal_id, member_user_id=row.member_user_id,
        previous_amount=row.previous_amount, proposed_amount=row.proposed_amount,
        effective_on=row.effective_on,
    )


@router.get("/{association_id}/annual-budgets/{budget_id}/increase-sources",
            response_model=list[HOAIncreaseSourceOut])
def increase_sources(
    association_id: int, budget_id: int, response: Response,
    property_id: int = Query(ge=1),
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org, assoc = _accountant(
        db, actor=current_user, assoc=association_id, prop=property_id,
    )
    budget = _budget(
        db, org=org, association_id=assoc.id,
        property_id=property_id, budget_id=budget_id,
    )
    if budget.status != "APPROVED":
        raise HTTPException(status_code=409, detail="Board-approved annual budget required.")
    q = db.query(
        HOAMemberAssessmentCharge, HOAAssessmentDecision, HOAAssessmentProposal,
    ).join(
        HOAAssessmentDecision,
        HOAAssessmentDecision.id == HOAMemberAssessmentCharge.decision_id,
    ).join(
        HOAAssessmentProposal,
        HOAAssessmentProposal.id == HOAAssessmentDecision.proposal_id,
    ).filter(
        HOAMemberAssessmentCharge.organization_id == org,
        HOAMemberAssessmentCharge.association_id == assoc.id,
        HOAMemberAssessmentCharge.property_id == property_id,
        HOAMemberAssessmentCharge.status.in_(("OPEN", "PAID")),
        HOAAssessmentDecision.organization_id == org,
        HOAAssessmentDecision.association_id == assoc.id,
        HOAAssessmentDecision.property_id == property_id,
        HOAAssessmentDecision.decision == "APPROVED",
        HOAAssessmentProposal.organization_id == org,
        HOAAssessmentProposal.association_id == assoc.id,
        HOAAssessmentProposal.property_id == property_id,
        HOAAssessmentProposal.assessment_type == "RECURRING",
        HOAAssessmentProposal.is_active.is_(True),
        HOAAssessmentProposal.proposed_first_on < date(budget.calendar_year, 1, 1),
    ).order_by(HOAMemberAssessmentCharge.id.desc()).limit(501).all()
    if len(q) > 500:
        raise HTTPException(status_code=422, detail="Too many source assessments.")
    response.headers["Cache-Control"] = "no-store"
    return [HOAIncreaseSourceOut(
        charge_id=c.id, member_user_id=c.member_user_id, proposal_id=p.id,
        previous_amount=c.amount, frequency=p.frequency,
    ) for c, d, p in q if p.proposed_first_on.year < budget.calendar_year]


@router.get("/{association_id}/annual-budgets/{budget_id}/increases",
            response_model=list[HOAIncreaseOut])
def list_increases(
    association_id: int, budget_id: int, response: Response,
    property_id: int = Query(ge=1),
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org, assoc = _accountant(
        db, actor=current_user, assoc=association_id, prop=property_id,
    )
    _budget(db, org=org, association_id=assoc.id,
            property_id=property_id, budget_id=budget_id)
    rows = db.query(HOAAnnualAssessmentIncrease).filter(
        HOAAnnualAssessmentIncrease.organization_id == org,
        HOAAnnualAssessmentIncrease.association_id == assoc.id,
        HOAAnnualAssessmentIncrease.property_id == property_id,
        HOAAnnualAssessmentIncrease.budget_id == budget_id,
    ).order_by(HOAAnnualAssessmentIncrease.id).limit(501).all()
    if len(rows) > 500:
        raise HTTPException(status_code=422, detail="Too many recorded increase links.")
    response.headers["Cache-Control"] = "no-store"
    return [_out(row) for row in rows]


@router.post("/{association_id}/annual-budgets/{budget_id}/increases",
             response_model=HOAIncreaseOut, status_code=201)
def propose_increase(
    association_id: int, budget_id: int, payload: HOAIncreaseCreateIn,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org, assoc = _accountant(
        db, actor=current_user, assoc=association_id, prop=payload.property_id,
    )
    budget = _budget(
        db, org=org, association_id=assoc.id, property_id=payload.property_id,
        budget_id=budget_id, lock=True,
    )
    if budget.status != "APPROVED":
        raise HTTPException(status_code=409, detail="Board-approved annual budget required.")
    if payload.effective_on.year != budget.calendar_year:
        raise HTTPException(status_code=422, detail="Increase start must fall within the approved budget year.")
    prior, decision, proposal = _prior(
        db, org=org, association_id=assoc.id, property_id=payload.property_id,
        charge_id=payload.source_charge_id, lock=True,
    )
    if proposal.proposed_first_on.year >= budget.calendar_year:
        raise HTTPException(status_code=409, detail="Increase requires a previously adopted recurring assessment.")
    if payload.proposed_amount <= prior.amount:
        raise HTTPException(status_code=422, detail="Increased member amount must exceed the previously issued amount.")
    link, contact = _contact_link(
        db, org_id=org, association_id=assoc.id,
        property_id=payload.property_id, link_id=prior.contact_link_id,
    )
    member = _verified_member(db, org=org, contact=contact)
    if member is None or member.id != prior.member_user_id or decision.member_user_id != prior.member_user_id:
        raise HTTPException(status_code=409, detail="Prior responsible member identity is no longer verified.")
    existing = db.query(HOAAnnualAssessmentIncrease).filter(
        HOAAnnualAssessmentIncrease.budget_id == budget.id,
        HOAAnnualAssessmentIncrease.source_charge_id == prior.id,
    ).first()
    if existing is not None:
        stored_proposal = db.get(HOAAssessmentProposal, existing.proposal_id)
        if (stored_proposal is not None and stored_proposal.is_active
                and stored_proposal.title == payload.title
                and existing.proposed_amount == payload.proposed_amount
                and existing.effective_on == payload.effective_on):
            return _out(existing)
        raise HTTPException(status_code=409, detail="Increase already recorded for this annual budget and assessment.")
    if db.query(HOAAssessmentProposal.id).filter(
        HOAAssessmentProposal.organization_id == org,
        HOAAssessmentProposal.association_id == assoc.id,
        HOAAssessmentProposal.property_id == payload.property_id,
        HOAAssessmentProposal.is_active.is_(True),
    ).limit(201).count() >= 200:
        raise HTTPException(status_code=422, detail="Too many assessment proposals.")
    # New proposal plus payer reference are atomic with the provenance link.
    # Nothing is automatically approved or posted.
    next_proposal = HOAAssessmentProposal(
        organization_id=org, association_id=assoc.id,
        property_id=payload.property_id, title=payload.title,
        assessment_type="RECURRING", frequency=proposal.frequency,
        proposed_amount=payload.proposed_amount,
        proposed_first_on=payload.effective_on, proposed_through=None,
        is_active=True, created_by_id=current_user.id, updated_by_id=current_user.id,
    )
    db.add(next_proposal)
    try:
        db.flush()
        db.add(HOAPayerDraft(
            organization_id=org, association_id=assoc.id,
            property_id=payload.property_id, proposal_id=next_proposal.id,
            contact_link_id=link.id, is_active=True,
            created_by_id=current_user.id, updated_by_id=current_user.id,
        ))
        entry = HOAAnnualAssessmentIncrease(
            organization_id=org, association_id=assoc.id,
            property_id=payload.property_id, budget_id=budget.id,
            source_charge_id=prior.id, proposal_id=next_proposal.id,
            member_user_id=member.id, previous_amount=prior.amount,
            proposed_amount=payload.proposed_amount,
            effective_on=payload.effective_on, created_by_id=current_user.id,
        )
        db.add(entry)
        db.flush()
        append_audit_log(
            db, organization_id=org, user_id=current_user.id,
            entity_type="hoa_annual_assessment_increase", entity_id=entry.id,
            action="budget_linked_increase_proposed",
            new_value={"association_id":assoc.id,"property_id":payload.property_id,
                       "budget_id":budget.id,"source_charge_id":prior.id,
                       "proposal_id":next_proposal.id,"member_user_id":member.id},
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Concurrent or duplicate annual increase proposal.") from exc
    db.refresh(entry)
    return _out(entry)
