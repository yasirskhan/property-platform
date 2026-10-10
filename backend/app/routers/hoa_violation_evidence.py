"""Private, scoped staff violation evidence index.

Property attachment bytes remain in universal attachments. Evidence is
never automatically shared with members or proof of an issued notice.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import PurePath
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.entity_attachment import EntityAttachment
from app.models.hoa_violation_evidence import HOAViolationEvidence
from app.models.user import User
from app.routers.auth import get_current_user
from app.routers.hoa_assessments import _scope
from app.routers.hoa_governing_evidence import _require_attachment_feature
from app.routers.hoa_violation_cases import _case
from app.services.audit import append_audit_log

router = APIRouter(prefix="/api/hoa/associations", tags=["HOA staff case evidence"])
SUFFIXES = {".pdf", ".doc", ".docx", ".jpg", ".jpeg", ".png", ".webp"}


class EvidenceIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    property_id: int = Field(ge=1)
    attachment_id: int = Field(ge=1)
    evidence_type: Literal["PHOTO", "DOCUMENT", "OTHER"]


class EvidenceOut(BaseModel):
    id: int
    case_id: int
    attachment_id: int
    evidence_type: Literal["PHOTO", "DOCUMENT", "OTHER"]
    filename: str
    recorded_at: datetime
    private_only: Literal[True] = True
    legal_notice_served: Literal[False] = False
    legal_violation_proven: Literal[False] = False


def _target(db: Session, *, actor: User, association_id: int,
            property_id: int, case_id: int, write: bool):
    org, assoc = _scope(
        db, actor=actor, association_id=association_id,
        property_id=property_id, write=write,
    )
    _require_attachment_feature(db, actor)
    case = _case(
        db, org_id=org, association_id=assoc.id,
        property_id=property_id, case_id=case_id,
    )
    return org, assoc, case


def _attachment(db: Session, *, org: int, property_id: int, attachment_id: int):
    row = db.query(EntityAttachment).filter(
        EntityAttachment.id == attachment_id,
        EntityAttachment.organization_id == org,
        EntityAttachment.entity_type == "properties",
        EntityAttachment.entity_id == property_id,
        EntityAttachment.is_active.is_(True),
        EntityAttachment.share_with_tenants.is_(False),
        EntityAttachment.share_with_owners.is_(False),
    ).first()
    if row is None or PurePath(row.original_name).suffix.lower() not in SUFFIXES:
        raise HTTPException(status_code=404, detail="Private property evidence file not found.")
    return row


def _out(link: HOAViolationEvidence, file: EntityAttachment):
    return EvidenceOut(
        id=link.id, case_id=link.case_id,
        attachment_id=link.attachment_id,
        evidence_type=link.evidence_type,
        filename=file.original_name, recorded_at=link.recorded_at,
    )


@router.get("/{association_id}/staff-cases/{case_id}/evidence",
            response_model=list[EvidenceOut])
def list_case_evidence(
    association_id: int, case_id: int, response: Response,
    property_id: int = Query(ge=1),
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org, assoc, case = _target(
        db, actor=current_user, association_id=association_id,
        property_id=property_id, case_id=case_id, write=False,
    )
    rows = db.query(HOAViolationEvidence, EntityAttachment).join(
        EntityAttachment, EntityAttachment.id == HOAViolationEvidence.attachment_id,
    ).filter(
        HOAViolationEvidence.organization_id == org,
        HOAViolationEvidence.association_id == assoc.id,
        HOAViolationEvidence.property_id == property_id,
        HOAViolationEvidence.case_id == case.id,
        HOAViolationEvidence.is_active.is_(True),
        EntityAttachment.organization_id == org,
        EntityAttachment.entity_type == "properties",
        EntityAttachment.entity_id == property_id,
        EntityAttachment.is_active.is_(True),
        EntityAttachment.share_with_tenants.is_(False),
        EntityAttachment.share_with_owners.is_(False),
    ).order_by(HOAViolationEvidence.id).limit(101).all()
    if len(rows) > 100:
        raise HTTPException(status_code=422, detail="Too many case evidence links.")
    response.headers["Cache-Control"] = "no-store"
    return [_out(link, attachment) for link, attachment in rows]


@router.post("/{association_id}/staff-cases/{case_id}/evidence",
             response_model=EvidenceOut, status_code=201)
def link_case_evidence(
    association_id: int, case_id: int, payload: EvidenceIn,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org, assoc, case = _target(
        db, actor=current_user, association_id=association_id,
        property_id=payload.property_id, case_id=case_id, write=True,
    )
    if case.stage == "CLOSED":
        raise HTTPException(status_code=409, detail="Closed case evidence cannot change.")
    file = _attachment(
        db, org=org, property_id=payload.property_id,
        attachment_id=payload.attachment_id,
    )
    if db.query(HOAViolationEvidence.id).filter(
        HOAViolationEvidence.organization_id == org,
        HOAViolationEvidence.case_id == case.id,
        HOAViolationEvidence.attachment_id == file.id,
    ).first():
        raise HTTPException(status_code=409, detail="Case evidence already recorded; archived links cannot be restored.")
    count = db.query(HOAViolationEvidence.id).filter(
        HOAViolationEvidence.organization_id == org,
        HOAViolationEvidence.case_id == case.id,
        HOAViolationEvidence.is_active.is_(True),
    ).limit(100).all()
    if len(count) >= 100:
        raise HTTPException(status_code=422, detail="Case evidence link limit reached.")
    row = HOAViolationEvidence(
        organization_id=org, association_id=assoc.id,
        property_id=payload.property_id, case_id=case.id,
        attachment_id=file.id, evidence_type=payload.evidence_type,
        recorded_by_id=current_user.id,
    )
    db.add(row)
    try:
        db.flush()
        append_audit_log(
            db, organization_id=org, user_id=current_user.id,
            entity_type="hoa_violation_evidence", entity_id=row.id,
            action="private_case_evidence_linked",
            new_value={
                "association_id": assoc.id, "property_id": payload.property_id,
                "case_id": case.id, "attachment_id": file.id,
                "evidence_type": row.evidence_type,
            },
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Evidence link changed concurrently.") from exc
    db.refresh(row)
    return _out(row, file)


@router.delete("/{association_id}/staff-cases/{case_id}/evidence/{link_id}",
               status_code=204)
def archive_case_evidence(
    association_id: int, case_id: int, link_id: int,
    property_id: int = Query(ge=1),
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org, assoc, case = _target(
        db, actor=current_user, association_id=association_id,
        property_id=property_id, case_id=case_id, write=True,
    )
    if case.stage == "CLOSED":
        raise HTTPException(status_code=409, detail="Closed case evidence cannot change.")
    row = db.query(HOAViolationEvidence).filter(
        HOAViolationEvidence.id == link_id,
        HOAViolationEvidence.organization_id == org,
        HOAViolationEvidence.association_id == assoc.id,
        HOAViolationEvidence.property_id == property_id,
        HOAViolationEvidence.case_id == case.id,
        HOAViolationEvidence.is_active.is_(True),
    ).with_for_update().first()
    if row is None:
        raise HTTPException(status_code=404, detail="Active case evidence link not found.")
    from app.models.hoa_violation_service_record import HOAViolationServiceRecord
    if db.query(HOAViolationServiceRecord.id).filter(
        HOAViolationServiceRecord.organization_id == org,
        HOAViolationServiceRecord.case_id == case.id,
        HOAViolationServiceRecord.service_proof_attachment_id == row.attachment_id,
    ).first() is not None:
        raise HTTPException(status_code=409, detail="Evidenced service proof cannot be archived.")
    from app.models.hoa_violation_fine import HOAViolationFine
    if db.query(HOAViolationFine.id).filter(
        HOAViolationFine.organization_id == org,
        HOAViolationFine.association_id == assoc.id,
        HOAViolationFine.property_id == property_id,
        HOAViolationFine.case_id == case.id,
        HOAViolationFine.hearing_record_attachment_id == row.attachment_id,
    ).first() is not None:
        raise HTTPException(status_code=409, detail="Recorded board hearing proof cannot be archived.")
    row.is_active = False
    row.archived_by_id = current_user.id
    row.archived_at = datetime.utcnow()
    db.flush()
    append_audit_log(
        db, organization_id=org, user_id=current_user.id,
        entity_type="hoa_violation_evidence", entity_id=row.id,
        action="private_case_evidence_archived",
        new_value={
            "association_id": assoc.id, "property_id": property_id,
            "case_id": case.id,
        },
    )
    db.commit()
    return Response(status_code=204, headers={"Cache-Control": "no-store"})
