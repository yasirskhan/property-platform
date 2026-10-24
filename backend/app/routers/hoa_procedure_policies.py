"""Scoped staff procedure configuration, not a source of HOA legal authority."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.hoa_governing_evidence import HOAGoverningEvidence
from app.models.hoa_procedure_policy import HOAProcedurePolicy
from app.models.user import User
from app.routers.auth import get_current_user
from app.routers.hoa_assessments import _scope
from app.routers.hoa_governing_evidence import _attachment, _require_attachment_feature
from app.schemas.hoa_procedure_policy import HOAProcedurePolicyIn, HOAProcedurePolicyOut
from app.services.audit import append_audit_log

router = APIRouter(prefix="/api/hoa/associations", tags=["HOA staff procedure settings"])


def _existing(db: Session, org_id: int, association_id: int, property_id: int):
    return db.query(HOAProcedurePolicy).filter(
        HOAProcedurePolicy.organization_id == org_id,
        HOAProcedurePolicy.association_id == association_id,
        HOAProcedurePolicy.property_id == property_id,
    ).first()


def _out(row: HOAProcedurePolicy) -> HOAProcedurePolicyOut:
    return HOAProcedurePolicyOut(
        id=row.id, association_id=row.association_id,
        property_id=row.property_id, revision=row.revision,
        jurisdiction_state=row.jurisdiction_state,
        jurisdiction_locality=row.jurisdiction_locality,
        notice_preparation_days=row.notice_preparation_days,
        cure_preparation_days=row.cure_preparation_days,
        hearing_request_days=row.hearing_request_days,
        proposed_fine_cap=row.proposed_fine_cap,
        draft_notice_text=row.draft_notice_text,
        supporting_evidence_id=row.supporting_evidence_id,
        updated_at=row.updated_at,
    )


@router.get("/{association_id}/procedure-policy",
            response_model=HOAProcedurePolicyOut | None)
def get_policy(
    association_id: int, response: Response, property_id: int = Query(ge=1),
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org_id, assoc = _scope(
        db, actor=current_user, association_id=association_id,
        property_id=property_id, write=False,
    )
    row = _existing(db, org_id, assoc.id, property_id)
    response.headers["Cache-Control"] = "no-store"
    return _out(row) if row is not None and row.is_active else None


@router.put("/{association_id}/procedure-policy", response_model=HOAProcedurePolicyOut)
def put_policy(
    association_id: int, payload: HOAProcedurePolicyIn,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org_id, assoc = _scope(
        db, actor=current_user, association_id=association_id,
        property_id=payload.property_id, write=True,
    )
    if payload.supporting_evidence_id is not None:
        _require_attachment_feature(db, current_user)
        link = db.query(HOAGoverningEvidence).filter(
            HOAGoverningEvidence.id == payload.supporting_evidence_id,
            HOAGoverningEvidence.organization_id == org_id,
            HOAGoverningEvidence.association_id == assoc.id,
            HOAGoverningEvidence.property_id == payload.property_id,
            HOAGoverningEvidence.is_active.is_(True),
        ).first()
        if link is None:
            raise HTTPException(status_code=404, detail="Private HOA document reference not found.")
        _attachment(
            db, org_id=org_id, prop_id=payload.property_id,
            attachment_id=link.attachment_id,
        )
    row = db.query(HOAProcedurePolicy).filter(
        HOAProcedurePolicy.organization_id == org_id,
        HOAProcedurePolicy.association_id == assoc.id,
        HOAProcedurePolicy.property_id == payload.property_id,
    ).with_for_update().first()
    if row is None:
        row = HOAProcedurePolicy(
            organization_id=org_id, association_id=assoc.id,
            property_id=payload.property_id, revision=1,
            created_by_id=current_user.id,
        )
        db.add(row)
        action = "staff_policy_created"
    else:
        row.revision += 1
        action = "staff_policy_updated"
    row.is_active = True
    row.updated_by_id = current_user.id
    for key, value in payload.model_dump(exclude={"property_id"}).items():
        setattr(row, key, value)
    try:
        db.flush()
        append_audit_log(
            db, organization_id=org_id, user_id=current_user.id,
            entity_type="hoa_procedure_policy", entity_id=row.id,
            action=action,
            new_value={
                "association_id": assoc.id, "property_id": payload.property_id,
                "revision": row.revision,
                "source_ref_present": payload.supporting_evidence_id is not None,
            },
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Procedure settings changed concurrently.") from exc
    db.refresh(row)
    return _out(row)
