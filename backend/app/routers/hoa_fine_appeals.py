"""Operational staff-recorded fine appeals with direct board disposition.

An open appeal holds new financial posting or receipt allocation. Vacatur
requires the already verified separate receipt/GL reversal workflow;
appeal records themselves never create or erase transactions.
"""
from __future__ import annotations

from datetime import date, datetime
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.hoa_violation_fine_appeal import HOAFineAppeal
from app.models.user import User
from app.routers.auth import get_current_user
from app.routers.hoa_arc_board_decisions import _board_scope
from app.routers.hoa_assessments import _scope
from app.routers.hoa_member_assessments import _accountant
from app.routers.hoa_violation_cases import _case
from app.routers.hoa_violation_fines import _fine, _private_case_proof
from app.schemas.hoa_fine_appeal import (
    HOAFineAppealIn, HOAFineAppealDecisionIn, HOAFineAppealOut,
)
from app.services.audit import append_audit_log

router = APIRouter(prefix="/api/hoa/associations", tags=["HOA fine appeals"])


def _read_scope(db, actor, assoc_id, prop_id):
    try:
        org, assoc = _accountant(db, actor=actor, assoc=assoc_id, prop=prop_id)
        return org, assoc
    except HTTPException:
        org, assoc, _ = _board_scope(
            db, actor=actor, association_id=assoc_id, property_id=prop_id,
        )
        return org, assoc


def _appeals(db, org, assoc_id, prop_id, case_id, fine_id):
    return db.query(HOAFineAppeal).filter(
        HOAFineAppeal.organization_id == org,
        HOAFineAppeal.association_id == assoc_id,
        HOAFineAppeal.property_id == prop_id,
        HOAFineAppeal.case_id == case_id,
        HOAFineAppeal.fine_id == fine_id,
    )


def _out(row, fine):
    return HOAFineAppealOut(
        id=row.id, case_id=row.case_id, fine_id=row.fine_id,
        member_user_id=row.member_user_id, received_on=row.received_on,
        appeal_reason=row.appeal_reason,
        supporting_attachment_id=row.supporting_attachment_id,
        status=row.status, decided_on=row.decided_on,
        decision_note=row.decision_note,
        decision_board_seat_id=row.decision_board_seat_id,
        accounting_reversal_pending=(
            row.status == "VACATED" and fine.status == "POSTED"
        ), recorded_at=row.created_at,
    )


@router.get("/{association_id}/staff-cases/{case_id}/fine/appeals",
            response_model=list[HOAFineAppealOut])
def list_appeals(
    association_id: int, case_id: int, response: Response,
    property_id: int = Query(ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org, assoc = _read_scope(db, current_user, association_id, property_id)
    _case(db, org_id=org, association_id=assoc.id,
          property_id=property_id, case_id=case_id)
    fine = _fine(db, org, assoc.id, property_id, case_id)
    response.headers["Cache-Control"] = "no-store"
    if fine is None:
        return []
    rows = _appeals(db, org, assoc.id, property_id, case_id, fine.id).order_by(
        HOAFineAppeal.id,
    ).limit(101).all()
    if len(rows) > 100:
        raise HTTPException(status_code=422, detail="Appeal history limit reached.")
    return [_out(row, fine) for row in rows]


@router.post("/{association_id}/staff-cases/{case_id}/fine/appeals",
             response_model=HOAFineAppealOut, status_code=201)
def record_appeal(
    association_id: int, case_id: int, payload: HOAFineAppealIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org, assoc = _scope(
        db, actor=current_user, association_id=association_id,
        property_id=payload.property_id, write=True,
    )
    _case(db, org_id=org, association_id=assoc.id,
          property_id=payload.property_id, case_id=case_id)
    fine = _fine(db, org, assoc.id, payload.property_id, case_id, lock=True)
    if fine is None or fine.decision != "APPROVED":
        raise HTTPException(status_code=409, detail="An adopted fine is required for an appeal.")
    if payload.received_on < fine.decided_on or payload.received_on > date.today():
        raise HTTPException(status_code=422, detail="Appeal date must follow the board decision and not be future-dated.")
    matching = db.query(HOAFineAppeal).filter(
        HOAFineAppeal.organization_id == org,
        HOAFineAppeal.request_key == payload.request_key,
    ).first()
    if matching is not None:
        if (matching.fine_id == fine.id and matching.received_on == payload.received_on
            and matching.appeal_reason == payload.appeal_reason
            and matching.supporting_attachment_id == payload.supporting_attachment_id):
            return _out(matching, fine)
        raise HTTPException(status_code=409, detail="Appeal request key already used.")
    history = _appeals(db, org, assoc.id, payload.property_id, case_id, fine.id).all()
    if len(history) >= 20:
        raise HTTPException(status_code=422, detail="Appeal history limit reached.")
    if any(a.status in {"OPEN", "VACATED"} for a in history):
        raise HTTPException(status_code=409, detail="Fine already has an open or vacated appeal.")
    if payload.supporting_attachment_id is not None:
        _private_case_proof(
            db, org=org, association_id=assoc.id, property_id=payload.property_id,
            case_id=case_id, attachment_id=payload.supporting_attachment_id,
        )
    row = HOAFineAppeal(
        organization_id=org, association_id=assoc.id,
        property_id=payload.property_id, case_id=case_id,
        fine_id=fine.id, member_user_id=fine.member_user_id,
        request_key=payload.request_key, received_on=payload.received_on,
        appeal_reason=payload.appeal_reason,
        supporting_attachment_id=payload.supporting_attachment_id,
        received_by_id=current_user.id, status="OPEN",
    )
    db.add(row)
    try:
        db.flush()
        append_audit_log(
            db, organization_id=org, user_id=current_user.id,
            entity_type="hoa_violation_fine_appeal", entity_id=row.id,
            action="fine_appeal_received",
            new_value={"association_id":assoc.id,"property_id":payload.property_id,
                       "case_id":case_id,"fine_id":fine.id,"status":"OPEN"},
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Concurrent fine appeal request.") from exc
    db.refresh(row)
    return _out(row, fine)


@router.post("/{association_id}/staff-cases/{case_id}/fine/appeals/{appeal_id}/decision",
             response_model=HOAFineAppealOut)
def decide_appeal(
    association_id: int, case_id: int, appeal_id: int,
    payload: HOAFineAppealDecisionIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org, assoc, seat = _board_scope(
        db, actor=current_user, association_id=association_id,
        property_id=payload.property_id,
    )
    _case(db, org_id=org, association_id=assoc.id,
          property_id=payload.property_id, case_id=case_id)
    fine = _fine(db, org, assoc.id, payload.property_id, case_id, lock=True)
    if fine is None:
        raise HTTPException(status_code=404, detail="Fine not found.")
    row = _appeals(db, org, assoc.id, payload.property_id, case_id, fine.id).filter(
        HOAFineAppeal.id == appeal_id,
    ).with_for_update().first()
    if row is None:
        raise HTTPException(status_code=404, detail="Appeal not found.")
    if row.status != "OPEN":
        if (row.status == payload.result
            and row.decision_request_key == payload.request_key
            and row.decision_note == payload.decision_note):
            return _out(row, fine)
        raise HTTPException(status_code=409, detail="Appeal already has a final board disposition.")
    reused = db.query(HOAFineAppeal.id).filter(
        HOAFineAppeal.organization_id == org,
        HOAFineAppeal.decision_request_key == payload.request_key,
    ).first()
    if reused is not None:
        raise HTTPException(status_code=409, detail="Appeal decision request key already used.")
    row.status = payload.result
    row.decided_on = date.today()
    row.decided_at = datetime.utcnow()
    row.decision_note = payload.decision_note
    row.decision_board_seat_id = seat.id
    row.decided_by_id = current_user.id
    row.decision_request_key = payload.request_key
    try:
        db.flush()
        append_audit_log(
            db, organization_id=org, user_id=current_user.id,
            entity_type="hoa_violation_fine_appeal", entity_id=row.id,
            action="board_appeal_disposition",
            new_value={"association_id":assoc.id,"property_id":payload.property_id,
                       "case_id":case_id,"fine_id":fine.id,"status":row.status,
                       "board_seat_id":seat.id},
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Concurrent fine appeal decision.") from exc
    db.refresh(row)
    return _out(row, fine)
