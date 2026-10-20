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
    active: bool

class ActiveUpdate(BaseModel):
    active: bool

class GeneratedOut(BaseModel):
    work_order_id: int
    newly_created: bool
    tenant_id: int | None

@router.post("/schedules", response_model=ScheduleOut, status_code=201)
def create(payload: ScheduleCreate, db: Session = Depends(get_db),
           current_user: User = Depends(get_current_user)):
    return service.create_schedule(db, current_user, **payload.model_dump())

@router.get("/schedules", response_model=list[ScheduleOut])
def listing(db: Session = Depends(get_db),
            current_user: User = Depends(get_current_user)):
    return service.list_schedules(db, current_user)

@router.patch("/schedules/{schedule_id}", response_model=ScheduleOut)
def change_active(schedule_id: int, payload: ActiveUpdate,
                  db: Session = Depends(get_db),
                  current_user: User = Depends(get_current_user)):
    return service.set_active(db, current_user, schedule_id, payload.active)

@router.post("/schedules/{schedule_id}/generate", response_model=GeneratedOut)
def generate(schedule_id: int, as_of: Annotated[date | None, Query()] = None,
             db: Session = Depends(get_db),
             current_user: User = Depends(get_current_user)):
    wo, fresh = service.generate_due(db, current_user, schedule_id, as_of=as_of or date.today())
    return GeneratedOut(work_order_id=wo.id, newly_created=fresh, tenant_id=wo.tenant_id)
