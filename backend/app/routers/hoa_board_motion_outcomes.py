"""Record an association board's final choice on an exact authenticated tally.

An authorized board member expressly finalizes the vote register using
adopted organization-provided thresholds. The platform does not invent
quorum rules, automatically declare legal compliance or create charges.
"""
from __future__ import annotations

from collections import Counter
from datetime import date
from hashlib import sha256

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.hoa_board_motion_outcome import HOABoardMotionOutcome
from app.models.hoa_board_rule_adoption import HOABoardRuleAdoption
from app.models.hoa_board_vote import HOABoardVote
from app.models.user import User
from app.routers.auth import get_current_user
from app.routers.hoa_arc_board_decisions import _board_scope
from app.routers.hoa_board_rule_adoptions import _proposal, _digest
from app.routers.hoa_meeting_drafts import _row as _meeting
from app.routers.hoa_meeting_workspace import _motion
from app.schemas.hoa_board_motion_outcome import (
    HOAMotionOutcomeIn, HOAMotionOutcomeOut, HOAMotionOutcomePreviewOut,
)
from app.services.audit import append_audit_log

router = APIRouter(prefix="/api/hoa/associations", tags=["HOA board motion final outcomes"])


def _out(row):
    return HOAMotionOutcomeOut(
        id=row.id, motion_draft_id=row.motion_draft_id,
        motion_sha256=row.motion_sha256, rule_adoption_id=row.rule_adoption_id,
        vote_register_sha256=row.vote_register_sha256,
        quorum_min=row.quorum_min, approval_min=row.approval_min,
        votes_for=row.votes_for, votes_against=row.votes_against,
        votes_abstain=row.votes_abstain, outcome=row.outcome,
        recorded_by_seat_id=row.recorded_by_seat_id, recorded_at=row.recorded_at,
    )


def _votes(db, org, assoc, prop, meeting, motion):
    rows = db.query(HOABoardVote).filter(
        HOABoardVote.organization_id == org,
        HOABoardVote.association_id == assoc,
        HOABoardVote.property_id == prop,
        HOABoardVote.meeting_draft_id == meeting,
        HOABoardVote.motion_draft_id == motion,
    ).order_by(HOABoardVote.id).limit(501).all()
    if len(rows) > 500:
        raise HTTPException(status_code=422, detail="Too many recorded motion votes.")
    counts = Counter(v.choice for v in rows)
    exact = ";".join(
        f"{v.id}:{v.board_seat_id}:{v.voter_user_id}:{v.choice}:{v.motion_sha256}"
        for v in rows
    )
    return counts, len(rows), sha256(exact.encode("utf-8")).hexdigest()


def _adopted(db, org, assoc, prop, *, lock=False):
    rule = _proposal(db, org, assoc, prop, lock=lock)
    digest = _digest(rule)
    if digest is None:
        return None
    return db.query(HOABoardRuleAdoption).filter(
        HOABoardRuleAdoption.organization_id == org,
        HOABoardRuleAdoption.association_id == assoc,
        HOABoardRuleAdoption.property_id == prop,
        HOABoardRuleAdoption.rule_draft_id == rule.id,
        HOABoardRuleAdoption.proposal_sha256 == digest,
    ).first()


def _existing(db, org, assoc, prop, meeting, motion):
    return db.query(HOABoardMotionOutcome).filter(
        HOABoardMotionOutcome.organization_id == org,
        HOABoardMotionOutcome.association_id == assoc,
        HOABoardMotionOutcome.property_id == prop,
        HOABoardMotionOutcome.meeting_draft_id == meeting,
        HOABoardMotionOutcome.motion_draft_id == motion,
    ).first()


@router.get("/{association_id}/meeting-drafts/{meeting_id}/board-motions/{motion_id}/outcome",
            response_model=HOAMotionOutcomePreviewOut)
def get_motion_outcome(
    association_id: int, meeting_id: int, motion_id: int,
    response: Response, property_id: int = Query(ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org, assoc, seat = _board_scope(
        db, actor=current_user, association_id=association_id, property_id=property_id,
    )
    _meeting(db, org, assoc.id, property_id, meeting_id)
    motion = _motion(db, org, assoc.id, property_id, meeting_id, motion_id)
    digest = sha256(motion.proposed_motion.encode("utf-8")).hexdigest()
    counts, tally, register_digest = _votes(
        db, org, assoc.id, property_id, meeting_id, motion.id,
    )
    adoption = _adopted(db, org, assoc.id, property_id)
    outcome = _existing(db, org, assoc.id, property_id, meeting_id, motion.id)
    met = adoption is not None and tally >= adoption.quorum_min
    response.headers["Cache-Control"] = "no-store"
    return HOAMotionOutcomePreviewOut(
        motion_draft_id=motion.id, motion_sha256=digest,
        rule_adoption_id=adoption.id if adoption else None,
        vote_register_sha256=register_digest,
        quorum_min=adoption.quorum_min if adoption else None,
        approval_min=adoption.approval_min if adoption else None,
        votes_for=counts["FOR"], votes_against=counts["AGAINST"],
        votes_abstain=counts["ABSTAIN"], quorum_met=met,
        predicted_outcome=("PASSED" if counts["FOR"] >= adoption.approval_min
                           else "NOT_PASSED") if met else None,
        recorded=_out(outcome) if outcome else None,
    )


@router.post("/{association_id}/meeting-drafts/{meeting_id}/board-motions/{motion_id}/outcome",
             response_model=HOAMotionOutcomeOut, status_code=201)
def record_motion_outcome(
    association_id: int, meeting_id: int, motion_id: int,
    payload: HOAMotionOutcomeIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org, assoc, seat = _board_scope(
        db, actor=current_user, association_id=association_id,
        property_id=payload.property_id,
    )
    meeting = _meeting(db, org, assoc.id, payload.property_id, meeting_id, lock=True)
    if meeting.proposed_on > date.today():
        raise HTTPException(status_code=409, detail="Future meeting cannot finalize a motion.")
    motion = _motion(
        db, org, assoc.id, payload.property_id, meeting_id, motion_id, lock=True,
    )
    digest = sha256(motion.proposed_motion.encode("utf-8")).hexdigest()
    if digest != payload.motion_sha256:
        raise HTTPException(status_code=409, detail="Motion text changed.")
    existing = _existing(db, org, assoc.id, payload.property_id, meeting_id, motion.id)
    if existing is not None:
        if (existing.motion_sha256 == digest
            and existing.rule_adoption_id == payload.rule_adoption_id
            and existing.vote_register_sha256 == payload.expected_vote_register_sha256):
            return _out(existing)
        raise HTTPException(status_code=409, detail="Motion outcome already finalized.")
    adoption = _adopted(db, org, assoc.id, payload.property_id, lock=True)
    if adoption is None or adoption.id != payload.rule_adoption_id:
        raise HTTPException(status_code=409, detail="Current board-adopted voting thresholds required.")
    counts, tally, register_digest = _votes(
        db, org, assoc.id, payload.property_id, meeting_id, motion.id,
    )
    if payload.expected_vote_register_sha256 != register_digest:
        raise HTTPException(status_code=409, detail="Vote register changed. Review the final tally.")
    if tally < adoption.quorum_min:
        raise HTTPException(status_code=409, detail="Recorded votes do not meet adopted quorum.")
    row = HOABoardMotionOutcome(
        organization_id=org, association_id=assoc.id,
        property_id=payload.property_id, meeting_draft_id=meeting_id,
        motion_draft_id=motion.id, motion_sha256=digest,
        rule_adoption_id=adoption.id, vote_register_sha256=register_digest,
        quorum_min=adoption.quorum_min, approval_min=adoption.approval_min,
        votes_for=counts["FOR"], votes_against=counts["AGAINST"],
        votes_abstain=counts["ABSTAIN"],
        outcome="PASSED" if counts["FOR"] >= adoption.approval_min else "NOT_PASSED",
        recorded_by_seat_id=seat.id, recorded_by_user_id=current_user.id,
    )
    db.add(row)
    try:
        db.flush()
        append_audit_log(
            db, organization_id=org, user_id=current_user.id,
            entity_type="hoa_board_motion_outcome", entity_id=row.id,
            action="board_motion_final_outcome_recorded",
            new_value={
                "association_id": assoc.id, "property_id": payload.property_id,
                "meeting_draft_id": meeting_id, "motion_draft_id": motion.id,
                "rule_adoption_id": adoption.id,
                "motion_sha256": digest, "vote_register_sha256": register_digest,
                "votes_for": row.votes_for, "votes_against": row.votes_against,
                "votes_abstain": row.votes_abstain, "outcome": row.outcome,
            },
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Concurrent or duplicate board motion finalization.") from exc
    db.refresh(row)
    return _out(row)
