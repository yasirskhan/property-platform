"""HOA board seat and quorum proposal registry.

A contact link is not an authenticated board identity; proposed eligibility is
not a legal right to vote. No effective vote, notice or accounting action.
"""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.contact import Contact
from app.models.hoa_association import HOAContactLink
from app.models.hoa_board import HOABoardRuleDraft, HOABoardSeat
from app.models.user import User
from app.routers.auth import get_current_user
from app.routers.hoa_associations import _contact_scope
from app.schemas.hoa_board import (
    HOABoardRosterOut, HOABoardRulesIn, HOABoardRulesOut,
    HOABoardSeatIn, HOABoardSeatOut,
)
from app.services.audit import append_audit_log

router = APIRouter(prefix="/api/hoa/associations", tags=["HOA board proposals"])


def _link(db: Session, org_id: int, association_id: int,
          property_id: int, link_id: int) -> tuple[HOAContactLink, Contact]:
    record = db.query(HOAContactLink, Contact).join(
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
    if record is None:
        raise HTTPException(status_code=404, detail="Active association contact not found.")
    return record


def _seat(db: Session, *, org_id: int, assoc_id: int, prop_id: int,
          seat_id: int) -> HOABoardSeat:
    row = db.query(HOABoardSeat).filter(
        HOABoardSeat.id == seat_id,
        HOABoardSeat.organization_id == org_id,
        HOABoardSeat.association_id == assoc_id,
        HOABoardSeat.property_id == prop_id,
        HOABoardSeat.is_active.is_(True),
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Proposed seat not found.")
    return row


def _seat_out(row: HOABoardSeat, contact: Contact) -> HOABoardSeatOut:
    return HOABoardSeatOut(
        id=row.id, property_id=row.property_id,
        contact_link_id=row.contact_link_id,
        contact_name=contact.display_name,
        proposed_role=row.proposed_role,
        staff_voting_eligible=row.staff_voting_eligible,
    )


def _rules_out(row: HOABoardRuleDraft) -> HOABoardRulesOut:
    return HOABoardRulesOut(
        id=row.id, property_id=row.property_id,
        proposed_quorum_min=row.proposed_quorum_min,
        proposed_approval_min=row.proposed_approval_min,
    )


def _audit(db: Session, *, actor: User, row, action: str) -> None:
    append_audit_log(
        db, organization_id=row.organization_id, user_id=actor.id,
        entity_type=("hoa_board_seat" if isinstance(row, HOABoardSeat)
                     else "hoa_board_rule_draft"),
        entity_id=row.id, action=action,
        new_value={"association_id": row.association_id,
                   "property_id": row.property_id},
    )


@router.get("/{association_id}/board-proposals", response_model=HOABoardRosterOut)
def get_board_proposals(
    association_id: int, response: Response,
    property_id: int = Query(ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org, assoc = _contact_scope(
        db, actor=current_user, association_id=association_id,
        property_id=property_id, write=False,
    )
    rows = db.query(HOABoardSeat, Contact).join(
        HOAContactLink, HOAContactLink.id == HOABoardSeat.contact_link_id,
    ).join(Contact, Contact.id == HOAContactLink.contact_id).filter(
        HOABoardSeat.organization_id == org,
        HOABoardSeat.association_id == assoc.id,
        HOABoardSeat.property_id == property_id,
        HOABoardSeat.is_active.is_(True),
        HOAContactLink.organization_id == org,
        HOAContactLink.association_id == assoc.id,
        HOAContactLink.property_id == property_id,
        HOAContactLink.is_active.is_(True),
        Contact.organization_id == org,
        Contact.is_active.is_(True),
        Contact.deleted_at.is_(None),
    ).order_by(HOABoardSeat.id).limit(101).all()
    if len(rows) > 100:
        raise HTTPException(status_code=422, detail="Too many staff board proposals.")
    rules = db.query(HOABoardRuleDraft).filter(
        HOABoardRuleDraft.organization_id == org,
        HOABoardRuleDraft.association_id == assoc.id,
        HOABoardRuleDraft.property_id == property_id,
        HOABoardRuleDraft.is_active.is_(True),
    ).first()
    response.headers["Cache-Control"] = "no-store"
    return HOABoardRosterOut(
        association_id=assoc.id, property_id=property_id,
        seats=[_seat_out(row, contact) for row, contact in rows],
        rules=_rules_out(rules) if rules else None,
    )


@router.post("/{association_id}/board-proposals/seats",
             response_model=HOABoardSeatOut, status_code=201)
def record_board_seat(
    association_id: int, payload: HOABoardSeatIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org, assoc = _contact_scope(
        db, actor=current_user, association_id=association_id,
        property_id=payload.property_id, write=True,
    )
    _, contact = _link(
        db, org, assoc.id, payload.property_id, payload.contact_link_id,
    )
    existing = db.query(HOABoardSeat).filter(
        HOABoardSeat.association_id == assoc.id,
        HOABoardSeat.property_id == payload.property_id,
        HOABoardSeat.contact_link_id == payload.contact_link_id,
    ).first()
    if existing is not None:
        raise HTTPException(status_code=409, detail="Seat proposal already recorded.")
    row = HOABoardSeat(
        organization_id=org, association_id=assoc.id,
        property_id=payload.property_id, contact_link_id=payload.contact_link_id,
        proposed_role=payload.proposed_role,
        staff_voting_eligible=payload.staff_voting_eligible,
        created_by_id=current_user.id, updated_by_id=current_user.id,
    )
    db.add(row)
    try:
        db.flush()
        _audit(db, actor=current_user, row=row, action="staff_seat_proposed")
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Seat proposal already recorded.") from exc
    db.refresh(row)
    return _seat_out(row, contact)


@router.delete("/{association_id}/board-proposals/seats/{seat_id}", status_code=204)
def archive_board_seat(
    association_id: int, seat_id: int,
    property_id: int = Query(ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org, assoc = _contact_scope(
        db, actor=current_user, association_id=association_id,
        property_id=property_id, write=True,
    )
    row = _seat(db, org_id=org, assoc_id=assoc.id,
                prop_id=property_id, seat_id=seat_id)
    row.is_active = False
    row.updated_by_id = current_user.id
    db.flush()
    _audit(db, actor=current_user, row=row, action="staff_seat_archived")
    db.commit()
    return Response(status_code=204, headers={"Cache-Control": "no-store"})


@router.put("/{association_id}/board-proposals/rules",
            response_model=HOABoardRulesOut)
def configure_proposed_board_rules(
    association_id: int, payload: HOABoardRulesIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org, assoc = _contact_scope(
        db, actor=current_user, association_id=association_id,
        property_id=payload.property_id, write=True,
    )
    row = db.query(HOABoardRuleDraft).filter(
        HOABoardRuleDraft.organization_id == org,
        HOABoardRuleDraft.association_id == assoc.id,
        HOABoardRuleDraft.property_id == payload.property_id,
    ).with_for_update().first()
    if row is not None and not row.is_active:
        raise HTTPException(status_code=409, detail="Archived board rule proposal cannot be restored.")
    if row is None:
        row = HOABoardRuleDraft(
            organization_id=org, association_id=assoc.id,
            property_id=payload.property_id,
        )
        db.add(row)
    row.proposed_quorum_min = payload.proposed_quorum_min
    row.proposed_approval_min = payload.proposed_approval_min
    row.updated_by_id = current_user.id
    try:
        db.flush()
        _audit(db, actor=current_user, row=row, action="staff_rules_configured")
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Board rules were updated concurrently.") from exc
    db.refresh(row)
    return _rules_out(row)
