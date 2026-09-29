"""Operational association fine decision and separately authorized GL posting.

A configured procedure and association board decide the fine, not the
platform. Recorded service and hearing outcome are explicit prerequisites.
Every financial movement uses the verified central GL; no tenant Charge,
automatic statutory conclusion, external delivery or payment capture.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.entity_attachment import EntityAttachment
from app.models.gl_entry import GLEntry
from app.models.gl_transaction import GLTransaction
from app.models.hoa_violation_evidence import HOAViolationEvidence
from app.models.hoa_violation_fine import HOAViolationFine
from app.models.hoa_violation_fine_appeal import HOAFineAppeal
from app.models.hoa_violation_recipient import HOAViolationRecipientDraft
from app.models.hoa_violation_service_record import HOAViolationServiceRecord
from app.models.user import User
from app.routers.auth import get_current_user
from app.routers.hoa_arc_board_decisions import _board_scope, _verified_member
from app.routers.hoa_member_assessments import _accountant, _accounts
from app.routers.hoa_violation_cases import _case, _policy
from app.routers.hoa_violation_recipients import _matched_contact
from app.schemas.gl_transaction import PostingLine
from app.schemas.hoa_violation_fine import (
    HOAFineDecisionIn, HOAFineOut, HOAFinePostIn, HOAFineReverseIn,
)
from app.services.audit import append_audit_log
from app.services.gl_posting import PostingError, post_transaction

router = APIRouter(prefix="/api/hoa/associations", tags=["HOA operative violation fines"])


def _fine(db, org, association_id, property_id, case_id, *, lock=False):
    query = db.query(HOAViolationFine).filter(
        HOAViolationFine.organization_id == org,
        HOAViolationFine.association_id == association_id,
        HOAViolationFine.property_id == property_id,
        HOAViolationFine.case_id == case_id,
    )
    return (query.with_for_update() if lock else query).first()


def _out(row):
    return HOAFineOut(
        id=row.id, case_id=row.case_id, property_id=row.property_id,
        decision=row.decision, status=row.status, member_user_id=row.member_user_id,
        amount=row.amount, amount_paid=row.amount_paid,
        hearing_disposition=row.hearing_disposition,
        hearing_held_on=row.hearing_held_on,
        hearing_record_attachment_id=row.hearing_record_attachment_id,
        board_seat_id=row.board_seat_id, service_record_id=row.service_record_id,
        policy_revision=row.policy_revision, decided_on=row.decided_on,
        receivable_gl_account_id=row.receivable_gl_account_id,
        income_gl_account_id=row.income_gl_account_id,
        gl_transaction_id=row.gl_transaction_id,
        reversal_transaction_id=row.reversal_transaction_id,
        posted_on=row.posted_on, reversed_on=row.reversed_on,
        decision_note=row.decision_note, recorded_at=row.decided_at,
    )


def _service(db, *, org, association_id, property_id, case_id):
    return db.query(HOAViolationServiceRecord).filter(
        HOAViolationServiceRecord.organization_id == org,
        HOAViolationServiceRecord.association_id == association_id,
        HOAViolationServiceRecord.property_id == property_id,
        HOAViolationServiceRecord.case_id == case_id,
    ).first()


def _current_member(db, *, org, association_id, property_id, service):
    link, contact, user = _matched_contact(
        db, org=org, association_id=association_id,
        property_id=property_id, contact_link_id=service.contact_link_id,
    )
    recipient = db.query(HOAViolationRecipientDraft).filter(
        HOAViolationRecipientDraft.organization_id == org,
        HOAViolationRecipientDraft.association_id == association_id,
        HOAViolationRecipientDraft.property_id == property_id,
        HOAViolationRecipientDraft.case_id == service.case_id,
        HOAViolationRecipientDraft.is_active.is_(True),
        HOAViolationRecipientDraft.contact_link_id == service.contact_link_id,
        HOAViolationRecipientDraft.matched_user_id == service.member_user_id,
    ).first()
    if recipient is None or user.id != service.member_user_id:
        raise HTTPException(status_code=409, detail="Current verified responsible member must match served recipient.")
    return user


def _private_case_proof(db, *, org, association_id, property_id, case_id, attachment_id):
    proof = db.query(EntityAttachment).filter(
        EntityAttachment.id == attachment_id,
        EntityAttachment.organization_id == org,
        EntityAttachment.entity_type == "properties",
        EntityAttachment.entity_id == property_id,
        EntityAttachment.is_active.is_(True),
        EntityAttachment.deleted_at.is_(None),
        EntityAttachment.share_with_owners.is_(False),
        EntityAttachment.share_with_tenants.is_(False),
    ).first()
    if proof is None or db.query(HOAViolationEvidence.id).filter(
        HOAViolationEvidence.organization_id == org,
        HOAViolationEvidence.association_id == association_id,
        HOAViolationEvidence.property_id == property_id,
        HOAViolationEvidence.case_id == case_id,
        HOAViolationEvidence.attachment_id == attachment_id,
        HOAViolationEvidence.is_active.is_(True),
    ).first() is None:
        raise HTTPException(status_code=409, detail="Current private case-linked proof is required.")
    return proof


def _procedure(db, *, org, association_id, property_id, case, service):
    if case.stage != "FINE_PROPOSED" or case.proposed_fine is None:
        raise HTTPException(status_code=409, detail="Staff case must have a recorded fine proposal.")
    policy = _policy(
        db, org_id=org, association_id=association_id, property_id=property_id,
    )
    if (policy is None or policy.proposed_fine_cap is None
        or service is None or service.policy_revision != policy.revision
        or policy.cure_preparation_days is None
        or policy.hearing_request_days is None):
        raise HTTPException(status_code=409, detail="Current configured procedure and evidenced notice service required.")
    if case.proposed_fine > policy.proposed_fine_cap:
        raise HTTPException(status_code=409, detail="Proposed fine exceeds current configured cap.")
    _private_case_proof(
        db, org=org, association_id=association_id,
        property_id=property_id, case_id=case.id,
        attachment_id=service.service_proof_attachment_id,
    )
    return policy


@router.get("/{association_id}/staff-cases/{case_id}/fine",
            response_model=HOAFineOut | None)
def get_fine(
    association_id: int, case_id: int, response: Response,
    property_id: int = Query(ge=1),
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    # Staff accounting permissions may read the member receivable.
    try:
        org, assoc = _accountant(
            db, actor=current_user, assoc=association_id, prop=property_id,
        )
    except HTTPException:
        org, assoc, _seat = _board_scope(
            db, actor=current_user, association_id=association_id,
            property_id=property_id,
        )
    _case(db, org_id=org, association_id=assoc.id,
          property_id=property_id, case_id=case_id)
    response.headers["Cache-Control"] = "no-store"
    row = _fine(db, org, assoc.id, property_id, case_id)
    return _out(row) if row is not None else None


@router.post("/{association_id}/staff-cases/{case_id}/fine/board-decision",
             response_model=HOAFineOut, status_code=201)
def decide_fine(
    association_id: int, case_id: int, payload: HOAFineDecisionIn,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org, assoc, seat = _board_scope(
        db, actor=current_user, association_id=association_id,
        property_id=payload.property_id,
    )
    case = _case(db, org_id=org, association_id=assoc.id,
                 property_id=payload.property_id, case_id=case_id)
    old = _fine(db, org, assoc.id, payload.property_id, case.id, lock=True)
    if old is not None:
        if (old.request_key == payload.request_key
            and old.decision == payload.decision
            and old.amount == payload.amount
            and old.member_user_id == payload.member_user_id
            and old.decision_note == payload.decision_note
            and old.hearing_disposition == payload.hearing_disposition
            and old.hearing_held_on == payload.hearing_held_on
            and old.hearing_record_attachment_id == payload.hearing_record_attachment_id):
            return _out(old)
        raise HTTPException(status_code=409, detail="Case already has a final board fine decision.")
    service = _service(
        db, org=org, association_id=assoc.id, property_id=payload.property_id,
        case_id=case.id,
    )
    policy = _procedure(
        db, org=org, association_id=assoc.id, property_id=payload.property_id,
        case=case, service=service,
    )
    today = date.today()
    if today < service.cure_earliest_on:
        raise HTTPException(status_code=409, detail="Configured cure opportunity has not elapsed.")
    if payload.hearing_disposition == "NO_REQUEST_RECORDED":
        if today < service.hearing_request_earliest_on:
            raise HTTPException(status_code=409, detail="Configured hearing-request opportunity has not elapsed.")
    else:
        if (payload.hearing_held_on < service.served_on
            or payload.hearing_held_on > today):
            raise HTTPException(status_code=422, detail="Held hearing date must follow service and cannot be future-dated.")
        _private_case_proof(
            db, org=org, association_id=assoc.id,
            property_id=payload.property_id, case_id=case.id,
            attachment_id=payload.hearing_record_attachment_id,
        )
    member_id = None
    if payload.decision == "APPROVED":
        member = _current_member(
            db, org=org, association_id=assoc.id,
            property_id=payload.property_id, service=service,
        )
        if payload.member_user_id != member.id:
            raise HTTPException(status_code=409, detail="Fine must name the actually verified served member.")
        if payload.amount > policy.proposed_fine_cap or payload.amount > case.proposed_fine:
            raise HTTPException(status_code=422, detail="Fine exceeds configured cap or case proposal.")
        member_id = member.id
    existing_key = db.query(HOAViolationFine.id).filter(
        HOAViolationFine.organization_id == org,
        HOAViolationFine.request_key == payload.request_key,
    ).first()
    if existing_key:
        raise HTTPException(status_code=409, detail="Fine request key already used.")
    row = HOAViolationFine(
        organization_id=org, association_id=assoc.id,
        property_id=payload.property_id, case_id=case.id,
        service_record_id=service.id, board_seat_id=seat.id,
        board_user_id=current_user.id, member_user_id=member_id,
        contact_link_id=service.contact_link_id if member_id else None,
        decision=payload.decision, status=payload.decision,
        amount=payload.amount, decision_note=payload.decision_note,
        hearing_disposition=payload.hearing_disposition,
        hearing_held_on=payload.hearing_held_on,
        hearing_record_attachment_id=payload.hearing_record_attachment_id,
        decided_on=today, request_key=payload.request_key,
        policy_revision=policy.revision,
    )
    db.add(row)
    try:
        db.flush()
        append_audit_log(
            db, organization_id=org, user_id=current_user.id,
            entity_type="hoa_violation_fine", entity_id=row.id,
            action="association_fine_decision",
            new_value={
                "association_id": assoc.id, "property_id": payload.property_id,
                "case_id": case.id, "decision": row.decision,
                "board_seat_id": seat.id, "service_record_id": service.id,
                "member_user_id": row.member_user_id,
                "amount": str(row.amount) if row.amount is not None else None,
                "hearing_disposition": row.hearing_disposition,
                "hearing_held_on": row.hearing_held_on.isoformat() if row.hearing_held_on else None,
            },
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Duplicate or concurrent fine decision.") from exc
    db.refresh(row)
    return _out(row)


@router.post("/{association_id}/staff-cases/{case_id}/fine/post",
             response_model=HOAFineOut)
def post_fine(
    association_id: int, case_id: int, payload: HOAFinePostIn,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org, assoc = _accountant(
        db, actor=current_user, assoc=association_id, prop=payload.property_id,
    )
    case = _case(db, org_id=org, association_id=assoc.id,
                 property_id=payload.property_id, case_id=case_id)
    row = _fine(db, org, assoc.id, payload.property_id, case.id, lock=True)
    if row is None:
        raise HTTPException(status_code=404, detail="Authorized board fine decision not found.")
    if row.status == "POSTED":
        if (row.receivable_gl_account_id == payload.receivable_gl_account_id
            and row.income_gl_account_id == payload.income_gl_account_id
            and row.posted_on == payload.posting_on):
            return _out(row)
        raise HTTPException(status_code=409, detail="Fine already posted with different terms.")
    if row.status != "APPROVED" or row.gl_transaction_id is not None:
        raise HTTPException(status_code=409, detail="Only unposted approved fine may be posted.")
    if db.query(HOAFineAppeal.id).filter(
        HOAFineAppeal.organization_id == org,
        HOAFineAppeal.association_id == assoc.id,
        HOAFineAppeal.property_id == payload.property_id,
        HOAFineAppeal.fine_id == row.id,
        HOAFineAppeal.status.in_(("OPEN", "VACATED")),
    ).first() is not None:
        raise HTTPException(status_code=409, detail="Open or vacated appeal holds fine posting.")
    service = _service(db, org=org, association_id=assoc.id,
                       property_id=payload.property_id, case_id=case.id)
    policy = _procedure(
        db, org=org, association_id=assoc.id,
        property_id=payload.property_id, case=case, service=service,
    )
    if (row.service_record_id != service.id or row.policy_revision != policy.revision
        or row.contact_link_id != service.contact_link_id
        or payload.posting_on < row.decided_on or payload.posting_on > date.today()):
        raise HTTPException(status_code=409, detail="Fine decision or posting date is no longer valid.")
    member = _current_member(
        db, org=org, association_id=assoc.id,
        property_id=payload.property_id, service=service,
    )
    if member.id != row.member_user_id:
        raise HTTPException(status_code=409, detail="Board-selected liable member no longer verified.")
    receivable, income = _accounts(
        db, org=org, receivable_id=payload.receivable_gl_account_id,
        income_id=payload.income_gl_account_id,
    )
    try:
        transaction = post_transaction(
            db, organization_id=org, transaction_date=payload.posting_on,
            transaction_type="JOURNAL_ENTRY", memo="HOA board-approved violation fine",
            lines=[
                PostingLine(gl_account_id=receivable.id, property_id=payload.property_id,
                            debit=row.amount, credit=Decimal("0")),
                PostingLine(gl_account_id=income.id, property_id=payload.property_id,
                            debit=Decimal("0"), credit=row.amount),
            ], created_by=current_user, source_type="hoa_violation_fine",
            source_id=row.id, reference_number=f"HOAFINE{row.id}",
            commit=False, write_audit=False,
        )
        row.status = "POSTED"
        row.receivable_gl_account_id = receivable.id
        row.income_gl_account_id = income.id
        row.gl_transaction_id = transaction.id
        row.posted_on = payload.posting_on
        db.flush()
        append_audit_log(
            db, organization_id=org, user_id=current_user.id,
            entity_type="hoa_violation_fine", entity_id=row.id,
            action="member_fine_posted", new_value={
                "association_id": assoc.id, "property_id": payload.property_id,
                "case_id": case.id, "member_user_id": row.member_user_id,
                "gl_transaction_id": transaction.id,
            },
        )
        db.commit()
    except PostingError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Central GL rejected HOA fine posting.") from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Concurrent fine posting.") from exc
    db.refresh(row)
    return _out(row)


@router.post("/{association_id}/staff-cases/{case_id}/fine/reverse",
             response_model=HOAFineOut)
def reverse_fine(
    association_id: int, case_id: int, payload: HOAFineReverseIn,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org, assoc = _accountant(
        db, actor=current_user, assoc=association_id, prop=payload.property_id,
    )
    case = _case(db, org_id=org, association_id=assoc.id,
                 property_id=payload.property_id, case_id=case_id)
    row = _fine(db, org, assoc.id, payload.property_id, case.id, lock=True)
    if row is None or row.status != "POSTED":
        raise HTTPException(status_code=409, detail="Only posted, unreversed fine can be reversed.")
    if row.amount_paid != Decimal("0.00"):
        raise HTTPException(status_code=409, detail="Reverse all allocated fine receipts before reversing the fine.")
    original = db.query(GLTransaction).filter(
        GLTransaction.id == row.gl_transaction_id,
        GLTransaction.organization_id == org,
        GLTransaction.source_type == "hoa_violation_fine",
        GLTransaction.source_id == row.id,
        GLTransaction.is_reversed.is_(False),
    ).with_for_update().first()
    if original is None:
        raise HTTPException(status_code=409, detail="Fine original ledger source missing.")
    if payload.reversal_on < original.transaction_date or payload.reversal_on > date.today():
        raise HTTPException(status_code=422, detail="Reversal cannot predate original or be future-dated.")
    entries = db.query(GLEntry).filter(
        GLEntry.organization_id == org, GLEntry.transaction_id == original.id,
    ).all()
    if len(entries) != 2:
        raise HTTPException(status_code=409, detail="Unexpected fine ledger posting shape.")
    try:
        reversal = post_transaction(
            db, organization_id=org, transaction_date=payload.reversal_on,
            transaction_type="REVERSAL", memo="HOA violation fine reversal",
            lines=[
                PostingLine(gl_account_id=e.gl_account_id, property_id=e.property_id,
                            unit_id=e.unit_id, owner_id=e.owner_id,
                            debit=e.credit, credit=e.debit) for e in entries
            ], created_by=current_user, source_type="hoa_violation_fine",
            source_id=row.id, reversal_of_id=original.id,
            commit=False, write_audit=False,
        )
        original.is_reversed = True
        row.reversal_transaction_id = reversal.id
        row.reversed_on = payload.reversal_on
        row.reversal_reason = payload.reason.strip()
        row.status = "REVERSED"
        db.flush()
        append_audit_log(
            db, organization_id=org, user_id=current_user.id,
            entity_type="hoa_violation_fine", entity_id=row.id,
            action="member_fine_reversed", new_value={
                "association_id": assoc.id, "property_id": payload.property_id,
                "case_id": case.id, "reversal_gl_transaction_id": reversal.id,
            },
        )
        db.commit()
    except PostingError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Central GL rejected fine reversal.") from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Concurrent fine reversal.") from exc
    db.refresh(row)
    return _out(row)
