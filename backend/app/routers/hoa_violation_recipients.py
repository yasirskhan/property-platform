"""Verified-login recipient reference for a staff HOA violation case.

This is only a potential correspondence recipient. It never serves a
statutory notice, certifies a debtor, or creates a fee/GL entry.
"""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.contact import Contact
from app.models.hoa_association import HOAContactLink
from app.models.hoa_violation_recipient import HOAViolationRecipientDraft
from app.models.user import User
from app.routers.auth import get_current_user
from app.routers.hoa_assessments import _scope
from app.routers.hoa_violation_cases import _case
from app.schemas.hoa_violation_recipient import HOAViolationRecipientIn, HOAViolationRecipientOut
from app.services.audit import append_audit_log
from app.services.menu_resolver import permission_allows_user

router = APIRouter(prefix="/api/hoa/associations", tags=["HOA case correspondence preparation"])


def _prerequisites(
    db: Session, *, actor: User, association_id: int, property_id: int,
    case_id: int, write: bool,
):
    org, assoc = _scope(
        db, actor=actor, association_id=association_id,
        property_id=property_id, write=write,
    )
    if not permission_allows_user(db, user=actor, menu_key="PEOPLE.CONTACTS"):
        raise HTTPException(status_code=403, detail="Contact permission required.")
    case = _case(
        db, org_id=org, association_id=assoc.id,
        property_id=property_id, case_id=case_id,
    )
    return org, assoc, case


def _matched_contact(db: Session, *, org: int, association_id: int,
                     property_id: int, contact_link_id: int):
    result = db.query(HOAContactLink, Contact, User).join(
        Contact, Contact.id == HOAContactLink.contact_id,
    ).join(
        User, func.lower(func.trim(User.email)) == func.lower(func.trim(Contact.email)),
    ).filter(
        HOAContactLink.id == contact_link_id,
        HOAContactLink.organization_id == org,
        HOAContactLink.association_id == association_id,
        HOAContactLink.property_id == property_id,
        HOAContactLink.is_active.is_(True),
        Contact.organization_id == org,
        Contact.is_active.is_(True),
        Contact.deleted_at.is_(None),
        Contact.email.is_not(None),
        User.organization_id == org,
        User.is_active.is_(True),
        User.is_verified.is_(True),
        User.deleted_at.is_(None),
    ).first()
    if result is None:
        raise HTTPException(status_code=409, detail="Same-scope contact needs a matching verified login.")
    return result


def _out(db: Session, row: HOAViolationRecipientDraft) -> HOAViolationRecipientOut:
    _, contact, user = _matched_contact(
        db, org=row.organization_id, association_id=row.association_id,
        property_id=row.property_id, contact_link_id=row.contact_link_id,
    )
    if user.id != row.matched_user_id:
        raise HTTPException(status_code=409, detail="Recorded recipient identity no longer matches.")
    return HOAViolationRecipientOut(
        id=row.id, case_id=row.case_id, property_id=row.property_id,
        contact_link_id=row.contact_link_id, contact_name=contact.display_name,
        matched_user_id=user.id, updated_at=row.updated_at,
    )


def _record(db: Session, *, org: int, assoc_id: int,
            property_id: int, case_id: int):
    return db.query(HOAViolationRecipientDraft).filter(
        HOAViolationRecipientDraft.organization_id == org,
        HOAViolationRecipientDraft.association_id == assoc_id,
        HOAViolationRecipientDraft.property_id == property_id,
        HOAViolationRecipientDraft.case_id == case_id,
    ).with_for_update().first()


@router.get("/{association_id}/staff-cases/{case_id}/recipient",
            response_model=HOAViolationRecipientOut | None)
def get_case_recipient(
    association_id: int, case_id: int, response: Response,
    property_id: int = Query(ge=1),
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org, assoc, case = _prerequisites(
        db, actor=current_user, association_id=association_id,
        property_id=property_id, case_id=case_id, write=False,
    )
    response.headers["Cache-Control"] = "no-store"
    record = _record(db, org=org, assoc_id=assoc.id,
                     property_id=property_id, case_id=case.id)
    if record is None or not record.is_active:
        return None
    return _out(db, record)


@router.put("/{association_id}/staff-cases/{case_id}/recipient",
            response_model=HOAViolationRecipientOut)
def set_case_recipient(
    association_id: int, case_id: int, payload: HOAViolationRecipientIn,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org, assoc, case = _prerequisites(
        db, actor=current_user, association_id=association_id,
        property_id=payload.property_id, case_id=case_id, write=True,
    )
    if case.stage == "CLOSED":
        raise HTTPException(status_code=409, detail="Closed case cannot change correspondence.")
    link, contact, user = _matched_contact(
        db, org=org, association_id=assoc.id, property_id=payload.property_id,
        contact_link_id=payload.contact_link_id,
    )
    record = _record(db, org=org, assoc_id=assoc.id,
                     property_id=payload.property_id, case_id=case.id)
    if record is not None and record.is_active and record.contact_link_id == link.id and record.matched_user_id == user.id:
        raise HTTPException(status_code=409, detail="Recipient reference already recorded.")
    action = "recipient_rerecorded" if record is not None else "recipient_recorded"
    if record is None:
        record = HOAViolationRecipientDraft(
            organization_id=org, association_id=assoc.id,
            property_id=payload.property_id, case_id=case.id,
            created_by_id=current_user.id,
        )
        db.add(record)
    record.contact_link_id = link.id
    record.matched_user_id = user.id
    record.is_active = True
    record.updated_by_id = current_user.id
    try:
        db.flush()
        append_audit_log(
            db, organization_id=org, user_id=current_user.id,
            entity_type="hoa_violation_recipient_draft", entity_id=record.id,
            action=action,
            new_value={
                "association_id": assoc.id, "property_id": payload.property_id,
                "case_id": case.id, "contact_link_id": link.id,
                "matched_user_id": user.id,
            },
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Recipient changed concurrently.") from exc
    db.refresh(record)
    return _out(db, record)


@router.delete("/{association_id}/staff-cases/{case_id}/recipient", status_code=204)
def clear_case_recipient(
    association_id: int, case_id: int, property_id: int = Query(ge=1),
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org, assoc, case = _prerequisites(
        db, actor=current_user, association_id=association_id,
        property_id=property_id, case_id=case_id, write=True,
    )
    if case.stage == "CLOSED":
        raise HTTPException(status_code=409, detail="Closed case cannot change correspondence.")
    record = _record(db, org=org, assoc_id=assoc.id,
                     property_id=property_id, case_id=case.id)
    if record is None or not record.is_active:
        raise HTTPException(status_code=404, detail="Recipient reference not found.")
    record.is_active = False
    record.updated_by_id = current_user.id
    db.flush()
    append_audit_log(
        db, organization_id=org, user_id=current_user.id,
        entity_type="hoa_violation_recipient_draft", entity_id=record.id,
        action="recipient_cleared",
        new_value={
            "association_id": assoc.id, "property_id": property_id,
            "case_id": case.id,
        },
    )
    db.commit()
    return Response(status_code=204, headers={"Cache-Control": "no-store"})
