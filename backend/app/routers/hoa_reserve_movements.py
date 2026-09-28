"""HOA reserve request preparation. No call to post_transaction() or banking.

A recorded GL account is not verified statutory reserve ownership. This
service cannot execute transfers, even with an org-entered policy.
"""
from __future__ import annotations
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.gl_account import GLAccount
from app.models.hoa_reserve_movement_draft import HOAReserveMovementDraft
from app.models.user import User, UserRole
from app.routers.auth import get_current_user
from app.routers.hoa_reserve_accounts import _accounts, _reserve, _scope_with_accounting
from app.schemas.hoa_reserve_movement import HOAReserveMovementIn, HOAReserveMovementOut
from app.services.audit import append_audit_log

router = APIRouter(prefix="/api/hoa/associations", tags=["HOA reserve movement planning"])


def _scope(db: Session, actor: User, assoc_id: int, property_id: int, *, write: bool):
    org, assoc = _scope_with_accounting(
        db, actor=actor, association_id=assoc_id, property_id=property_id,
        write=write,
    )
    # Planned transfers reveal org-wide financial intent, unlike a property
    # roster. Do not expand scope to assigned managers.
    if actor.role not in (UserRole.ADMIN, UserRole.OWNER):
        raise HTTPException(status_code=403, detail="Reserve financial planning requires admin/owner.")
    reserve = _reserve(db, org_id=org, association_id=assoc.id, property_id=property_id)
    if reserve is None or not reserve.is_active:
        raise HTTPException(status_code=404, detail="Active reserve mapping not found.")
    gl, bank = _accounts(db, org_id=org, row=reserve)
    if not gl.is_active or gl.deleted_at is not None or (
        bank is not None and (not bank.is_active or bank.deleted_at is not None)
    ):
        raise HTTPException(status_code=409, detail="Reserve mapping needs active GL review.")
    return org, assoc, reserve, gl


def _out(row: HOAReserveMovementDraft) -> HOAReserveMovementOut:
    return HOAReserveMovementOut(
        id=row.id, property_id=row.property_id, association_id=row.association_id,
        reserve_gl_account_id=row.reserve_gl_account_id,
        counterparty_gl_account_id=row.counterparty_gl_account_id,
        direction=row.direction, planned_on=row.planned_on,
        amount=row.amount, memo=row.memo, status=row.status,
        created_at=row.created_at, cancelled_at=row.cancelled_at,
    )


def _audit(db: Session, actor: User, row: HOAReserveMovementDraft, action: str):
    append_audit_log(
        db, organization_id=row.organization_id, user_id=actor.id,
        entity_type="hoa_reserve_movement_draft", entity_id=row.id,
        action=action, new_value={
            "association_id": row.association_id, "property_id": row.property_id,
            "reserve_gl_account_id": row.reserve_gl_account_id,
        },
    )


@router.get("/{association_id}/reserve-movement-drafts",
            response_model=list[HOAReserveMovementOut])
def list_movement_drafts(
    association_id: int, response: Response,
    property_id: int = Query(ge=1),
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org, assoc, reserve, gl = _scope(db, current_user, association_id, property_id, write=False)
    records = db.query(HOAReserveMovementDraft).filter(
        HOAReserveMovementDraft.organization_id == org,
        HOAReserveMovementDraft.association_id == assoc.id,
        HOAReserveMovementDraft.property_id == property_id,
        HOAReserveMovementDraft.reserve_gl_account_id == gl.id,
    ).order_by(HOAReserveMovementDraft.id).limit(201).all()
    if len(records) > 200:
        raise HTTPException(status_code=422, detail="Too many movement drafts.")
    response.headers["Cache-Control"] = "no-store"
    return [_out(row) for row in records]


@router.post("/{association_id}/reserve-movement-drafts",
             response_model=HOAReserveMovementOut, status_code=201)
def create_movement_draft(
    association_id: int, payload: HOAReserveMovementIn,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org, assoc, reserve, gl = _scope(
        db, current_user, association_id, payload.property_id, write=True,
    )
    existing = db.query(HOAReserveMovementDraft).filter(
        HOAReserveMovementDraft.organization_id == org,
        HOAReserveMovementDraft.idempotency_key == payload.idempotency_key,
    ).first()
    if existing is not None:
        same = (
            existing.association_id == assoc.id
            and existing.property_id == payload.property_id
            and existing.reserve_gl_account_id == gl.id
            and existing.counterparty_gl_account_id == payload.counterparty_gl_account_id
            and existing.direction == payload.direction
            and existing.planned_on == payload.planned_on
            and existing.amount == payload.amount
            and existing.memo == payload.memo
        )
        if not same:
            raise HTTPException(status_code=409, detail="Movement request key already used.")
        return _out(existing)
    if payload.counterparty_gl_account_id == gl.id:
        raise HTTPException(status_code=422, detail="Movement account cannot equal reserve account.")
    counterparty = db.query(GLAccount).filter(
        GLAccount.id == payload.counterparty_gl_account_id,
        GLAccount.organization_id == org,
        GLAccount.account_type == "ASSET",
        GLAccount.include_on_cash_flow.is_(True),
        GLAccount.is_active.is_(True),
        GLAccount.deleted_at.is_(None),
    ).first()
    if counterparty is None:
        raise HTTPException(status_code=404, detail="Active cash-like counterpart GL not found.")
    rows = db.query(HOAReserveMovementDraft.id).filter(
        HOAReserveMovementDraft.organization_id == org,
        HOAReserveMovementDraft.association_id == assoc.id,
        HOAReserveMovementDraft.property_id == payload.property_id,
    ).limit(201).all()
    if len(rows) >= 200:
        raise HTTPException(status_code=422, detail="Too many reserve movement drafts.")
    record = HOAReserveMovementDraft(
        organization_id=org, association_id=assoc.id, property_id=payload.property_id,
        reserve_gl_account_id=gl.id,
        created_by_id=current_user.id,
        **payload.model_dump(exclude={"property_id"}),
    )
    db.add(record)
    try:
        db.flush()
        _audit(db, current_user, record, "staff_movement_planned")
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Concurrent reserve movement request.") from exc
    db.refresh(record)
    return _out(record)


@router.post("/{association_id}/reserve-movement-drafts/{draft_id}/cancel",
             response_model=HOAReserveMovementOut)
def cancel_movement_draft(
    association_id: int, draft_id: int, property_id: int = Query(ge=1),
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org, assoc, reserve, gl = _scope(db, current_user, association_id, property_id, write=True)
    row = db.query(HOAReserveMovementDraft).filter(
        HOAReserveMovementDraft.id == draft_id,
        HOAReserveMovementDraft.organization_id == org,
        HOAReserveMovementDraft.association_id == assoc.id,
        HOAReserveMovementDraft.property_id == property_id,
        HOAReserveMovementDraft.reserve_gl_account_id == gl.id,
    ).with_for_update().first()
    if row is None:
        raise HTTPException(status_code=404, detail="Movement draft not found.")
    if row.status == "CANCELLED":
        raise HTTPException(status_code=409, detail="Movement draft already cancelled.")
    row.status = "CANCELLED"
    row.cancelled_at = datetime.utcnow()
    row.cancelled_by_id = current_user.id
    db.flush()
    _audit(db, current_user, row, "staff_movement_cancelled")
    db.commit()
    db.refresh(row)
    return _out(row)
