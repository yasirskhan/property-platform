"""HOA staff review state machine; no legal enforcement or financial posting."""
from __future__ import annotations

from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.hoa_observation import HOAObservation
from app.models.hoa_procedure_policy import HOAProcedurePolicy
from app.models.hoa_violation_case import HOAViolationCase
from app.models.hoa_violation_case_event import HOAViolationCaseEvent
from app.models.hoa_case_task import HOACaseTask
from app.models.user import User
from app.routers.auth import get_current_user
from app.routers.hoa_assessments import _scope
from app.schemas.hoa_violation_case import (
    HOAViolationAdvanceIn, HOAViolationCaseIn, HOAViolationCaseOut,
    HOAViolationCaseEventOut,
)
from app.services.audit import append_audit_log

router = APIRouter(prefix="/api/hoa/associations", tags=["HOA staff case workflow"])

_ALLOWED = {
    "OPEN": {"NOTICE_DRAFT", "RESOLVED"},
    "NOTICE_DRAFT": {"CURE_TRACKING", "HEARING_PLANNED", "RESOLVED"},
    "CURE_TRACKING": {"HEARING_PLANNED", "FINE_PROPOSED", "RESOLVED"},
    "HEARING_PLANNED": {"FINE_PROPOSED", "RESOLVED"},
    "FINE_PROPOSED": {"HEARING_PLANNED", "RESOLVED"},
    "RESOLVED": {"CLOSED"},
    "CLOSED": set(),
}


def _observation(db: Session, *, org_id: int, association_id: int,
                 property_id: int, observation_id: int) -> HOAObservation:
    row = db.query(HOAObservation).filter(
        HOAObservation.id == observation_id,
        HOAObservation.organization_id == org_id,
        HOAObservation.association_id == association_id,
        HOAObservation.property_id == property_id,
        HOAObservation.is_active.is_(True),
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Active staff observation not found.")
    return row


def _case(db: Session, *, org_id: int, association_id: int,
          property_id: int, case_id: int) -> HOAViolationCase:
    row = db.query(HOAViolationCase).join(
        HOAObservation, HOAObservation.id == HOAViolationCase.observation_id,
    ).filter(
        HOAViolationCase.id == case_id,
        HOAViolationCase.organization_id == org_id,
        HOAViolationCase.association_id == association_id,
        HOAViolationCase.property_id == property_id,
        HOAViolationCase.is_active.is_(True),
        HOAObservation.organization_id == org_id,
        HOAObservation.association_id == association_id,
        HOAObservation.property_id == property_id,
        HOAObservation.is_active.is_(True),
    ).with_for_update().first()
    if row is None:
        raise HTTPException(status_code=404, detail="Active staff case not found.")
    return row


def _policy(db: Session, *, org_id: int, association_id: int,
            property_id: int) -> HOAProcedurePolicy | None:
    return db.query(HOAProcedurePolicy).filter(
        HOAProcedurePolicy.organization_id == org_id,
        HOAProcedurePolicy.association_id == association_id,
        HOAProcedurePolicy.property_id == property_id,
        HOAProcedurePolicy.is_active.is_(True),
    ).first()


def _out(row: HOAViolationCase) -> HOAViolationCaseOut:
    return HOAViolationCaseOut(
        id=row.id, association_id=row.association_id,
        property_id=row.property_id, observation_id=row.observation_id,
        stage=row.stage, draft_notice_on=row.draft_notice_on,
        tentative_cure_on=row.tentative_cure_on,
        tentative_hearing_on=row.tentative_hearing_on,
        proposed_fine=row.proposed_fine, staff_resolution=row.staff_resolution,
        policy_revision=row.policy_revision, updated_at=row.updated_at,
    )


def _audit(db: Session, *, row: HOAViolationCase, actor: User, action: str) -> None:
    append_audit_log(
        db, organization_id=row.organization_id, user_id=actor.id,
        entity_type="hoa_violation_case", entity_id=row.id,
        action=action, new_value={
            "association_id": row.association_id,
            "property_id": row.property_id,
            "observation_id": row.observation_id,
            "stage": row.stage, "policy_revision": row.policy_revision,
        },
    )


def _record_transition(db: Session, *, row: HOAViolationCase, actor: User,
                       previous: str | None, staff_action_on=None) -> None:
    db.add(HOAViolationCaseEvent(
        organization_id=row.organization_id, association_id=row.association_id,
        property_id=row.property_id, case_id=row.id,
        from_stage=previous, to_stage=row.stage,
        policy_revision=row.policy_revision,
        staff_action_on=staff_action_on,
        tentative_cure_on=row.tentative_cure_on,
        tentative_hearing_on=row.tentative_hearing_on,
        proposed_fine=row.proposed_fine,
        staff_resolution=row.staff_resolution,
        recorded_by_id=actor.id,
    ))


@router.get("/{association_id}/staff-cases/{case_id}/history",
            response_model=list[HOAViolationCaseEventOut])
def get_case_history(
    association_id: int, case_id: int, response: Response,
    property_id: int = Query(ge=1),
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org_id, assoc = _scope(
        db, actor=current_user, association_id=association_id,
        property_id=property_id, write=False,
    )
    case = _case(
        db, org_id=org_id, association_id=assoc.id,
        property_id=property_id, case_id=case_id,
    )
    events = db.query(HOAViolationCaseEvent).filter(
        HOAViolationCaseEvent.organization_id == org_id,
        HOAViolationCaseEvent.association_id == assoc.id,
        HOAViolationCaseEvent.property_id == property_id,
        HOAViolationCaseEvent.case_id == case.id,
    ).order_by(HOAViolationCaseEvent.id).limit(201).all()
    if len(events) > 200:
        raise HTTPException(status_code=422, detail="Case history exceeds display limit.")
    response.headers["Cache-Control"] = "no-store"
    return [
        HOAViolationCaseEventOut(
            id=e.id, case_id=e.case_id,
            from_stage=e.from_stage, to_stage=e.to_stage,
            policy_revision=e.policy_revision, staff_action_on=e.staff_action_on,
            tentative_cure_on=e.tentative_cure_on,
            tentative_hearing_on=e.tentative_hearing_on,
            proposed_fine=e.proposed_fine, staff_resolution=e.staff_resolution,
            recorded_at=e.recorded_at,
        ) for e in events
    ]


@router.get("/{association_id}/staff-cases", response_model=list[HOAViolationCaseOut])
def list_cases(
    association_id: int, response: Response, property_id: int = Query(ge=1),
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org_id, assoc = _scope(
        db, actor=current_user, association_id=association_id,
        property_id=property_id, write=False,
    )
    records = db.query(HOAViolationCase, HOAObservation).join(
        HOAObservation, HOAObservation.id == HOAViolationCase.observation_id,
    ).filter(
        HOAViolationCase.organization_id == org_id,
        HOAViolationCase.association_id == assoc.id,
        HOAViolationCase.property_id == property_id,
        HOAViolationCase.is_active.is_(True),
        HOAObservation.organization_id == org_id,
        HOAObservation.association_id == assoc.id,
        HOAObservation.property_id == property_id,
        HOAObservation.is_active.is_(True),
    ).order_by(HOAViolationCase.id).limit(201).all()
    if len(records) > 200:
        raise HTTPException(status_code=422, detail="Too many staff cases.")
    response.headers["Cache-Control"] = "no-store"
    return [_out(case) for case, _observation_row in records]


@router.post("/{association_id}/staff-cases", response_model=HOAViolationCaseOut, status_code=201)
def create_case(
    association_id: int, payload: HOAViolationCaseIn,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org_id, assoc = _scope(
        db, actor=current_user, association_id=association_id,
        property_id=payload.property_id, write=True,
    )
    source = _observation(
        db, org_id=org_id, association_id=assoc.id,
        property_id=payload.property_id, observation_id=payload.observation_id,
    )
    if db.query(HOAViolationCase.id).filter(
        HOAViolationCase.organization_id == org_id,
        HOAViolationCase.observation_id == source.id,
    ).first():
        raise HTTPException(status_code=409, detail="Observation already has a staff case.")
    count = db.query(HOAViolationCase.id).filter(
        HOAViolationCase.organization_id == org_id,
        HOAViolationCase.association_id == assoc.id,
        HOAViolationCase.property_id == payload.property_id,
        HOAViolationCase.is_active.is_(True),
    ).limit(200).all()
    if len(count) >= 200:
        raise HTTPException(status_code=422, detail="Too many staff cases.")
    row = HOAViolationCase(
        organization_id=org_id, association_id=assoc.id,
        property_id=payload.property_id, observation_id=source.id,
        stage="OPEN", created_by_id=current_user.id,
        updated_by_id=current_user.id,
    )
    db.add(row)
    try:
        db.flush()
        _record_transition(db, row=row, actor=current_user, previous=None)
        _audit(db, row=row, actor=current_user, action="staff_case_created")
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Observation already has a staff case.") from exc
    db.refresh(row)
    return _out(row)


@router.post("/{association_id}/staff-cases/{case_id}/advance",
             response_model=HOAViolationCaseOut)
def advance_case(
    association_id: int, case_id: int, payload: HOAViolationAdvanceIn,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org_id, assoc = _scope(
        db, actor=current_user, association_id=association_id,
        property_id=payload.property_id, write=True,
    )
    row = _case(
        db, org_id=org_id, association_id=assoc.id,
        property_id=payload.property_id, case_id=case_id,
    )
    if payload.next_stage not in _ALLOWED.get(row.stage, set()):
        raise HTTPException(status_code=409, detail="Invalid staff workflow transition.")
    if payload.next_stage in {"FINE_PROPOSED", "HEARING_PLANNED"}:
        from app.models.hoa_violation_fine import HOAViolationFine
        if db.query(HOAViolationFine.id).filter(
            HOAViolationFine.organization_id == org_id,
            HOAViolationFine.association_id == assoc.id,
            HOAViolationFine.property_id == payload.property_id,
            HOAViolationFine.case_id == row.id,
        ).first() is not None:
            raise HTTPException(status_code=409, detail="Final board fine decision cannot be changed by staff stage edits.")
    if payload.next_stage == "CLOSED":
        outstanding = db.query(HOACaseTask.id).filter(
            HOACaseTask.organization_id == org_id,
            HOACaseTask.association_id == assoc.id,
            HOACaseTask.property_id == payload.property_id,
            HOACaseTask.case_id == row.id,
            HOACaseTask.status.in_(("OPEN", "IN_PROGRESS")),
        ).first()
        if outstanding is not None:
            raise HTTPException(
                status_code=409,
                detail="Complete or cancel outstanding internal follow-up tasks before closing.",
            )
    policy = _policy(
        db, org_id=org_id, association_id=assoc.id,
        property_id=payload.property_id,
    )
    if payload.next_stage == "NOTICE_DRAFT":
        if policy is None or not policy.draft_notice_text:
            raise HTTPException(status_code=409, detail="Staff notice text must be configured first.")
        row.draft_notice_on = payload.action_on
    elif payload.next_stage == "CURE_TRACKING":
        if row.draft_notice_on is None:
            raise HTTPException(status_code=409, detail="No staff notice preparation date.")
        if policy is None or policy.cure_preparation_days is None:
            raise HTTPException(status_code=409, detail="Staff cure period must be configured first.")
        try:
            row.tentative_cure_on = row.draft_notice_on + timedelta(
                days=policy.cure_preparation_days,
            )
        except OverflowError as exc:
            raise HTTPException(status_code=422, detail="Computed preparation date out of range.") from exc
    elif payload.next_stage == "HEARING_PLANNED":
        row.tentative_hearing_on = payload.action_on
    elif payload.next_stage == "FINE_PROPOSED":
        if policy is None or policy.proposed_fine_cap is None:
            raise HTTPException(status_code=409, detail="Proposed fine cap must be configured first.")
        if payload.proposed_fine > policy.proposed_fine_cap:
            raise HTTPException(status_code=422, detail="Exceeds configured proposal cap.")
        row.proposed_fine = payload.proposed_fine
    elif payload.next_stage == "RESOLVED":
        row.staff_resolution = payload.staff_resolution.strip()
    previous_stage = row.stage
    row.stage = payload.next_stage
    row.policy_revision = policy.revision if policy else None
    row.updated_by_id = current_user.id
    _record_transition(db, row=row, actor=current_user,
                       previous=previous_stage, staff_action_on=payload.action_on)
    db.flush()
    _audit(db, row=row, actor=current_user, action="staff_case_advanced")
    db.commit()
    db.refresh(row)
    return _out(row)
