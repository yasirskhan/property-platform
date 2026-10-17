"""Active staff follow-up tasks for HOA violation cases; no statutory service."""
from __future__ import annotations

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.hoa_case_task import HOACaseTask
from app.models.property import PropertyAssignment
from app.models.user import User, UserRole
from app.routers.auth import get_current_user
from app.routers.hoa_assessments import _scope
from app.routers.hoa_violation_cases import _case
from app.schemas.hoa_case_task import (
    HOACaseTaskCreateIn, HOACaseTaskTransitionIn,
    HOACaseTaskOut, HOACaseTaskAssigneeOut,
)
from app.services.audit import append_audit_log

router = APIRouter(prefix="/api/hoa/associations", tags=["HOA case tasks"])

_STAFF = {UserRole.ADMIN, UserRole.OWNER, UserRole.MANAGER}
_NEXT = {"OPEN": {"IN_PROGRESS", "CANCELLED"},
         "IN_PROGRESS": {"DONE", "CANCELLED"},
         "DONE": set(), "CANCELLED": set()}


def _assignee(db: Session, *, org: int, prop: int, user_id: int) -> User:
    actor = db.query(User).filter(
        User.id == user_id, User.organization_id == org,
        User.is_active.is_(True), User.is_verified.is_(True),
        User.deleted_at.is_(None), User.role.in_(_STAFF),
    ).first()
    if actor is None:
        raise HTTPException(status_code=404, detail="Eligible active staff assignee not found.")
    if actor.role == UserRole.MANAGER:
        valid = db.query(PropertyAssignment.id).filter(
            PropertyAssignment.user_id == actor.id,
            PropertyAssignment.property_id == prop,
            PropertyAssignment.is_active.is_(True),
            PropertyAssignment.deleted_at.is_(None),
        ).first()
        if valid is None:
            raise HTTPException(status_code=404, detail="Staff assignee has no active property assignment.")
    return actor


def _task(db: Session, *, org: int, assoc: int, prop: int,
          case_id: int, task_id: int):
    row = db.query(HOACaseTask).filter(
        HOACaseTask.id == task_id,
        HOACaseTask.organization_id == org,
        HOACaseTask.association_id == assoc,
        HOACaseTask.property_id == prop,
        HOACaseTask.case_id == case_id,
    ).with_for_update().first()
    if row is None:
        raise HTTPException(status_code=404, detail="Scoped case task not found.")
    return row


def _out(row: HOACaseTask) -> HOACaseTaskOut:
    return HOACaseTaskOut(
        id=row.id, case_id=row.case_id,
        kind=row.kind, title=row.title, details=row.details,
        assigned_user_id=row.assigned_user_id,
        due_on=row.due_on, status=row.status,
        version=row.version, completed_at=row.completed_at,
        result_note=row.result_note,
        updated_at=row.updated_at,
    )


def _audit(db: Session, *, task: HOACaseTask, actor: User,
           action: str, previous: str | None = None, note: str | None = None):
    append_audit_log(
        db, organization_id=task.organization_id, user_id=actor.id,
        entity_type="hoa_case_task", entity_id=task.id,
        action=action,
        new_value={
            "association_id": task.association_id,
            "property_id": task.property_id, "case_id": task.case_id,
            "assigned_user_id": task.assigned_user_id,
            "previous_status": previous, "status": task.status,
            "version": task.version, "note_recorded_privately": bool(note),
        },
    )

@router.get("/{association_id}/staff-cases/{case_id}/task-assignees",
            response_model=list[HOACaseTaskAssigneeOut])
def list_assignees(
    association_id: int, case_id: int, response: Response,
    property_id: int = Query(ge=1),
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org, assoc = _scope(
        db, actor=current_user, association_id=association_id,
        property_id=property_id, write=False,
    )
    _case(db, org_id=org, association_id=assoc.id, property_id=property_id, case_id=case_id)
    users = db.query(User).filter(
        User.organization_id == org, User.is_active.is_(True),
        User.is_verified.is_(True), User.deleted_at.is_(None),
        User.role.in_(_STAFF),
    ).order_by(User.id).limit(201).all()
    if len(users) > 200:
        raise HTTPException(status_code=422, detail="Too many staff accounts.")
    response.headers["Cache-Control"] = "no-store"
    result = []
    for user in users:
        try:
            _assignee(db, org=org, prop=property_id, user_id=user.id)
        except HTTPException:
            continue
        result.append(HOACaseTaskAssigneeOut(
            id=user.id, name=(user.first_name + " " + user.last_name).strip(),
            role=user.role.value,
        ))
    return result


@router.get("/{association_id}/staff-cases/{case_id}/tasks",
            response_model=list[HOACaseTaskOut])
def list_tasks(
    association_id: int, case_id: int, response: Response,
    property_id: int = Query(ge=1),
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org, assoc = _scope(
        db, actor=current_user, association_id=association_id,
        property_id=property_id, write=False,
    )
    case = _case(db, org_id=org, association_id=assoc.id,
                 property_id=property_id, case_id=case_id)
    tasks = db.query(HOACaseTask).filter(
        HOACaseTask.organization_id == org,
        HOACaseTask.association_id == assoc.id,
        HOACaseTask.property_id == property_id,
        HOACaseTask.case_id == case.id,
    ).order_by(HOACaseTask.id).limit(101).all()
    if len(tasks) > 100:
        raise HTTPException(status_code=422, detail="Case task history exceeds display limit.")
    response.headers["Cache-Control"] = "no-store"
    return [_out(row) for row in tasks]


@router.post("/{association_id}/staff-cases/{case_id}/tasks",
             response_model=HOACaseTaskOut, status_code=201)
def create_task(
    association_id: int, case_id: int, payload: HOACaseTaskCreateIn,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org, assoc = _scope(
        db, actor=current_user, association_id=association_id,
        property_id=payload.property_id, write=True,
    )
    case = _case(db, org_id=org, association_id=assoc.id,
                 property_id=payload.property_id, case_id=case_id)
    existing = db.query(HOACaseTask).filter(
        HOACaseTask.organization_id == org, HOACaseTask.case_id == case.id,
        HOACaseTask.request_key == payload.request_key,
    ).with_for_update().first()
    if existing is not None:
        same = (
            existing.title == payload.title and
            existing.details == payload.details and
            existing.kind == payload.kind and
            existing.assigned_user_id == payload.assigned_user_id and
            existing.due_on == payload.due_on
        )
        if not same:
            raise HTTPException(status_code=409, detail="Task request key reused with different values.")
        return _out(existing)
    if case.stage in {"RESOLVED", "CLOSED"}:
        raise HTTPException(status_code=409, detail="Cannot open follow-up on resolved case.")
    _assignee(db, org=org, prop=payload.property_id, user_id=payload.assigned_user_id)
    count = db.query(HOACaseTask.id).filter(
        HOACaseTask.organization_id == org, HOACaseTask.case_id == case.id,
    ).limit(100).all()
    if len(count) >= 100:
        raise HTTPException(status_code=422, detail="Case task limit reached.")
    now = datetime.utcnow()
    row = HOACaseTask(
        organization_id=org, association_id=assoc.id,
        property_id=payload.property_id, case_id=case.id,
        request_key=payload.request_key,
        title=payload.title, details=payload.details, kind=payload.kind,
        assigned_user_id=payload.assigned_user_id, due_on=payload.due_on,
        status="OPEN", version=1,
        created_by_id=current_user.id, updated_by_id=current_user.id,
        created_at=now, updated_at=now,
    )
    db.add(row)
    try:
        db.flush()
        _audit(db, task=row, actor=current_user, action="internal_task_created")
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Task request changed concurrently.") from exc
    db.refresh(row)
    return _out(row)

@router.post("/{association_id}/staff-cases/{case_id}/tasks/{task_id}/transition",
             response_model=HOACaseTaskOut)
def transition_task(
    association_id: int, case_id: int, task_id: int,
    payload: HOACaseTaskTransitionIn,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org, assoc = _scope(
        db, actor=current_user, association_id=association_id,
        property_id=payload.property_id, write=False,
    )
    case = _case(db, org_id=org, association_id=assoc.id,
                 property_id=payload.property_id, case_id=case_id)
    task = _task(db, org=org, assoc=assoc.id, prop=payload.property_id,
                 case_id=case.id, task_id=task_id)
    if current_user.role not in {UserRole.ADMIN, UserRole.OWNER}:
        if current_user.role != UserRole.MANAGER or current_user.id != task.assigned_user_id:
            raise HTTPException(status_code=403, detail="Only the assigned manager may update this task.")
        _assignee(db, org=org, prop=payload.property_id, user_id=current_user.id)
    if case.stage == "CLOSED":
        raise HTTPException(status_code=409, detail="Closed case tasks are immutable.")
    if task.version != payload.expected_version:
        raise HTTPException(status_code=409, detail="Task changed; refresh before updating.")
    if payload.next_status not in _NEXT.get(task.status, set()):
        raise HTTPException(status_code=409, detail="Task transition is not allowed.")
    if (payload.next_status == "DONE") and not (payload.action_note or "").strip():
        raise HTTPException(status_code=422, detail="A completion note is required.")
    if (payload.next_status == "CANCELLED") and current_user.role not in {UserRole.ADMIN, UserRole.OWNER}:
        raise HTTPException(status_code=403, detail="Only association staff admin or owner may cancel a task.")
    previous = task.status
    task.status = payload.next_status
    task.version += 1
    task.updated_by_id = current_user.id
    task.updated_at = datetime.utcnow()
    if task.status == "DONE":
        task.completed_at = task.updated_at
    task.result_note = (payload.action_note or "").strip() or None
    _audit(db, task=task, actor=current_user,
           action="internal_task_transitioned",
           previous=previous, note=payload.action_note)
    db.commit()
    db.refresh(task)
    return _out(task)
