"""Authenticated board portal: enumerate ONLY live association meetings for this board seat.

A board delegation allows this read without granting organization-wide property
permissions. No staff notes outside the member's association/property scope
and no vote, charge, notice or unverified contact-to-login inference.
"""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.contact import Contact
from app.models.hoa_association import HOAAssociation, HOAContactLink, HOAPropertyMembership
from app.models.hoa_board import HOABoardSeat
from app.models.hoa_meeting_draft import HOAMeetingDraft
from app.models.property import Property
from app.models.user import Organization, User
from app.routers.auth import get_current_user
from app.routers.hoa_arc_board_decisions import HOA_GATES
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
