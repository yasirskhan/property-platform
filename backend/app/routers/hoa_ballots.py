"""Staff-reported HOA ballots, gated from legal board voting."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.contact import Contact
from app.models.hoa_association import HOAContactLink
from app.models.hoa_board import HOABoardSeat
from app.models.hoa_ballot import HOABallotRecord
from app.models.user import User
from app.routers.auth import get_current_user
from app.routers.hoa_associations import _contact_scope
from app.routers.hoa_meeting_drafts import _row as _meeting
from app.routers.hoa_meeting_workspace import _motion
from app.schemas.hoa_ballot import HOABallotIn, HOABallotOut, HOABallotListOut
from app.services.audit import append_audit_log

router = APIRouter(prefix="/api/hoa/associations", tags=["HOA staff ballot reports"])


def _seat_contact(db: Session, *, org_id: int, association_id: int,
                  property_id: int, seat_id: int):
    result = db.query(HOABoardSeat, Contact).join(
        HOAContactLink, HOAContactLink.id == HOABoardSeat.contact_link_id,
    ).join(Contact, Contact.id == HOAContactLink.contact_id).filter(
        HOABoardSeat.id == seat_id,
        HOABoardSeat.organization_id == org_id,
        HOABoardSeat.association_id == association_id,
        HOABoardSeat.property_id == property_id,
        HOABoardSeat.is_active.is_(True),
        HOAContactLink.organization_id == org_id,
        HOAContactLink.association_id == association_id,
        HOAContactLink.property_id == property_id,
        HOAContactLink.is_active.is_(True),
        Contact.organization_id == org_id,
        Contact.is_active.is_(True),
        Contact.deleted_at.is_(None),
    ).first()
    if result is None:
        raise HTTPException(status_code=404, detail="Active staff board contact not found.")
    return result


def _out(row: HOABallotRecord, contact: Contact) -> HOABallotOut:
    return HOABallotOut(
        id=row.id, motion_draft_id=row.motion_draft_id,
        board_seat_id=row.board_seat_id, contact_name=contact.display_name,
        staff_reported_choice=row.staff_reported_choice,
    )


def _audit(db: Session, actor: User, row: HOABallotRecord, action: str) -> None:
    append_audit_log(
        db, organization_id=row.organization_id, user_id=actor.id,
        entity_type="hoa_ballot_record", entity_id=row.id, action=action,
        new_value={"association_id": row.association_id, "property_id": row.property_id,
                   "meeting_draft_id": row.meeting_draft_id,
                   "motion_draft_id": row.motion_draft_id},
    )


@router.get("/{association_id}/meeting-drafts/{meeting_id}/motions/{motion_id}/ballot-records",
            response_model=HOABallotListOut)
def list_ballot_records(
    association_id: int, meeting_id: int, motion_id: int, response: Response,
    property_id: int = Query(ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org, association = _contact_scope(
        db, actor=current_user, association_id=association_id,
        property_id=property_id, write=False,
    )
    _meeting(db, org, association.id, property_id, meeting_id)
    _motion(db, org, association.id, property_id, meeting_id, motion_id)
    rows = db.query(HOABallotRecord, Contact).join(
        HOABoardSeat, HOABoardSeat.id == HOABallotRecord.board_seat_id,
    ).join(HOAContactLink, HOAContactLink.id == HOABoardSeat.contact_link_id).join(
        Contact, Contact.id == HOAContactLink.contact_id,
    ).filter(
        HOABallotRecord.organization_id == org,
        HOABallotRecord.association_id == association.id,
        HOABallotRecord.property_id == property_id,
        HOABallotRecord.meeting_draft_id == meeting_id,
        HOABallotRecord.motion_draft_id == motion_id,
        HOABallotRecord.is_active.is_(True),
        HOABoardSeat.organization_id == org,
        HOABoardSeat.association_id == association.id,
        HOABoardSeat.property_id == property_id,
        HOABoardSeat.is_active.is_(True),
        HOAContactLink.organization_id == org,
        HOAContactLink.association_id == association.id,
        HOAContactLink.property_id == property_id,
        HOAContactLink.is_active.is_(True),
        Contact.organization_id == org,
        Contact.is_active.is_(True), Contact.deleted_at.is_(None),
    ).order_by(HOABallotRecord.id).limit(101).all()
    if len(rows) > 100:
        raise HTTPException(status_code=422, detail="Too many staff ballot records.")
    response.headers["Cache-Control"] = "no-store"
    return HOABallotListOut(
        meeting_draft_id=meeting_id, motion_draft_id=motion_id,
        ballots=[_out(row, contact) for row, contact in rows],
    )


@router.post("/{association_id}/meeting-drafts/{meeting_id}/motions/{motion_id}/ballot-records",
             response_model=HOABallotOut, status_code=201)
def record_ballot(
    association_id: int, meeting_id: int, motion_id: int,
    payload: HOABallotIn,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org, association = _contact_scope(
        db, actor=current_user, association_id=association_id,
        property_id=payload.property_id, write=True,
    )
    _meeting(db, org, association.id, payload.property_id, meeting_id)
    _motion(db, org, association.id, payload.property_id, meeting_id, motion_id)
    seat, contact = _seat_contact(
        db, org_id=org, association_id=association.id,
        property_id=payload.property_id, seat_id=payload.board_seat_id,
    )
    if not seat.staff_voting_eligible:
        raise HTTPException(status_code=422, detail="Contact is not staff-proposed eligible.")
    duplicate = db.query(HOABallotRecord.id).filter(
        HOABallotRecord.motion_draft_id == motion_id,
        HOABallotRecord.board_seat_id == seat.id,
    ).first()
    if duplicate is not None:
        raise HTTPException(status_code=409, detail="Staff ballot record already exists.")
    count = db.query(HOABallotRecord.id).filter(
        HOABallotRecord.organization_id == org,
        HOABallotRecord.motion_draft_id == motion_id,
        HOABallotRecord.is_active.is_(True),
    ).limit(100).count()
    if count >= 100:
        raise HTTPException(status_code=422, detail="Too many staff ballot records.")
    row = HOABallotRecord(
        organization_id=org, association_id=association.id,
        property_id=payload.property_id, meeting_draft_id=meeting_id,
        motion_draft_id=motion_id, board_seat_id=seat.id,
        staff_reported_choice=payload.staff_reported_choice,
        created_by_id=current_user.id, updated_by_id=current_user.id,
    )
    db.add(row)
    try:
        db.flush()
        _audit(db, current_user, row, "staff_ballot_reported")
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Staff ballot record already exists.") from exc
    db.refresh(row)
    return _out(row, contact)


@router.delete("/{association_id}/meeting-drafts/{meeting_id}/motions/{motion_id}/ballot-records/{record_id}",
               status_code=204)
def archive_ballot_record(
    association_id: int, meeting_id: int, motion_id: int, record_id: int,
    property_id: int = Query(ge=1),
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org, association = _contact_scope(
        db, actor=current_user, association_id=association_id,
        property_id=property_id, write=True,
    )
    _meeting(db, org, association.id, property_id, meeting_id)
    _motion(db, org, association.id, property_id, meeting_id, motion_id)
    row = db.query(HOABallotRecord).filter(
        HOABallotRecord.id == record_id,
        HOABallotRecord.organization_id == org,
        HOABallotRecord.association_id == association.id,
        HOABallotRecord.property_id == property_id,
        HOABallotRecord.meeting_draft_id == meeting_id,
        HOABallotRecord.motion_draft_id == motion_id,
        HOABallotRecord.is_active.is_(True),
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Staff ballot record not found.")
    _seat_contact(db, org_id=org, association_id=association.id,
                  property_id=property_id, seat_id=row.board_seat_id)
    row.is_active = False
    row.updated_by_id = current_user.id
    db.flush()
    _audit(db, current_user, row, "staff_ballot_archived")
    db.commit()
    return Response(status_code=204, headers={"Cache-Control": "no-store"})
