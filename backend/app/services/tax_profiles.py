"""Restricted taxpayer-profile encryption and scope.

No raw TIN, legal name or mailing address is returned to the browser or audit
log; verified paper W-9 is tracked as metadata, not as an unencrypted upload.
This module NEVER files a tax return and NEVER exports a TIN.
"""
from __future__ import annotations

import json

from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.tax_profile import TaxProfile
from app.models.user import User, UserRole
from app.schemas.tax_profile import TaxProfileOut, TaxProfileUpsertIn
from app.services.audit import append_audit_log
from app.services.menu_resolver import permission_allows_user


def _crypto() -> Fernet:
    key = settings.TAX_PROFILE_ENCRYPTION_KEY
    if not key or key == settings.ENCRYPTION_KEY:
        raise HTTPException(status_code=503, detail="Dedicated tax profile encryption is not configured.")
    try:
        return Fernet(key.encode("utf-8"))
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=503, detail="Tax profile encryption is unavailable.") from exc


def require_tax_admin(db: Session, current_user: User) -> int:
    if current_user.organization_id is None:
        raise HTTPException(status_code=403, detail="Tax reporting permission required.")
    role = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role or "")
    if role.upper() != "ADMIN" or not permission_allows_user(db, user=current_user, menu_key="REPORTING.ALL"):
        raise HTTPException(status_code=403, detail="Tax reporting permission required.")
    return int(current_user.organization_id)


def _subject(db: Session, *, organization_id: int, subject_type: str, subject_id: int) -> None:
    if subject_type == "ORGANIZATION":
        if subject_id != organization_id:
            raise HTTPException(status_code=404, detail="Tax profile subject not found.")
        return
    role = UserRole.OWNER if subject_type == "OWNER" else UserRole.VENDOR
    person = (
        db.query(User)
        .filter(User.id == subject_id, User.organization_id == organization_id,
                User.role == role, User.is_active.is_(True), User.deleted_at.is_(None))
        .first()
    )
    if person is None:
        raise HTTPException(status_code=404, detail="Tax profile subject not found.")


def _decode(row: TaxProfile, fernet: Fernet) -> dict[str, str]:
    try:
        raw = fernet.decrypt(row.encrypted_payload.encode("utf-8"))
        data = json.loads(raw)
        if not isinstance(data, dict) or not isinstance(data.get("tin"), str):
            raise ValueError("Invalid profile")
        return data
    except (InvalidToken, ValueError, UnicodeError, TypeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=503, detail="Tax profile could not be decrypted.") from exc


def _out(row: TaxProfile, fernet: Fernet) -> TaxProfileOut:
    data = _decode(row, fernet)
    return TaxProfileOut(
        id=row.id, subject_type=row.subject_type, subject_id=row.subject_id,
        tin_last4=data["tin"][-4:],
        w9_on_file=bool(row.w9_on_file), w9_received_on=row.w9_received_on,
        updated_at=row.updated_at,
    )


def list_tax_profiles(db: Session, *, current_user: User) -> list[TaxProfileOut]:
    organization_id = require_tax_admin(db, current_user)
    fernet = _crypto()
    rows = db.query(TaxProfile).filter(
        TaxProfile.organization_id == organization_id,
    ).order_by(TaxProfile.subject_type, TaxProfile.subject_id).all()
    # Never expose a record for a user moved to another organization.
    result = []
    for row in rows:
        try:
            _subject(db, organization_id=organization_id,
                     subject_type=row.subject_type, subject_id=row.subject_id)
        except HTTPException:
            continue
        result.append(_out(row, fernet))
    return result


def upsert_tax_profile(
    db: Session, *, current_user: User, payload: TaxProfileUpsertIn,
) -> TaxProfileOut:
    organization_id = require_tax_admin(db, current_user)
    fernet = _crypto()  # fail closed before any database mutation
    _subject(db, organization_id=organization_id,
             subject_type=payload.subject_type, subject_id=payload.subject_id)
    tin_raw = payload.tin.get_secret_value().strip()
    if not tin_raw or any(c not in "0123456789- " for c in tin_raw):
        raise HTTPException(status_code=422, detail="Tax ID must contain nine digits.")
    tin = tin_raw.replace("-", "").replace(" ", "")
    if len(tin) != 9 or not tin.isdigit():
        raise HTTPException(status_code=422, detail="Tax ID must contain nine digits.")
    safe = payload.model_dump(exclude={"tin", "w9_on_file", "w9_received_on"})
    safe["tin"] = tin
    # All person/company identifiers and mailing fields are encrypted together.
    ciphertext = fernet.encrypt(json.dumps(safe, sort_keys=True, default=str).encode("utf-8")).decode("ascii")
    row = db.query(TaxProfile).filter(
        TaxProfile.organization_id == organization_id,
        TaxProfile.subject_type == payload.subject_type,
        TaxProfile.subject_id == payload.subject_id,
    ).first()
    created = row is None
    old_metadata = None if created else {"w9_on_file": row.w9_on_file}
    if row is None:
        row = TaxProfile(
            organization_id=organization_id, subject_type=payload.subject_type,
            subject_id=payload.subject_id,
        )
        db.add(row)
    row.encrypted_payload = ciphertext
    row.w9_on_file = payload.w9_on_file
    row.w9_received_on = payload.w9_received_on
    row.updated_by_id = current_user.id
    db.flush()
    append_audit_log(
        db, user_id=current_user.id, organization_id=organization_id,
        entity_type="tax_profile", entity_id=row.id,
        action="created" if created else "updated",
        old_value=old_metadata,
        new_value={"subject_type": payload.subject_type, "subject_id": payload.subject_id,
                   "w9_on_file": payload.w9_on_file},
    )
    db.commit()
    db.refresh(row)
    return _out(row, fernet)
