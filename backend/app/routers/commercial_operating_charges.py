"""Operational Commercial CAM/NNN charge posting and reversal."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.charge import Charge
from app.models.commercial_lease_abstract import CommercialLeaseTerms
from app.models.commercial_operating_charge import CommercialOperatingCharge
from app.models.gl_account import GLAccount
from app.models.gl_entry import GLEntry
from app.models.gl_transaction import GLTransaction
from app.models.lease import LeaseStatus
from app.models.user import User
from app.routers.auth import get_current_user
from app.routers.commercial_lease_abstracts import _item, _lease, _property, _source_attachment
from app.schemas.commercial_operating_charge import (
    CommercialGLAccountOptionOut,
    CommercialOperatingChargeIssueIn,
    CommercialOperatingChargeOut,
    CommercialOperatingChargeReverseIn,
)
from app.schemas.gl_transaction import PostingLine
from app.services.audit import append_audit_log
from app.services.gl_posting import PostingError, post_transaction
from app.services.menu_resolver import permission_allows_user

router = APIRouter(prefix="/api/properties", tags=["Commercial CAM and NNN"])
ACCOUNTING_KEYS = ("ACCOUNTING.CHARGES", "ACCOUNTING.RECEIVABLES", "ACCOUNTING.GL_ACCOUNTS")
CENT = Decimal("0.01")


def _accountant(db: Session, *, property_id: int, actor: User):
    prop = _property(db, property_id, actor, write=True)
    if any(not permission_allows_user(db, user=actor, menu_key=key) for key in ACCOUNTING_KEYS):
        raise HTTPException(status_code=403, detail="Commercial accounting permissions required.")
    return prop


def _scope(db: Session, *, property_id: int, abstract_id: int, actor: User):
    prop = _accountant(db, property_id=property_id, actor=actor)
    abstract = _item(db, prop, abstract_id)
    lease, unit = _lease(db, prop, abstract.lease_id)
    status = lease.status.value if hasattr(lease.status, "value") else str(lease.status)
    if status != LeaseStatus.ACTIVE.value:
        raise HTTPException(status_code=409, detail="Commercial lease must be active for operating charges.")
    terms = db.query(CommercialLeaseTerms).filter(
        CommercialLeaseTerms.organization_id == prop.organization_id,
        CommercialLeaseTerms.property_id == prop.id,
        CommercialLeaseTerms.lease_id == lease.id,
        CommercialLeaseTerms.abstract_id == abstract.id,
        CommercialLeaseTerms.is_active.is_(True),
    ).with_for_update().first()
    if terms is None or terms.billing_authorized_at is None or terms.billing_authorized_by_id is None:
        raise HTTPException(status_code=409, detail="Current Commercial terms are not authorized for billing.")
    _source_attachment(
        db, prop=prop, lease=lease,
        attachment_id=terms.source_attachment_id, actor=actor,
    )
    return prop, abstract, lease, unit, terms


def _accounts(db: Session, *, org: int, receivable_id: int, income_id: int):
    if receivable_id == income_id:
        raise HTTPException(status_code=422, detail="Commercial receivable and income accounts must differ.")
    found = []
    for ident, kind in ((receivable_id, "ASSET"), (income_id, "INCOME")):
        row = db.query(GLAccount).filter(
            GLAccount.id == ident,
            GLAccount.organization_id == org,
            GLAccount.account_type == kind,
            GLAccount.is_active.is_(True),
            GLAccount.deleted_at.is_(None),
        ).first()
        if row is None:
            raise HTTPException(status_code=404, detail="Active scoped Commercial GL accounts required.")
        found.append(row)
    return found


def _amounts(terms: CommercialLeaseTerms, kind: str):
    cam = Decimal(terms.cam_estimate_monthly or 0).quantize(CENT, rounding=ROUND_HALF_UP)
    tax = Decimal(terms.property_tax_estimate_monthly or 0).quantize(CENT, rounding=ROUND_HALF_UP)
    insurance = Decimal(terms.insurance_estimate_monthly or 0).quantize(CENT, rounding=ROUND_HALF_UP)
    if kind == "CAM":
        tax = Decimal("0.00")
        insurance = Decimal("0.00")
    total = (cam + tax + insurance).quantize(CENT, rounding=ROUND_HALF_UP)
    if total <= 0:
        raise HTTPException(status_code=422, detail="Current terms do not contain a positive amount for this charge.")
    return cam, tax, insurance, total


def _out(row: CommercialOperatingCharge) -> CommercialOperatingChargeOut:
    return CommercialOperatingChargeOut.model_validate(row, from_attributes=True)


@router.get("/{property_id}/commercial-lease-abstracts/{abstract_id}/operating-charges/gl-options",
            response_model=list[CommercialGLAccountOptionOut])
def gl_options(
    property_id: int, abstract_id: int, response: Response,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    prop, *_ = _scope(db, property_id=property_id, abstract_id=abstract_id, actor=current_user)
    rows = db.query(GLAccount).filter(
        GLAccount.organization_id == prop.organization_id,
        GLAccount.account_type.in_(("ASSET", "INCOME")),
        GLAccount.is_active.is_(True), GLAccount.deleted_at.is_(None),
    ).order_by(GLAccount.gl_number, GLAccount.id).limit(501).all()
    if len(rows) > 500:
        raise HTTPException(status_code=422, detail="Too many Commercial GL account options.")
    response.headers["Cache-Control"] = "no-store"
    return [
        CommercialGLAccountOptionOut(
            id=row.id, gl_number=row.gl_number, name=row.name,
            account_type=row.account_type,
        )
        for row in rows
    ]


@router.get("/{property_id}/commercial-lease-abstracts/{abstract_id}/operating-charges",
            response_model=list[CommercialOperatingChargeOut])
def list_operating_charges(
    property_id: int, abstract_id: int, response: Response,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    prop, abstract, lease, _unit, _terms = _scope(
        db, property_id=property_id, abstract_id=abstract_id, actor=current_user,
    )
    rows = db.query(CommercialOperatingCharge).filter(
        CommercialOperatingCharge.organization_id == prop.organization_id,
        CommercialOperatingCharge.property_id == prop.id,
        CommercialOperatingCharge.lease_id == lease.id,
        CommercialOperatingCharge.abstract_id == abstract.id,
    ).order_by(CommercialOperatingCharge.id.desc()).limit(501).all()
    if len(rows) > 500:
        raise HTTPException(status_code=422, detail="Too many Commercial operating charges.")
    response.headers["Cache-Control"] = "no-store"
    return [_out(row) for row in rows]


@router.post("/{property_id}/commercial-lease-abstracts/{abstract_id}/operating-charges",
             response_model=CommercialOperatingChargeOut, status_code=201)
def issue_operating_charge(
    property_id: int, abstract_id: int, payload: CommercialOperatingChargeIssueIn,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    prop, abstract, lease, unit, terms = _scope(
        db, property_id=property_id, abstract_id=abstract_id, actor=current_user,
    )
    if payload.posting_on > date.today():
        raise HTTPException(status_code=422, detail="Commercial charge cannot be future-posted.")
    if terms.effective_on > payload.period_start:
        raise HTTPException(status_code=409, detail="Current Commercial terms are not effective for this period.")

    existing = db.query(CommercialOperatingCharge).filter(
        CommercialOperatingCharge.organization_id == prop.organization_id,
        CommercialOperatingCharge.request_key == payload.request_key.strip(),
    ).first()
    cam, tax, insurance, total = _amounts(terms, payload.kind)
    if existing is not None:
        if (
            existing.property_id != prop.id or existing.abstract_id != abstract.id
            or existing.terms_id != terms.id or existing.kind != payload.kind
            or existing.period_start != payload.period_start or existing.period_end != payload.period_end
            or existing.posting_on != payload.posting_on or existing.due_on != payload.due_on
            or existing.receivable_gl_account_id != payload.receivable_gl_account_id
            or existing.income_gl_account_id != payload.income_gl_account_id
            or existing.total_amount != total
        ):
            raise HTTPException(status_code=409, detail="Commercial request key already used with different terms.")
        return _out(existing)

    receivable, income = _accounts(
        db, org=prop.organization_id,
        receivable_id=payload.receivable_gl_account_id,
        income_id=payload.income_gl_account_id,
    )
    description = (
        f"Commercial CAM {payload.period_start.isoformat()} to {payload.period_end.isoformat()}"
        if payload.kind == "CAM"
        else f"Commercial NNN {payload.period_start.isoformat()} to {payload.period_end.isoformat()}"
    )
    charge = Charge(
        organization_id=prop.organization_id,
        tenant_user_id=lease.tenant_id,
        unit_id=unit.id, property_id=prop.id,
        gl_account_id=income.id,
        charge_date=payload.posting_on,
        description=description,
        amount=total, amount_paid=Decimal("0.00"),
        is_paid=False, is_active=True,
        created_by_id=current_user.id,
    )
    db.add(charge)
    try:
        db.flush()
        txn = post_transaction(
            db,
            organization_id=prop.organization_id,
            transaction_date=payload.posting_on,
            transaction_type="JOURNAL_ENTRY",
            memo=description,
            lines=[
                PostingLine(
                    gl_account_id=receivable.id, property_id=prop.id, unit_id=unit.id,
                    debit=total, credit=Decimal("0.00"),
                ),
                PostingLine(
                    gl_account_id=income.id, property_id=prop.id, unit_id=unit.id,
                    debit=Decimal("0.00"), credit=total,
                ),
            ],
            created_by=current_user,
            reference_number=f"COM{charge.id}",
            source_type="commercial_operating_charge", source_id=charge.id,
            commit=False, write_audit=False,
        )
        row = CommercialOperatingCharge(
            organization_id=prop.organization_id,
            property_id=prop.id, unit_id=unit.id, lease_id=lease.id,
            abstract_id=abstract.id, terms_id=terms.id,
            tenant_user_id=lease.tenant_id, kind=payload.kind,
            period_start=payload.period_start, period_end=payload.period_end,
            posting_on=payload.posting_on, due_on=payload.due_on,
            cam_amount=cam, tax_amount=tax, insurance_amount=insurance,
            total_amount=total,
            receivable_gl_account_id=receivable.id,
            income_gl_account_id=income.id,
            charge_id=charge.id, gl_transaction_id=txn.id,
            request_key=payload.request_key.strip(),
            status="POSTED", created_by_id=current_user.id,
        )
        db.add(row)
        db.flush()
        append_audit_log(
            db, organization_id=prop.organization_id, user_id=current_user.id,
            entity_type="commercial_operating_charge", entity_id=row.id,
            action="commercial_operating_charge_posted",
            new_value={
                "property_id": prop.id, "lease_id": lease.id,
                "terms_id": terms.id, "kind": row.kind,
                "total_amount": str(row.total_amount),
                "charge_id": charge.id, "gl_transaction_id": txn.id,
            },
        )
        db.commit()
    except PostingError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Commercial operating charge GL posting rejected.") from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Concurrent or duplicate Commercial operating charge.") from exc
    db.refresh(row)
    return _out(row)


@router.post("/{property_id}/commercial-lease-abstracts/{abstract_id}/operating-charges/{row_id}/reverse",
             response_model=CommercialOperatingChargeOut)
def reverse_operating_charge(
    property_id: int, abstract_id: int, row_id: int,
    payload: CommercialOperatingChargeReverseIn,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    prop, abstract, lease, _unit, _terms = _scope(
        db, property_id=property_id, abstract_id=abstract_id, actor=current_user,
    )
    row = db.query(CommercialOperatingCharge).filter(
        CommercialOperatingCharge.id == row_id,
        CommercialOperatingCharge.organization_id == prop.organization_id,
        CommercialOperatingCharge.property_id == prop.id,
        CommercialOperatingCharge.lease_id == lease.id,
        CommercialOperatingCharge.abstract_id == abstract.id,
    ).with_for_update().first()
    if row is None:
        raise HTTPException(status_code=404, detail="Commercial operating charge not found.")
    if row.status == "REVERSED":
        return _out(row)
    charge = db.query(Charge).filter(
        Charge.id == row.charge_id,
        Charge.organization_id == prop.organization_id,
    ).with_for_update().first()
    if charge is None or charge.amount_paid != Decimal("0.00") or charge.is_paid:
        raise HTTPException(status_code=409, detail="Paid Commercial charge cannot be reversed.")
    original = db.query(GLTransaction).filter(
        GLTransaction.id == row.gl_transaction_id,
        GLTransaction.organization_id == prop.organization_id,
        GLTransaction.is_reversed.is_(False),
    ).with_for_update().first()
    if (
        original is None
        or original.source_type != "commercial_operating_charge"
        or original.source_id != charge.id
    ):
        raise HTTPException(status_code=409, detail="Original Commercial GL source is invalid.")
    if payload.reversal_on < original.transaction_date or payload.reversal_on > date.today():
        raise HTTPException(status_code=422, detail="Commercial reversal date is outside the allowed range.")
    entries = db.query(GLEntry).filter(
        GLEntry.organization_id == prop.organization_id,
        GLEntry.transaction_id == original.id,
    ).all()
    if len(entries) != 2:
        raise HTTPException(status_code=409, detail="Unexpected Commercial GL shape.")
    try:
        reverse = post_transaction(
            db,
            organization_id=prop.organization_id,
            transaction_date=payload.reversal_on,
            transaction_type="REVERSAL",
            memo=f"Reverse {row.kind} Commercial operating charge",
            lines=[
                PostingLine(
                    gl_account_id=e.gl_account_id, property_id=e.property_id,
                    unit_id=e.unit_id, owner_id=e.owner_id,
                    debit=e.credit, credit=e.debit,
                )
                for e in entries
            ],
            created_by=current_user,
            source_type="commercial_operating_charge", source_id=charge.id,
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
            entity_type="commercial_operating_charge", entity_id=row.id,
            action="commercial_operating_charge_reversed",
            new_value={
                "property_id": prop.id, "lease_id": lease.id,
                "charge_id": charge.id,
                "reversal_gl_transaction_id": reverse.id,
            },
        )
        db.commit()
    except PostingError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Commercial charge reversal GL posting rejected.") from exc
    db.refresh(row)
    return _out(row)
