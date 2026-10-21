"""Preventive maintenance: explicit staff schedules, no unattended dispatch."""
from datetime import date
from typing import Annotated
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.routers.auth import get_current_user
from app.models.user import User
from app.services import preventive_maintenance as service

router = APIRouter(prefix="/api/maintenance/preventive", tags=["Preventive Maintenance"])

class ScheduleCreate(BaseModel):
    unit_id: int = Field(ge=1)
    title: str = Field(min_length=3, max_length=255)
    description: str = Field(min_length=10, max_length=2000)
    interval_days: int = Field(ge=1, le=3650)
    next_due_date: date
    end_date: date | None = None

class ScheduleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    organization_id: int
    property_id: int
    unit_id: int
    title: str
    description: str
    interval_days: int
    next_due_date: date
    end_date: date | None = None
    executor_user_id: int | None = None
    active: bool

class ActiveUpdate(BaseModel):
    active: bool

class ScheduleSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str | None = Field(default=None, min_length=3, max_length=255)
    description: str | None = Field(default=None, min_length=10, max_length=2000)
    interval_days: int | None = Field(default=None, ge=1, le=3650)
    end_date: date | None = None


class AssumeExecution(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=10, max_length=500)


class ExecutionStatusOut(BaseModel):
    schedule_id: int
    executor_user_id: int
    status: str
    due: bool


@router.get("/schedules/{schedule_id}/execution-status", response_model=ExecutionStatusOut)
def get_execution_status(schedule_id: int, db: Session = Depends(get_db),
                         current_user: User = Depends(get_current_user)):
    return service.execution_status(db, current_user, schedule_id)


@router.post("/schedules/{schedule_id}/assume-execution", response_model=ScheduleOut)
def assume_execution(schedule_id: int, payload: AssumeExecution,
                     db: Session = Depends(get_db),
                     current_user: User = Depends(get_current_user)):
    return service.assume_execution(db, current_user, schedule_id, reason=payload.reason)


class GeneratedOut(BaseModel):
    work_order_id: int
    newly_created: bool
    tenant_id: int | None

@router.post("/schedules", response_model=ScheduleOut, status_code=201)
def create(payload: ScheduleCreate, db: Session = Depends(get_db),
           current_user: User = Depends(get_current_user)):
    return service.create_schedule(db, current_user, **payload.model_dump())

@router.get("/schedules", response_model=list[ScheduleOut])
def listing(limit: Annotated[int, Query(ge=1, le=100)] = 100,
            offset: Annotated[int, Query(ge=0, le=100000)] = 0,
            db: Session = Depends(get_db),
            current_user: User = Depends(get_current_user)):
    return service.list_schedules(db, current_user, limit=limit, offset=offset)

@router.get("/schedules/{schedule_id}", response_model=ScheduleOut)
def detail(schedule_id: int, db: Session = Depends(get_db),
           current_user: User = Depends(get_current_user)):
    return service.read_schedule(db, current_user, schedule_id)

@router.patch("/schedules/{schedule_id}", response_model=ScheduleOut)
def change_active(schedule_id: int, payload: ActiveUpdate,
                  db: Session = Depends(get_db),
                  current_user: User = Depends(get_current_user)):
    return service.set_active(db, current_user, schedule_id, payload.active)

@router.patch("/schedules/{schedule_id}/settings", response_model=ScheduleOut)
def edit_settings(schedule_id: int, payload: ScheduleSettings,
                  db: Session = Depends(get_db),
                  current_user: User = Depends(get_current_user)):
    return service.update_settings(
        db, current_user, schedule_id, **payload.model_dump(exclude_unset=True),
    )


class DuePreviewOut(BaseModel):
    schedule_id: int
    as_of: date
    next_due_date: date
    active: bool
    due_dates: list[date]
    has_more: bool


@router.get("/schedules/{schedule_id}/due-preview", response_model=DuePreviewOut)
def due_preview(schedule_id: int,
                as_of: Annotated[date | None, Query()] = None,
                limit: Annotated[int, Query(ge=1, le=120)] = 12,
                db: Session = Depends(get_db),
                current_user: User = Depends(get_current_user)):
    return service.preview_due(
        db, current_user, schedule_id, as_of=as_of or date.today(), limit=limit,
    )


@router.post("/schedules/{schedule_id}/generate", response_model=GeneratedOut)
def generate(schedule_id: int, as_of: Annotated[date | None, Query()] = None,
             db: Session = Depends(get_db),
             current_user: User = Depends(get_current_user)):
    wo, fresh = service.generate_due(db, current_user, schedule_id, as_of=as_of or date.today())
    return GeneratedOut(work_order_id=wo.id, newly_created=fresh, tenant_id=wo.tenant_id)


class OccurrenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    schedule_id: int
    due_date: date
    work_order_id: int

@router.get("/schedules/{schedule_id}/occurrences", response_model=list[OccurrenceOut])
def history(schedule_id: int,
            limit: Annotated[int, Query(ge=1, le=100)] = 100,
            offset: Annotated[int, Query(ge=0, le=100000)] = 0,
            db: Session = Depends(get_db),
            current_user: User = Depends(get_current_user)):
    return service.list_occurrences(db, current_user, schedule_id,
                                    limit=limit, offset=offset)
