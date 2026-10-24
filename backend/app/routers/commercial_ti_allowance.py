"""Commercial TI allowance utilization tracking without implied payment."""
from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.commercial_ti_allowance import CommercialTIAllowanceUse
from app.models.entity_attachment import EntityAttachment
from app.models.user import User
from app.routers.auth import get_current_user
from app.routers.commercial_lease_abstracts import _attachment_gate
from app.routers.commercial_operating_charges import _scope
from app.schemas.commercial_ti_allowance import (
    CommercialTIAllowanceEvidenceOut,
    CommercialTIAllowanceSummaryOut,
    CommercialTIAllowanceUseIn,
    CommercialTIAllowanceUseOut,
    CommercialTIAllowanceVoidIn,
)
from app.services.audit import append_audit_log

router = APIRouter(prefix="/api/properties", tags=["Commercial TI allowance"])
CENT = Decimal("0.01")


def _evidence(db: Session, *, prop, lease, attachment_id: int, actor: User):
    _attachment_gate(db, actor)
    row = db.query(EntityAttachment).filter(
        EntityAttachment.id == attachment_id,
        EntityAttachment.organization_id == prop.organization_id,
        EntityAttachment.is_active.is_(True),
        EntityAttachment.deleted_at.is_(None),
        EntityAttachment.share_with_tenants.is_(False),
        EntityAttachment.share_with_owners.is_(False),
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Private TI evidence not found.")
    valid = (
        (row.entity_type == "properties" and row.entity_id == prop.id)
        or (row.entity_type == "leases" and row.entity_id == lease.id)
    )
    if not valid:
        raise HTTPException(status_code=404, detail="Private TI evidence not found.")
    return row


def _out(row: CommercialTIAllowanceUse) -> CommercialTIAllowanceUseOut:
    return CommercialTIAllowanceUseOut.model_validate(row, from_attributes=True)


def _allowance(terms) -> Decimal:
    if terms.ti_allowance_total is None:
        raise HTTPException(status_code=409, detail="Current authorized terms do not record a TI allowance.")
    value = Decimal(terms.ti_allowance_total).quantize(CENT, rounding=ROUND_HALF_UP)
    if value <= 0:
        raise HTTPException(status_code=409, detail="Current TI allowance must be positive.")
    return value


def _used(db: Session, *, org: int, abstract_id: int) -> Decimal:
    rows = db.query(CommercialTIAllowanceUse.amount).filter(
        CommercialTIAllowanceUse.organization_id == org,
        CommercialTIAllowanceUse.abstract_id == abstract_id,
        CommercialTIAllowanceUse.status == "ACTIVE",
    ).all()
    return sum((Decimal(row[0]) for row in rows), Decimal("0.00")).quantize(CENT)


@router.get("/{property_id}/commercial-lease-abstracts/{abstract_id}/ti-allowance/evidence-candidates",
            response_model=list[CommercialTIAllowanceEvidenceOut])
def evidence_candidates(
    property_id: int, abstract_id: int, response: Response,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    prop, _abstract, lease, _unit, terms = _scope(
        db, property_id=property_id, abstract_id=abstract_id, actor=current_user,
    )
    _allowance(terms)
    _attachment_gate(db, current_user)
    rows = db.query(EntityAttachment).filter(
        EntityAttachment.organization_id == prop.organization_id,
        EntityAttachment.is_active.is_(True),
        EntityAttachment.deleted_at.is_(None),
        EntityAttachment.share_with_tenants.is_(False),
        EntityAttachment.share_with_owners.is_(False),
    ).order_by(EntityAttachment.created_at.desc(), EntityAttachment.id.desc()).limit(301).all()
    visible = [
        row for row in rows
        if (row.entity_type == "properties" and row.entity_id == prop.id)
        or (row.entity_type == "leases" and row.entity_id == lease.id)
    ]
    if len(visible) > 100:
        raise HTTPException(status_code=422, detail="Too many TI evidence documents.")
    response.headers["Cache-Control"] = "no-store"
    return [
        CommercialTIAllowanceEvidenceOut(
            id=row.id, filename=row.original_name, target_type=row.entity_type,
        )
        for row in visible
    ]


@router.get("/{property_id}/commercial-lease-abstracts/{abstract_id}/ti-allowance/summary",
            response_model=CommercialTIAllowanceSummaryOut)
def ti_summary(
    property_id: int, abstract_id: int, response: Response,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    prop, abstract, _lease, _unit, terms = _scope(
        db, property_id=property_id, abstract_id=abstract_id, actor=current_user,
    )
    allowance = _allowance(terms)
    used = _used(db, org=prop.organization_id, abstract_id=abstract.id)
    if used > allowance:
        raise HTTPException(status_code=409, detail="TI allowance utilization exceeds current authorized terms.")
    response.headers["Cache-Control"] = "no-store"
    return CommercialTIAllowanceSummaryOut(
        allowance_total=allowance, used_active=used,
        remaining=(allowance - used).quantize(CENT),
        terms_id=terms.id,
    )


@router.get("/{property_id}/commercial-lease-abstracts/{abstract_id}/ti-allowance",
            response_model=list[CommercialTIAllowanceUseOut])
def list_ti_uses(
    property_id: int, abstract_id: int, response: Response,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    prop, abstract, lease, _unit, _terms = _scope(
        db, property_id=property_id, abstract_id=abstract_id, actor=current_user,
    )
    rows = db.query(CommercialTIAllowanceUse).filter(
        CommercialTIAllowanceUse.organization_id == prop.organization_id,
        CommercialTIAllowanceUse.property_id == prop.id,
        CommercialTIAllowanceUse.lease_id == lease.id,
        CommercialTIAllowanceUse.abstract_id == abstract.id,
    ).order_by(CommercialTIAllowanceUse.id.desc()).limit(501).all()
    if len(rows) > 500:
        raise HTTPException(status_code=422, detail="Too many TI allowance utilization records.")
    response.headers["Cache-Control"] = "no-store"
    return [_out(row) for row in rows]


@router.post("/{property_id}/commercial-lease-abstracts/{abstract_id}/ti-allowance",
             response_model=CommercialTIAllowanceUseOut, status_code=201)
def record_ti_use(
    property_id: int, abstract_id: int, payload: CommercialTIAllowanceUseIn,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    prop, abstract, lease, unit, terms = _scope(
        db, property_id=property_id, abstract_id=abstract_id, actor=current_user,
    )
    allowance = _allowance(terms)
    if payload.incurred_on > date.today():
        raise HTTPException(status_code=422, detail="TI utilization date cannot be in the future.")
    if payload.incurred_on < terms.effective_on:
        raise HTTPException(status_code=409, detail="Current Commercial terms were not effective on the TI utilization date.")
    evidence = _evidence(
        db, prop=prop, lease=lease,
        attachment_id=payload.evidence_attachment_id, actor=current_user,
    )
    amount = Decimal(payload.amount).quantize(CENT, rounding=ROUND_HALF_UP)
    existing = db.query(CommercialTIAllowanceUse).filter(
        CommercialTIAllowanceUse.organization_id == prop.organization_id,
        CommercialTIAllowanceUse.request_key == payload.request_key.strip(),
    ).first()
    if existing is not None:
        if (
            existing.abstract_id != abstract.id
            or existing.terms_id != terms.id
            or existing.evidence_attachment_id != evidence.id
            or existing.incurred_on != payload.incurred_on
            or existing.amount != amount
            or existing.note != payload.note.strip()
        ):
            raise HTTPException(status_code=409, detail="TI request key already used differently.")
        return _out(existing)

    used = _used(db, org=prop.organization_id, abstract_id=abstract.id)
    remaining = (allowance - used - amount).quantize(CENT)
    if remaining < 0:
        raise HTTPException(status_code=409, detail="TI utilization exceeds the current authorized allowance.")
    row = CommercialTIAllowanceUse(
        organization_id=prop.organization_id,
        property_id=prop.id, unit_id=unit.id, lease_id=lease.id,
        abstract_id=abstract.id, terms_id=terms.id,
        tenant_user_id=lease.tenant_id,
        evidence_attachment_id=evidence.id,
        incurred_on=payload.incurred_on,
        amount=amount, allowance_total=allowance,
        remaining_after=remaining,
        note=payload.note.strip(),
        request_key=payload.request_key.strip(),
        status="ACTIVE", created_by_id=current_user.id,
    )
    db.add(row)
    try:
        db.flush()
        append_audit_log(
            db, organization_id=prop.organization_id, user_id=current_user.id,
            entity_type="commercial_ti_allowance_use", entity_id=row.id,
            action="commercial_ti_allowance_utilization_recorded",
            new_value={
                "property_id": prop.id, "lease_id": lease.id,
                "terms_id": terms.id, "amount": str(row.amount),
                "allowance_total": str(row.allowance_total),
                "remaining_after": str(row.remaining_after),
                "evidence_attachment_id": evidence.id,
                "financial_posting": False,
            },
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Concurrent or duplicate TI utilization.") from exc
    db.refresh(row)
    return _out(row)


@router.post("/{property_id}/commercial-lease-abstracts/{abstract_id}/ti-allowance/{row_id}/void",
             response_model=CommercialTIAllowanceUseOut)
def void_ti_use(
    property_id: int, abstract_id: int, row_id: int,
    payload: CommercialTIAllowanceVoidIn,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    prop, abstract, lease, _unit, _terms = _scope(
        db, property_id=property_id, abstract_id=abstract_id, actor=current_user,
    )
    row = db.query(CommercialTIAllowanceUse).filter(
        CommercialTIAllowanceUse.id == row_id,
        CommercialTIAllowanceUse.organization_id == prop.organization_id,
        CommercialTIAllowanceUse.property_id == prop.id,
        CommercialTIAllowanceUse.lease_id == lease.id,
        CommercialTIAllowanceUse.abstract_id == abstract.id,
    ).with_for_update().first()
    if row is None:
        raise HTTPException(status_code=404, detail="TI utilization record not found.")
    if row.status == "VOIDED":
        return _out(row)
    if payload.voided_on < row.incurred_on or payload.voided_on > date.today():
        raise HTTPException(status_code=422, detail="TI void date is outside the allowed range.")
    row.status = "VOIDED"
    row.voided_on = payload.voided_on
    row.void_reason = payload.reason.strip()
    append_audit_log(
        db, organization_id=prop.organization_id, user_id=current_user.id,
        entity_type="commercial_ti_allowance_use", entity_id=row.id,
        action="commercial_ti_allowance_utilization_voided",
        new_value={"voided_on": row.voided_on.isoformat(), "financial_posting": False},
    )
    db.commit()
    db.refresh(row)
    return _out(row)
