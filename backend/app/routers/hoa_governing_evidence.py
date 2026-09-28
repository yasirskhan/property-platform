"""Staff evidence index; file bytes remain in verified universal attachments."""
from __future__ import annotations
from pathlib import PurePath

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.entity_attachment import EntityAttachment
from app.models.hoa_governing_evidence import HOAGoverningEvidence
from app.models.user import User
from app.routers.auth import get_current_user
from app.routers.hoa_assessments import _scope
from app.schemas.hoa_governing_evidence import HOAEvidenceLinkIn, HOAEvidenceOut
from app.services.audit import append_audit_log
from app.services.customer_features import resolve_customer_features

router = APIRouter(prefix="/api/hoa/associations", tags=["HOA governing-document staff evidence"])
ATTACHMENT_FEATURE = "release.documents.attachments"
ALLOWED_SUFFIXES = {".pdf", ".doc", ".docx"}


def _require_attachment_feature(db: Session, user: User):
    decision = next(
        (x for x in resolve_customer_features(db, user=user)
         if x.key == ATTACHMENT_FEATURE),
        None,
    )
    if decision is None or not decision.allowed:
        raise HTTPException(status_code=404, detail="Document storage unavailable.")


def _attachment(db: Session, *, org_id: int, prop_id: int, attachment_id: int) -> EntityAttachment:
    row = db.query(EntityAttachment).filter(
        EntityAttachment.id == attachment_id,
        EntityAttachment.organization_id == org_id,
        EntityAttachment.entity_type == "properties",
        EntityAttachment.entity_id == prop_id,
        EntityAttachment.is_active.is_(True),
        EntityAttachment.share_with_tenants.is_(False),
        EntityAttachment.share_with_owners.is_(False),
    ).first()
    if row is None or PurePath(row.original_name).suffix.lower() not in ALLOWED_SUFFIXES:
        raise HTTPException(status_code=404, detail="Private property document not found.")
    return row


def _out(record: HOAGoverningEvidence, attachment: EntityAttachment) -> HOAEvidenceOut:
    return HOAEvidenceOut(
        id=record.id, association_id=record.association_id,
        property_id=record.property_id, attachment_id=attachment.id,
        evidence_type=record.evidence_type, filename=attachment.original_name,
        recorded_at=record.created_at,
    )


@router.get("/{association_id}/governing-evidence", response_model=list[HOAEvidenceOut])
def list_evidence(
    association_id: int, response: Response, property_id: int = Query(ge=1),
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org_id, association = _scope(
        db, actor=current_user, association_id=association_id,
        property_id=property_id, write=False,
    )
    _require_attachment_feature(db, current_user)
    response.headers["Cache-Control"] = "no-store"
    records = db.query(HOAGoverningEvidence, EntityAttachment).join(
        EntityAttachment, EntityAttachment.id == HOAGoverningEvidence.attachment_id,
    ).filter(
        HOAGoverningEvidence.organization_id == org_id,
        HOAGoverningEvidence.association_id == association.id,
        HOAGoverningEvidence.property_id == property_id,
        HOAGoverningEvidence.is_active.is_(True),
        EntityAttachment.organization_id == org_id,
        EntityAttachment.entity_type == "properties",
        EntityAttachment.entity_id == property_id,
        EntityAttachment.is_active.is_(True),
        EntityAttachment.share_with_tenants.is_(False),
        EntityAttachment.share_with_owners.is_(False),
    ).order_by(HOAGoverningEvidence.id.asc()).limit(201).all()
    if len(records) > 200:
        raise HTTPException(status_code=422, detail="Too many documents to display.")
    return [_out(record, attachment) for record, attachment in records]


@router.post("/{association_id}/governing-evidence", response_model=HOAEvidenceOut, status_code=201)
def link_evidence(
    association_id: int, payload: HOAEvidenceLinkIn,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org_id, association = _scope(
        db, actor=current_user, association_id=association_id,
        property_id=payload.property_id, write=True,
    )
    _require_attachment_feature(db, current_user)
    attachment = _attachment(
        db, org_id=org_id, prop_id=payload.property_id,
        attachment_id=payload.attachment_id,
    )
    existing = db.query(HOAGoverningEvidence).filter(
        HOAGoverningEvidence.organization_id == org_id,
        HOAGoverningEvidence.association_id == association.id,
        HOAGoverningEvidence.property_id == payload.property_id,
        HOAGoverningEvidence.attachment_id == attachment.id,
    ).first()
    if existing is not None:
        # Archived references cannot silently resurrect after a relink.
        raise HTTPException(status_code=409, detail="Document reference already recorded.")
    count = db.query(HOAGoverningEvidence.id).filter(
        HOAGoverningEvidence.organization_id == org_id,
        HOAGoverningEvidence.association_id == association.id,
        HOAGoverningEvidence.property_id == payload.property_id,
        HOAGoverningEvidence.is_active.is_(True),
    ).limit(200).all()
    if len(count) >= 200:
        raise HTTPException(status_code=422, detail="Too many document references.")
    row = HOAGoverningEvidence(
        organization_id=org_id, association_id=association.id,
        property_id=payload.property_id, attachment_id=attachment.id,
        evidence_type=payload.evidence_type, created_by_id=current_user.id,
        updated_by_id=current_user.id,
    )
    db.add(row)
    try:
        db.flush()
        append_audit_log(
            db, organization_id=org_id, user_id=current_user.id,
            entity_type="hoa_governing_evidence", entity_id=row.id,
            action="staff_document_reference_recorded",
            new_value={"association_id": association.id, "property_id": payload.property_id,
                       "attachment_id": attachment.id, "evidence_type": row.evidence_type},
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Document reference changed concurrently.") from exc
    db.refresh(row)
    return _out(row, attachment)


@router.delete("/{association_id}/governing-evidence/{reference_id}", status_code=204)
def archive_evidence(
    association_id: int, reference_id: int, property_id: int,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org_id, association = _scope(
        db, actor=current_user, association_id=association_id,
        property_id=property_id, write=True,
    )
    _require_attachment_feature(db, current_user)
    row = db.query(HOAGoverningEvidence).filter(
        HOAGoverningEvidence.id == reference_id,
        HOAGoverningEvidence.organization_id == org_id,
        HOAGoverningEvidence.association_id == association.id,
        HOAGoverningEvidence.property_id == property_id,
        HOAGoverningEvidence.is_active.is_(True),
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Document reference not found.")
    row.is_active = False
    row.updated_by_id = current_user.id
    db.flush()
    append_audit_log(
        db, organization_id=org_id, user_id=current_user.id,
        entity_type="hoa_governing_evidence", entity_id=row.id,
        action="staff_document_reference_archived",
        new_value={"association_id": association.id, "property_id": property_id},
    )
    db.commit()
    return Response(status_code=204, headers={"Cache-Control": "no-store"})
