"""Operational association annual-budget adoption with immutable revisions.

An authenticated association board member records a real approval/denial.
This is an approved budget, not a member assessment, GL posting or cash transfer.
Staff drafts are association-specific and never inferred from unrelated property budgets.
"""
from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.entity_attachment import EntityAttachment
from app.models.gl_account import GLAccount
from app.models.hoa_annual_budget import HOAAnnualBudget
from app.models.user import User
from app.routers.auth import get_current_user
from app.routers.hoa_arc_board_decisions import _board_scope, _decision_maker
from app.routers.hoa_assessments import _scope
from app.schemas.hoa_annual_budget import (
    HOAAnnualBudgetCreateIn, HOAAnnualBudgetReviseIn,
    HOAAnnualBudgetDecisionIn, HOAAnnualBudgetOut, HOAAnnualBudgetAccountOut,
)
from app.services.audit import append_audit_log
from app.services.menu_resolver import permission_allows_user

router = APIRouter(prefix="/api/hoa/associations", tags=["HOA annual budget"])
_MAX_TOTAL = Decimal("999999999999.99")


def _staff(db: Session, *, actor: User, association_id: int, property_id: int,
           write: bool):
    org, association = _scope(
        db, actor=actor, association_id=association_id,
        property_id=property_id, write=write,
    )
    if not permission_allows_user(db, user=actor, menu_key="ACCOUNTING.GL_ACCOUNTS"):
        raise HTTPException(status_code=403, detail="HOA budget accounting permission required.")
    return org, association


def _read(db: Session, *, actor: User, association_id: int, property_id: int):
    try:
        return _staff(db, actor=actor, association_id=association_id,
                      property_id=property_id, write=False)
    except HTTPException:
        # A specifically authorized, verified board login may read its OWN
        # association/property budget even without the staff-wide menu.
        org, association, _seat = _board_scope(
            db, actor=actor, association_id=association_id, property_id=property_id,
        )
        return org, association


def _budget(db: Session, *, org: int, association_id: int, property_id: int,
            budget_id: int, lock: bool = False) -> HOAAnnualBudget:
    q = db.query(HOAAnnualBudget).filter(
        HOAAnnualBudget.id == budget_id,
        HOAAnnualBudget.organization_id == org,
        HOAAnnualBudget.association_id == association_id,
        HOAAnnualBudget.property_id == property_id,
        HOAAnnualBudget.is_active.is_(True),
    )
    row = (q.with_for_update() if lock else q).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Association annual budget not found.")
    return row


def _snapshot(db: Session, *, org: int, lines, reserve_allocation: Decimal):
    ids = [entry.gl_account_id for entry in lines]
    accounts = db.query(GLAccount).filter(
        GLAccount.organization_id == org,
        GLAccount.id.in_(ids),
        GLAccount.is_active.is_(True),
        GLAccount.deleted_at.is_(None),
        GLAccount.account_type.in_(("INCOME", "EXPENSE")),
    ).all()
    mapped = {a.id: a for a in accounts}
    if len(mapped) != len(ids):
        raise HTTPException(status_code=404, detail="Active same-organization budget GL account not found.")
    income = Decimal("0.00")
    expense = Decimal("0.00")
    snapshot = []
    for line in sorted(lines, key=lambda value: value.gl_account_id):
        account = mapped[line.gl_account_id]
        amount = line.annual_amount
        if account.account_type == "INCOME":
            income += amount
        else:
            expense += amount
        snapshot.append({
            "gl_account_id": account.id, "gl_number": account.gl_number,
            "gl_name": account.name, "account_type": account.account_type,
            "annual_amount": str(amount),
        })
    if income > _MAX_TOTAL or expense > _MAX_TOTAL:
        raise HTTPException(status_code=422, detail="Annual budget total is too large.")
    if reserve_allocation > expense:
        raise HTTPException(status_code=422, detail="Planned reserve allocation cannot exceed annual expenses.")
    return json.dumps(snapshot, sort_keys=True), income, expense


def _out(row: HOAAnnualBudget) -> HOAAnnualBudgetOut:
    return HOAAnnualBudgetOut(
        id=row.id, property_id=row.property_id, calendar_year=row.calendar_year,
        revision=row.revision, version=row.version,
        description=row.description, lines=json.loads(row.lines_json),
        total_income=row.total_income, total_expense=row.total_expense,
        reserve_allocation=row.reserve_allocation, status=row.status,
        board_seat_id=row.board_seat_id,
        decision_maker_seat_id=row.decision_maker_seat_id,
        decision_method=row.decision_method, decided_on=row.decided_on,
        decision_note=row.decision_note, created_at=row.created_at,
    )


def _audit(db: Session, *, row: HOAAnnualBudget, actor: User, action: str):
    append_audit_log(
        db, organization_id=row.organization_id, user_id=actor.id,
        entity_type="hoa_annual_budget", entity_id=row.id,
        action=action,
        new_value={
            "association_id": row.association_id, "property_id": row.property_id,
            "calendar_year": row.calendar_year, "revision": row.revision,
            "version": row.version, "status": row.status,
            "decision_maker_seat_id": row.decision_maker_seat_id,
        },
    )


@router.get("/{association_id}/annual-budgets/accounts",
            response_model=list[HOAAnnualBudgetAccountOut])
def annual_budget_accounts(
    association_id: int, response: Response, property_id: int = Query(ge=1),
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org, _ = _staff(db, actor=current_user, association_id=association_id,
                    property_id=property_id, write=False)
    accounts = db.query(GLAccount).filter(
        GLAccount.organization_id == org, GLAccount.is_active.is_(True),
        GLAccount.deleted_at.is_(None),
        GLAccount.account_type.in_(("INCOME", "EXPENSE")),
    ).order_by(GLAccount.gl_number, GLAccount.id).limit(501).all()
    if len(accounts) > 500:
        raise HTTPException(status_code=422, detail="Too many HOA budget GL accounts.")
    response.headers["Cache-Control"] = "no-store"
    return [HOAAnnualBudgetAccountOut(
        id=a.id, number=a.gl_number, name=a.name,
        account_type=a.account_type,
    ) for a in accounts]


@router.get("/{association_id}/annual-budgets",
            response_model=list[HOAAnnualBudgetOut])
def list_annual_budgets(
    association_id: int, response: Response, property_id: int = Query(ge=1),
    calendar_year: int | None = Query(default=None, ge=2000, le=2100),
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org, association = _read(db, actor=current_user,
                             association_id=association_id, property_id=property_id)
    q = db.query(HOAAnnualBudget).filter(
        HOAAnnualBudget.organization_id == org,
        HOAAnnualBudget.association_id == association.id,
        HOAAnnualBudget.property_id == property_id,
        HOAAnnualBudget.is_active.is_(True),
    )
    if calendar_year is not None:
        q = q.filter(HOAAnnualBudget.calendar_year == calendar_year)
    rows = q.order_by(HOAAnnualBudget.calendar_year.desc(),
                      HOAAnnualBudget.revision.desc()).limit(251).all()
    if len(rows) > 250:
        raise HTTPException(status_code=422, detail="Too many annual budget revisions; filter by year.")
    response.headers["Cache-Control"] = "no-store"
    return [_out(row) for row in rows]


@router.post("/{association_id}/annual-budgets",
             response_model=HOAAnnualBudgetOut, status_code=201)
def create_annual_budget(
    association_id: int, payload: HOAAnnualBudgetCreateIn,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org, association = _staff(
        db, actor=current_user, association_id=association_id,
        property_id=payload.property_id, write=True,
    )
    lines, income, expense = _snapshot(
        db, org=org, lines=payload.lines,
        reserve_allocation=payload.reserve_allocation,
    )
    latest = db.query(HOAAnnualBudget).filter(
        HOAAnnualBudget.organization_id == org,
        HOAAnnualBudget.association_id == association.id,
        HOAAnnualBudget.property_id == payload.property_id,
        HOAAnnualBudget.calendar_year == payload.calendar_year,
    ).order_by(HOAAnnualBudget.revision.desc()).with_for_update().first()
    if latest is not None and latest.is_active and latest.status == "DRAFT":
        if (latest.lines_json == lines
                and latest.description == payload.description
                and latest.reserve_allocation == payload.reserve_allocation):
            return _out(latest)
        raise HTTPException(status_code=409, detail="Revise the existing draft before creating another.")
    row = HOAAnnualBudget(
        organization_id=org, association_id=association.id,
        property_id=payload.property_id, calendar_year=payload.calendar_year,
        revision=latest.revision + 1 if latest else 1,
        version=1, description=payload.description,
        lines_json=lines, total_income=income, total_expense=expense,
        reserve_allocation=payload.reserve_allocation,
        status="DRAFT", created_by_id=current_user.id,
    )
    db.add(row)
    try:
        db.flush()
        _audit(db, row=row, actor=current_user, action="annual_budget_drafted")
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Concurrent annual budget draft.") from exc
    db.refresh(row)
    return _out(row)


@router.put("/{association_id}/annual-budgets/{budget_id}",
            response_model=HOAAnnualBudgetOut)
def revise_annual_budget(
    association_id: int, budget_id: int, payload: HOAAnnualBudgetReviseIn,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org, association = _staff(
        db, actor=current_user, association_id=association_id,
        property_id=payload.property_id, write=True,
    )
    row = _budget(db, org=org, association_id=association.id,
                  property_id=payload.property_id, budget_id=budget_id, lock=True)
    if row.status != "DRAFT" or row.version != payload.expected_version:
        raise HTTPException(status_code=409, detail="Budget is final or its revision is stale.")
    if row.calendar_year != payload.calendar_year:
        raise HTTPException(status_code=409, detail="Budget calendar year cannot change.")
    lines, income, expense = _snapshot(db, org=org, lines=payload.lines,
                                       reserve_allocation=payload.reserve_allocation)
    row.description = payload.description
    row.lines_json = lines
    row.total_income, row.total_expense = income, expense
    row.reserve_allocation = payload.reserve_allocation
    row.version += 1
    _audit(db, row=row, actor=current_user, action="annual_budget_revised")
    db.commit()
    db.refresh(row)
    return _out(row)


@router.post("/{association_id}/annual-budgets/{budget_id}/decision",
             response_model=HOAAnnualBudgetOut)
def decide_annual_budget(
    association_id: int, budget_id: int, payload: HOAAnnualBudgetDecisionIn,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org, association, recorder = _board_scope(
        db, actor=current_user, association_id=association_id,
        property_id=payload.property_id,
    )
    row = _budget(db, org=org, association_id=association.id,
                  property_id=payload.property_id, budget_id=budget_id, lock=True)
    if row.status != "DRAFT" or row.version != payload.expected_version:
        raise HTTPException(status_code=409, detail="Annual budget is already decided or stale.")
    maker, method, decision_day = recorder, "DIRECT", date.today()
    supporting = None
    if payload.offline_meeting_on is not None:
        if not recorder.can_record_offline:
            raise HTTPException(status_code=403, detail="Designated offline recorder required.")
        maker = _decision_maker(
            db, org=org, association_id=association.id,
            property_id=payload.property_id,
            seat_id=payload.decision_maker_seat_id,
        )
        supporting = db.query(EntityAttachment).filter(
            EntityAttachment.id == payload.supporting_attachment_id,
            EntityAttachment.organization_id == org,
            EntityAttachment.entity_type == "properties",
            EntityAttachment.entity_id == payload.property_id,
            EntityAttachment.is_active.is_(True),
            EntityAttachment.share_with_tenants.is_(False),
            EntityAttachment.share_with_owners.is_(False),
        ).first()
        if supporting is None:
            raise HTTPException(status_code=404, detail="Private board meeting record not found.")
        method = "OFFLINE"
        decision_day = payload.offline_meeting_on
    if decision_day > date.today():
        raise HTTPException(status_code=422, detail="Future board decisions cannot be recorded.")
    row.status = payload.decision
    row.board_seat_id = recorder.id
    row.decision_maker_seat_id = maker.id
    row.decision_method = method
    row.decided_on = decision_day
    row.decided_at = datetime.utcnow()
    row.decision_note = payload.decision_note
    row.supporting_attachment_id = supporting.id if supporting else None
    row.decided_by_id = current_user.id
    row.version += 1
    try:
        _audit(db, row=row, actor=current_user, action="annual_budget_board_decided")
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Concurrent annual budget decision.") from exc
    db.refresh(row)
    return _out(row)
