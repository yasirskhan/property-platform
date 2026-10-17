"""One authorized HOA board member may adopt one exact staff-minutes revision.

This records the member's action, not independent certification of quorum,
notice, full-board vote or statutory governance.
"""
from __future__ import annotations

from datetime import date
from hashlib import sha256

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.hoa_meeting_minutes import (
    HOAMeetingMinutesDraft, HOAMeetingMinutesApproval,
)
from app.models.user import User
from app.routers.auth import get_current_user
from app.routers.hoa_arc_board_decisions import _board_scope
from app.routers.hoa_meeting_drafts import _row as meeting_row
from app.routers.hoa_meeting_minutes import _row as minutes_row, _out as minutes_out
from app.schemas.hoa_meeting_minutes import HOAMinutesDraftOut
from app.schemas.hoa_meeting_minutes_approval import (
    HOAMinutesBoardApprovalIn, HOAMinutesBoardApprovalOut,
)
from app.services.audit import append_audit_log

router = APIRouter(prefix="/api/hoa/associations", tags=["HOA board minutes approvals"])


def _approval(db: Session, *, org: int, assoc: int, prop: int, meeting: int):
    return db.query(HOAMeetingMinutesApproval).filter(
        HOAMeetingMinutesApproval.organization_id == org,
        HOAMeetingMinutesApproval.association_id == assoc,
        HOAMeetingMinutesApproval.property_id == prop,
        HOAMeetingMinutesApproval.meeting_draft_id == meeting,
    ).first()


def _out(row: HOAMeetingMinutesApproval) -> HOAMinutesBoardApprovalOut:
    return HOAMinutesBoardApprovalOut(
        id=row.id, meeting_draft_id=row.meeting_draft_id,
        minutes_draft_id=row.minutes_draft_id, property_id=row.property_id,
        minutes_revision=row.minutes_revision, content_sha256=row.content_sha256,
        board_seat_id=row.board_seat_id, approved_by_user_id=row.approved_by_user_id,
        approved_at=row.approved_at, approval_note=row.approval_note,
    )


@router.get("/{association_id}/meeting-drafts/{meeting_id}/minutes-board-preview",
            response_model=HOAMinutesDraftOut | None)
def board_minutes_preview(
    association_id: int, meeting_id: int, response: Response,
    property_id: int = Query(ge=1),
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org, assoc, seat = _board_scope(
        db, actor=current_user, association_id=association_id,
        property_id=property_id,
    )
    meeting_row(db, org, assoc.id, property_id, meeting_id)
    response.headers["Cache-Control"] = "no-store"
    row = minutes_row(db, org, assoc.id, property_id, meeting_id)
    return minutes_out(row) if row is not None and row.is_active else None


@router.get("/{association_id}/meeting-drafts/{meeting_id}/minutes-board-approval",
            response_model=HOAMinutesBoardApprovalOut | None)
def get_minutes_approval(
    association_id: int, meeting_id: int, response: Response,
    property_id: int = Query(ge=1),
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org, assoc, seat = _board_scope(
        db, actor=current_user, association_id=association_id,
        property_id=property_id,
    )
    meeting_row(db, org, assoc.id, property_id, meeting_id)
    response.headers["Cache-Control"] = "no-store"
    row = _approval(db, org=org, assoc=assoc.id, prop=property_id, meeting=meeting_id)
    return _out(row) if row is not None else None


@router.post("/{association_id}/meeting-drafts/{meeting_id}/minutes-board-approval",
             response_model=HOAMinutesBoardApprovalOut, status_code=201)
def record_minutes_approval(
    association_id: int, meeting_id: int, payload: HOAMinutesBoardApprovalIn,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org, assoc, seat = _board_scope(
        db, actor=current_user, association_id=association_id,
        property_id=payload.property_id,
    )
    meeting = meeting_row(db, org, assoc.id, payload.property_id, meeting_id)
    if meeting.proposed_on > date.today():
        raise HTTPException(status_code=409, detail="Minutes cannot be approved before the recorded meeting date.")
    row = minutes_row(
        db, org, assoc.id, payload.property_id, meeting_id, lock=True,
    )
    if row is None or not row.is_active:
        raise HTTPException(status_code=404, detail="Active staff minutes not found.")
    existing = _approval(
        db, org=org, assoc=assoc.id, prop=payload.property_id, meeting=meeting_id,
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="This meeting's minutes already have a board-member approval.")
    digest = sha256(row.staff_minutes.encode("utf-8")).hexdigest()
    if row.revision != payload.minutes_revision or digest != payload.content_sha256:
        raise HTTPException(status_code=409, detail="Minutes changed. Reload and approve the exact current revision.")
    record = HOAMeetingMinutesApproval(
        organization_id=org, association_id=assoc.id,
        property_id=payload.property_id, meeting_draft_id=meeting_id,
        minutes_draft_id=row.id, minutes_revision=row.revision,
        content_sha256=digest, board_seat_id=seat.id,
        approved_by_user_id=current_user.id,
        approval_note=payload.approval_note,
    )
    db.add(record)
    try:
        db.flush()
        append_audit_log(
            db, organization_id=org, user_id=current_user.id,
            entity_type="hoa_meeting_minutes_approval", entity_id=record.id,
            action="board_member_minutes_approved",
            new_value={
                "association_id": assoc.id,
                "property_id": payload.property_id,
                "meeting_draft_id": meeting_id,
                "minutes_draft_id": row.id,
                "minutes_revision": row.revision,
                "content_sha256": digest,
                "board_seat_id": seat.id,
            },
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Concurrent or duplicate minutes approval.") from exc
    db.refresh(record)
    return _out(record)
