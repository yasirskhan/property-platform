"""Admin-only encrypted W-9 scan archive; never use generic attachments.

The staff member attests to examining the signed original/scan. This is not
electronic W-9 signature capture, IRS e-filing, or PDF malware scanning.
"""
from __future__ import annotations

from datetime import date

from cryptography.fernet import InvalidToken
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.tax_profile import TaxProfile
from app.models.tax_w9_document import TaxW9Document
from app.models.user import User
from app.schemas.tax_w9 import TaxW9DocumentOut
from app.services.audit import append_audit_log
from app.services.tax_profiles import _crypto, _subject, require_tax_admin


MAX_W9_BYTES = 5 * 1024 * 1024


def _profile(db: Session, *, current_user: User, tax_profile_id: int) -> TaxProfile:
    org = require_tax_admin(db, current_user)
    profile = (
        db.query(TaxProfile)
        .filter(TaxProfile.id == tax_profile_id, TaxProfile.organization_id == org)
        .first()
    )
    if profile is None or profile.subject_type not in {"OWNER", "VENDOR"}:
        raise HTTPException(status_code=404, detail="Recipient tax profile not found.")
    _subject(db, organization_id=org, subject_type=profile.subject_type, subject_id=profile.subject_id)
    return profile


def _out(doc: TaxW9Document) -> TaxW9DocumentOut:
    return TaxW9DocumentOut(
        id=doc.id, tax_profile_id=doc.tax_profile_id,
        size_bytes=doc.size_bytes, received_on=doc.received_on,
        uploaded_at=doc.uploaded_at, uploaded_by_id=doc.uploaded_by_id,
    )


def _valid_pdf(contents: bytes) -> None:
    if len(contents) > MAX_W9_BYTES:
        raise HTTPException(status_code=413, detail="W-9 PDF must be 5 MB or smaller.")
    if len(contents) < 32 or not contents.startswith(b"%PDF-") or b"%%EOF" not in contents[-2048:]:
        raise HTTPException(status_code=422, detail="A PDF document is required.")


def archive_signed_w9(
    db: Session, *, current_user: User, tax_profile_id: int,
    contents: bytes, received_on: date, signed_original_confirmed: bool,
) -> TaxW9DocumentOut:
    profile = _profile(db, current_user=current_user, tax_profile_id=tax_profile_id)
    crypto = _crypto()
    if not signed_original_confirmed:
        raise HTTPException(status_code=422, detail="A staff signature-review attestation is required.")
    if received_on > date.today():
        raise HTTPException(status_code=422, detail="Received date cannot be in the future.")
    _valid_pdf(contents)
    doc = TaxW9Document(
        organization_id=profile.organization_id, tax_profile_id=profile.id,
        encrypted_pdf=crypto.encrypt(contents), size_bytes=len(contents),
        received_on=received_on, uploaded_by_id=current_user.id,
    )
    db.add(doc)
    profile.w9_on_file = True
    profile.w9_received_on = received_on
    db.flush()
    append_audit_log(
        db, user_id=current_user.id, organization_id=profile.organization_id,
        entity_type="tax_w9_document", entity_id=doc.id, action="archived",
        new_value={"tax_profile_id": profile.id, "size_bytes": doc.size_bytes,
                   "received_on": received_on.isoformat(), "paper_signature_attested": True},
    )
    db.commit()
    db.refresh(doc)
    return _out(doc)


def list_archived_w9(db: Session, *, current_user: User, tax_profile_id: int) -> list[TaxW9DocumentOut]:
    profile = _profile(db, current_user=current_user, tax_profile_id=tax_profile_id)
    _crypto()  # fail closed if a dedicated tax key is not configured
    rows = (
        db.query(TaxW9Document)
        .filter(TaxW9Document.organization_id == profile.organization_id,
                TaxW9Document.tax_profile_id == profile.id)
        .order_by(TaxW9Document.uploaded_at.desc(), TaxW9Document.id.desc())
        .all()
    )
    append_audit_log(
        db, user_id=current_user.id, organization_id=profile.organization_id,
        entity_type="tax_w9_document", entity_id=profile.id, action="metadata_listed",
        new_value={"tax_profile_id": profile.id, "count": len(rows)},
    )
    db.commit()
    return [_out(row) for row in rows]


def download_archived_w9(
    db: Session, *, current_user: User, tax_profile_id: int, document_id: int,
) -> bytes:
    profile = _profile(db, current_user=current_user, tax_profile_id=tax_profile_id)
    crypto = _crypto()
    doc = (
        db.query(TaxW9Document)
        .filter(TaxW9Document.id == document_id,
                TaxW9Document.tax_profile_id == profile.id,
                TaxW9Document.organization_id == profile.organization_id)
        .first()
    )
    if doc is None:
        raise HTTPException(status_code=404, detail="Signed W-9 document not found.")
    try:
        plain = crypto.decrypt(doc.encrypted_pdf)
    except (InvalidToken, ValueError, TypeError) as exc:
        raise HTTPException(status_code=503, detail="Signed W-9 decryption unavailable.") from exc
    _valid_pdf(plain)
    append_audit_log(
        db, user_id=current_user.id, organization_id=profile.organization_id,
        entity_type="tax_w9_document", entity_id=doc.id, action="downloaded",
        new_value={"tax_profile_id": profile.id},
    )
    db.commit()
    return plain
