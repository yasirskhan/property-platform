"""Scoped staff meeting plans, not an HOA board portal or official action."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.core.database import get_db
from app.models.hoa_meeting_draft import HOAMeetingDraft
from app.models.user import User
from app.models.hoa_meeting_minutes import HOAMeetingMinutesApproval
from app.routers.auth import get_current_user
from app.routers.hoa_assessments import _scope
from app.schemas.hoa_meeting_draft import HOAMeetingDraftIn, HOAMeetingDraftOut
from app.services.audit import append_audit_log
from app.services.hoa_meeting_workspace_cleanup import archive_meeting_workspace

router = APIRouter(prefix="/api/hoa/associations", tags=["HOA staff meeting plans"])


def _row(db: Session, org_id: int, association_id: int, property_id: int, draft_id: int) -> HOAMeetingDraft:
    found = db.query(HOAMeetingDraft).filter(
        HOAMeetingDraft.id == draft_id,
        HOAMeetingDraft.organization_id == org_id,
        HOAMeetingDraft.association_id == association_id,
        HOAMeetingDraft.property_id == property_id,
        HOAMeetingDraft.is_active.is_(True),
    ).first()
    if found is None:
        raise HTTPException(status_code=404, detail="Staff meeting draft not found.")
    return found


def _out(row: HOAMeetingDraft) -> HOAMeetingDraftOut:
    return HOAMeetingDraftOut(
        id=row.id, association_id=row.association_id,
        property_id=row.property_id, title=row.title,
        proposed_on=row.proposed_on, staff_agenda=row.staff_agenda,
        updated_at=row.updated_at,
    )


@router.get("/{association_id}/meeting-drafts", response_model=list[HOAMeetingDraftOut])
def list_meeting_drafts(
    association_id: int, response: Response, property_id: int = Query(ge=1),
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org_id, assoc = _scope(
        db, actor=current_user, association_id=association_id,
        property_id=property_id, write=False,
    )
    response.headers["Cache-Control"] = "no-store"
    records = db.query(HOAMeetingDraft).filter(
        HOAMeetingDraft.organization_id == org_id,
        HOAMeetingDraft.association_id == assoc.id,
        HOAMeetingDraft.property_id == property_id,
        HOAMeetingDraft.is_active.is_(True),
    ).order_by(HOAMeetingDraft.id.asc()).limit(201).all()
    if len(records) > 200:
        raise HTTPException(status_code=422, detail="Too many staff meeting drafts.")
    return [_out(row) for row in records]


@router.post("/{association_id}/meeting-drafts", response_model=HOAMeetingDraftOut, status_code=201)
def create_meeting_draft(
    association_id: int, payload: HOAMeetingDraftIn,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org_id, assoc = _scope(
        db, actor=current_user, association_id=association_id,
        property_id=payload.property_id, write=True,
    )
    existing = db.query(HOAMeetingDraft.id).filter(
        HOAMeetingDraft.organization_id == org_id,
        HOAMeetingDraft.association_id == assoc.id,
        HOAMeetingDraft.property_id == payload.property_id,
        HOAMeetingDraft.is_active.is_(True),
    ).limit(200).all()
    if len(existing) >= 200:
        raise HTTPException(status_code=422, detail="Too many staff meeting drafts.")
    row = HOAMeetingDraft(
        organization_id=org_id, association_id=assoc.id,
        created_by_id=current_user.id, updated_by_id=current_user.id,
        **payload.model_dump(),
    )
    db.add(row)
    try:
        db.flush()
        append_audit_log(
            db, organization_id=org_id, user_id=current_user.id,
            entity_type="hoa_meeting_draft", entity_id=row.id, action="staff_draft_created",
            new_value={"association_id": assoc.id, "property_id": row.property_id},
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Meeting draft changed concurrently.") from exc
    db.refresh(row)
    return _out(row)


@router.put("/{association_id}/meeting-drafts/{draft_id}", response_model=HOAMeetingDraftOut)
def update_meeting_draft(
    association_id: int, draft_id: int, payload: HOAMeetingDraftIn,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org_id, assoc = _scope(
        db, actor=current_user, association_id=association_id,
        property_id=payload.property_id, write=True,
    )
    row = _row(db, org_id, assoc.id, payload.property_id, draft_id)
    if db.query(HOAMeetingMinutesApproval.id).filter(
        HOAMeetingMinutesApproval.organization_id == org_id,
        HOAMeetingMinutesApproval.association_id == assoc.id,
        HOAMeetingMinutesApproval.property_id == payload.property_id,
        HOAMeetingMinutesApproval.meeting_draft_id == draft_id,
    ).first() is not None:
        raise HTTPException(status_code=409, detail="Meeting has adopted minutes; no silent plan changes.")
    row.title = payload.title
    row.proposed_on = payload.proposed_on
    row.staff_agenda = payload.staff_agenda
    row.updated_by_id = current_user.id
    db.flush()
    append_audit_log(
        db, organization_id=org_id, user_id=current_user.id,
        entity_type="hoa_meeting_draft", entity_id=row.id, action="staff_draft_updated",
        new_value={"association_id": assoc.id, "property_id": row.property_id},
    )
    db.commit()
    db.refresh(row)
    return _out(row)


@router.delete("/{association_id}/meeting-drafts/{draft_id}", status_code=204)
def archive_meeting_draft(
    association_id: int, draft_id: int, property_id: int,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org_id, assoc = _scope(
        db, actor=current_user, association_id=association_id,
        property_id=property_id, write=True,
    )
    row = _row(db, org_id, assoc.id, property_id, draft_id)
    if db.query(HOAMeetingMinutesApproval.id).filter(
        HOAMeetingMinutesApproval.organization_id == org_id,
        HOAMeetingMinutesApproval.association_id == assoc.id,
        HOAMeetingMinutesApproval.property_id == property_id,
        HOAMeetingMinutesApproval.meeting_draft_id == draft_id,
    ).first() is not None:
        raise HTTPException(status_code=409, detail="Meeting with adopted minutes cannot be archived.")
    archive_meeting_workspace(
        db, organization_id=org_id, association_id=assoc.id,
        property_id=property_id, meeting_draft_id=row.id,
        actor_id=current_user.id, action="meeting_draft_archived",
    )
    row.is_active = False
    row.updated_by_id = current_user.id
    db.flush()
    append_audit_log(
        db, organization_id=org_id, user_id=current_user.id,
        entity_type="hoa_meeting_draft", entity_id=row.id, action="staff_draft_archived",
        new_value={"association_id": assoc.id, "property_id": row.property_id},
    )
    db.commit()
    return Response(status_code=204, headers={"Cache-Control": "no-store"})
