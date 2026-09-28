"""Scoped staff-prepared meeting minutes; no legally effective board action."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.hoa_meeting_minutes import HOAMeetingMinutesDraft
from app.models.user import User
from app.routers.auth import get_current_user
from app.routers.hoa_assessments import _scope
from app.routers.hoa_meeting_drafts import _row as _meeting
from app.schemas.hoa_meeting_minutes import HOAMinutesDraftIn, HOAMinutesDraftOut
from app.services.audit import append_audit_log

router = APIRouter(prefix="/api/hoa/associations", tags=["HOA staff meeting minutes"])


def _row(db: Session, org_id: int, assoc_id: int, property_id: int,
         meeting_id: int) -> HOAMeetingMinutesDraft | None:
    return db.query(HOAMeetingMinutesDraft).filter(
        HOAMeetingMinutesDraft.organization_id == org_id,
        HOAMeetingMinutesDraft.association_id == assoc_id,
        HOAMeetingMinutesDraft.property_id == property_id,
        HOAMeetingMinutesDraft.meeting_draft_id == meeting_id,
    ).first()


def _out(row: HOAMeetingMinutesDraft) -> HOAMinutesDraftOut:
    return HOAMinutesDraftOut(
        id=row.id, meeting_draft_id=row.meeting_draft_id,
        property_id=row.property_id, staff_minutes=row.staff_minutes,
        updated_at=row.updated_at,
    )


def _audit(db: Session, actor: User, row: HOAMeetingMinutesDraft, action: str) -> None:
    # Never place meeting body or ballot contents into audit metadata.
    append_audit_log(
        db, organization_id=row.organization_id, user_id=actor.id,
        entity_type="hoa_meeting_minutes_draft", entity_id=row.id,
        action=action,
        new_value={"association_id": row.association_id,
                   "property_id": row.property_id,
                   "meeting_draft_id": row.meeting_draft_id},
    )


@router.get("/{association_id}/meeting-drafts/{meeting_id}/minutes-draft",
            response_model=HOAMinutesDraftOut | None)
def get_minutes_draft(
    association_id: int, meeting_id: int, response: Response,
    property_id: int = Query(ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org, assoc = _scope(db, actor=current_user, association_id=association_id,
                        property_id=property_id, write=False)
    _meeting(db, org, assoc.id, property_id, meeting_id)
    response.headers["Cache-Control"] = "no-store"
    row = _row(db, org, assoc.id, property_id, meeting_id)
    return _out(row) if row is not None and row.is_active else None


@router.put("/{association_id}/meeting-drafts/{meeting_id}/minutes-draft",
            response_model=HOAMinutesDraftOut)
def save_minutes_draft(
    association_id: int, meeting_id: int, payload: HOAMinutesDraftIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org, assoc = _scope(db, actor=current_user, association_id=association_id,
                        property_id=payload.property_id, write=True)
    _meeting(db, org, assoc.id, payload.property_id, meeting_id)
    row = _row(db, org, assoc.id, payload.property_id, meeting_id)
    if row is not None and not row.is_active:
        raise HTTPException(status_code=409, detail="Archived minutes cannot be resurrected.")
    created = row is None
    if created:
        row = HOAMeetingMinutesDraft(
            organization_id=org, association_id=assoc.id,
            property_id=payload.property_id, meeting_draft_id=meeting_id,
            created_by_id=current_user.id,
        )
        db.add(row)
    row.staff_minutes = payload.staff_minutes
    row.updated_by_id = current_user.id
    try:
        db.flush()
        _audit(db, current_user, row,
               "staff_minutes_drafted" if created else "staff_minutes_revised")
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Staff minutes changed concurrently.") from exc
    db.refresh(row)
    return _out(row)


@router.delete("/{association_id}/meeting-drafts/{meeting_id}/minutes-draft",
               status_code=204)
def archive_minutes_draft(
    association_id: int, meeting_id: int,
    property_id: int = Query(ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org, assoc = _scope(db, actor=current_user, association_id=association_id,
                        property_id=property_id, write=True)
    _meeting(db, org, assoc.id, property_id, meeting_id)
    row = _row(db, org, assoc.id, property_id, meeting_id)
    if row is None or not row.is_active:
        raise HTTPException(status_code=404, detail="Staff minutes draft not found.")
    row.is_active = False
    row.updated_by_id = current_user.id
    db.flush()
    _audit(db, current_user, row, "staff_minutes_archived")
    db.commit()
    return Response(status_code=204, headers={"Cache-Control": "no-store"})
