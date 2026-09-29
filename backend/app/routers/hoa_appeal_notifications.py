"""Optional authorized fine-appeal outcome email, using existing letter templates and SMTP.

A final board disposition is the sole outcome source. Sending is an independent
explicit action: it never posts or reverses accounting. SMTP acceptance never
proves recipient delivery or statutory notice service.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core import email as email_service
from app.core.database import get_db
from app.models.hoa_fine_appeal_notification import HOAFineAppealNotification
from app.models.hoa_violation_fine_appeal import HOAFineAppeal
from app.models.hoa_violation_recipient import HOAViolationRecipientDraft
from app.models.letter_template import LetterTemplate
from app.models.property import Property
from app.models.user import Organization, User
from app.routers.auth import get_current_user
from app.routers.hoa_arc_board_decisions import _board_scope
from app.routers.hoa_violation_fines import _fine
from app.routers.hoa_violation_recipients import _matched_contact, _prerequisites
from app.schemas.hoa_appeal_notification import (
    HOAAppealNotificationIn, HOAAppealNotificationOut, HOAAppealTemplateOut,
)
from app.services.audit import append_audit_log
from app.services.letters import TOKEN, render_plain, validate_letter

router = APIRouter(prefix="/api/hoa/associations", tags=["HOA appeal outcome email"])
MAX_ATTEMPTS = 20


def _scope(db, actor, association_id, property_id, case_id, *, write):
    org, assoc, case = _prerequisites(
        db, actor=actor, association_id=association_id,
        property_id=property_id, case_id=case_id, write=write,
    )
    return org, assoc, case


def _authorized(db, actor, association_id, property_id, case_id):
    org, assoc, case = _scope(
        db, actor, association_id, property_id, case_id, write=True,
    )
    _, _, seat = _board_scope(
        db, actor=actor, association_id=assoc.id, property_id=property_id,
    )
    return org, assoc, case, seat


def _appeal(db, org, assoc, prop, case, appeal_id):
    fine = _fine(db, org, assoc, prop, case)
    if fine is None:
        raise HTTPException(status_code=404, detail="Scoped fine not found.")
    row = db.query(HOAFineAppeal).filter(
        HOAFineAppeal.id == appeal_id,
        HOAFineAppeal.organization_id == org,
        HOAFineAppeal.association_id == assoc,
        HOAFineAppeal.property_id == prop,
        HOAFineAppeal.case_id == case,
        HOAFineAppeal.fine_id == fine.id,
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Scoped fine appeal not found.")
    return fine, row


def _recipient(db, *, org, assoc, prop, case, fine, appeal):
    if (appeal.status not in {"UPHELD", "VACATED"}
        or appeal.decided_on is None or appeal.decision_board_seat_id is None):
        raise HTTPException(status_code=409, detail="A final board appeal decision is required.")
    if fine.member_user_id is None or fine.contact_link_id is None or (
        fine.member_user_id != appeal.member_user_id
    ):
        raise HTTPException(status_code=409, detail="Recorded fine member identity is unavailable.")
    record = db.query(HOAViolationRecipientDraft).filter(
        HOAViolationRecipientDraft.organization_id == org,
        HOAViolationRecipientDraft.association_id == assoc,
        HOAViolationRecipientDraft.property_id == prop,
        HOAViolationRecipientDraft.case_id == case,
        HOAViolationRecipientDraft.is_active.is_(True),
        HOAViolationRecipientDraft.contact_link_id == fine.contact_link_id,
        HOAViolationRecipientDraft.matched_user_id == fine.member_user_id,
    ).first()
    if record is None:
        raise HTTPException(status_code=409, detail="Original responsible recipient is no longer verified.")
    link, _, member = _matched_contact(
        db, org=org, association_id=assoc, property_id=prop,
        contact_link_id=fine.contact_link_id,
    )
    if member.id != fine.member_user_id or not (member.email or "").strip():
        raise HTTPException(status_code=409, detail="Original responsible member has changed.")
    return link, member


def _template(db, org, template_id):
    template = db.query(LetterTemplate).filter(
        LetterTemplate.id == template_id,
        LetterTemplate.organization_id == org,
        LetterTemplate.is_active.is_(True),
        LetterTemplate.category == "CUSTOM",
        LetterTemplate.title.ilike("HOA Appeal:%"),
    ).first()
    if template is None:
        raise HTTPException(status_code=404, detail="Active association appeal letter template not found.")
    validate_letter(template.subject, template.body)
    if (set(TOKEN.findall(template.subject + template.body))
        - {"organization_name", "property_name"}):
        raise HTTPException(status_code=422, detail="Only organization and property merge tags are allowed for appeals.")
    if "\n" in template.subject or "\r" in template.subject:
        raise HTTPException(status_code=422, detail="Email subject must have one line.")
    return template


def _render(db, *, template, org, prop, appeal):
    organization = db.get(Organization, org)
    property_row = db.get(Property, prop)
    if organization is None or property_row is None:
        raise HTTPException(status_code=404, detail="Scoped association property not found.")
    values = {"organization_name": organization.name, "property_name": property_row.name}
    subject = render_plain(template.subject, values)
    body = render_plain(template.body, values)
    body += (
        "\n\nRecorded final association board appeal outcome: " + appeal.status +
        "\nAppeal reference: #" + str(appeal.id) +
        "\nDecision date: " + appeal.decided_on.isoformat() +
        "\nThis email does not create or reverse a financial transaction, "
        "confirm a refund, prove inbox delivery, or establish statutory notice service."
    )
    return subject, body


def _out(row):
    return HOAAppealNotificationOut(
        id=row.id, appeal_id=row.appeal_id, template_id=row.template_id,
        outcome=row.outcome_snapshot, status=row.status,
        attempt_count=row.attempt_count, smtp_accepted_at=row.smtp_accepted_at,
    )


def _delivery(db, org, assoc, prop, case, appeal_id, delivery_id=None, *, lock=False):
    query = db.query(HOAFineAppealNotification).filter(
        HOAFineAppealNotification.organization_id == org,
        HOAFineAppealNotification.association_id == assoc,
        HOAFineAppealNotification.property_id == prop,
        HOAFineAppealNotification.case_id == case,
        HOAFineAppealNotification.appeal_id == appeal_id,
    )
    if delivery_id is not None:
        query = query.filter(HOAFineAppealNotification.id == delivery_id)
    return (query.with_for_update() if lock else query).first()


def _dispatch(db, *, actor, association_id, property_id, case_id, appeal_id, delivery_id):
    org, assoc, case, _ = _authorized(
        db, actor, association_id, property_id, case_id,
    )
    row = _delivery(
        db, org, assoc.id, property_id, case.id, appeal_id, delivery_id,
        lock=True,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Appeal email not found.")
    if row.status == "SMTP_ACCEPTED":
        return _out(row)
    if (row.status == "SENDING" and row.last_attempt_at
        and datetime.utcnow() - row.last_attempt_at < timedelta(minutes=10)):
        raise HTTPException(status_code=409, detail="Appeal email attempt is in progress.")
    if row.attempt_count >= MAX_ATTEMPTS:
        raise HTTPException(status_code=409, detail="Appeal email retry limit reached.")
    fine, appeal = _appeal(
        db, org, assoc.id, property_id, case.id, appeal_id,
    )
    link, member = _recipient(
        db, org=org, assoc=assoc.id, prop=property_id,
        case=case.id, fine=fine, appeal=appeal,
    )
    if (row.fine_id != fine.id or row.outcome_snapshot != appeal.status
        or row.contact_link_id != link.id or row.recipient_user_id != member.id
        or row.recipient_email != member.email.strip().lower()):
        raise HTTPException(status_code=409, detail="Outcome or verified recipient has changed.")
    # Durable claim before SMTP. Crash recovery may cause at-least-once delivery;
    # neither retry nor SMTP acceptance proves actual receipt.
    row.status = "SENDING"
    row.attempt_count += 1
    row.last_attempt_at = datetime.utcnow()
    append_audit_log(
        db, organization_id=org, user_id=actor.id,
        entity_type="hoa_fine_appeal_notification", entity_id=row.id,
        action="appeal_outcome_email_attempted",
        new_value={"association_id": assoc.id, "property_id": property_id,
                   "appeal_id": appeal_id, "attempt": row.attempt_count},
    )
    db.commit()
    test_mode = email_service.settings.EMAIL_MODE == "console"
    try:
        email_service.send_email(
            to=row.recipient_email, subject=row.subject_snapshot,
            body=row.body_snapshot, organization_id=org, db=db,
        )
    except Exception:
        row.status = "FAILED"
        action = "appeal_outcome_email_failed"
    else:
        row.status = "TEST_ONLY" if test_mode else "SMTP_ACCEPTED"
        row.smtp_accepted_at = None if test_mode else datetime.utcnow()
        action = "appeal_outcome_email_test_only" if test_mode else "appeal_outcome_email_smtp_accepted"
    append_audit_log(
        db, organization_id=org, user_id=actor.id,
        entity_type="hoa_fine_appeal_notification", entity_id=row.id,
        action=action,
        new_value={"association_id": assoc.id, "property_id": property_id,
                   "appeal_id": appeal_id, "attempt": row.attempt_count},
    )
    db.commit()
    db.refresh(row)
    return _out(row)


@router.get("/{association_id}/staff-cases/{case_id}/fine/appeal-email-templates",
            response_model=list[HOAAppealTemplateOut])
def list_appeal_email_templates(
    association_id: int, case_id: int, response: Response,
    property_id: int = Query(ge=1), db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org, _, _ = _scope(
        db, current_user, association_id, property_id, case_id, write=False,
    )
    templates = db.query(LetterTemplate).filter(
        LetterTemplate.organization_id == org,
        LetterTemplate.is_active.is_(True),
        LetterTemplate.category == "CUSTOM",
        LetterTemplate.title.ilike("HOA Appeal:%"),
    ).order_by(LetterTemplate.id).limit(101).all()
    if len(templates) > 100:
        raise HTTPException(status_code=422, detail="Too many appeal email templates.")
    response.headers["Cache-Control"] = "no-store"
    return [HOAAppealTemplateOut(
        id=row.id, title=row.title, subject=row.subject, body=row.body,
    ) for row in templates]


@router.get("/{association_id}/staff-cases/{case_id}/fine/appeals/{appeal_id}/notifications",
            response_model=list[HOAAppealNotificationOut])
def list_appeal_notifications(
    association_id: int, case_id: int, appeal_id: int, response: Response,
    property_id: int = Query(ge=1), db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org, assoc, case = _scope(
        db, current_user, association_id, property_id, case_id, write=False,
    )
    _appeal(db, org, assoc.id, property_id, case.id, appeal_id)
    row = _delivery(db, org, assoc.id, property_id, case.id, appeal_id)
    response.headers["Cache-Control"] = "no-store"
    return [_out(row)] if row is not None else []


@router.post("/{association_id}/staff-cases/{case_id}/fine/appeals/{appeal_id}/notifications",
             response_model=HOAAppealNotificationOut, status_code=201)
def send_appeal_notification(
    association_id: int, case_id: int, appeal_id: int,
    payload: HOAAppealNotificationIn, db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org, assoc, case, seat = _authorized(
        db, current_user, association_id, payload.property_id, case_id,
    )
    fine, appeal = _appeal(
        db, org, assoc.id, payload.property_id, case.id, appeal_id,
    )
    link, member = _recipient(
        db, org=org, assoc=assoc.id, prop=payload.property_id,
        case=case.id, fine=fine, appeal=appeal,
    )
    existing = db.query(HOAFineAppealNotification).filter(
        HOAFineAppealNotification.organization_id == org,
        HOAFineAppealNotification.request_key == payload.request_key,
    ).with_for_update().first()
    if existing is not None:
        if (existing.appeal_id == appeal.id and existing.template_id == payload.template_id
            and existing.association_id == assoc.id and existing.property_id == payload.property_id
            and existing.case_id == case.id):
            return _out(existing)
        raise HTTPException(status_code=409, detail="Appeal email request key already used.")
    if _delivery(db, org, assoc.id, payload.property_id, case.id, appeal.id):
        raise HTTPException(status_code=409, detail="Appeal outcome already has an email request.")
    template = _template(db, org, payload.template_id)
    subject, body = _render(
        db, template=template, org=org, prop=payload.property_id, appeal=appeal,
    )
    row = HOAFineAppealNotification(
        organization_id=org, association_id=assoc.id,
        property_id=payload.property_id, case_id=case.id, fine_id=fine.id,
        appeal_id=appeal.id, template_id=template.id,
        contact_link_id=link.id, recipient_user_id=member.id,
        recipient_email=member.email.strip().lower(),
        board_seat_id=seat.id, requested_by_id=current_user.id,
        request_key=payload.request_key, subject_snapshot=subject,
        body_snapshot=body, outcome_snapshot=appeal.status, status="PENDING",
    )
    db.add(row)
    try:
        db.flush()
        append_audit_log(
            db, organization_id=org, user_id=current_user.id,
            entity_type="hoa_fine_appeal_notification", entity_id=row.id,
            action="appeal_outcome_email_queued",
            new_value={"association_id": assoc.id, "property_id":payload.property_id,
                       "case_id":case.id, "appeal_id":appeal.id,
                       "board_seat_id":seat.id, "template_id":template.id},
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Concurrent appeal email request.") from exc
    return _dispatch(
        db, actor=current_user, association_id=assoc.id,
        property_id=payload.property_id, case_id=case.id,
        appeal_id=appeal.id, delivery_id=row.id,
    )


@router.post("/{association_id}/staff-cases/{case_id}/fine/appeals/{appeal_id}/notifications/{delivery_id}/retry",
             response_model=HOAAppealNotificationOut)
def retry_appeal_notification(
    association_id: int, case_id: int, appeal_id: int, delivery_id: int,
    property_id: int = Query(ge=1), db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _dispatch(
        db, actor=current_user, association_id=association_id,
        property_id=property_id, case_id=case_id,
        appeal_id=appeal_id, delivery_id=delivery_id,
    )
