"""Scoped, explicit email delivery of existing HOA documents.

This is document distribution, not statutory service. SMTP acceptance is not
proof of inbox delivery. A console-mode run does not transmit file bytes.
"""
from __future__ import annotations

import hashlib
import mimetypes
import re
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core import email as email_service
from app.core.database import get_db
from app.models.contact import Contact
from app.models.entity_attachment import EntityAttachment
from app.models.hoa_association import HOAContactLink
from app.models.hoa_document_delivery import HOADocumentDelivery
from app.models.hoa_governing_evidence import HOAGoverningEvidence
from app.models.user import User
from app.routers.auth import get_current_user
from app.routers.hoa_associations import _contact_scope
from app.routers.hoa_governing_evidence import _attachment, _require_attachment_feature
from app.schemas.hoa_document_delivery import (
    HOADocumentDeliveryOut, HOADocumentRecipientOut, HOADocumentSendIn,
)
from app.services.attachment_storage import attachment_path
from app.services.audit import append_audit_log

router = APIRouter(prefix="/api/hoa/associations", tags=["HOA document delivery"])
MAX_EMAIL_FILE_BYTES = 5 * 1024 * 1024
MAX_ATTEMPTS = 20


def _scope(db: Session, actor: User, association_id: int, property_id: int):
    org, association = _contact_scope(
        db, actor=actor, association_id=association_id,
        property_id=property_id, write=True,
    )
    _require_attachment_feature(db, actor)
    return org, association


def _source(db: Session, *, org: int, association_id: int,
            property_id: int, evidence_id: int):
    reference = db.query(HOAGoverningEvidence).filter(
        HOAGoverningEvidence.id == evidence_id,
        HOAGoverningEvidence.organization_id == org,
        HOAGoverningEvidence.association_id == association_id,
        HOAGoverningEvidence.property_id == property_id,
        HOAGoverningEvidence.is_active.is_(True),
    ).first()
    if reference is None:
        raise HTTPException(status_code=404, detail="Active scoped document reference not found.")
    document = _attachment(
        db, org_id=org, prop_id=property_id,
        attachment_id=reference.attachment_id,
    )
    return reference, document


def _recipient(db: Session, *, org: int, association_id: int,
               property_id: int, link_id: int):
    match = db.query(HOAContactLink, Contact).join(
        Contact, Contact.id == HOAContactLink.contact_id,
    ).filter(
        HOAContactLink.id == link_id,
        HOAContactLink.organization_id == org,
        HOAContactLink.association_id == association_id,
        HOAContactLink.property_id == property_id,
        HOAContactLink.is_active.is_(True),
        Contact.organization_id == org,
        Contact.is_active.is_(True),
        Contact.deleted_at.is_(None),
    ).first()
    if match is None:
        raise HTTPException(status_code=404, detail="Current association contact not found.")
    link, contact = match
    email = (contact.email or "").strip().lower()
    if not email:
        raise HTTPException(status_code=409, detail="Contact has no verified login email.")
    member = db.query(User).filter(
        User.organization_id == org,
        User.is_active.is_(True), User.is_verified.is_(True),
        User.deleted_at.is_(None),
        func.lower(func.trim(User.email)) == email,
    ).first()
    if member is None:
        raise HTTPException(status_code=409, detail="Contact has no current verified login.")
    return link, contact, member


def _file_bytes(document: EntityAttachment) -> bytes:
    if document.size_bytes > MAX_EMAIL_FILE_BYTES:
        raise HTTPException(status_code=413, detail="Email document exceeds 5 MB limit.")
    try:
        path = attachment_path(document.storage_key)
        if not path.is_file() or path.stat().st_size > MAX_EMAIL_FILE_BYTES:
            raise HTTPException(status_code=404, detail="Email document unavailable or oversized.")
        contents = path.read_bytes()
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="Email document unavailable.") from exc
    if not contents or len(contents) > MAX_EMAIL_FILE_BYTES or len(contents) != document.size_bytes:
        raise HTTPException(status_code=409, detail="Document bytes do not match stored metadata.")
    return contents


def _out(row: HOADocumentDelivery) -> HOADocumentDeliveryOut:
    return HOADocumentDeliveryOut(
        id=row.id, evidence_id=row.evidence_id,
        contact_link_id=row.contact_link_id, status=row.status,
        attempt_count=row.attempt_count, created_at=row.created_at,
        accepted_at=row.accepted_at, file_sha256=row.file_sha256,
        email_attachment_included=row.status == "SMTP_ACCEPTED",
    )


def _dispatch(db: Session, *, row_id: int, actor: User) -> HOADocumentDeliveryOut:
    row = db.query(HOADocumentDelivery).filter(
        HOADocumentDelivery.id == row_id,
        HOADocumentDelivery.organization_id == actor.organization_id,
    ).with_for_update().first()
    if row is None:
        raise HTTPException(status_code=404, detail="Delivery not found.")
    if row.status == "SMTP_ACCEPTED":
        return _out(row)
    if (row.status == "SENDING" and row.last_attempt_at is not None
            and datetime.utcnow() - row.last_attempt_at < timedelta(minutes=10)):
        raise HTTPException(status_code=409, detail="A document email attempt is in progress.")
    if row.attempt_count >= MAX_ATTEMPTS:
        raise HTTPException(status_code=409, detail="Document email retry limit reached.")
    # Recheck live access, identity and file before every attempted SMTP call.
    org, association = _scope(db, actor, row.association_id, row.property_id)
    _, document = _source(
        db, org=org, association_id=association.id,
        property_id=row.property_id, evidence_id=row.evidence_id,
    )
    if document.id != row.attachment_id:
        raise HTTPException(status_code=409, detail="Document reference changed.")
    _, _, member = _recipient(
        db, org=org, association_id=association.id,
        property_id=row.property_id, link_id=row.contact_link_id,
    )
    if member.id != row.recipient_user_id or member.email.strip().lower() != row.recipient_email:
        raise HTTPException(status_code=409, detail="Document recipient changed.")
    contents = _file_bytes(document)
    if hashlib.sha256(contents).hexdigest() != row.file_sha256:
        raise HTTPException(status_code=409, detail="Original document version changed.")
    # Durable claim before SMTP. If the process crashes the stale claim is retryable.
    row.status = "SENDING"
    row.attempt_count += 1
    row.last_attempt_at = datetime.utcnow()
    append_audit_log(
        db, organization_id=org, user_id=actor.id,
        entity_type="hoa_document_delivery", entity_id=row.id,
        action="document_delivery_attempted",
        new_value={"association_id": association.id, "property_id": row.property_id,
                   "evidence_id": row.evidence_id, "attempt": row.attempt_count},
    )
    db.commit()
    safe_name = re.sub(r"[^\w.() -]", "_", document.original_name.split("/")[-1].split("\\")[-1])[:120]
    content_type = mimetypes.guess_type(safe_name)[0] or "application/octet-stream"
    test_mode = email_service.settings.EMAIL_MODE == "console"
    try:
        email_service.send_email(
            to=row.recipient_email, subject="Association governing document copy",
            body=(
                "Your association has provided a copy of a recorded document as an email "
                "attachment. The association is responsible for the document and its version. "
                "This transmission is not a statutory violation notice or a legal certification."
            ),
            organization_id=org, db=db,
            attachments=[(safe_name, contents, content_type)],
        )
    except Exception:
        row.status = "FAILED"
        action = "document_delivery_failed"
    else:
        # In console mode send_email logs text, not attachment bytes.
        row.status = "TEST_ONLY" if test_mode else "SMTP_ACCEPTED"
        row.accepted_at = datetime.utcnow() if not test_mode else None
        action = "document_delivery_test_only" if test_mode else "document_delivery_smtp_accepted"
    append_audit_log(
        db, organization_id=org, user_id=actor.id,
        entity_type="hoa_document_delivery", entity_id=row.id,
        action=action, new_value={"association_id": association.id,
                                  "property_id": row.property_id, "attempt": row.attempt_count},
    )
    db.commit()
    db.refresh(row)
    return _out(row)


@router.get("/{association_id}/governing-evidence/eligible-recipients",
            response_model=list[HOADocumentRecipientOut])
def eligible_recipients(
    association_id: int, response: Response, property_id: int = Query(ge=1),
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org, association = _scope(db, current_user, association_id, property_id)
    links = db.query(HOAContactLink).filter(
        HOAContactLink.organization_id == org,
        HOAContactLink.association_id == association.id,
        HOAContactLink.property_id == property_id,
        HOAContactLink.is_active.is_(True),
    ).order_by(HOAContactLink.id).limit(501).all()
    if len(links) > 500:
        raise HTTPException(status_code=422, detail="Too many association contacts.")
    response.headers["Cache-Control"] = "no-store"
    result = []
    for link in links:
        try:
            _, contact, _ = _recipient(
                db, org=org, association_id=association.id,
                property_id=property_id, link_id=link.id,
            )
        except HTTPException:
            continue
        result.append(HOADocumentRecipientOut(
            contact_link_id=link.id, contact_name=contact.display_name,
        ))
    return result


@router.get("/{association_id}/governing-evidence/deliveries",
            response_model=list[HOADocumentDeliveryOut])
def delivery_history(
    association_id: int, response: Response, property_id: int = Query(ge=1),
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org, association = _scope(db, current_user, association_id, property_id)
    history = db.query(HOADocumentDelivery).filter(
        HOADocumentDelivery.organization_id == org,
        HOADocumentDelivery.association_id == association.id,
        HOADocumentDelivery.property_id == property_id,
    ).order_by(HOADocumentDelivery.id.desc()).limit(101).all()
    if len(history) > 100:
        raise HTTPException(status_code=422, detail="Document delivery history exceeds display limit.")
    response.headers["Cache-Control"] = "no-store"
    return [_out(row) for row in history]


@router.post("/{association_id}/governing-evidence/{evidence_id}/deliveries",
             response_model=HOADocumentDeliveryOut, status_code=201)
def send_document(
    association_id: int, evidence_id: int, payload: HOADocumentSendIn,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org, association = _scope(db, current_user, association_id, payload.property_id)
    existing = db.query(HOADocumentDelivery).filter(
        HOADocumentDelivery.association_id == association.id,
        HOADocumentDelivery.property_id == payload.property_id,
        HOADocumentDelivery.request_key == payload.request_key,
    ).with_for_update().first()
    if existing is not None:
        if (existing.evidence_id != evidence_id or
                existing.contact_link_id != payload.contact_link_id):
            raise HTTPException(status_code=409, detail="Document delivery key reused for different request.")
        return _out(existing)
    reference, document = _source(
        db, org=org, association_id=association.id,
        property_id=payload.property_id, evidence_id=evidence_id,
    )
    link, _, member = _recipient(
        db, org=org, association_id=association.id,
        property_id=payload.property_id, link_id=payload.contact_link_id,
    )
    contents = _file_bytes(document)
    row = HOADocumentDelivery(
        organization_id=org, association_id=association.id,
        property_id=payload.property_id, evidence_id=reference.id,
        attachment_id=document.id, contact_link_id=link.id,
        recipient_user_id=member.id, recipient_email=member.email.strip().lower(),
        request_key=payload.request_key,
        file_sha256=hashlib.sha256(contents).hexdigest(),
        status="PENDING", created_by_id=current_user.id,
    )
    db.add(row)
    try:
        db.flush()
        append_audit_log(
            db, organization_id=org, user_id=current_user.id,
            entity_type="hoa_document_delivery", entity_id=row.id,
            action="document_delivery_requested",
            new_value={"association_id": association.id, "property_id": payload.property_id,
                       "evidence_id": evidence_id, "contact_link_id": link.id},
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Concurrent document delivery request.") from exc
    return _dispatch(db, row_id=row.id, actor=current_user)


@router.post("/{association_id}/governing-evidence/deliveries/{delivery_id}/retry",
             response_model=HOADocumentDeliveryOut)
def retry_document(
    association_id: int, delivery_id: int, property_id: int,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org, association = _scope(db, current_user, association_id, property_id)
    row = db.query(HOADocumentDelivery).filter(
        HOADocumentDelivery.id == delivery_id,
        HOADocumentDelivery.organization_id == org,
        HOADocumentDelivery.association_id == association.id,
        HOADocumentDelivery.property_id == property_id,
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Document delivery not found.")
    if row.status == "SMTP_ACCEPTED":
        return _out(row)
    return _dispatch(db, row_id=row.id, actor=current_user)
