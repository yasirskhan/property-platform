"""HOA meeting staff participation and motion proposals, not a board portal or vote."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.contact import Contact
from app.models.hoa_association import HOAContactLink
from app.models.hoa_meeting_workspace import HOAMeetingParticipation, HOAMotionDraft
from app.models.user import User
from app.routers.auth import get_current_user
from app.routers.hoa_associations import _contact_scope
from app.routers.hoa_assessments import _scope
from app.routers.hoa_meeting_drafts import _row as _meeting
from app.schemas.hoa_meeting_workspace import (
    HOAMeetingAttendanceIn, HOAMeetingAttendanceOut,
    HOAMeetingWorkspaceOut, HOAMotionDraftIn, HOAMotionDraftOut,
)
from app.services.audit import append_audit_log
from app.services.hoa_ballot_cleanup import archive_ballots

router = APIRouter(prefix="/api/hoa/associations", tags=["HOA staff meeting workspace"])


def _attendance(db: Session, org_id: int, association_id: int, property_id: int,
                meeting_id: int, participation_id: int) -> HOAMeetingParticipation:
    row = db.query(HOAMeetingParticipation).filter(
        HOAMeetingParticipation.id == participation_id,
        HOAMeetingParticipation.organization_id == org_id,
        HOAMeetingParticipation.association_id == association_id,
        HOAMeetingParticipation.property_id == property_id,
        HOAMeetingParticipation.meeting_draft_id == meeting_id,
        HOAMeetingParticipation.is_active.is_(True),
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Staff attendance not found.")
    return row


def _motion(db: Session, org_id: int, association_id: int, property_id: int,
            meeting_id: int, motion_id: int) -> HOAMotionDraft:
    row = db.query(HOAMotionDraft).filter(
        HOAMotionDraft.id == motion_id,
        HOAMotionDraft.organization_id == org_id,
        HOAMotionDraft.association_id == association_id,
        HOAMotionDraft.property_id == property_id,
        HOAMotionDraft.meeting_draft_id == meeting_id,
        HOAMotionDraft.is_active.is_(True),
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Proposed motion not found.")
    return row


def _contact(db: Session, org_id: int, association_id: int,
             property_id: int, link_id: int) -> tuple[HOAContactLink, Contact]:
    row = db.query(HOAContactLink, Contact).join(
        Contact, Contact.id == HOAContactLink.contact_id,
    ).filter(
        HOAContactLink.id == link_id,
        HOAContactLink.organization_id == org_id,
        HOAContactLink.association_id == association_id,
        HOAContactLink.property_id == property_id,
        HOAContactLink.is_active.is_(True),
        Contact.organization_id == org_id,
        Contact.is_active.is_(True),
        Contact.deleted_at.is_(None),
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Active staff contact link not found.")
    return row


def _audit(db: Session, actor: User, row, action: str) -> None:
    append_audit_log(
        db, organization_id=row.organization_id, user_id=actor.id,
        entity_type=("hoa_meeting_participation"
                     if isinstance(row, HOAMeetingParticipation)
                     else "hoa_motion_draft"),
        entity_id=row.id, action=action,
        new_value={
            "association_id": row.association_id,
            "property_id": row.property_id,
            "meeting_draft_id": row.meeting_draft_id,
        },
    )


def _participation_out(row: HOAMeetingParticipation, contact: Contact):
    return HOAMeetingAttendanceOut(
        id=row.id, contact_link_id=row.contact_link_id,
        contact_name=contact.display_name,
        staff_attendance=row.staff_attendance,
    )


def _motion_out(row: HOAMotionDraft):
    return HOAMotionDraftOut(
        id=row.id, proposed_motion=row.proposed_motion,
        updated_at=row.updated_at,
    )


@router.get("/{association_id}/meeting-drafts/{meeting_id}/workspace",
            response_model=HOAMeetingWorkspaceOut)
def get_workspace(
    association_id: int, meeting_id: int, response: Response,
    property_id: int = Query(ge=1),
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org_id, association = _contact_scope(
        db, actor=current_user, association_id=association_id,
        property_id=property_id, write=False,
    )
    _meeting(db, org_id, association.id, property_id, meeting_id)
    attendance = db.query(HOAMeetingParticipation, Contact).join(
        HOAContactLink, HOAContactLink.id == HOAMeetingParticipation.contact_link_id,
    ).join(Contact, Contact.id == HOAContactLink.contact_id).filter(
        HOAMeetingParticipation.organization_id == org_id,
        HOAMeetingParticipation.association_id == association.id,
        HOAMeetingParticipation.property_id == property_id,
        HOAMeetingParticipation.meeting_draft_id == meeting_id,
        HOAMeetingParticipation.is_active.is_(True),
        HOAContactLink.organization_id == org_id,
        HOAContactLink.association_id == association.id,
        HOAContactLink.property_id == property_id,
        HOAContactLink.is_active.is_(True),
        Contact.organization_id == org_id,
        Contact.is_active.is_(True),
        Contact.deleted_at.is_(None),
    ).order_by(HOAMeetingParticipation.id).limit(101).all()
    motions = db.query(HOAMotionDraft).filter(
        HOAMotionDraft.organization_id == org_id,
        HOAMotionDraft.association_id == association.id,
        HOAMotionDraft.property_id == property_id,
        HOAMotionDraft.meeting_draft_id == meeting_id,
        HOAMotionDraft.is_active.is_(True),
    ).order_by(HOAMotionDraft.id).limit(101).all()
    if len(attendance) > 100 or len(motions) > 100:
        raise HTTPException(status_code=422, detail="Meeting staff records exceed preview limit.")
    response.headers["Cache-Control"] = "no-store"
    return HOAMeetingWorkspaceOut(
        meeting_draft_id=meeting_id, association_id=association.id,
        property_id=property_id,
        attendance=[_participation_out(row, contact) for row, contact in attendance],
        motions=[_motion_out(row) for row in motions],
    )


@router.post("/{association_id}/meeting-drafts/{meeting_id}/workspace/attendance",
             response_model=HOAMeetingAttendanceOut, status_code=201)
def record_attendance(
    association_id: int, meeting_id: int, payload: HOAMeetingAttendanceIn,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org_id, association = _contact_scope(
        db, actor=current_user, association_id=association_id,
        property_id=payload.property_id, write=True,
    )
    _meeting(db, org_id, association.id, payload.property_id, meeting_id)
    link, contact = _contact(
        db, org_id, association.id, payload.property_id, payload.contact_link_id,
    )
    existing = db.query(HOAMeetingParticipation).filter(
        HOAMeetingParticipation.meeting_draft_id == meeting_id,
        HOAMeetingParticipation.contact_link_id == link.id,
    ).with_for_update().first()
    if existing is not None and not existing.is_active:
        raise HTTPException(status_code=409, detail="Archived staff attendance cannot be resurrected.")
    if existing is not None:
        row = existing
        action = "staff_attendance_corrected"
    else:
        if db.query(HOAMeetingParticipation.id).filter(
            HOAMeetingParticipation.organization_id == org_id,
            HOAMeetingParticipation.meeting_draft_id == meeting_id,
            HOAMeetingParticipation.is_active.is_(True),
        ).limit(100).count() >= 100:
            raise HTTPException(status_code=422, detail="Too many meeting attendance records.")
        row = HOAMeetingParticipation(
            organization_id=org_id, association_id=association.id,
            property_id=payload.property_id, meeting_draft_id=meeting_id,
            contact_link_id=link.id, created_by_id=current_user.id,
        )
        db.add(row)
        action = "staff_attendance_recorded"
    row.staff_attendance = payload.staff_attendance
    row.updated_by_id = current_user.id
    try:
        db.flush()
        _audit(db, current_user, row, action)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Meeting attendance changed concurrently.") from exc
    db.refresh(row)
    return _participation_out(row, contact)


@router.delete("/{association_id}/meeting-drafts/{meeting_id}/workspace/attendance/{participation_id}", status_code=204)
def archive_attendance(
    association_id: int, meeting_id: int, participation_id: int,
    property_id: int = Query(ge=1),
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org_id, association = _scope(
        db, actor=current_user, association_id=association_id,
        property_id=property_id, write=True,
    )
    _meeting(db, org_id, association.id, property_id, meeting_id)
    row = _attendance(db, org_id, association.id, property_id, meeting_id, participation_id)
    row.is_active = False
    row.updated_by_id = current_user.id
    db.flush()
    _audit(db, current_user, row, "staff_attendance_archived")
    db.commit()
    return Response(status_code=204, headers={"Cache-Control": "no-store"})


@router.post("/{association_id}/meeting-drafts/{meeting_id}/workspace/motions",
             response_model=HOAMotionDraftOut, status_code=201)
def propose_motion(
    association_id: int, meeting_id: int, payload: HOAMotionDraftIn,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org_id, association = _scope(
        db, actor=current_user, association_id=association_id,
        property_id=payload.property_id, write=True,
    )
    _meeting(db, org_id, association.id, payload.property_id, meeting_id)
    if db.query(HOAMotionDraft.id).filter(
        HOAMotionDraft.organization_id == org_id,
        HOAMotionDraft.meeting_draft_id == meeting_id,
        HOAMotionDraft.is_active.is_(True),
    ).limit(100).count() >= 100:
        raise HTTPException(status_code=422, detail="Too many proposed motions.")
    row = HOAMotionDraft(
        organization_id=org_id, association_id=association.id,
        property_id=payload.property_id, meeting_draft_id=meeting_id,
        proposed_motion=payload.proposed_motion,
        created_by_id=current_user.id, updated_by_id=current_user.id,
    )
    db.add(row)
    db.flush()
    _audit(db, current_user, row, "staff_motion_proposed")
    db.commit()
    db.refresh(row)
    return _motion_out(row)


@router.delete("/{association_id}/meeting-drafts/{meeting_id}/workspace/motions/{motion_id}", status_code=204)
def archive_motion(
    association_id: int, meeting_id: int, motion_id: int,
    property_id: int = Query(ge=1),
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org_id, association = _scope(
        db, actor=current_user, association_id=association_id,
        property_id=property_id, write=True,
    )
    _meeting(db, org_id, association.id, property_id, meeting_id)
    row = _motion(db, org_id, association.id, property_id, meeting_id, motion_id)
    archive_ballots(
        db, organization_id=org_id, association_id=association.id,
        property_id=property_id, meeting_draft_id=meeting_id,
        motion_draft_id=row.id, actor_id=current_user.id,
        action="staff_motion_archived",
    )
    row.is_active = False
    row.updated_by_id = current_user.id
    db.flush()
    _audit(db, current_user, row, "staff_motion_archived")
    db.commit()
    return Response(status_code=204, headers={"Cache-Control": "no-store"})
