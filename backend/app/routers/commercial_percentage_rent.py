"""Annual Commercial percentage-rent posting from source-backed sales evidence."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.charge import Charge
from app.models.commercial_percentage_rent import CommercialPercentageRentCharge
from app.models.entity_attachment import EntityAttachment
from app.models.gl_entry import GLEntry
from app.models.gl_transaction import GLTransaction
from app.models.user import User
from app.routers.auth import get_current_user
from app.routers.commercial_lease_abstracts import _attachment_gate
from app.routers.commercial_operating_charges import _accounts, _scope
from app.schemas.commercial_percentage_rent import (
    CommercialPercentageRentEvidenceOut,
    CommercialPercentageRentIn,
    CommercialPercentageRentOut,
    CommercialPercentageRentReverseIn,
)
from app.schemas.gl_transaction import PostingLine
from app.services.audit import append_audit_log
from app.services.gl_posting import PostingError, post_transaction

router = APIRouter(prefix="/api/properties", tags=["Commercial percentage rent"])
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
        raise HTTPException(status_code=404, detail="Private tenant-sales evidence not found.")
    valid = (
        (row.entity_type == "properties" and row.entity_id == prop.id)
        or (row.entity_type == "leases" and row.entity_id == lease.id)
    )
    if not valid:
        raise HTTPException(status_code=404, detail="Private tenant-sales evidence not found.")
    return row


def _out(row: CommercialPercentageRentCharge) -> CommercialPercentageRentOut:
    return CommercialPercentageRentOut.model_validate(row, from_attributes=True)


@router.get("/{property_id}/commercial-lease-abstracts/{abstract_id}/percentage-rent/evidence-candidates",
            response_model=list[CommercialPercentageRentEvidenceOut])
def evidence_candidates(
    property_id: int, abstract_id: int, response: Response,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    prop, _abstract, lease, _unit, terms = _scope(
        db, property_id=property_id, abstract_id=abstract_id, actor=current_user,
    )
    if terms.percentage_rent_rate is None or terms.percentage_rent_breakpoint_annual is None:
        raise HTTPException(status_code=409, detail="Current authorized terms do not record percentage rent.")
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
        raise HTTPException(status_code=422, detail="Too many tenant-sales evidence documents.")
    response.headers["Cache-Control"] = "no-store"
    return [
        CommercialPercentageRentEvidenceOut(
            id=row.id, filename=row.original_name, target_type=row.entity_type,
        )
        for row in visible
    ]


@router.get("/{property_id}/commercial-lease-abstracts/{abstract_id}/percentage-rent",
            response_model=list[CommercialPercentageRentOut])
def list_percentage_rent(
    property_id: int, abstract_id: int, response: Response,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    prop, abstract, lease, _unit, _terms = _scope(
        db, property_id=property_id, abstract_id=abstract_id, actor=current_user,
    )
    rows = db.query(CommercialPercentageRentCharge).filter(
        CommercialPercentageRentCharge.organization_id == prop.organization_id,
        CommercialPercentageRentCharge.property_id == prop.id,
        CommercialPercentageRentCharge.lease_id == lease.id,
        CommercialPercentageRentCharge.abstract_id == abstract.id,
    ).order_by(
        CommercialPercentageRentCharge.reporting_year.desc(),
        CommercialPercentageRentCharge.id.desc(),
    ).limit(101).all()
    if len(rows) > 100:
        raise HTTPException(status_code=422, detail="Too many percentage-rent records.")
    response.headers["Cache-Control"] = "no-store"
    return [_out(row) for row in rows]


@router.post("/{property_id}/commercial-lease-abstracts/{abstract_id}/percentage-rent",
             response_model=CommercialPercentageRentOut, status_code=201)
def record_percentage_rent(
    property_id: int, abstract_id: int, payload: CommercialPercentageRentIn,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    prop, abstract, lease, unit, terms = _scope(
        db, property_id=property_id, abstract_id=abstract_id, actor=current_user,
    )
    if terms.percentage_rent_rate is None or terms.percentage_rent_breakpoint_annual is None:
        raise HTTPException(status_code=409, detail="Current authorized terms do not record percentage rent.")
    if Decimal(terms.percentage_rent_rate) <= 0:
        raise HTTPException(status_code=409, detail="Current percentage-rent rate must be positive.")
    if payload.posting_on > date.today():
        raise HTTPException(status_code=422, detail="Percentage rent cannot be future-posted.")
    if payload.due_on < payload.posting_on:
        raise HTTPException(status_code=422, detail="Percentage-rent due date cannot precede posting.")
    if payload.reporting_year > payload.posting_on.year:
        raise HTTPException(status_code=422, detail="Percentage-rent reporting year cannot follow posting year.")
    if terms.effective_on.year > payload.reporting_year:
        raise HTTPException(status_code=409, detail="Current Commercial terms were not effective in this reporting year.")
    evidence = _evidence(
        db, prop=prop, lease=lease,
        attachment_id=payload.evidence_attachment_id, actor=current_user,
    )

    rate = Decimal(terms.percentage_rent_rate).quantize(Decimal("0.0001"))
    breakpoint = Decimal(terms.percentage_rent_breakpoint_annual).quantize(CENT, rounding=ROUND_HALF_UP)
    gross = Decimal(payload.gross_sales).quantize(CENT, rounding=ROUND_HALF_UP)
    excess = max(gross - breakpoint, Decimal("0.00")).quantize(CENT)
    due = (excess * rate / Decimal("100")).quantize(CENT, rounding=ROUND_HALF_UP)

    existing = db.query(CommercialPercentageRentCharge).filter(
        CommercialPercentageRentCharge.organization_id == prop.organization_id,
        CommercialPercentageRentCharge.request_key == payload.request_key.strip(),
    ).first()
    if existing is not None:
        if (
            existing.abstract_id != abstract.id
            or existing.terms_id != terms.id
            or existing.reporting_year != payload.reporting_year
            or existing.evidence_attachment_id != evidence.id
            or existing.gross_sales != gross
            or existing.breakpoint_annual != breakpoint
            or existing.rate_percent != rate
            or existing.posting_on != payload.posting_on
            or existing.due_on != payload.due_on
            or existing.receivable_gl_account_id != payload.receivable_gl_account_id
            or existing.income_gl_account_id != payload.income_gl_account_id
        ):
            raise HTTPException(status_code=409, detail="Percentage-rent request key already used differently.")
        return _out(existing)
    if db.query(CommercialPercentageRentCharge.id).filter(
        CommercialPercentageRentCharge.abstract_id == abstract.id,
        CommercialPercentageRentCharge.reporting_year == payload.reporting_year,
    ).first() is not None:
        raise HTTPException(status_code=409, detail="This Commercial lease already has percentage rent for that year.")

    receivable, income = _accounts(
        db, org=prop.organization_id,
        receivable_id=payload.receivable_gl_account_id,
        income_id=payload.income_gl_account_id,
    )
    row = CommercialPercentageRentCharge(
        organization_id=prop.organization_id,
        property_id=prop.id, unit_id=unit.id, lease_id=lease.id,
        abstract_id=abstract.id, terms_id=terms.id,
        tenant_user_id=lease.tenant_id,
        evidence_attachment_id=evidence.id,
        reporting_year=payload.reporting_year,
        gross_sales=gross, breakpoint_annual=breakpoint,
        rate_percent=rate, excess_sales=excess,
        percentage_rent_due=due,
        posting_on=payload.posting_on, due_on=payload.due_on,
        receivable_gl_account_id=receivable.id,
        income_gl_account_id=income.id,
        request_key=payload.request_key.strip(),
        status="ZERO" if due == 0 else "POSTED",
        created_by_id=current_user.id,
    )
    db.add(row)
    try:
        db.flush()
        if due > 0:
            charge = Charge(
                organization_id=prop.organization_id,
                tenant_user_id=lease.tenant_id,
                unit_id=unit.id, property_id=prop.id,
                gl_account_id=income.id,
                charge_date=payload.posting_on,
                description=f"Commercial percentage rent {payload.reporting_year}",
                amount=due, amount_paid=Decimal("0.00"),
                is_paid=False, is_active=True,
                created_by_id=current_user.id,
            )
            db.add(charge)
            db.flush()
            txn = post_transaction(
                db,
                organization_id=prop.organization_id,
                transaction_date=payload.posting_on,
                transaction_type="JOURNAL_ENTRY",
                memo=f"Commercial percentage rent {payload.reporting_year}",
                lines=[
                    PostingLine(
                        gl_account_id=receivable.id, property_id=prop.id, unit_id=unit.id,
                        debit=due, credit=Decimal("0.00"),
                    ),
                    PostingLine(
                        gl_account_id=income.id, property_id=prop.id, unit_id=unit.id,
                        debit=Decimal("0.00"), credit=due,
                    ),
                ],
                created_by=current_user,
                reference_number=f"CPR{row.id}",
                source_type="commercial_percentage_rent", source_id=row.id,
                commit=False, write_audit=False,
            )
            row.charge_id = charge.id
            row.gl_transaction_id = txn.id
        db.flush()
        append_audit_log(
            db, organization_id=prop.organization_id, user_id=current_user.id,
            entity_type="commercial_percentage_rent", entity_id=row.id,
            action="commercial_percentage_rent_recorded",
            new_value={
                "property_id": prop.id, "lease_id": lease.id,
                "year": row.reporting_year, "terms_id": terms.id,
                "gross_sales": str(row.gross_sales),
                "breakpoint": str(row.breakpoint_annual),
                "rate_percent": str(row.rate_percent),
                "percentage_rent_due": str(row.percentage_rent_due),
                "gl_transaction_id": row.gl_transaction_id,
            },
        )
        db.commit()
    except PostingError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Commercial percentage-rent GL posting rejected.") from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Concurrent or duplicate Commercial percentage rent.") from exc
    db.refresh(row)
    return _out(row)


@router.post("/{property_id}/commercial-lease-abstracts/{abstract_id}/percentage-rent/{row_id}/reverse",
             response_model=CommercialPercentageRentOut)
def reverse_percentage_rent(
    property_id: int, abstract_id: int, row_id: int,
    payload: CommercialPercentageRentReverseIn,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    prop, abstract, lease, _unit, _terms = _scope(
        db, property_id=property_id, abstract_id=abstract_id, actor=current_user,
    )
    row = db.query(CommercialPercentageRentCharge).filter(
        CommercialPercentageRentCharge.id == row_id,
        CommercialPercentageRentCharge.organization_id == prop.organization_id,
        CommercialPercentageRentCharge.property_id == prop.id,
        CommercialPercentageRentCharge.lease_id == lease.id,
        CommercialPercentageRentCharge.abstract_id == abstract.id,
    ).with_for_update().first()
    if row is None:
        raise HTTPException(status_code=404, detail="Percentage-rent record not found.")
    if row.status == "REVERSED":
        return _out(row)
    if row.status == "ZERO" or row.gl_transaction_id is None or row.charge_id is None:
        raise HTTPException(status_code=409, detail="Zero percentage rent has no financial posting to reverse.")

    charge = db.query(Charge).filter(
        Charge.id == row.charge_id,
        Charge.organization_id == prop.organization_id,
    ).with_for_update().first()
    if charge is None or charge.amount_paid != Decimal("0.00") or charge.is_paid:
        raise HTTPException(status_code=409, detail="Paid percentage-rent charge cannot be reversed.")
    original = db.query(GLTransaction).filter(
        GLTransaction.id == row.gl_transaction_id,
        GLTransaction.organization_id == prop.organization_id,
        GLTransaction.is_reversed.is_(False),
    ).with_for_update().first()
    if (
        original is None
        or original.source_type != "commercial_percentage_rent"
        or original.source_id != row.id
    ):
        raise HTTPException(status_code=409, detail="Original percentage-rent GL source is invalid.")
    if payload.reversal_on < original.transaction_date or payload.reversal_on > date.today():
        raise HTTPException(status_code=422, detail="Percentage-rent reversal date is outside the allowed range.")
    entries = db.query(GLEntry).filter(
        GLEntry.organization_id == prop.organization_id,
        GLEntry.transaction_id == original.id,
    ).all()
    if len(entries) != 2:
        raise HTTPException(status_code=409, detail="Unexpected percentage-rent GL shape.")

    try:
        reverse = post_transaction(
            db,
            organization_id=prop.organization_id,
            transaction_date=payload.reversal_on,
            transaction_type="REVERSAL",
            memo=f"Reverse Commercial percentage rent {row.reporting_year}",
            lines=[
                PostingLine(
                    gl_account_id=e.gl_account_id, property_id=e.property_id,
                    unit_id=e.unit_id, owner_id=e.owner_id,
                    debit=e.credit, credit=e.debit,
                )
                for e in entries
            ],
            created_by=current_user,
            source_type="commercial_percentage_rent", source_id=row.id,
            reversal_of_id=original.id,
            commit=False, write_audit=False,
        )
        original.is_reversed = True
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
            entity_type="commercial_percentage_rent", entity_id=row.id,
            action="commercial_percentage_rent_reversed",
            new_value={"reversal_gl_transaction_id": reverse.id},
        )
        db.commit()
    except PostingError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Percentage-rent reversal GL posting rejected.") from exc
    db.refresh(row)
    return _out(row)
