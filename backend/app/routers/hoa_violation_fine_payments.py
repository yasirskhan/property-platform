"""Offline-recorded fine-specific receipts, protected by the existing central GL.

No bank or card collection occurs. Recorded funds must already have been received.
Each receipt is bound to an authorized posted fine and verified liable member.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.deposit_line import DepositLine
from app.models.gl_account import GLAccount
from app.models.gl_entry import GLEntry
from app.models.gl_transaction import GLTransaction
from app.models.hoa_violation_fine_payment import HOAViolationFinePayment
from app.models.receipt import Receipt
from app.models.receipt_line import ReceiptLine
from app.models.user import User
from app.routers.auth import get_current_user
from app.routers.hoa_member_assessments import _accountant
from app.routers.hoa_member_payments import _cash
from app.routers.hoa_violation_cases import _case
from app.routers.hoa_violation_fines import _fine, _service, _current_member
from app.schemas.gl_transaction import PostingLine
from app.schemas.hoa_member_payment import HOAReceiptCashOption
from app.schemas.hoa_violation_fine_payment import (
    HOAFinePaymentIn, HOAFinePaymentOut, HOAFinePaymentReverseIn,
)
from app.services.audit import append_audit_log
from app.services.gl_posting import post_transaction, PostingError

router = APIRouter(prefix="/api/hoa/associations", tags=["HOA violation fine receipts"])


def _out(row):
    return HOAFinePaymentOut(
        id=row.id, fine_id=row.fine_id, property_id=row.property_id,
        member_user_id=row.member_user_id, amount=row.amount,
        received_on=row.received_on, payment_reference=row.payment_reference,
        cash_gl_account_id=row.cash_gl_account_id, receipt_id=row.receipt_id,
        status=row.status, reversal_receipt_id=row.reversal_receipt_id,
        reversed_on=row.reversed_on, created_at=row.created_at,
    )


def _audit(db, row, actor, action):
    append_audit_log(
        db, organization_id=row.organization_id, user_id=actor.id,
        entity_type="hoa_violation_fine_payment", entity_id=row.id,
        action=action, new_value={
            "association_id": row.association_id,
            "property_id": row.property_id, "fine_id": row.fine_id,
            "member_user_id": row.member_user_id, "receipt_id": row.receipt_id,
            "reversal_receipt_id": row.reversal_receipt_id,
            "status": row.status, "amount": str(row.amount),
        },
    )


def _posted_fine(db, org, assoc, property_id, case_id, lock=False):
    _case(db, org_id=org, association_id=assoc,
          property_id=property_id, case_id=case_id)
    fine = _fine(db, org, assoc, property_id, case_id, lock=lock)
    if fine is None:
        raise HTTPException(status_code=404, detail="Scoped fine not found.")
    return fine


@router.get("/{association_id}/staff-cases/{case_id}/fine/payments/cash-options",
            response_model=list[HOAReceiptCashOption])
def fine_cash_options(
    association_id: int, case_id: int, response: Response,
    property_id: int = Query(ge=1),
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org, assoc = _accountant(db, actor=current_user,
                             assoc=association_id, prop=property_id)
    fine = _posted_fine(db, org, assoc.id, property_id, case_id)
    if fine.status != "POSTED" or fine.receivable_gl_account_id is None:
        raise HTTPException(status_code=409, detail="A posted fine is required.")
    accounts = db.query(GLAccount).filter(
        GLAccount.organization_id == org,
        GLAccount.account_type == "ASSET",
        GLAccount.include_on_cash_flow.is_(True),
        GLAccount.is_active.is_(True), GLAccount.deleted_at.is_(None),
        GLAccount.id != fine.receivable_gl_account_id,
    ).order_by(GLAccount.gl_number, GLAccount.id).limit(501).all()
    if len(accounts) > 500:
        raise HTTPException(status_code=422, detail="Too many available cash accounts.")
    response.headers["Cache-Control"] = "no-store"
    return [HOAReceiptCashOption(id=a.id, number=a.gl_number, name=a.name) for a in accounts]


@router.get("/{association_id}/staff-cases/{case_id}/fine/payments",
            response_model=list[HOAFinePaymentOut])
def list_fine_payments(
    association_id: int, case_id: int, response: Response,
    property_id: int = Query(ge=1),
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org, assoc = _accountant(db, actor=current_user,
                             assoc=association_id, prop=property_id)
    fine = _posted_fine(db, org, assoc.id, property_id, case_id)
    rows = db.query(HOAViolationFinePayment).filter(
        HOAViolationFinePayment.organization_id == org,
        HOAViolationFinePayment.association_id == assoc.id,
        HOAViolationFinePayment.property_id == property_id,
        HOAViolationFinePayment.fine_id == fine.id,
    ).order_by(HOAViolationFinePayment.id).limit(501).all()
    if len(rows) > 500:
        raise HTTPException(status_code=422, detail="Too many fine receipt records.")
    response.headers["Cache-Control"] = "no-store"
    return [_out(row) for row in rows]


@router.post("/{association_id}/staff-cases/{case_id}/fine/payments",
             response_model=HOAFinePaymentOut, status_code=201)
def record_fine_payment(
    association_id: int, case_id: int, payload: HOAFinePaymentIn,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org, assoc = _accountant(db, actor=current_user,
                             assoc=association_id, prop=payload.property_id)
    fine = _posted_fine(db, org, assoc.id, payload.property_id,
                        case_id, lock=True)
    old = db.query(HOAViolationFinePayment).filter(
        HOAViolationFinePayment.organization_id == org,
        HOAViolationFinePayment.idempotency_key == payload.idempotency_key,
    ).first()
    if old is not None:
        same = (
            old.association_id == assoc.id and old.property_id == payload.property_id
            and old.fine_id == fine.id and old.member_user_id == payload.member_user_id
            and old.cash_gl_account_id == payload.cash_gl_account_id
            and old.received_on == payload.received_on and old.amount == payload.amount
            and old.payment_reference == payload.payment_reference
        )
        if not same:
            raise HTTPException(status_code=409, detail="Fine receipt request key already used.")
        return _out(old)
    if (fine.status != "POSTED" or fine.gl_transaction_id is None
        or fine.receivable_gl_account_id is None or fine.member_user_id is None):
        raise HTTPException(status_code=409, detail="A board-approved posted fine is required.")
    if payload.member_user_id != fine.member_user_id:
        raise HTTPException(status_code=409, detail="Fine payment must name the assessed member.")
    service = _service(db, org=org, association_id=assoc.id,
                       property_id=payload.property_id, case_id=case_id)
    if service is None or service.id != fine.service_record_id:
        raise HTTPException(status_code=409, detail="Original fine recipient evidence missing.")
    member = _current_member(db, org=org, association_id=assoc.id,
                             property_id=payload.property_id, service=service)
    if member.id != fine.member_user_id:
        raise HTTPException(status_code=409, detail="Responsible member no longer matches the served recipient.")
    if payload.received_on > date.today() or payload.received_on < fine.posted_on:
        raise HTTPException(status_code=422, detail="Received date outside posted fine period.")
    outstanding = fine.amount - fine.amount_paid
    if outstanding <= 0 or payload.amount > outstanding:
        raise HTTPException(status_code=409, detail="Fine receipt exceeds outstanding balance.")
    cash = _cash(db, org=org, cash_id=payload.cash_gl_account_id,
                 receivable_id=fine.receivable_gl_account_id)
    original = db.query(GLTransaction).filter(
        GLTransaction.id == fine.gl_transaction_id,
        GLTransaction.organization_id == org,
        GLTransaction.source_type == "hoa_violation_fine",
        GLTransaction.source_id == fine.id,
        GLTransaction.is_reversed.is_(False),
    ).first()
    if original is None:
        raise HTTPException(status_code=409, detail="Original fine GL unavailable.")
    receivable = db.query(GLAccount).filter(
        GLAccount.id == fine.receivable_gl_account_id,
        GLAccount.organization_id == org, GLAccount.account_type == "ASSET",
        GLAccount.is_active.is_(True), GLAccount.deleted_at.is_(None),
    ).first()
    if receivable is None:
        raise HTTPException(status_code=409, detail="Active member receivable account missing.")
    if db.query(HOAViolationFinePayment.id).filter(
        HOAViolationFinePayment.organization_id == org,
        HOAViolationFinePayment.fine_id == fine.id,
    ).limit(500).count() >= 500:
        raise HTTPException(status_code=422, detail="Fine payment history limit reached.")
    try:
        receipt = Receipt(
            organization_id=org, type="HOA_FINE",
            receipt_date=payload.received_on, amount=payload.amount,
            cash_gl_account_id=cash.id, property_id=payload.property_id,
            received_from=(member.first_name + " " + member.last_name).strip(),
            exclude_from_mgmt_fee=True, reference_number=payload.payment_reference,
            remarks="HOA violation fine received offline",
            created_by_id=current_user.id, is_reversed=False, is_active=True,
        )
        db.add(receipt); db.flush()
        transaction = post_transaction(
            db, organization_id=org, transaction_date=payload.received_on,
            transaction_type="RECEIPT", memo="HOA fine payment received offline",
            lines=[
                PostingLine(gl_account_id=cash.id, property_id=payload.property_id,
                            debit=payload.amount, credit=Decimal("0")),
                PostingLine(gl_account_id=receivable.id, property_id=payload.property_id,
                            debit=Decimal("0"), credit=payload.amount),
            ], created_by=current_user, reference_number=payload.payment_reference,
            source_type="receipt", source_id=receipt.id,
            commit=False, write_audit=False,
        )
        receipt.gl_transaction_id = transaction.id
        db.add(ReceiptLine(
            organization_id=org, receipt_id=receipt.id,
            gl_account_id=receivable.id, property_id=payload.property_id,
            description="HOA violation fine receivable payment",
            amount_to_pay=payload.amount, line_date=payload.received_on,
            is_prepayment=False,
        ))
        payment = HOAViolationFinePayment(
            organization_id=org, association_id=assoc.id,
            property_id=payload.property_id, fine_id=fine.id,
            member_user_id=member.id, receipt_id=receipt.id,
            cash_gl_account_id=cash.id, amount=payload.amount,
            received_on=payload.received_on, idempotency_key=payload.idempotency_key,
            payment_reference=payload.payment_reference,
            status="POSTED", created_by_id=current_user.id,
        )
        db.add(payment)
        fine.amount_paid += payload.amount
        db.flush()
        _audit(db, payment, current_user, "fine_receipt_allocated")
        db.commit()
    except PostingError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Central GL refused fine receipt.") from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Duplicate or concurrent fine receipt.") from exc
    db.refresh(payment)
    return _out(payment)


@router.post("/{association_id}/staff-cases/{case_id}/fine/payments/{payment_id}/reverse",
             response_model=HOAFinePaymentOut)
def reverse_fine_payment(
    association_id: int, case_id: int, payment_id: int,
    payload: HOAFinePaymentReverseIn,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org, assoc = _accountant(db, actor=current_user,
                             assoc=association_id, prop=payload.property_id)
    fine = _posted_fine(db, org, assoc.id, payload.property_id,
                        case_id, lock=True)
    payment = db.query(HOAViolationFinePayment).filter(
        HOAViolationFinePayment.id == payment_id,
        HOAViolationFinePayment.organization_id == org,
        HOAViolationFinePayment.association_id == assoc.id,
        HOAViolationFinePayment.property_id == payload.property_id,
        HOAViolationFinePayment.fine_id == fine.id,
    ).with_for_update().first()
    if payment is None:
        raise HTTPException(status_code=404, detail="Fine payment not found.")
    if payment.status != "POSTED" or payment.reversal_receipt_id is not None:
        raise HTTPException(status_code=409, detail="Fine payment already reversed.")
    if fine.status != "POSTED" or fine.amount_paid < payment.amount:
        raise HTTPException(status_code=409, detail="Fine receipt allocation cannot be reconciled.")
    original = db.query(Receipt).filter(
        Receipt.id == payment.receipt_id,
        Receipt.organization_id == org,
        Receipt.property_id == payload.property_id,
        Receipt.type == "HOA_FINE", Receipt.is_reversed.is_(False),
    ).with_for_update().first()
    if original is None or original.amount != payment.amount:
        raise HTTPException(status_code=409, detail="Original fine receipt differs or missing.")
    posted = db.query(GLTransaction).filter(
        GLTransaction.id == original.gl_transaction_id,
        GLTransaction.organization_id == org,
        GLTransaction.source_type == "receipt",
        GLTransaction.source_id == original.id,
        GLTransaction.is_reversed.is_(False),
    ).with_for_update().first()
    if posted is None:
        raise HTTPException(status_code=409, detail="Original receipt GL invalid.")
    if payload.reversal_on < posted.transaction_date or payload.reversal_on > date.today():
        raise HTTPException(status_code=422, detail="Fine receipt reversal date is invalid.")
    if db.query(DepositLine.id).filter(
        DepositLine.organization_id == org, DepositLine.receipt_id == original.id,
    ).first() is not None:
        raise HTTPException(status_code=409, detail="Deposited fine receipt requires bank reconciliation before reversal.")
    entries = db.query(GLEntry).filter(
        GLEntry.organization_id == org, GLEntry.transaction_id == posted.id,
    ).all()
    if (len(entries) != 2 or {e.gl_account_id for e in entries}
            != {payment.cash_gl_account_id, fine.receivable_gl_account_id}):
        raise HTTPException(status_code=409, detail="Fine receipt GL shape invalid.")
    try:
        reversal = post_transaction(
            db, organization_id=org, transaction_date=payload.reversal_on,
            transaction_type="REVERSAL", memo="HOA violation fine receipt reversal",
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
            organization_id=org, type="HOA_FINE",
            receipt_date=payload.reversal_on, amount=payment.amount,
            cash_gl_account_id=original.cash_gl_account_id,
            received_from=original.received_from, property_id=payload.property_id,
            exclude_from_mgmt_fee=True, reference_number=original.reference_number,
            remarks="Reversal of HOA fine receipt",
            gl_transaction_id=reversal.id, reversal_of_id=original.id,
            created_by_id=current_user.id, is_reversed=False, is_active=True,
        )
        db.add(mirror); db.flush()
        payment.status = "REVERSED"
        payment.reversal_receipt_id = mirror.id
        payment.reversed_on = payload.reversal_on
        payment.reversal_reason = payload.reason
        payment.reversed_by_id = current_user.id
        fine.amount_paid -= payment.amount
        db.flush()
        _audit(db, payment, current_user, "fine_receipt_reversed")
        db.commit()
    except PostingError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Central GL refused fine receipt reversal.") from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Concurrent fine receipt reversal.") from exc
    db.refresh(payment)
    return _out(payment)
