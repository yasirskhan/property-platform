"""Restricted encrypted staff Form 8609 scan archive.

A staff confirmation is NOT proof that an agency signed/issued the form,
that IRS received it, or that credits may be claimed. Files never enter
general attachment storage, browser logs, outgoing email, or GL.
"""
from __future__ import annotations
from datetime import date
from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.affordable_8609_document import Affordable8609Document
from app.models.user import User, UserRole
from app.routers.affordable_8609_readiness import _building
from app.schemas.affordable_8609_document import Affordable8609DocumentOut
from app.services.audit import append_audit_log

MAX_8609_BYTES = 5 * 1024 * 1024


def _crypto() -> Fernet:
    key = settings.COMPLIANCE_DOCUMENT_ENCRYPTION_KEY
    if not key or key in (
        settings.ENCRYPTION_KEY, settings.TAX_PROFILE_ENCRYPTION_KEY,
        settings.APPLICATION_ENCRYPTION_KEY,
    ):
        raise HTTPException(status_code=503, detail="Dedicated compliance document encryption is not configured.")
    try:
        return Fernet(key.encode("utf-8"))
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=503, detail="Compliance document encryption is unavailable.") from exc


def _scope(db: Session, *, property_id: int, program_id: int, building_id: int,
           user: User, write: bool):
    # For sensitive agency form scans, manager/crew/tenant do not inherit
    # access from the less-sensitive staff BIN/readiness registers.
    prop, building = _building(db, property_id=property_id, program_id=program_id,
                               building_id=building_id, user=user, write=write)
    if user.role not in {UserRole.ADMIN, UserRole.OWNER}:
        raise HTTPException(status_code=403, detail="Restricted Form 8609 document access required.")
    return prop, building


def _valid_pdf(contents: bytes) -> None:
    if len(contents) > MAX_8609_BYTES:
        raise HTTPException(status_code=413, detail="Form 8609 scan must be 5 MB or smaller.")
    if len(contents) < 32 or not contents.startswith(b"%PDF-") or b"%%EOF" not in contents[-2048:]:
        raise HTTPException(status_code=422, detail="A PDF scan is required.")


def _out(document: Affordable8609Document) -> Affordable8609DocumentOut:
    return Affordable8609DocumentOut.model_validate(document)


def archive_8609(
    db: Session, *, current_user: User, property_id: int, program_id: int,
    building_id: int, contents: bytes, received_on: date, signed_copy_reviewed: bool,
) -> Affordable8609DocumentOut:
    prop, building = _scope(db, property_id=property_id, program_id=program_id,
                            building_id=building_id, user=current_user, write=True)
    crypto = _crypto()
    if not signed_copy_reviewed:
        raise HTTPException(status_code=422, detail="Staff scan-review confirmation required.")
    if received_on > date.today():
        raise HTTPException(status_code=422, detail="Received date cannot be in the future.")
    _valid_pdf(contents)
    doc = Affordable8609Document(
        organization_id=prop.organization_id, property_id=prop.id,
        program_id=program_id, building_id=building.id,
        encrypted_pdf=crypto.encrypt(contents), size_bytes=len(contents),
        received_on=received_on, uploaded_by_id=current_user.id,
    )
    db.add(doc)
    db.flush()
    append_audit_log(
        db, organization_id=prop.organization_id, user_id=current_user.id,
        entity_type="affordable_8609_document", entity_id=doc.id,
        action="archived",
        new_value={"building_id": building.id, "received_on": received_on.isoformat(),
                   "size_bytes": doc.size_bytes, "staff_reviewed_scan": True},
    )
    db.commit()
    db.refresh(doc)
    return _out(doc)


def list_8609(
    db: Session, *, current_user: User, property_id: int, program_id: int,
    building_id: int,
) -> list[Affordable8609DocumentOut]:
    prop, building = _scope(db, property_id=property_id, program_id=program_id,
                            building_id=building_id, user=current_user, write=False)
    _crypto()
    rows = db.query(Affordable8609Document).filter(
        Affordable8609Document.organization_id == prop.organization_id,
        Affordable8609Document.property_id == prop.id,
        Affordable8609Document.program_id == program_id,
        Affordable8609Document.building_id == building.id,
    ).order_by(Affordable8609Document.uploaded_at.desc(),
               Affordable8609Document.id.desc()).limit(101).all()
    if len(rows) > 100:
        raise HTTPException(status_code=422, detail="Archive list exceeds preview limit.")
    append_audit_log(
        db, organization_id=prop.organization_id, user_id=current_user.id,
        entity_type="affordable_8609_document", entity_id=building.id,
        action="metadata_listed", new_value={"building_id": building.id, "count": len(rows)},
    )
    db.commit()
    return [_out(row) for row in rows]


def download_8609(
    db: Session, *, current_user: User, property_id: int, program_id: int,
    building_id: int, document_id: int,
) -> bytes:
    prop, building = _scope(db, property_id=property_id, program_id=program_id,
                            building_id=building_id, user=current_user, write=False)
    crypto = _crypto()
    doc = db.query(Affordable8609Document).filter(
        Affordable8609Document.id == document_id,
        Affordable8609Document.organization_id == prop.organization_id,
        Affordable8609Document.property_id == prop.id,
        Affordable8609Document.program_id == program_id,
        Affordable8609Document.building_id == building.id,
    ).first()
    if doc is None:
        raise HTTPException(status_code=404, detail="Form 8609 scan not found.")
    try:
        plain = crypto.decrypt(doc.encrypted_pdf)
    except (InvalidToken, ValueError, TypeError) as exc:
        raise HTTPException(status_code=503, detail="Form 8609 scan cannot be decrypted.") from exc
    _valid_pdf(plain)
    append_audit_log(
        db, organization_id=prop.organization_id, user_id=current_user.id,
        entity_type="affordable_8609_document", entity_id=doc.id,
        action="downloaded", new_value={"building_id": building.id},
    )
    db.commit()
    return plain
