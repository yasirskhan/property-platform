"""Authorized HOA correspondence email, preserving independent legal service rules.

An active association-authorized board login explicitly approves an exact
current private correspondence revision. This sends the approved text using
existing mail transport; SMTP acceptance is not proof of legal service.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core import email as email_service
from app.core.database import get_db
from app.models.hoa_violation_correspondence import HOAViolationCorrespondenceDraft
from app.models.hoa_violation_notice_delivery import HOAViolationNoticeDelivery
from app.models.user import User
from app.routers.auth import get_current_user
from app.routers.hoa_arc_board_decisions import _board_scope
from app.routers.hoa_violation_recipients import _prerequisites, _out as recipient_out
from app.routers.hoa_violation_correspondence import _data
from app.schemas.hoa_violation_notice_delivery import (
    HOAViolationNoticeSendIn, HOAViolationNoticeDeliveryOut,
)
from app.services.audit import append_audit_log

router = APIRouter(prefix="/api/hoa/associations", tags=["HOA authorized case email"])
MAX_ATTEMPTS = 20


def _out(row: HOAViolationNoticeDelivery):
    return HOAViolationNoticeDeliveryOut(
        id=row.id, correspondence_id=row.correspondence_id,
        correspondence_revision=row.correspondence_revision,
        policy_revision=row.policy_revision, status=row.status,
        attempt_count=row.attempt_count, smtp_accepted_at=row.smtp_accepted_at,
        board_seat_id=row.board_seat_id,
    )


def _scope(db, actor, association_id, property_id, case_id):
    # Staff access and board authorization are independent, BOTH required
    # for an explicit staff-produced, association-authorized send.
    org, assoc, case = _prerequisites(
        db, actor=actor, association_id=association_id,
        property_id=property_id, case_id=case_id, write=True,
    )
    _, _, seat = _board_scope(
        db, actor=actor, association_id=assoc.id, property_id=property_id,
    )
    return org, assoc, case, seat


def _draft(db, org, assoc, prop, case, draft_id, revision, policy_revision):
    row = db.query(HOAViolationCorrespondenceDraft).filter(
        HOAViolationCorrespondenceDraft.id == draft_id,
        HOAViolationCorrespondenceDraft.organization_id == org,
        HOAViolationCorrespondenceDraft.association_id == assoc,
        HOAViolationCorrespondenceDraft.property_id == prop,
        HOAViolationCorrespondenceDraft.case_id == case,
        HOAViolationCorrespondenceDraft.revision == revision,
        HOAViolationCorrespondenceDraft.policy_revision == policy_revision,
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Exact scoped correspondence revision not found.")
    latest = db.query(HOAViolationCorrespondenceDraft.id).filter(
        HOAViolationCorrespondenceDraft.organization_id == org,
        HOAViolationCorrespondenceDraft.association_id == assoc,
        HOAViolationCorrespondenceDraft.property_id == prop,
        HOAViolationCorrespondenceDraft.case_id == case,
    ).order_by(HOAViolationCorrespondenceDraft.revision.desc()).first()
    if latest is None or latest.id != row.id:
        raise HTTPException(status_code=409, detail="A newer correspondence revision exists.")
    return row


def _current(db, org, assoc, case, row):
    recipient, policy = _data(
        db, org=org, assoc_id=assoc, property_id=row.property_id,
        case_id=case.id,
    )
    if (case.stage not in {"NOTICE_DRAFT", "CURE_TRACKING", "HEARING_PLANNED"}
        or case.stage != row.stage):
        raise HTTPException(status_code=409, detail="Current case stage does not permit this email.")
    if (policy is None or policy.id != row.policy_id
        or policy.revision != row.policy_revision
        or not policy.draft_notice_text or policy.cure_preparation_days is None):
        raise HTTPException(status_code=409, detail="Current configured notice and cure procedure required.")
    if (recipient is None or not recipient.is_active
        or recipient.id != row.recipient_reference_id
        or recipient.contact_link_id != row.contact_link_id
        or recipient.matched_user_id != row.matched_user_id):
        raise HTTPException(status_code=409, detail="Correspondence recipient changed.")
    live = recipient_out(db, recipient)
    if live.matched_user_id != row.matched_user_id:
        raise HTTPException(status_code=409, detail="Recipient identity changed.")
    user = db.get(User, row.matched_user_id)
    if (user is None or not user.is_active or not user.is_verified
        or user.deleted_at is not None or user.organization_id != org
        or not (user.email or "").strip()):
        raise HTTPException(status_code=409, detail="Verified email recipient unavailable.")
    return user.email.strip().lower()


def _record(db, org, assoc, prop, case, delivery_id, lock=False):
    query = db.query(HOAViolationNoticeDelivery).filter(
        HOAViolationNoticeDelivery.id == delivery_id,
        HOAViolationNoticeDelivery.organization_id == org,
        HOAViolationNoticeDelivery.association_id == assoc,
        HOAViolationNoticeDelivery.property_id == prop,
        HOAViolationNoticeDelivery.case_id == case,
    )
    row = (query.with_for_update() if lock else query).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Association correspondence email not found.")
    return row


def _dispatch(db, *, actor, org, assoc, case, delivery):
    delivery = _record(
        db, org, assoc, case.property_id, case.id, delivery.id, lock=True,
    )
    if delivery.status == "SMTP_ACCEPTED":
        return _out(delivery)
    if (delivery.status == "SENDING" and delivery.last_attempt_at
        and datetime.utcnow() - delivery.last_attempt_at < timedelta(minutes=10)):
        raise HTTPException(status_code=409, detail="Correspondence email attempt is in progress.")
    if delivery.attempt_count >= MAX_ATTEMPTS:
        raise HTTPException(status_code=409, detail="Correspondence retry limit reached.")
    draft = _draft(
        db, org, assoc, case.property_id, case.id,
        delivery.correspondence_id, delivery.correspondence_revision,
        delivery.policy_revision,
    )
    email = _current(db, org, assoc, case, draft)
    if (email != delivery.recipient_email
        or draft.matched_user_id != delivery.recipient_user_id
        or draft.contact_link_id != delivery.contact_link_id):
        raise HTTPException(status_code=409, detail="Recorded email recipient no longer matches.")
    delivery.status = "SENDING"
    delivery.attempt_count += 1
    delivery.last_attempt_at = datetime.utcnow()
    append_audit_log(
        db, organization_id=org, user_id=actor.id,
        entity_type="hoa_violation_notice_delivery", entity_id=delivery.id,
        action="authorized_correspondence_email_attempt",
        new_value={"association_id": assoc, "property_id": case.property_id,
                   "case_id": case.id, "revision": draft.revision,
                   "attempt": delivery.attempt_count},
    )
    db.commit()
    test_mode = email_service.settings.EMAIL_MODE == "console"
    try:
        email_service.send_email(
            to=delivery.recipient_email,
            subject=draft.subject,
            body=draft.body,
            organization_id=org, db=db,
        )
    except Exception:
        delivery.status = "FAILED"
        action = "authorized_correspondence_email_failed"
    else:
        delivery.status = "TEST_ONLY" if test_mode else "SMTP_ACCEPTED"
        delivery.smtp_accepted_at = None if test_mode else datetime.utcnow()
        action = ("authorized_correspondence_email_test_only" if test_mode
                  else "authorized_correspondence_email_smtp_accepted")
    append_audit_log(
        db, organization_id=org, user_id=actor.id,
        entity_type="hoa_violation_notice_delivery", entity_id=delivery.id,
        action=action,
        new_value={"association_id": assoc, "property_id": case.property_id,
                   "case_id": case.id, "attempt": delivery.attempt_count},
    )
    db.commit()
    db.refresh(delivery)
    return _out(delivery)


@router.get("/{association_id}/staff-cases/{case_id}/notice-emails",
            response_model=list[HOAViolationNoticeDeliveryOut])
def list_notice_emails(
    association_id: int, case_id: int, response: Response,
    property_id: int = Query(ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org, assoc, case = _prerequisites(
        db, actor=current_user, association_id=association_id,
        property_id=property_id, case_id=case_id, write=False,
    )
    rows = db.query(HOAViolationNoticeDelivery).filter(
        HOAViolationNoticeDelivery.organization_id == org,
        HOAViolationNoticeDelivery.association_id == assoc.id,
        HOAViolationNoticeDelivery.property_id == property_id,
        HOAViolationNoticeDelivery.case_id == case.id,
    ).order_by(HOAViolationNoticeDelivery.id).limit(51).all()
    if len(rows) > 50:
        raise HTTPException(status_code=422, detail="Email history display limit reached.")
    response.headers["Cache-Control"] = "no-store"
    return [_out(row) for row in rows]


@router.post("/{association_id}/staff-cases/{case_id}/correspondence/{draft_id}/email",
             response_model=HOAViolationNoticeDeliveryOut, status_code=201)
def send_notice_email(
    association_id: int, case_id: int, draft_id: int,
    payload: HOAViolationNoticeSendIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org, assoc, case, seat = _scope(
        db, current_user, association_id, payload.property_id, case_id,
    )
    existing = db.query(HOAViolationNoticeDelivery).filter(
        HOAViolationNoticeDelivery.organization_id == org,
        HOAViolationNoticeDelivery.request_key == payload.request_key,
    ).with_for_update().first()
    if existing is not None:
        if (existing.association_id != assoc.id
            or existing.property_id != case.property_id
            or existing.case_id != case.id
            or existing.correspondence_id != draft_id
            or existing.correspondence_revision != payload.correspondence_revision
            or existing.policy_revision != payload.policy_revision):
            raise HTTPException(status_code=409, detail="Email request key already used.")
        return _out(existing)
    draft = _draft(
        db, org, assoc.id, case.property_id, case.id,
        draft_id, payload.correspondence_revision, payload.policy_revision,
    )
    email = _current(db, org, assoc.id, case, draft)
    prior = db.query(HOAViolationNoticeDelivery).filter(
        HOAViolationNoticeDelivery.correspondence_id == draft.id,
    ).first()
    if prior is not None:
        raise HTTPException(status_code=409, detail="This correspondence revision already has an email request.")
    row = HOAViolationNoticeDelivery(
        organization_id=org, association_id=assoc.id,
        property_id=case.property_id, case_id=case.id,
        correspondence_id=draft.id, correspondence_revision=draft.revision,
        policy_id=draft.policy_id, policy_revision=draft.policy_revision,
        contact_link_id=draft.contact_link_id, recipient_user_id=draft.matched_user_id,
        recipient_email=email, board_seat_id=seat.id,
        requested_by_id=current_user.id, request_key=payload.request_key,
        status="PENDING",
    )
    db.add(row)
    try:
        db.flush()
        append_audit_log(
            db, organization_id=org, user_id=current_user.id,
            entity_type="hoa_violation_notice_delivery", entity_id=row.id,
            action="authorized_correspondence_email_requested",
            new_value={"association_id": assoc.id, "property_id": case.property_id,
                       "case_id": case.id, "correspondence_id": draft.id,
                       "board_seat_id": seat.id, "policy_revision": draft.policy_revision},
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Concurrent duplicate email request.") from exc
    return _dispatch(db, actor=current_user, org=org, assoc=assoc.id, case=case, delivery=row)


@router.post("/{association_id}/staff-cases/{case_id}/notice-emails/{delivery_id}/retry",
             response_model=HOAViolationNoticeDeliveryOut)
def retry_notice_email(
    association_id: int, case_id: int, delivery_id: int,
    property_id: int = Query(ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org, assoc, case, seat = _scope(
        db, current_user, association_id, property_id, case_id,
    )
    row = _record(db, org, assoc.id, property_id, case.id, delivery_id)
    if row.status == "SMTP_ACCEPTED":
        return _out(row)
    return _dispatch(db, actor=current_user, org=org, assoc=assoc.id,
                     case=case, delivery=row)
