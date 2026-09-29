"""One immutable, authenticated board-member choice per active motion.

Not staff-reported ballot data and not an automatic quorum or board resolution.
The association governs official procedure; this records each actual member act.
"""
from __future__ import annotations

from collections import Counter
from datetime import date
from hashlib import sha256

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.hoa_board_vote import HOABoardVote
from app.models.hoa_board_motion_outcome import HOABoardMotionOutcome
from app.models.hoa_meeting_workspace import HOAMotionDraft
from app.models.user import User
from app.routers.auth import get_current_user
from app.routers.hoa_arc_board_decisions import _board_scope
from app.routers.hoa_meeting_drafts import _row as meeting_row
from app.routers.hoa_meeting_workspace import _motion as motion_row
from app.schemas.hoa_board_vote import HOABoardVoteIn, HOABoardVoteOut, HOABoardMotionOut
from app.services.audit import append_audit_log

router = APIRouter(prefix="/api/hoa/associations", tags=["HOA authenticated board motion votes"])


def _out(row: HOABoardVote) -> HOABoardVoteOut:
    return HOABoardVoteOut(
        id=row.id, motion_draft_id=row.motion_draft_id,
        board_seat_id=row.board_seat_id, choice=row.choice,
        motion_sha256=row.motion_sha256, voted_at=row.voted_at,
    )


@router.get("/{association_id}/meeting-drafts/{meeting_id}/board-motions",
            response_model=list[HOABoardMotionOut])
def board_motions(
    association_id: int, meeting_id: int, response: Response,
    property_id: int = Query(ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org, assoc, seat = _board_scope(
        db, actor=current_user, association_id=association_id, property_id=property_id,
    )
    meeting_row(db, org, assoc.id, property_id, meeting_id)
    motions = db.query(HOAMotionDraft).filter(
        HOAMotionDraft.organization_id == org,
        HOAMotionDraft.association_id == assoc.id,
        HOAMotionDraft.property_id == property_id,
        HOAMotionDraft.meeting_draft_id == meeting_id,
        HOAMotionDraft.is_active.is_(True),
    ).order_by(HOAMotionDraft.id).limit(101).all()
    if len(motions) > 100:
        raise HTTPException(status_code=422, detail="Meeting has too many motions.")
    if not motions:
        response.headers["Cache-Control"] = "no-store"
        return []
    votes = db.query(HOABoardVote).filter(
        HOABoardVote.organization_id == org,
        HOABoardVote.association_id == assoc.id,
        HOABoardVote.property_id == property_id,
        HOABoardVote.meeting_draft_id == meeting_id,
        HOABoardVote.motion_draft_id.in_([m.id for m in motions]),
    ).all()
    by_motion = Counter(v.motion_draft_id for v in votes)
    choices = Counter((v.motion_draft_id, v.choice) for v in votes)
    grouped = {m.id: [] for m in motions}
    for v in sorted(votes, key=lambda row: row.id):
        grouped[v.motion_draft_id].append(_out(v))
    own = {v.motion_draft_id: v for v in votes if v.board_seat_id == seat.id}
    response.headers["Cache-Control"] = "no-store"
    return [
        HOABoardMotionOut(
            id=m.id, meeting_draft_id=meeting_id, proposed_motion=m.proposed_motion,
            motion_sha256=sha256(m.proposed_motion.encode("utf-8")).hexdigest(),
            recorded_votes=by_motion[m.id],
            votes_for=choices[(m.id, "FOR")],
            votes_against=choices[(m.id, "AGAINST")],
            votes_abstain=choices[(m.id, "ABSTAIN")],
            vote_register=grouped[m.id],
            my_vote=_out(own[m.id]) if m.id in own else None,
        ) for m in motions
    ]


@router.post("/{association_id}/meeting-drafts/{meeting_id}/board-motions/{motion_id}/vote",
             response_model=HOABoardVoteOut, status_code=201)
def cast_board_vote(
    association_id: int, meeting_id: int, motion_id: int,
    payload: HOABoardVoteIn,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org, assoc, seat = _board_scope(
        db, actor=current_user, association_id=association_id,
        property_id=payload.property_id,
    )
    meeting = meeting_row(db, org, assoc.id, payload.property_id, meeting_id, lock=True)
    if meeting.proposed_on > date.today():
        raise HTTPException(status_code=409, detail="Cannot cast a vote before the scheduled meeting date.")
    motion = db.query(HOAMotionDraft).filter(
        HOAMotionDraft.id == motion_id,
        HOAMotionDraft.organization_id == org,
        HOAMotionDraft.association_id == assoc.id,
        HOAMotionDraft.property_id == payload.property_id,
        HOAMotionDraft.meeting_draft_id == meeting_id,
        HOAMotionDraft.is_active.is_(True),
    ).with_for_update().first()
    if motion is None:
        raise HTTPException(status_code=404, detail="Active board motion not found.")
    digest = sha256(motion.proposed_motion.encode("utf-8")).hexdigest()
    if digest != payload.motion_sha256:
        raise HTTPException(status_code=409, detail="Motion text changed. Review current wording.")
    prior = db.query(HOABoardVote).filter(
        HOABoardVote.organization_id == org,
        HOABoardVote.association_id == assoc.id,
        HOABoardVote.property_id == payload.property_id,
        HOABoardVote.meeting_draft_id == meeting_id,
        HOABoardVote.motion_draft_id == motion.id,
        HOABoardVote.board_seat_id == seat.id,
    ).first()
    if prior is not None:
        if prior.motion_sha256 == digest and prior.choice == payload.choice:
            return _out(prior)
        raise HTTPException(status_code=409, detail="Your immutable motion vote is already recorded.")
    if db.query(HOABoardMotionOutcome.id).filter(
        HOABoardMotionOutcome.organization_id == org,
        HOABoardMotionOutcome.association_id == assoc.id,
        HOABoardMotionOutcome.property_id == payload.property_id,
        HOABoardMotionOutcome.meeting_draft_id == meeting_id,
        HOABoardMotionOutcome.motion_draft_id == motion.id,
    ).first() is not None:
        raise HTTPException(status_code=409, detail="Finalized board motion does not accept additional votes.")
    row = HOABoardVote(
        organization_id=org, association_id=assoc.id,
        property_id=payload.property_id, meeting_draft_id=meeting_id,
        motion_draft_id=motion.id, board_seat_id=seat.id,
        voter_user_id=current_user.id, motion_sha256=digest,
        choice=payload.choice,
    )
    db.add(row)
    try:
        db.flush()
        append_audit_log(
            db, organization_id=org, user_id=current_user.id,
            entity_type="hoa_board_vote", entity_id=row.id,
            action="board_member_motion_vote_recorded",
            new_value={
                "association_id": assoc.id, "property_id": payload.property_id,
                "meeting_draft_id": meeting_id, "motion_draft_id": motion.id,
                "board_seat_id": seat.id, "choice": row.choice,
                "motion_sha256": digest,
            },
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Concurrent or duplicate member vote.") from exc
    db.refresh(row)
    return _out(row)
