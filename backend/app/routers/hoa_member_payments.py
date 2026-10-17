"""Actual offline-recorded HOA member receipt with central GL allocation.

No bank collection is initiated. Reuse existing Receipt / ReceiptLine
and post_transaction() atomically; payment row only links the HOA charge.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.deposit_line import DepositLine
from app.models.gl_account import GLAccount
from app.models.gl_entry import GLEntry
from app.models.gl_transaction import GLTransaction
from app.models.hoa_member_assessment import HOAAssessmentDecision, HOAMemberAssessmentCharge
from app.models.hoa_member_assessment_payment import HOAMemberAssessmentPayment
from app.models.receipt import Receipt
from app.models.receipt_line import ReceiptLine
from app.models.user import User
from app.routers.auth import get_current_user
from app.routers.hoa_arc_applications import _contact_link
from app.routers.hoa_arc_board_decisions import _verified_member
from app.routers.hoa_member_assessments import _accountant
from app.schemas.gl_transaction import PostingLine
from app.schemas.hoa_member_payment import (
    HOAMemberPaymentIn, HOAMemberPaymentOut,
    HOAMemberPaymentReverseIn, HOAReceiptCashOption,
)
from app.services.audit import append_audit_log
from app.services.gl_posting import PostingError, post_transaction

router = APIRouter(prefix="/api/hoa/associations", tags=["HOA member assessment receipt allocation"])


def _charge(db: Session, *, org: int, assoc: int, prop: int, proposal: int,
            charge_id: int, lock: bool = False):
    query = db.query(HOAMemberAssessmentCharge).join(
        HOAAssessmentDecision,
        HOAAssessmentDecision.id == HOAMemberAssessmentCharge.decision_id,
    ).filter(
        HOAMemberAssessmentCharge.id == charge_id,
        HOAMemberAssessmentCharge.organization_id == org,
        HOAMemberAssessmentCharge.association_id == assoc,
        HOAMemberAssessmentCharge.property_id == prop,
        HOAAssessmentDecision.organization_id == org,
        HOAAssessmentDecision.association_id == assoc,
        HOAAssessmentDecision.property_id == prop,
        HOAAssessmentDecision.proposal_id == proposal,
    )
    row = (query.with_for_update() if lock else query).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Scoped member assessment not found.")
    return row


def _out(row: HOAMemberAssessmentPayment):
    return HOAMemberPaymentOut(
        id=row.id, charge_id=row.charge_id, property_id=row.property_id,
        member_user_id=row.member_user_id, amount=row.amount,
        received_on=row.received_on, payment_reference=row.payment_reference,
        cash_gl_account_id=row.cash_gl_account_id, receipt_id=row.receipt_id,
        status=row.status, reversal_receipt_id=row.reversal_receipt_id,
        reversed_on=row.reversed_on, created_at=row.created_at,
    )


def _audit(db: Session, *, row: HOAMemberAssessmentPayment, actor: User, action: str):
    append_audit_log(
        db, organization_id=row.organization_id, user_id=actor.id,
        entity_type="hoa_member_assessment_payment", entity_id=row.id,
        action=action, new_value={
            "association_id": row.association_id,
            "property_id": row.property_id,
            "charge_id": row.charge_id,
            "member_user_id": row.member_user_id,
            "receipt_id": row.receipt_id,
            "reversal_receipt_id": row.reversal_receipt_id,
            "status": row.status,
            "amount": str(row.amount),
        },
    )


def _cash(db: Session, *, org: int, cash_id: int, receivable_id: int):
    account = db.query(GLAccount).filter(
        GLAccount.id == cash_id,
        GLAccount.organization_id == org,
        GLAccount.account_type == "ASSET",
        GLAccount.include_on_cash_flow.is_(True),
        GLAccount.is_active.is_(True),
        GLAccount.deleted_at.is_(None),
    ).first()
    if account is None or account.id == receivable_id:
        raise HTTPException(status_code=404, detail="Active distinct cash-like GL account required.")
    return account


@router.get("/{association_id}/draft-assessments/{proposal_id}/member-ledger/{charge_id}/cash-options",
            response_model=list[HOAReceiptCashOption])
def receipt_cash_options(
    association_id: int, proposal_id: int, charge_id: int,
    response: Response, property_id: int = Query(ge=1),
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org, assoc = _accountant(db, actor=current_user, assoc=association_id, prop=property_id)
    charge = _charge(db, org=org, assoc=assoc.id, prop=property_id,
                     proposal=proposal_id, charge_id=charge_id)
    accounts = db.query(GLAccount).filter(
        GLAccount.organization_id == org,
        GLAccount.account_type == "ASSET",
        GLAccount.include_on_cash_flow.is_(True),
        GLAccount.is_active.is_(True),
        GLAccount.deleted_at.is_(None),
        GLAccount.id != charge.receivable_gl_account_id,
    ).order_by(GLAccount.gl_number, GLAccount.id).limit(501).all()
    if len(accounts) > 500:
        raise HTTPException(status_code=422, detail="Too many cash GL accounts.")
    response.headers["Cache-Control"] = "no-store"
    return [HOAReceiptCashOption(id=a.id, number=a.gl_number, name=a.name) for a in accounts]


@router.get("/{association_id}/draft-assessments/{proposal_id}/member-ledger/{charge_id}/payments",
            response_model=list[HOAMemberPaymentOut])
def list_assessment_payments(
    association_id: int, proposal_id: int, charge_id: int,
    response: Response, property_id: int = Query(ge=1),
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org, assoc = _accountant(db, actor=current_user, assoc=association_id, prop=property_id)
    charge = _charge(db, org=org, assoc=assoc.id, prop=property_id,
                     proposal=proposal_id, charge_id=charge_id)
    rows = db.query(HOAMemberAssessmentPayment).filter(
        HOAMemberAssessmentPayment.organization_id == org,
        HOAMemberAssessmentPayment.association_id == assoc.id,
        HOAMemberAssessmentPayment.property_id == property_id,
        HOAMemberAssessmentPayment.charge_id == charge.id,
    ).order_by(HOAMemberAssessmentPayment.id).limit(501).all()
    if len(rows) > 500:
        raise HTTPException(status_code=422, detail="Too many member receipts.")
    response.headers["Cache-Control"] = "no-store"
    return [_out(row) for row in rows]


@router.post("/{association_id}/draft-assessments/{proposal_id}/member-ledger/{charge_id}/payments",
             response_model=HOAMemberPaymentOut, status_code=201)
def record_assessment_payment(
    association_id: int, proposal_id: int, charge_id: int,
    payload: HOAMemberPaymentIn,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org, assoc = _accountant(
        db, actor=current_user, assoc=association_id, prop=payload.property_id,
    )
    charge = _charge(
        db, org=org, assoc=assoc.id, prop=payload.property_id,
        proposal=proposal_id, charge_id=charge_id, lock=True,
    )
    existing = db.query(HOAMemberAssessmentPayment).filter(
        HOAMemberAssessmentPayment.organization_id == org,
        HOAMemberAssessmentPayment.idempotency_key == payload.idempotency_key,
    ).first()
    if existing is not None:
        same = (
            existing.association_id == assoc.id
            and existing.property_id == payload.property_id
            and existing.charge_id == charge.id
            and existing.member_user_id == payload.member_user_id
            and existing.cash_gl_account_id == payload.cash_gl_account_id
            and existing.amount == payload.amount
            and existing.received_on == payload.received_on
            and existing.payment_reference == payload.payment_reference
        )
        if not same:
            raise HTTPException(status_code=409, detail="Receipt request key already used.")
        return _out(existing)
    if charge.status not in {"OPEN", "PAID"}:
        raise HTTPException(status_code=409, detail="Cannot pay a reversed member assessment.")
    if charge.member_user_id != payload.member_user_id:
        raise HTTPException(status_code=409, detail="Receipt member differs from assessed member.")
    decision = db.query(HOAAssessmentDecision).filter(
        HOAAssessmentDecision.id == charge.decision_id,
        HOAAssessmentDecision.organization_id == org,
        HOAAssessmentDecision.association_id == assoc.id,
        HOAAssessmentDecision.property_id == payload.property_id,
        HOAAssessmentDecision.proposal_id == proposal_id,
        HOAAssessmentDecision.decision == "APPROVED",
    ).first()
    if decision is None or decision.member_user_id != charge.member_user_id:
        raise HTTPException(status_code=409, detail="Approved responsible member required.")
    link, contact = _contact_link(
        db, org_id=org, association_id=assoc.id,
        property_id=payload.property_id, link_id=charge.contact_link_id,
    )
    member = _verified_member(db, org=org, contact=contact)
    if member is None or member.id != charge.member_user_id:
        raise HTTPException(status_code=409, detail="Responsible member login no longer verified.")
    if payload.received_on > date.today():
        raise HTTPException(status_code=422, detail="Cannot record future received funds.")
    outstanding = charge.amount - charge.amount_paid
    if outstanding <= 0 or payload.amount > outstanding:
        raise HTTPException(status_code=409, detail="Receipt exceeds current outstanding assessment.")
    cash = _cash(db, org=org, cash_id=payload.cash_gl_account_id,
                 receivable_id=charge.receivable_gl_account_id)
    ar = db.query(GLAccount).filter(
        GLAccount.id == charge.receivable_gl_account_id,
        GLAccount.organization_id == org,
        GLAccount.account_type == "ASSET",
        GLAccount.is_active.is_(True),
        GLAccount.deleted_at.is_(None),
    ).first()
    if ar is None:
        raise HTTPException(status_code=409, detail="Original active scoped receivable GL missing.")
    if db.query(HOAMemberAssessmentPayment.id).filter(
        HOAMemberAssessmentPayment.organization_id == org,
        HOAMemberAssessmentPayment.charge_id == charge.id,
    ).limit(500).count() >= 500:
        raise HTTPException(status_code=422, detail="Member payment history limit reached.")
    try:
        # Existing first-party Receipt and receipt-line storage, not a
        # second receipt/ledger. The protected HOA route is the only creator
        # of type HOA_MEMBER; generic receipt input forbids that type.
        receipt = Receipt(
            organization_id=org, type="HOA_MEMBER",
            receipt_date=payload.received_on, amount=payload.amount,
            cash_gl_account_id=cash.id,
            property_id=payload.property_id,
            received_from=(member.first_name + " " + member.last_name).strip(),
            exclude_from_mgmt_fee=True, reference_number=payload.payment_reference,
            remarks="HOA member assessment received offline",
            created_by_id=current_user.id,
            is_reversed=False, is_active=True,
        )
        db.add(receipt)
        db.flush()
        transaction = post_transaction(
            db, organization_id=org, transaction_date=payload.received_on,
            transaction_type="RECEIPT", memo="HOA verified member payment received offline",
            lines=[
                PostingLine(gl_account_id=cash.id, property_id=payload.property_id,
                            debit=payload.amount, credit=Decimal("0")),
                PostingLine(gl_account_id=ar.id, property_id=payload.property_id,
                            debit=Decimal("0"), credit=payload.amount),
            ], created_by=current_user, reference_number=payload.payment_reference,
            source_type="receipt", source_id=receipt.id,
            commit=False, write_audit=False,
        )
        receipt.gl_transaction_id = transaction.id
        db.add(ReceiptLine(
            organization_id=org, receipt_id=receipt.id,
            gl_account_id=ar.id, property_id=payload.property_id,
            description="HOA member assessment receivable payment",
            amount_to_pay=payload.amount, line_date=payload.received_on,
            is_prepayment=False,
        ))
        payment = HOAMemberAssessmentPayment(
            organization_id=org, association_id=assoc.id,
            property_id=payload.property_id, charge_id=charge.id,
            member_user_id=member.id, receipt_id=receipt.id,
            cash_gl_account_id=cash.id, amount=payload.amount,
            received_on=payload.received_on,
            idempotency_key=payload.idempotency_key,
            payment_reference=payload.payment_reference,
            status="POSTED", created_by_id=current_user.id,
        )
        db.add(payment)
        charge.amount_paid += payload.amount
        charge.status = "PAID" if charge.amount_paid == charge.amount else "OPEN"
        db.flush()
        _audit(db, row=payment, actor=current_user, action="member_receipt_allocated")
        db.commit()
    except PostingError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Central GL refused member receipt posting.") from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Concurrent or duplicate HOA member receipt.") from exc
    db.refresh(payment)
    return _out(payment)


@router.post("/{association_id}/draft-assessments/{proposal_id}/member-ledger/{charge_id}/payments/{payment_id}/reverse",
             response_model=HOAMemberPaymentOut)
def reverse_assessment_payment(
    association_id: int, proposal_id: int, charge_id: int, payment_id: int,
    payload: HOAMemberPaymentReverseIn,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org, assoc = _accountant(
        db, actor=current_user, assoc=association_id, prop=payload.property_id,
    )
    charge = _charge(
        db, org=org, assoc=assoc.id, prop=payload.property_id,
        proposal=proposal_id, charge_id=charge_id, lock=True,
    )
    payment = db.query(HOAMemberAssessmentPayment).filter(
        HOAMemberAssessmentPayment.id == payment_id,
        HOAMemberAssessmentPayment.organization_id == org,
        HOAMemberAssessmentPayment.association_id == assoc.id,
        HOAMemberAssessmentPayment.property_id == payload.property_id,
        HOAMemberAssessmentPayment.charge_id == charge.id,
    ).with_for_update().first()
    if payment is None:
        raise HTTPException(status_code=404, detail="Scoped member payment not found.")
    if payment.status != "POSTED" or payment.reversal_receipt_id is not None:
        raise HTTPException(status_code=409, detail="Member receipt already reversed.")
    original = db.query(Receipt).filter(
        Receipt.id == payment.receipt_id,
        Receipt.organization_id == org,
        Receipt.property_id == payload.property_id,
        Receipt.type == "HOA_MEMBER",
        Receipt.is_reversed.is_(False),
    ).with_for_update().first()
    if original is None or original.amount != payment.amount:
        raise HTTPException(status_code=409, detail="Original HOA receipt is unavailable or differs.")
    posted = db.query(GLTransaction).filter(
        GLTransaction.id == original.gl_transaction_id,
        GLTransaction.organization_id == org,
        GLTransaction.source_type == "receipt",
        GLTransaction.source_id == original.id,
        GLTransaction.is_reversed.is_(False),
    ).with_for_update().first()
    if posted is None:
        raise HTTPException(status_code=409, detail="Original receipt GL source invalid.")
    if payload.reversal_on < posted.transaction_date or payload.reversal_on > date.today():
        raise HTTPException(status_code=422, detail="Reversal cannot predate receipt or be future-dated.")
    if db.query(DepositLine.id).filter(
        DepositLine.organization_id == org, DepositLine.receipt_id == original.id,
    ).first() is not None:
        raise HTTPException(status_code=409, detail="Deposited receipt requires separate bank reconciliation before reversal.")
    entries = db.query(GLEntry).filter(
        GLEntry.organization_id == org,
        GLEntry.transaction_id == posted.id,
    ).all()
    if (len(entries) != 2 or {e.gl_account_id for e in entries}
            != {payment.cash_gl_account_id, charge.receivable_gl_account_id}):
        raise HTTPException(status_code=409, detail="Original receipt GL shape invalid.")
    if charge.status not in {"OPEN", "PAID"} or charge.amount_paid < payment.amount:
        raise HTTPException(status_code=409, detail="Payment allocation cannot be reconciled.")
    try:
        reversal = post_transaction(
            db, organization_id=org, transaction_date=payload.reversal_on,
            transaction_type="REVERSAL", memo="HOA member receipt reversal",
            lines=[
                PostingLine(gl_account_id=e.gl_account_id, property_id=e.property_id,
                            unit_id=e.unit_id, owner_id=e.owner_id,
                            debit=e.credit, credit=e.debit) for e in entries
            ], created_by=current_user, source_type="receipt",
            source_id=original.id, reversal_of_id=posted.id,
            commit=False, write_audit=False,
        )
        posted.is_reversed = True
        original.is_reversed = True
        mirror = Receipt(
            organization_id=org, type="HOA_MEMBER",
            receipt_date=payload.reversal_on, amount=payment.amount,
            cash_gl_account_id=original.cash_gl_account_id,
            received_from=original.received_from,
            property_id=payload.property_id, exclude_from_mgmt_fee=True,
            reference_number=original.reference_number,
            remarks="Reversal of HOA member receipt",
            gl_transaction_id=reversal.id, reversal_of_id=original.id,
            created_by_id=current_user.id,
            is_reversed=False, is_active=True,
        )
        db.add(mirror)
        db.flush()
        payment.status = "REVERSED"
        payment.reversal_receipt_id = mirror.id
        payment.reversed_on = payload.reversal_on
        payment.reversal_reason = payload.reason
        payment.reversed_by_id = current_user.id
        charge.amount_paid -= payment.amount
        charge.status = "PAID" if charge.amount_paid == charge.amount else "OPEN"
        db.flush()
        _audit(db, row=payment, actor=current_user, action="member_receipt_reversed")
        db.commit()
    except PostingError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Central GL refused receipt reversal.") from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Concurrent HOA receipt reversal.") from exc
    db.refresh(payment)
    return _out(payment)
