"""Annual Commercial CAM reconciliation against posted estimate recoveries."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.charge import Charge
from app.models.commercial_cam_reconciliation import CommercialCAMReconciliation
from app.models.commercial_operating_charge import CommercialOperatingCharge
from app.models.entity_attachment import EntityAttachment
from app.models.gl_entry import GLEntry
from app.models.gl_transaction import GLTransaction
from app.models.user import User
from app.routers.auth import get_current_user
from app.routers.commercial_lease_abstracts import _attachment_gate
from app.routers.commercial_operating_charges import _accounts, _scope
from app.schemas.commercial_cam_reconciliation import (
    CommercialCAMReconciliationEvidenceOut,
    CommercialCAMReconciliationIn,
    CommercialCAMReconciliationOut,
    CommercialCAMReconciliationReverseIn,
)
from app.schemas.gl_transaction import PostingLine
from app.services.audit import append_audit_log
from app.services.gl_posting import PostingError, post_transaction

router = APIRouter(prefix="/api/properties", tags=["Commercial CAM reconciliation"])
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
        raise HTTPException(status_code=404, detail="Private CAM reconciliation evidence not found.")
    valid = (
        (row.entity_type == "properties" and row.entity_id == prop.id)
        or (row.entity_type == "leases" and row.entity_id == lease.id)
    )
    if not valid:
        raise HTTPException(status_code=404, detail="Private CAM reconciliation evidence not found.")
    return row


def _out(row: CommercialCAMReconciliation) -> CommercialCAMReconciliationOut:
    return CommercialCAMReconciliationOut.model_validate(row, from_attributes=True)


@router.get("/{property_id}/commercial-lease-abstracts/{abstract_id}/cam-reconciliations/evidence-candidates",
            response_model=list[CommercialCAMReconciliationEvidenceOut])
def evidence_candidates(
    property_id: int, abstract_id: int, response: Response,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    prop, _abstract, lease, _unit, _terms = _scope(
        db, property_id=property_id, abstract_id=abstract_id, actor=current_user,
    )
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
        raise HTTPException(status_code=422, detail="Too many CAM evidence documents.")
    response.headers["Cache-Control"] = "no-store"
    return [
        CommercialCAMReconciliationEvidenceOut(
            id=row.id, filename=row.original_name, target_type=row.entity_type,
        )
        for row in visible
    ]


@router.get("/{property_id}/commercial-lease-abstracts/{abstract_id}/cam-reconciliations",
            response_model=list[CommercialCAMReconciliationOut])
def list_reconciliations(
    property_id: int, abstract_id: int, response: Response,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    prop, abstract, lease, _unit, _terms = _scope(
        db, property_id=property_id, abstract_id=abstract_id, actor=current_user,
    )
    rows = db.query(CommercialCAMReconciliation).filter(
        CommercialCAMReconciliation.organization_id == prop.organization_id,
        CommercialCAMReconciliation.property_id == prop.id,
        CommercialCAMReconciliation.lease_id == lease.id,
        CommercialCAMReconciliation.abstract_id == abstract.id,
    ).order_by(
        CommercialCAMReconciliation.reconciliation_year.desc(),
        CommercialCAMReconciliation.id.desc(),
    ).limit(101).all()
    if len(rows) > 100:
        raise HTTPException(status_code=422, detail="Too many CAM reconciliation records.")
    response.headers["Cache-Control"] = "no-store"
    return [_out(row) for row in rows]


@router.post("/{property_id}/commercial-lease-abstracts/{abstract_id}/cam-reconciliations",
             response_model=CommercialCAMReconciliationOut, status_code=201)
def record_reconciliation(
    property_id: int, abstract_id: int, payload: CommercialCAMReconciliationIn,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    prop, abstract, lease, unit, terms = _scope(
        db, property_id=property_id, abstract_id=abstract_id, actor=current_user,
    )
    if terms.cam_share_percent is None:
        raise HTTPException(status_code=409, detail="Current authorized terms do not record a CAM share.")
    if payload.posting_on > date.today():
        raise HTTPException(status_code=422, detail="CAM reconciliation cannot be future-posted.")
    if payload.reconciliation_year > payload.posting_on.year:
        raise HTTPException(status_code=422, detail="CAM reconciliation year cannot follow the posting year.")
    if payload.due_on < payload.posting_on:
        raise HTTPException(status_code=422, detail="CAM reconciliation due date cannot precede posting.")
    evidence = _evidence(
        db, prop=prop, lease=lease,
        attachment_id=payload.evidence_attachment_id, actor=current_user,
    )
    existing = db.query(CommercialCAMReconciliation).filter(
        CommercialCAMReconciliation.organization_id == prop.organization_id,
        CommercialCAMReconciliation.request_key == payload.request_key.strip(),
    ).first()
    if existing is not None:
        if (
            existing.abstract_id != abstract.id
            or existing.reconciliation_year != payload.reconciliation_year
            or existing.evidence_attachment_id != evidence.id
            or existing.actual_cam_total != payload.actual_cam_total
            or existing.posting_on != payload.posting_on
            or existing.due_on != payload.due_on
            or existing.receivable_gl_account_id != payload.receivable_gl_account_id
            or existing.income_gl_account_id != payload.income_gl_account_id
        ):
            raise HTTPException(status_code=409, detail="CAM reconciliation request key already used differently.")
        return _out(existing)
    if db.query(CommercialCAMReconciliation.id).filter(
        CommercialCAMReconciliation.abstract_id == abstract.id,
        CommercialCAMReconciliation.reconciliation_year == payload.reconciliation_year,
    ).first() is not None:
        raise HTTPException(status_code=409, detail="This Commercial lease already has a reconciliation for that year.")

    receivable, income = _accounts(
        db, org=prop.organization_id,
        receivable_id=payload.receivable_gl_account_id,
        income_id=payload.income_gl_account_id,
    )
    share = Decimal(terms.cam_share_percent).quantize(Decimal("0.0001"))
    actual_total = Decimal(payload.actual_cam_total).quantize(CENT, rounding=ROUND_HALF_UP)
    actual_share = (actual_total * share / Decimal("100")).quantize(CENT, rounding=ROUND_HALF_UP)
    start = date(payload.reconciliation_year, 1, 1)
    end = date(payload.reconciliation_year, 12, 31)
    operating = db.query(CommercialOperatingCharge).filter(
        CommercialOperatingCharge.organization_id == prop.organization_id,
        CommercialOperatingCharge.property_id == prop.id,
        CommercialOperatingCharge.lease_id == lease.id,
        CommercialOperatingCharge.abstract_id == abstract.id,
        CommercialOperatingCharge.status == "POSTED",
        CommercialOperatingCharge.period_start >= start,
        CommercialOperatingCharge.period_start <= end,
    ).with_for_update().all()
    estimated = sum((Decimal(row.cam_amount) for row in operating), Decimal("0.00")).quantize(CENT)
    true_up = (actual_share - estimated).quantize(CENT, rounding=ROUND_HALF_UP)

    row = CommercialCAMReconciliation(
        organization_id=prop.organization_id,
        property_id=prop.id, unit_id=unit.id, lease_id=lease.id,
        abstract_id=abstract.id, terms_id=terms.id,
        tenant_user_id=lease.tenant_id,
        evidence_attachment_id=evidence.id,
        reconciliation_year=payload.reconciliation_year,
        actual_cam_total=actual_total,
        share_percent=share,
        actual_tenant_share=actual_share,
        estimated_cam_billed=estimated,
        true_up_amount=true_up,
        posting_on=payload.posting_on, due_on=payload.due_on,
        receivable_gl_account_id=receivable.id,
        income_gl_account_id=income.id,
        request_key=payload.request_key.strip(),
        status="ZERO" if true_up == 0 else "POSTED",
        created_by_id=current_user.id,
    )
    db.add(row)
    try:
        db.flush()
        if true_up != 0:
            amount = abs(true_up)
            charge = None
            if true_up > 0:
                charge = Charge(
                    organization_id=prop.organization_id,
                    tenant_user_id=lease.tenant_id,
                    unit_id=unit.id, property_id=prop.id,
                    gl_account_id=income.id,
                    charge_date=payload.posting_on,
                    description=f"Commercial CAM reconciliation {payload.reconciliation_year}",
                    amount=amount, amount_paid=Decimal("0.00"),
                    is_paid=False, is_active=True,
                    created_by_id=current_user.id,
                )
                db.add(charge)
                db.flush()
                row.charge_id = charge.id
            lines = (
                [
                    PostingLine(gl_account_id=receivable.id, property_id=prop.id, unit_id=unit.id,
                                debit=amount, credit=Decimal("0.00")),
                    PostingLine(gl_account_id=income.id, property_id=prop.id, unit_id=unit.id,
                                debit=Decimal("0.00"), credit=amount),
                ]
                if true_up > 0 else
                [
                    PostingLine(gl_account_id=income.id, property_id=prop.id, unit_id=unit.id,
                                debit=amount, credit=Decimal("0.00")),
                    PostingLine(gl_account_id=receivable.id, property_id=prop.id, unit_id=unit.id,
                                debit=Decimal("0.00"), credit=amount),
                ]
            )
            txn = post_transaction(
                db,
                organization_id=prop.organization_id,
                transaction_date=payload.posting_on,
                transaction_type="JOURNAL_ENTRY",
                memo=f"Commercial CAM annual reconciliation {payload.reconciliation_year}",
                lines=lines,
                created_by=current_user,
                reference_number=f"CAMR{row.id}",
                source_type="commercial_cam_reconciliation", source_id=row.id,
                commit=False, write_audit=False,
            )
            row.gl_transaction_id = txn.id
        db.flush()
        append_audit_log(
            db, organization_id=prop.organization_id, user_id=current_user.id,
            entity_type="commercial_cam_reconciliation", entity_id=row.id,
            action="commercial_cam_reconciliation_recorded",
            new_value={
                "property_id": prop.id, "lease_id": lease.id,
                "year": row.reconciliation_year,
                "actual_cam_total": str(row.actual_cam_total),
                "share_percent": str(row.share_percent),
                "estimated_cam_billed": str(row.estimated_cam_billed),
                "true_up_amount": str(row.true_up_amount),
                "gl_transaction_id": row.gl_transaction_id,
            },
        )
        db.commit()
    except PostingError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Commercial CAM reconciliation GL posting rejected.") from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Concurrent or duplicate CAM reconciliation.") from exc
    db.refresh(row)
    return _out(row)


@router.post("/{property_id}/commercial-lease-abstracts/{abstract_id}/cam-reconciliations/{row_id}/reverse",
             response_model=CommercialCAMReconciliationOut)
def reverse_reconciliation(
    property_id: int, abstract_id: int, row_id: int,
    payload: CommercialCAMReconciliationReverseIn,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    prop, abstract, lease, _unit, _terms = _scope(
        db, property_id=property_id, abstract_id=abstract_id, actor=current_user,
    )
    row = db.query(CommercialCAMReconciliation).filter(
        CommercialCAMReconciliation.id == row_id,
        CommercialCAMReconciliation.organization_id == prop.organization_id,
        CommercialCAMReconciliation.property_id == prop.id,
        CommercialCAMReconciliation.lease_id == lease.id,
        CommercialCAMReconciliation.abstract_id == abstract.id,
    ).with_for_update().first()
    if row is None:
        raise HTTPException(status_code=404, detail="CAM reconciliation not found.")
    if row.status == "REVERSED":
        return _out(row)
    if row.status == "ZERO" or row.gl_transaction_id is None:
        raise HTTPException(status_code=409, detail="Zero CAM reconciliation has no financial posting to reverse.")
    charge = None
    if row.charge_id is not None:
        charge = db.query(Charge).filter(
            Charge.id == row.charge_id,
            Charge.organization_id == prop.organization_id,
        ).with_for_update().first()
        if charge is None or charge.amount_paid != Decimal("0.00") or charge.is_paid:
            raise HTTPException(status_code=409, detail="Paid CAM reconciliation charge cannot be reversed.")
    original = db.query(GLTransaction).filter(
        GLTransaction.id == row.gl_transaction_id,
        GLTransaction.organization_id == prop.organization_id,
        GLTransaction.is_reversed.is_(False),
    ).with_for_update().first()
    if (
        original is None
        or original.source_type != "commercial_cam_reconciliation"
        or original.source_id != row.id
    ):
        raise HTTPException(status_code=409, detail="Original CAM reconciliation GL source is invalid.")
    if payload.reversal_on < original.transaction_date or payload.reversal_on > date.today():
        raise HTTPException(status_code=422, detail="CAM reconciliation reversal date is outside the allowed range.")
    entries = db.query(GLEntry).filter(
        GLEntry.organization_id == prop.organization_id,
        GLEntry.transaction_id == original.id,
    ).all()
    if len(entries) != 2:
        raise HTTPException(status_code=409, detail="Unexpected CAM reconciliation GL shape.")
    try:
        reverse = post_transaction(
            db,
            organization_id=prop.organization_id,
            transaction_date=payload.reversal_on,
            transaction_type="REVERSAL",
            memo=f"Reverse Commercial CAM reconciliation {row.reconciliation_year}",
            lines=[
                PostingLine(
                    gl_account_id=e.gl_account_id, property_id=e.property_id,
                    unit_id=e.unit_id, owner_id=e.owner_id,
                    debit=e.credit, credit=e.debit,
                )
                for e in entries
            ],
            created_by=current_user,
            source_type="commercial_cam_reconciliation", source_id=row.id,
            reversal_of_id=original.id,
            commit=False, write_audit=False,
        )
        original.is_reversed = True
        if charge is not None:
            charge.is_active = False
            charge.deleted_at = datetime.utcnow()
            charge.delete_reason = payload.reason.strip()
        row.status = "REVERSED"
        row.reversal_transaction_id = reverse.id
        row.reversal_on = payload.reversal_on
        row.reversal_reason = payload.reason.strip()
        db.flush()
        append_audit_log(
            db, organization_id=prop.organization_id, user_id=current_user.id,
            entity_type="commercial_cam_reconciliation", entity_id=row.id,
            action="commercial_cam_reconciliation_reversed",
            new_value={"reversal_gl_transaction_id": reverse.id},
        )
        db.commit()
    except PostingError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="CAM reconciliation reversal GL posting rejected.") from exc
    db.refresh(row)
    return _out(row)
