"""Rewrap encrypted tax records under the current dedicated key in bounded batches.

Previous keys are supplied only through TAX_PROFILE_PREVIOUS_KEYS_JSON in
server-side secret management. API never receives or returns raw key material,
taxpayer IDs, scanned forms, or decrypted profile fields.
"""
from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.tax_profile import TaxProfile
from app.models.tax_w9_document import TaxW9Document
from app.models.user import User
from app.schemas.tax_rotation import TaxRotationIn, TaxRotationOut
from app.services.audit import append_audit_log
from app.services.tax_profiles import _crypto, require_tax_admin


def rotate_org_tax_keys(
    db: Session, *, current_user: User, payload: TaxRotationIn,
) -> TaxRotationOut:
    organization_id = require_tax_admin(db, current_user)
    crypto = _crypto()
    try:
        active = Fernet(settings.TAX_PROFILE_ENCRYPTION_KEY.encode("utf-8"))
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=503, detail="Tax profile encryption is unavailable.") from exc

    profiles = (
        db.query(TaxProfile)
        .filter(TaxProfile.organization_id == organization_id,
                TaxProfile.id > payload.after_profile_id)
        .order_by(TaxProfile.id)
        .limit(payload.limit + 1)
        .all()
    )
    documents = (
        db.query(TaxW9Document)
        .filter(TaxW9Document.organization_id == organization_id,
                TaxW9Document.id > payload.after_document_id)
        .order_by(TaxW9Document.id)
        .limit(payload.limit + 1)
        .all()
    )
    more_profiles = len(profiles) > payload.limit
    more_documents = len(documents) > payload.limit
    profiles = profiles[:payload.limit]
    documents = documents[:payload.limit]
    rotated_p = rotated_d = 0

    # Fail atomic: a missing legacy key or corrupted ciphertext must not
    # partially rewrap the organization's profiles or signed W-9 documents.
    try:
        for row in profiles:
            token = row.encrypted_payload.encode("ascii")
            try:
                active.decrypt(token)
            except InvalidToken:
                plain = crypto.decrypt(token)
                row.encrypted_payload = active.encrypt(plain).decode("ascii")
                rotated_p += 1
                append_audit_log(
                    db, user_id=current_user.id, organization_id=organization_id,
                    entity_type="tax_profile", entity_id=row.id,
                    action="encryption_key_rotated",
                    new_value={"subject_type": row.subject_type, "subject_id": row.subject_id},
                )
        for row in documents:
            try:
                active.decrypt(row.encrypted_pdf)
            except InvalidToken:
                plain = crypto.decrypt(row.encrypted_pdf)
                row.encrypted_pdf = active.encrypt(plain)
                rotated_d += 1
                append_audit_log(
                    db, user_id=current_user.id, organization_id=organization_id,
                    entity_type="tax_w9_document", entity_id=row.id,
                    action="encryption_key_rotated",
                    new_value={"tax_profile_id": row.tax_profile_id},
                )
        db.commit()
    except (InvalidToken, ValueError, UnicodeError, TypeError) as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="Tax key rotation could not decrypt a stored record.") from exc
    except Exception:
        db.rollback()
        raise

    return TaxRotationOut(
        profiles_rewrapped=rotated_p, documents_rewrapped=rotated_d,
        next_profile_id=profiles[-1].id if profiles else payload.after_profile_id,
        next_document_id=documents[-1].id if documents else payload.after_document_id,
        more_profiles=more_profiles, more_documents=more_documents,
    )
