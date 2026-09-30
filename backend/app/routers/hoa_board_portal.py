"""Authenticated board portal: enumerate ONLY live association meetings for this board seat.

A board delegation allows this read without granting organization-wide property
permissions. No staff notes outside the member's association/property scope
and no vote, charge, notice or unverified contact-to-login inference.
"""
from __future__ import annotations

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.contact import Contact
from app.models.hoa_association import HOAAssociation, HOAContactLink, HOAPropertyMembership
from app.models.hoa_board import HOABoardSeat
from app.models.hoa_meeting_draft import HOAMeetingDraft
from app.models.hoa_violation_fine_appeal import HOAFineAppeal
from app.models.hoa_fine_appeal_notification import HOAFineAppealNotification
from app.models.property import Property
from app.models.user import Organization, User
from app.routers.auth import get_current_user
from app.routers.hoa_arc_board_decisions import HOA_GATES, _board_scope
from app.routers.hoa_violation_cases import _case
from app.routers.hoa_violation_fines import _fine, _private_case_proof
from app.routers.hoa_governing_evidence import _require_attachment_feature
from app.services.attachment_storage import attachment_path
from app.services.customer_features import resolve_customer_features

router = APIRouter(prefix="/api/hoa/board", tags=["HOA authenticated board portal"])


class HOABoardMeetingOut(BaseModel):
    association_id: int
    property_id: int
    meeting_id: int
    title: str
    proposed_on: date
    staff_agenda: str | None = None


@router.get("/my-meetings", response_model=list[HOABoardMeetingOut])
def my_board_meetings(
    response: Response, db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    actor = current_user
    if (
        actor.organization_id is None or not actor.is_active
        or actor.deleted_at is not None or not actor.is_verified
    ):
        raise HTTPException(status_code=403, detail="Verified board login required.")
    org = db.query(Organization.id).filter(
        Organization.id == actor.organization_id,
        Organization.is_active.is_(True),
        Organization.deleted_at.is_(None),
    ).first()
    if org is None:
        raise HTTPException(status_code=403, detail="Organization inactive.")
    grants = {entry.key: entry for entry in resolve_customer_features(db, user=actor)}
    if any(
        (value := grants.get(key)) is None
        or not (value.release_allowed and value.entitlement_allowed and value.org_config_allowed)
        for key in HOA_GATES
    ):
        raise HTTPException(status_code=404, detail="HOA board module unavailable.")

    q = db.query(HOAMeetingDraft).join(
        HOABoardSeat, and_(
            HOABoardSeat.organization_id == HOAMeetingDraft.organization_id,
            HOABoardSeat.association_id == HOAMeetingDraft.association_id,
            HOABoardSeat.property_id == HOAMeetingDraft.property_id,
        ),
    ).join(
        HOAContactLink, HOAContactLink.id == HOABoardSeat.contact_link_id,
    ).join(
        Contact, Contact.id == HOAContactLink.contact_id,
    ).join(
        HOAAssociation, HOAAssociation.id == HOAMeetingDraft.association_id,
    ).join(
        HOAPropertyMembership, and_(
            HOAPropertyMembership.association_id == HOAMeetingDraft.association_id,
            HOAPropertyMembership.property_id == HOAMeetingDraft.property_id,
            HOAPropertyMembership.organization_id == HOAMeetingDraft.organization_id,
        ),
    ).join(
        Property, Property.id == HOAMeetingDraft.property_id,
    ).filter(
        HOAMeetingDraft.organization_id == actor.organization_id,
        HOAMeetingDraft.is_active.is_(True),
        HOABoardSeat.organization_id == actor.organization_id,
        HOABoardSeat.authorized_user_id == actor.id,
        HOABoardSeat.is_active.is_(True),
        HOABoardSeat.decision_authorized.is_(True),
        HOABoardSeat.staff_voting_eligible.is_(True),
        HOAContactLink.organization_id == actor.organization_id,
        HOAContactLink.association_id == HOAMeetingDraft.association_id,
        HOAContactLink.property_id == HOAMeetingDraft.property_id,
        HOAContactLink.is_active.is_(True),
        Contact.organization_id == actor.organization_id,
        Contact.is_active.is_(True),
        Contact.deleted_at.is_(None),
        func.lower(func.trim(Contact.email)) == actor.email.strip().lower(),
        HOAAssociation.organization_id == actor.organization_id,
        HOAAssociation.is_active.is_(True),
        Property.organization_id == actor.organization_id,
        Property.is_active.is_(True),
        Property.deleted_at.is_(None),
    ).order_by(HOAMeetingDraft.id).limit(501).all()
    unique = {row.id: row for row in q}
    if len(q) > 500 or len(unique) > 200:
        raise HTTPException(status_code=422, detail="Board meeting list exceeds 200; contact the administrator.")
    response.headers["Cache-Control"] = "no-store"
    return [
        HOABoardMeetingOut(
            association_id=row.association_id, property_id=row.property_id,
            meeting_id=row.id, title=row.title, proposed_on=row.proposed_on,
            staff_agenda=row.staff_agenda,
        )
        for row in unique.values()
    ]


class HOABoardFineAppealOut(BaseModel):
    association_id: int
    property_id: int
    case_id: int
    fine_id: int
    appeal_id: int
    received_on: date
    member_user_id: int
    appeal_reason: str
    has_private_evidence: bool = False
    status: Literal["OPEN"] = "OPEN"


@router.get("/my-fine-appeals", response_model=list[HOABoardFineAppealOut])
def my_board_fine_appeals(
    response: Response, db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Only pending fine appeals for the actor's live board delegation."""
    actor = current_user
    if (actor.organization_id is None or not actor.is_active
        or actor.deleted_at is not None or not actor.is_verified):
        raise HTTPException(status_code=403, detail="Verified board login required.")
    org = db.query(Organization.id).filter(
        Organization.id == actor.organization_id,
        Organization.is_active.is_(True),
        Organization.deleted_at.is_(None),
    ).first()
    if org is None:
        raise HTTPException(status_code=403, detail="Organization inactive.")
    grants = {entry.key: entry for entry in resolve_customer_features(db, user=actor)}
    if any(
        (value := grants.get(key)) is None
        or not (value.release_allowed and value.entitlement_allowed and value.org_config_allowed)
        for key in HOA_GATES
    ):
        raise HTTPException(status_code=404, detail="HOA board module unavailable.")

    q = db.query(HOAFineAppeal).join(
        HOABoardSeat, and_(
            HOABoardSeat.organization_id == HOAFineAppeal.organization_id,
            HOABoardSeat.association_id == HOAFineAppeal.association_id,
            HOABoardSeat.property_id == HOAFineAppeal.property_id,
        ),
    ).join(
        HOAContactLink, HOAContactLink.id == HOABoardSeat.contact_link_id,
    ).join(
        Contact, Contact.id == HOAContactLink.contact_id,
    ).join(
        HOAAssociation, HOAAssociation.id == HOAFineAppeal.association_id,
    ).join(
        HOAPropertyMembership, and_(
            HOAPropertyMembership.association_id == HOAFineAppeal.association_id,
            HOAPropertyMembership.property_id == HOAFineAppeal.property_id,
            HOAPropertyMembership.organization_id == HOAFineAppeal.organization_id,
        ),
    ).join(
        Property, Property.id == HOAFineAppeal.property_id,
    ).filter(
        HOAFineAppeal.organization_id == actor.organization_id,
        HOAFineAppeal.status == "OPEN",
        HOABoardSeat.organization_id == actor.organization_id,
        HOABoardSeat.authorized_user_id == actor.id,
        HOABoardSeat.is_active.is_(True),
        HOABoardSeat.decision_authorized.is_(True),
        HOABoardSeat.staff_voting_eligible.is_(True),
        HOAContactLink.organization_id == actor.organization_id,
        HOAContactLink.association_id == HOAFineAppeal.association_id,
        HOAContactLink.property_id == HOAFineAppeal.property_id,
        HOAContactLink.is_active.is_(True),
        Contact.organization_id == actor.organization_id,
        Contact.is_active.is_(True), Contact.deleted_at.is_(None),
        func.lower(func.trim(Contact.email)) == actor.email.strip().lower(),
        HOAAssociation.organization_id == actor.organization_id,
        HOAAssociation.is_active.is_(True),
        Property.organization_id == actor.organization_id,
        Property.is_active.is_(True), Property.deleted_at.is_(None),
    ).order_by(HOAFineAppeal.id).limit(201).all()
    if len(q) > 200:
        raise HTTPException(status_code=422, detail="Board appeal list exceeds 200; contact the administrator.")
    result = []
    seen = set()
    for appeal in q:
        if appeal.id in seen:
            continue
        seen.add(appeal.id)
        # In addition to the scoped join, check the current board and
        # parent case at read time. Archive and role revocation fail closed.
        try:
            _board_scope(
                db, actor=actor, association_id=appeal.association_id,
                property_id=appeal.property_id,
            )
            _case(
                db, org_id=actor.organization_id,
                association_id=appeal.association_id,
                property_id=appeal.property_id, case_id=appeal.case_id,
            )
        except HTTPException:
            continue
        fine = _fine(
            db, actor.organization_id, appeal.association_id,
            appeal.property_id, appeal.case_id,
        )
        if fine is None or fine.id != appeal.fine_id or fine.member_user_id is None:
            continue
        has_evidence = False
        if appeal.supporting_attachment_id is not None:
            try:
                _private_case_proof(
                    db, org=actor.organization_id,
                    association_id=appeal.association_id,
                    property_id=appeal.property_id,
                    case_id=appeal.case_id,
                    attachment_id=appeal.supporting_attachment_id,
                )
            except HTTPException:
                pass
            else:
                has_evidence = True
        result.append(HOABoardFineAppealOut(
            association_id=appeal.association_id,
            property_id=appeal.property_id, case_id=appeal.case_id,
            fine_id=fine.id, appeal_id=appeal.id,
            received_on=appeal.received_on,
            member_user_id=fine.member_user_id,
            appeal_reason=appeal.appeal_reason,
            has_private_evidence=has_evidence,
        ))
        if len(result) > 100:
            raise HTTPException(status_code=422, detail="Board appeal list exceeds 100; contact the administrator.")
    response.headers["Cache-Control"] = "no-store"
    return result


class HOABoardFinalFineAppealOut(BaseModel):
    association_id: int
    property_id: int
    case_id: int
    fine_id: int
    appeal_id: int
    outcome: Literal["UPHELD", "VACATED"]
    decided_on: date
    notification_status: Literal[
        "PENDING", "SENDING", "FAILED", "TEST_ONLY", "SMTP_ACCEPTED"
    ] | None = None
    has_private_evidence: bool = False


@router.get("/my-final-fine-appeals",
            response_model=list[HOABoardFinalFineAppealOut])
def my_board_final_fine_appeals(
    response: Response, db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Final outcomes for the caller's LIVE verified, paid-HOA board seat only.

    No private appeal reason, email address, template text, generic contact
    access or broad staff property permission is exposed.
    """
    actor = current_user
    if (actor.organization_id is None or not actor.is_active
        or actor.deleted_at is not None or not actor.is_verified):
        raise HTTPException(status_code=403, detail="Verified board login required.")
    org = db.query(Organization.id).filter(
        Organization.id == actor.organization_id,
        Organization.is_active.is_(True), Organization.deleted_at.is_(None),
    ).first()
    if org is None:
        raise HTTPException(status_code=403, detail="Organization inactive.")
    grants = {item.key: item for item in resolve_customer_features(db, user=actor)}
    if any(
        (value := grants.get(key)) is None
        or not (value.release_allowed and value.entitlement_allowed
                and value.org_config_allowed)
        for key in HOA_GATES
    ):
        raise HTTPException(status_code=404, detail="HOA board module unavailable.")
    rows = db.query(HOAFineAppeal).join(
        HOABoardSeat, and_(
            HOABoardSeat.organization_id == HOAFineAppeal.organization_id,
            HOABoardSeat.association_id == HOAFineAppeal.association_id,
            HOABoardSeat.property_id == HOAFineAppeal.property_id,
        ),
    ).filter(
        HOAFineAppeal.organization_id == actor.organization_id,
        HOAFineAppeal.status.in_(("UPHELD", "VACATED")),
        HOABoardSeat.organization_id == actor.organization_id,
        HOABoardSeat.authorized_user_id == actor.id,
        HOABoardSeat.is_active.is_(True),
        HOABoardSeat.decision_authorized.is_(True),
        HOABoardSeat.staff_voting_eligible.is_(True),
    ).order_by(HOAFineAppeal.id.desc()).limit(201).all()
    if len(rows) > 200:
        raise HTTPException(status_code=422, detail="Board final appeal history exceeds 200.")
    found = []
    seen = set()
    for appeal in rows:
        if appeal.id in seen:
            continue
        seen.add(appeal.id)
        try:
            org_id, assoc, _ = _board_scope(
                db, actor=actor, association_id=appeal.association_id,
                property_id=appeal.property_id,
            )
            _case(
                db, org_id=org_id, association_id=assoc.id,
                property_id=appeal.property_id, case_id=appeal.case_id,
            )
        except HTTPException:
            continue
        fine = _fine(
            db, org_id, assoc.id, appeal.property_id, appeal.case_id,
        )
        if (fine is None or fine.id != appeal.fine_id
            or fine.member_user_id is None
            or fine.member_user_id != appeal.member_user_id
            or appeal.decided_on is None
            or appeal.decision_board_seat_id is None):
            continue
        notification = db.query(HOAFineAppealNotification).filter(
            HOAFineAppealNotification.organization_id == org_id,
            HOAFineAppealNotification.association_id == assoc.id,
            HOAFineAppealNotification.property_id == appeal.property_id,
            HOAFineAppealNotification.case_id == appeal.case_id,
            HOAFineAppealNotification.fine_id == fine.id,
            HOAFineAppealNotification.appeal_id == appeal.id,
        ).first()
        has_evidence = False
        if appeal.supporting_attachment_id is not None:
            try:
                _private_case_proof(
                    db, org=org_id, association_id=assoc.id,
                    property_id=appeal.property_id, case_id=appeal.case_id,
                    attachment_id=appeal.supporting_attachment_id,
                )
            except HTTPException:
                pass
            else:
                has_evidence = True
        found.append(HOABoardFinalFineAppealOut(
            association_id=assoc.id, property_id=appeal.property_id,
            case_id=appeal.case_id, fine_id=fine.id, appeal_id=appeal.id,
            outcome=appeal.status, decided_on=appeal.decided_on,
            notification_status=notification.status if notification else None,
            has_private_evidence=has_evidence,
        ))
        if len(found) > 100:
            raise HTTPException(status_code=422, detail="Board final appeal list exceeds 100.")
    response.headers["Cache-Control"] = "no-store"
    return found


@router.get("/fine-appeals/{appeal_id}/supporting-evidence")
def download_board_appeal_evidence(
    appeal_id: int, db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Download ONLY current private proof of an open or final appeal for its board.

    No staff property permission is granted to the board login; every read
    checks live board delegation, paid HOA and attachment release, parent
    case, fine, private case-evidence index and file storage.
    """
    actor = current_user
    if actor.organization_id is None or not actor.is_active or actor.deleted_at is not None:
        raise HTTPException(status_code=403, detail="Verified board login required.")
    appeal = db.query(HOAFineAppeal).filter(
        HOAFineAppeal.id == appeal_id,
        HOAFineAppeal.organization_id == actor.organization_id,
        HOAFineAppeal.status.in_(("OPEN", "UPHELD", "VACATED")),
    ).first()
    if appeal is None or appeal.supporting_attachment_id is None:
        raise HTTPException(status_code=404, detail="Appeal evidence not found.")
    org, association, _ = _board_scope(
        db, actor=actor, association_id=appeal.association_id,
        property_id=appeal.property_id,
    )
    _require_attachment_feature(db, actor)
    _case(
        db, org_id=org, association_id=association.id,
        property_id=appeal.property_id, case_id=appeal.case_id,
    )
    fine = _fine(
        db, org, association.id, appeal.property_id, appeal.case_id,
    )
    if fine is None or fine.id != appeal.fine_id or fine.member_user_id != appeal.member_user_id:
        raise HTTPException(status_code=404, detail="Appeal evidence not found.")
    proof = _private_case_proof(
        db, org=org, association_id=association.id,
        property_id=appeal.property_id, case_id=appeal.case_id,
        attachment_id=appeal.supporting_attachment_id,
    )
    try:
        file_path = attachment_path(proof.storage_key)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Private appeal file not found.") from exc
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Private appeal file not found.")
    return FileResponse(
        file_path, media_type=proof.content_type or "application/octet-stream",
        filename=proof.original_name,
        headers={"Cache-Control": "private, no-store"},
    )
