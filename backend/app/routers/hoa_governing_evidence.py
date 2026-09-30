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
from app.schemas.hoa_governing_evidence import (
    HOAEvidenceLinkIn, HOAEvidenceOut, HOAEvidenceReplaceIn,
    HOAEvidenceVersionOut,
)
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
        revision=record.revision, supersedes_id=record.supersedes_id,
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



@router.get("/{association_id}/governing-evidence/versions",
            response_model=list[HOAEvidenceVersionOut])
def evidence_version_history(
    association_id: int, response: Response, property_id: int = Query(ge=1),
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    """Staff-only history of linked source references, never general attachment access.

    Archived references remain visible as metadata for record-keeping.
    Missing, deleted or shared files are not available for download here.
    """
    org_id, association = _scope(
        db, actor=current_user, association_id=association_id,
        property_id=property_id, write=False,
    )
    _require_attachment_feature(db, current_user)
    records = db.query(HOAGoverningEvidence, EntityAttachment).join(
        EntityAttachment, EntityAttachment.id == HOAGoverningEvidence.attachment_id,
    ).filter(
        HOAGoverningEvidence.organization_id == org_id,
        HOAGoverningEvidence.association_id == association.id,
        HOAGoverningEvidence.property_id == property_id,
        EntityAttachment.organization_id == org_id,
        EntityAttachment.entity_type == "properties",
        EntityAttachment.entity_id == property_id,
    ).order_by(HOAGoverningEvidence.id).limit(201).all()
    if len(records) > 200:
        raise HTTPException(status_code=422, detail="Document version history exceeds 200.")
    response.headers["Cache-Control"] = "no-store"
    return [HOAEvidenceVersionOut(
        id=row.id, association_id=association.id, property_id=property_id,
        evidence_type=row.evidence_type, revision=row.revision,
        supersedes_id=row.supersedes_id, is_active=row.is_active,
        filename=attachment.original_name if (
            attachment.is_active and not attachment.share_with_tenants
            and not attachment.share_with_owners
        ) else "Private source no longer available",
        recorded_at=row.created_at,
    ) for row, attachment in records]


@router.post("/{association_id}/governing-evidence/{reference_id}/replace",
             response_model=HOAEvidenceOut, status_code=201)
def replace_evidence(
    association_id: int, reference_id: int, payload: HOAEvidenceReplaceIn,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    """Staff-authorized private replacement, with immutable source lineage.

    Replacement archives ONLY the prior reference. It does not delete its
    file, alter historical deliveries, adopt rules, post money or send notice.
    A repeated identical request key returns the same version without a
    second archive, audit event or new document reference.
    """
    org_id, association = _scope(
        db, actor=current_user, association_id=association_id,
        property_id=payload.property_id, write=True,
    )
    _require_attachment_feature(db, current_user)
    candidate = _attachment(
        db, org_id=org_id, prop_id=payload.property_id,
        attachment_id=payload.attachment_id,
    )
    duplicate = db.query(HOAGoverningEvidence).filter(
        HOAGoverningEvidence.organization_id == org_id,
        HOAGoverningEvidence.replacement_request_key == payload.request_key,
    ).first()
    if duplicate is not None:
        if (duplicate.association_id == association.id
            and duplicate.property_id == payload.property_id
            and duplicate.supersedes_id == reference_id
            and duplicate.attachment_id == candidate.id):
            return _out(duplicate, candidate)
        raise HTTPException(status_code=409, detail="Document replacement request key already used.")
    previous = db.query(HOAGoverningEvidence).filter(
        HOAGoverningEvidence.id == reference_id,
        HOAGoverningEvidence.organization_id == org_id,
        HOAGoverningEvidence.association_id == association.id,
        HOAGoverningEvidence.property_id == payload.property_id,
        HOAGoverningEvidence.is_active.is_(True),
    ).with_for_update().first()
    if previous is None:
        raise HTTPException(status_code=404, detail="Current governing document reference not found.")
    if previous.attachment_id == candidate.id:
        raise HTTPException(status_code=409, detail="Choose a different private document for the next version.")
    reused = db.query(HOAGoverningEvidence.id).filter(
        HOAGoverningEvidence.organization_id == org_id,
        HOAGoverningEvidence.association_id == association.id,
        HOAGoverningEvidence.property_id == payload.property_id,
        HOAGoverningEvidence.attachment_id == candidate.id,
    ).first()
    if reused is not None:
        raise HTTPException(status_code=409, detail="Document is already linked to this association.")
    count = db.query(HOAGoverningEvidence.id).filter(
        HOAGoverningEvidence.organization_id == org_id,
        HOAGoverningEvidence.association_id == association.id,
        HOAGoverningEvidence.property_id == payload.property_id,
    ).limit(200).all()
    if len(count) >= 200:
        raise HTTPException(status_code=422, detail="Document version history exceeds 200.")
    previous.is_active = False
    previous.updated_by_id = current_user.id
    row = HOAGoverningEvidence(
        organization_id=org_id, association_id=association.id,
        property_id=payload.property_id, attachment_id=candidate.id,
        evidence_type=previous.evidence_type, revision=previous.revision + 1,
        supersedes_id=previous.id, replacement_request_key=payload.request_key,
        is_active=True, created_by_id=current_user.id,
        updated_by_id=current_user.id,
    )
    db.add(row)
    try:
        db.flush()
        append_audit_log(
            db, organization_id=org_id, user_id=current_user.id,
            entity_type="hoa_governing_evidence", entity_id=previous.id,
            action="staff_document_reference_superseded",
            new_value={"association_id": association.id,
                       "property_id": payload.property_id,
                       "new_reference_id": row.id,
                       "revision": row.revision},
        )
        append_audit_log(
            db, organization_id=org_id, user_id=current_user.id,
            entity_type="hoa_governing_evidence", entity_id=row.id,
            action="staff_document_version_recorded",
            new_value={"association_id": association.id,
                       "property_id": payload.property_id,
                       "prior_reference_id": previous.id,
                       "revision": row.revision},
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Concurrent governing document replacement.") from exc
    db.refresh(row)
    return _out(row, candidate)


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
