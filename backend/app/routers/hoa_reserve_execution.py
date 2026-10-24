"""Board-authorized HOA reserve book posting and reversal (never a bank transfer)."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.entity_attachment import EntityAttachment
from app.models.gl_account import GLAccount
from app.models.gl_entry import GLEntry
from app.models.gl_transaction import GLTransaction
from app.models.hoa_reserve_account import HOAReserveAccount
from app.models.hoa_reserve_movement_decision import HOAReserveMovementDecision
from app.models.hoa_reserve_movement_draft import HOAReserveMovementDraft
from app.models.user import User
from app.routers.auth import get_current_user
from app.routers.hoa_arc_board_decisions import _board_scope, _decision_maker
from app.routers.hoa_reserve_accounts import _accounts, _reserve
from app.routers.hoa_reserve_movements import _scope as _accounting_scope
from app.schemas.gl_transaction import PostingLine
from app.schemas.hoa_reserve_execution import (
    HOAReserveDecisionIn, HOAReserveDecisionOut, HOAReservePostIn, HOAReserveReverseIn,
)
from app.services.audit import append_audit_log
from app.services.gl_posting import PostingError, post_transaction

router = APIRouter(prefix="/api/hoa/associations", tags=["HOA approved reserve book movement"])


def _draft(db: Session, *, org: int, assoc: int, prop: int, draft_id: int):
    row = db.query(HOAReserveMovementDraft).filter(
        HOAReserveMovementDraft.id == draft_id,
        HOAReserveMovementDraft.organization_id == org,
        HOAReserveMovementDraft.association_id == assoc,
        HOAReserveMovementDraft.property_id == prop,
    ).with_for_update().first()
    if row is None:
        raise HTTPException(status_code=404, detail="Scoped reserve draft not found.")
    return row


def _decision(db: Session, *, org: int, assoc: int, prop: int, draft_id: int,
              lock: bool = False):
    q = db.query(HOAReserveMovementDecision).filter(
        HOAReserveMovementDecision.organization_id == org,
        HOAReserveMovementDecision.association_id == assoc,
        HOAReserveMovementDecision.property_id == prop,
        HOAReserveMovementDecision.draft_id == draft_id,
    )
    return (q.with_for_update() if lock else q).first()


def _out(row: HOAReserveMovementDecision):
    return HOAReserveDecisionOut(
        id=row.id, draft_id=row.draft_id, property_id=row.property_id,
        decision=row.decision, status=row.status,
        board_seat_id=row.board_seat_id, maker_seat_id=row.maker_seat_id,
        record_method=row.record_method, decided_on=row.decided_on,
        amount=row.approved_amount, direction=row.direction,
        reserve_gl_account_id=row.reserve_gl_account_id,
        counterparty_gl_account_id=row.counterparty_gl_account_id,
        gl_transaction_id=row.gl_transaction_id,
        reversal_transaction_id=row.reversal_transaction_id,
        posted_on=row.posted_on, reversed_on=row.reversed_on,
    )


def _audit(db: Session, *, row: HOAReserveMovementDecision, actor: User, action: str):
    append_audit_log(
        db, organization_id=row.organization_id, user_id=actor.id,
        entity_type="hoa_reserve_movement_decision", entity_id=row.id,
        action=action, new_value={
            "association_id": row.association_id, "property_id": row.property_id,
            "draft_id": row.draft_id, "status": row.status,
            "gl_transaction_id": row.gl_transaction_id,
            "reversal_transaction_id": row.reversal_transaction_id,
        },
    )


def _eligible_cash(db: Session, *, org: int, row: HOAReserveMovementDraft):
    reserve = _reserve(db, org_id=org, association_id=row.association_id,
                       property_id=row.property_id)
    if reserve is None or not reserve.is_active or reserve.gl_account_id != row.reserve_gl_account_id:
        raise HTTPException(status_code=409, detail="Live reserve mapping differs from approved movement.")
    reserve_gl, bank = _accounts(db, org_id=org, row=reserve)
    if not reserve_gl.is_active or reserve_gl.deleted_at is not None or (
        bank is not None and (not bank.is_active or bank.deleted_at is not None)
    ):
        raise HTTPException(status_code=409, detail="Active reserve cash mapping required.")
    counterpart = db.query(GLAccount).filter(
        GLAccount.id == row.counterparty_gl_account_id,
        GLAccount.organization_id == org,
        GLAccount.account_type == "ASSET",
        GLAccount.include_on_cash_flow.is_(True),
        GLAccount.is_active.is_(True),
        GLAccount.deleted_at.is_(None),
    ).first()
    if counterpart is None or counterpart.id == reserve_gl.id:
        raise HTTPException(status_code=409, detail="Active distinct cash-like counterpart required.")
    foreign_reserve = db.query(HOAReserveAccount.id).filter(
        HOAReserveAccount.organization_id == org,
        HOAReserveAccount.is_active.is_(True),
        HOAReserveAccount.gl_account_id == counterpart.id,
    ).first()
    if foreign_reserve is not None:
        raise HTTPException(status_code=409, detail="Counterpart is another mapped reserve account.")
    return reserve_gl, counterpart


@router.post("/{association_id}/reserve-movement-drafts/{draft_id}/board-decision",
             response_model=HOAReserveDecisionOut, status_code=201)
def record_reserve_decision(
    association_id: int, draft_id: int, payload: HOAReserveDecisionIn,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org, association, seat = _board_scope(
        db, actor=current_user, association_id=association_id, property_id=payload.property_id,
    )
    draft = _draft(db, org=org, assoc=association.id, prop=payload.property_id, draft_id=draft_id)
    if draft.status != "DRAFT" or _decision(
        db, org=org, assoc=association.id, prop=payload.property_id, draft_id=draft.id,
    ) is not None:
        raise HTTPException(status_code=409, detail="Reserve request is cancelled or already decided.")
    if payload.decision == "APPROVED":
        _eligible_cash(db, org=org, row=draft)
    maker = seat
    supporting = None
    method = "DIRECT"
    decided_on = date.today()
    if payload.offline_meeting_on is not None:
        if not seat.can_record_offline:
            raise HTTPException(status_code=403, detail="Designated offline board recorder required.")
        maker = _decision_maker(
            db, org=org, association_id=association.id,
            property_id=payload.property_id, seat_id=payload.maker_seat_id,
        )
        supporting = db.query(EntityAttachment).filter(
            EntityAttachment.id == payload.supporting_attachment_id,
            EntityAttachment.organization_id == org,
            EntityAttachment.entity_type == "properties",
            EntityAttachment.entity_id == payload.property_id,
            EntityAttachment.is_active.is_(True),
            EntityAttachment.share_with_owners.is_(False),
            EntityAttachment.share_with_tenants.is_(False),
        ).first()
        if supporting is None:
            raise HTTPException(status_code=404, detail="Private meeting record unavailable.")
        method = "OFFLINE"
        decided_on = payload.offline_meeting_on
    if decided_on > date.today():
        raise HTTPException(status_code=422, detail="Future board decisions cannot be recorded.")
    row = HOAReserveMovementDecision(
        organization_id=org, association_id=association.id,
        property_id=payload.property_id, draft_id=draft.id,
        board_seat_id=seat.id, maker_seat_id=maker.id,
        recorded_by_id=current_user.id, decision=payload.decision,
        decision_note=payload.decision_note, decided_on=decided_on,
        record_method=method, supporting_attachment_id=supporting.id if supporting else None,
        approved_amount=draft.amount if payload.decision == "APPROVED" else None,
        reserve_gl_account_id=draft.reserve_gl_account_id,
        counterparty_gl_account_id=draft.counterparty_gl_account_id,
        direction=draft.direction, status=payload.decision,
    )
    db.add(row)
    try:
        db.flush()
        _audit(db, row=row, actor=current_user, action="reserve_board_decision_recorded")
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Concurrent reserve decision.") from exc
    db.refresh(row)
    return _out(row)


@router.get("/{association_id}/reserve-movement-drafts/{draft_id}/board-decision",
            response_model=HOAReserveDecisionOut | None)
def get_reserve_decision(
    association_id: int, draft_id: int, response: Response,
    property_id: int = Query(ge=1),
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org, association, reserve, gl = _accounting_scope(
        db, current_user, association_id, property_id, write=False,
    )
    _draft(db, org=org, assoc=association.id, prop=property_id, draft_id=draft_id)
    decision = _decision(db, org=org, assoc=association.id, prop=property_id, draft_id=draft_id)
    response.headers["Cache-Control"] = "no-store"
    return _out(decision) if decision else None


@router.post("/{association_id}/reserve-movement-drafts/{draft_id}/post",
             response_model=HOAReserveDecisionOut)
def post_reserve_book_movement(
    association_id: int, draft_id: int, payload: HOAReservePostIn,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org, association, reserve, gl = _accounting_scope(
        db, current_user, association_id, payload.property_id, write=True,
    )
    draft = _draft(db, org=org, assoc=association.id, prop=payload.property_id, draft_id=draft_id)
    row = _decision(db, org=org, assoc=association.id, prop=payload.property_id,
                    draft_id=draft_id, lock=True)
    if row is None or row.decision != "APPROVED":
        raise HTTPException(status_code=409, detail="Board approval is required.")
    if row.status == "POSTED" and row.posted_on == payload.transaction_on:
        return _out(row)
    if row.status != "APPROVED" or draft.status != "DRAFT":
        raise HTTPException(status_code=409, detail="Reserve book movement already processed.")
    if (payload.transaction_on < row.decided_on
            or payload.transaction_on < draft.planned_on
            or payload.transaction_on > date.today()):
        raise HTTPException(status_code=422, detail="Posting must follow both the board decision and planned date, and not be future.")
    if (row.reserve_gl_account_id != draft.reserve_gl_account_id
            or row.counterparty_gl_account_id != draft.counterparty_gl_account_id
            or row.direction != draft.direction or row.approved_amount != draft.amount):
        raise HTTPException(status_code=409, detail="Reserve request has changed since approval.")
    reserve_gl, counterpart = _eligible_cash(db, org=org, row=draft)
    debit, credit = (
        (reserve_gl.id, counterpart.id) if row.direction == "TO_RESERVE"
        else (counterpart.id, reserve_gl.id)
    )
    try:
        transaction = post_transaction(
            db, organization_id=org, transaction_date=payload.transaction_on,
            transaction_type="TRANSFER", memo="Approved HOA reserve book transfer",
            lines=[
                PostingLine(gl_account_id=debit, property_id=payload.property_id,
                            debit=row.approved_amount, credit=Decimal("0")),
                PostingLine(gl_account_id=credit, property_id=payload.property_id,
                            debit=Decimal("0"), credit=row.approved_amount),
            ], created_by=current_user, reference_number=f"HOAR{draft.id}",
            source_type="hoa_reserve_book_movement", source_id=draft.id,
            commit=False, write_audit=False,
        )
        row.gl_transaction_id = transaction.id
        row.posted_on = payload.transaction_on
        row.status = "POSTED"
        db.flush()
        _audit(db, row=row, actor=current_user, action="reserve_book_transfer_posted")
        db.commit()
    except PostingError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Central GL rejected reserve book posting.") from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Concurrent reserve book posting.") from exc
    db.refresh(row)
    return _out(row)


@router.post("/{association_id}/reserve-movement-drafts/{draft_id}/reverse",
             response_model=HOAReserveDecisionOut)
def reverse_reserve_book_movement(
    association_id: int, draft_id: int, payload: HOAReserveReverseIn,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org, association, reserve, gl = _accounting_scope(
        db, current_user, association_id, payload.property_id, write=True,
    )
    draft = _draft(db, org=org, assoc=association.id, prop=payload.property_id, draft_id=draft_id)
    row = _decision(db, org=org, assoc=association.id, prop=payload.property_id,
                    draft_id=draft_id, lock=True)
    if row is None or row.status != "POSTED" or row.reversal_transaction_id is not None:
        raise HTTPException(status_code=409, detail="No unreversed reserve book movement.")
    original = db.query(GLTransaction).filter(
        GLTransaction.id == row.gl_transaction_id,
        GLTransaction.organization_id == org,
        GLTransaction.is_reversed.is_(False),
        GLTransaction.source_type == "hoa_reserve_book_movement",
        GLTransaction.source_id == draft.id,
    ).with_for_update().first()
    if original is None:
        raise HTTPException(status_code=409, detail="Reserve book GL source invalid.")
    if payload.reversal_on < original.transaction_date or payload.reversal_on > date.today():
        raise HTTPException(status_code=422, detail="Reversal date must follow original and not be future.")
    entries = db.query(GLEntry).filter(
        GLEntry.organization_id == org, GLEntry.transaction_id == original.id,
    ).all()
    if len(entries) != 2 or {entry.gl_account_id for entry in entries} != {
        row.reserve_gl_account_id, row.counterparty_gl_account_id,
    }:
        raise HTTPException(status_code=409, detail="Original reserve GL entry shape invalid.")
    try:
        transaction = post_transaction(
            db, organization_id=org, transaction_date=payload.reversal_on,
            transaction_type="REVERSAL", memo="HOA reserve book correction",
            lines=[
                PostingLine(gl_account_id=e.gl_account_id, property_id=e.property_id,
                            unit_id=e.unit_id, owner_id=e.owner_id,
                            debit=e.credit, credit=e.debit) for e in entries
            ], created_by=current_user, source_type="hoa_reserve_book_movement",
            source_id=draft.id, reversal_of_id=original.id, commit=False, write_audit=False,
        )
        original.is_reversed = True
        row.reversal_transaction_id = transaction.id
        row.reversed_on = payload.reversal_on
        row.reversal_reason = payload.reason
        row.status = "REVERSED"
        db.flush()
        _audit(db, row=row, actor=current_user, action="reserve_book_transfer_reversed")
        db.commit()
    except PostingError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Central GL rejected reserve reversal.") from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Concurrent reserve book reversal.") from exc
    db.refresh(row)
    return _out(row)
