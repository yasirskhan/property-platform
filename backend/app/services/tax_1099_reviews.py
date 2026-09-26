"""Manual 1099 preparation, review and approval.

No accounting table is queried to derive reportable amounts. An administrator
must enter the tax-year amount and supporting reference explicitly. Approval
does not submit a return, generate an IRS file, or create a recipient copy.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.tax_1099_review import Tax1099Review
from app.models.tax_profile import TaxProfile
from app.models.tax_w9_document import TaxW9Document
from app.models.user import User
from app.schemas.tax_1099_review import (
    Tax1099ApprovalIn, Tax1099DataIn, Tax1099PrepareIn,
    Tax1099ReviewOut, Tax1099UpdateIn,
)
from app.services.audit import append_audit_log
from app.services.tax_profiles import _crypto, _decode, _subject, require_tax_admin


EXPECTED_RECIPIENT = {
    ("1099-NEC", "NONEMPLOYEE_COMPENSATION"): "VENDOR",
    ("1099-MISC", "RENTS"): "OWNER",
}


def _canonical(payload: Tax1099DataIn) -> dict[str, object]:
    return {
        "tax_year": payload.tax_year,
        "form_type": payload.form_type,
        "income_category": payload.income_category,
        "payer_profile_id": payload.payer_profile_id,
        "recipient_profile_id": payload.recipient_profile_id,
        "amount": format(payload.amount.quantize(Decimal("0.01")), "f"),
        "source_type": payload.source_type,
        "source_reference": payload.source_reference,
        "source_note": payload.source_note,
    }


def _fingerprint(payload: Tax1099DataIn) -> str:
    raw = json.dumps(_canonical(payload), sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def _row(db: Session, *, organization_id: int, record_id: int) -> Tax1099Review:
    row = db.query(Tax1099Review).filter(
        Tax1099Review.id == record_id,
        Tax1099Review.organization_id == organization_id,
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="1099 review record not found.")
    return row


def _profiles(
    db: Session, *, organization_id: int, payload: Tax1099DataIn,
    require_current_subject: bool = True, require_w9: bool = False,
) -> tuple[TaxProfile, TaxProfile, str, str, bool]:
    payer = db.query(TaxProfile).filter(
        TaxProfile.id == payload.payer_profile_id,
        TaxProfile.organization_id == organization_id,
        TaxProfile.subject_type == "ORGANIZATION",
        TaxProfile.subject_id == organization_id,
    ).first()
    recipient = db.query(TaxProfile).filter(
        TaxProfile.id == payload.recipient_profile_id,
        TaxProfile.organization_id == organization_id,
    ).first()
    if payer is None or recipient is None:
        raise HTTPException(status_code=404, detail="Required taxpayer profile not found.")
    expected = EXPECTED_RECIPIENT.get((payload.form_type, payload.income_category))
    if expected is None or recipient.subject_type != expected:
        raise HTTPException(status_code=422, detail="Recipient type does not match the selected 1099 classification.")
    if require_current_subject:
        _subject(
            db, organization_id=organization_id,
            subject_type=recipient.subject_type, subject_id=recipient.subject_id,
        )
    crypto = _crypto()
    payer_data = _decode(payer, crypto)
    recipient_data = _decode(recipient, crypto)
    evidence = db.query(TaxW9Document.id).filter(
        TaxW9Document.organization_id == organization_id,
        TaxW9Document.tax_profile_id == recipient.id,
    ).first() is not None
    if require_w9 and (not recipient.w9_on_file or not evidence):
        raise HTTPException(status_code=422, detail="Archived signed W-9 evidence is required before review.")
    return payer, recipient, payer_data["tin"][-4:], recipient_data["tin"][-4:], evidence


def _payload_from_row(row: Tax1099Review) -> Tax1099UpdateIn:
    return Tax1099UpdateIn(
        tax_year=row.tax_year, form_type=row.form_type,
        income_category=row.income_category,
        payer_profile_id=row.payer_profile_id,
        recipient_profile_id=row.recipient_profile_id,
        amount=row.amount, source_type=row.source_type,
        source_reference=row.source_reference, source_note=row.source_note,
    )


def _out(db: Session, row: Tax1099Review) -> Tax1099ReviewOut:
    payload = _payload_from_row(row)
    _, recipient, payer_last4, recipient_last4, evidence = _profiles(
        db, organization_id=row.organization_id, payload=payload,
        require_current_subject=False, require_w9=False,
    )
    return Tax1099ReviewOut(
        id=row.id, tax_year=row.tax_year, form_type=row.form_type,
        income_category=row.income_category,
        payer_profile_id=row.payer_profile_id, payer_tin_last4=payer_last4,
        recipient_profile_id=row.recipient_profile_id,
        recipient_subject_type=recipient.subject_type,
        recipient_subject_id=recipient.subject_id,
        recipient_tin_last4=recipient_last4,
        amount=row.amount, source_type=row.source_type,
        source_reference=row.source_reference, source_note=row.source_note,
        status=row.status, w9_evidence_present=evidence,
        source_review_confirmed=bool(row.source_review_confirmed),
        threshold_review_confirmed=bool(row.threshold_review_confirmed),
        recipient_review_confirmed=bool(row.recipient_review_confirmed),
        prepared_by_id=row.prepared_by_id, reviewed_by_id=row.reviewed_by_id,
        approved_by_id=row.approved_by_id, reviewed_at=row.reviewed_at,
        approved_at=row.approved_at, created_at=row.created_at,
        updated_at=row.updated_at,
    )


def list_reviews(db: Session, *, current_user: User, tax_year: int | None = None) -> list[Tax1099ReviewOut]:
    organization_id = require_tax_admin(db, current_user)
    query = db.query(Tax1099Review).filter(Tax1099Review.organization_id == organization_id)
    if tax_year is not None:
        if tax_year < 2020 or tax_year > 2100:
            raise HTTPException(status_code=422, detail="Invalid tax year.")
        query = query.filter(Tax1099Review.tax_year == tax_year)
    rows = query.order_by(Tax1099Review.tax_year.desc(), Tax1099Review.id.desc()).all()
    return [_out(db, row) for row in rows]


def prepare_review(db: Session, *, current_user: User, payload: Tax1099PrepareIn) -> Tax1099ReviewOut:
    organization_id = require_tax_admin(db, current_user)
    fingerprint = _fingerprint(payload)
    existing = db.query(Tax1099Review).filter(
        Tax1099Review.organization_id == organization_id,
        Tax1099Review.idempotency_key == payload.idempotency_key,
    ).first()
    if existing is not None:
        if existing.payload_fingerprint != fingerprint:
            raise HTTPException(status_code=409, detail="Idempotency key was already used for different 1099 data.")
        return _out(db, existing)
    _profiles(db, organization_id=organization_id, payload=payload)
    row = Tax1099Review(
        organization_id=organization_id, idempotency_key=payload.idempotency_key,
        payload_fingerprint=fingerprint, tax_year=payload.tax_year,
        form_type=payload.form_type, income_category=payload.income_category,
        payer_profile_id=payload.payer_profile_id,
        recipient_profile_id=payload.recipient_profile_id,
        amount=payload.amount, source_type=payload.source_type,
        source_reference=payload.source_reference, source_note=payload.source_note,
        status="PREPARED", prepared_by_id=current_user.id,
    )
    db.add(row)
    db.flush()
    append_audit_log(
        db, user_id=current_user.id, organization_id=organization_id,
        entity_type="tax_1099_review", entity_id=row.id, action="prepared",
        new_value={"tax_year": row.tax_year, "form_type": row.form_type,
                   "income_category": row.income_category,
                   "recipient_profile_id": row.recipient_profile_id},
    )
    db.commit()
    db.refresh(row)
    return _out(db, row)


def update_prepared(
    db: Session, *, current_user: User, record_id: int, payload: Tax1099UpdateIn,
) -> Tax1099ReviewOut:
    organization_id = require_tax_admin(db, current_user)
    row = _row(db, organization_id=organization_id, record_id=record_id)
    if row.status != "PREPARED":
        raise HTTPException(status_code=409, detail="Only PREPARED 1099 records can be edited.")
    _profiles(db, organization_id=organization_id, payload=payload)
    row.tax_year = payload.tax_year
    row.form_type = payload.form_type
    row.income_category = payload.income_category
    row.payer_profile_id = payload.payer_profile_id
    row.recipient_profile_id = payload.recipient_profile_id
    row.amount = payload.amount
    row.source_type = payload.source_type
    row.source_reference = payload.source_reference
    row.source_note = payload.source_note
    row.payload_fingerprint = _fingerprint(payload)
    append_audit_log(
        db, user_id=current_user.id, organization_id=organization_id,
        entity_type="tax_1099_review", entity_id=row.id, action="prepared_record_updated",
        new_value={"tax_year": row.tax_year, "form_type": row.form_type,
                   "income_category": row.income_category,
                   "recipient_profile_id": row.recipient_profile_id},
    )
    db.commit()
    db.refresh(row)
    return _out(db, row)


def mark_reviewed(db: Session, *, current_user: User, record_id: int) -> Tax1099ReviewOut:
    organization_id = require_tax_admin(db, current_user)
    row = _row(db, organization_id=organization_id, record_id=record_id)
    if row.status in {"REVIEWED", "APPROVED"}:
        return _out(db, row)
    if row.status != "PREPARED":
        raise HTTPException(status_code=409, detail="1099 record is not ready for review.")
    payload = _payload_from_row(row)
    _profiles(db, organization_id=organization_id, payload=payload, require_w9=True)
    row.status = "REVIEWED"
    row.reviewed_by_id = current_user.id
    row.reviewed_at = datetime.utcnow()
    append_audit_log(
        db, user_id=current_user.id, organization_id=organization_id,
        entity_type="tax_1099_review", entity_id=row.id, action="reviewed",
        new_value={"status": "REVIEWED", "tax_year": row.tax_year, "form_type": row.form_type},
    )
    db.commit()
    db.refresh(row)
    return _out(db, row)


def approve_review(
    db: Session, *, current_user: User, record_id: int, payload: Tax1099ApprovalIn,
) -> Tax1099ReviewOut:
    organization_id = require_tax_admin(db, current_user)
    row = _row(db, organization_id=organization_id, record_id=record_id)
    if row.status == "APPROVED":
        return _out(db, row)
    if row.status != "REVIEWED":
        raise HTTPException(status_code=409, detail="1099 record must be REVIEWED before approval.")
    current = _payload_from_row(row)
    _profiles(db, organization_id=organization_id, payload=current, require_w9=True)
    row.source_review_confirmed = payload.source_review_confirmed
    row.threshold_review_confirmed = payload.threshold_review_confirmed
    row.recipient_review_confirmed = payload.recipient_review_confirmed
    row.status = "APPROVED"
    row.approved_by_id = current_user.id
    row.approved_at = datetime.utcnow()
    append_audit_log(
        db, user_id=current_user.id, organization_id=organization_id,
        entity_type="tax_1099_review", entity_id=row.id, action="approved",
        new_value={"status": "APPROVED", "tax_year": row.tax_year, "form_type": row.form_type,
                   "approval_checks": ["source", "threshold_exceptions", "recipient_payer"]},
    )
    db.commit()
    db.refresh(row)
    return _out(db, row)
