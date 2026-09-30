"""Phase 4.10 student-housing foundation.

Academic cycles and bed inventory are explicit operational metadata only.
They do not establish student status, occupancy eligibility, a lease,
guarantor liability, rent, charges, or accounting entries.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.audit import log_action
from app.core.database import get_db
from app.models.property import (
    Property,
    PropertyAssignment,
    StudentAcademicCycle,
    StudentBed,
    Unit,
)
from app.models.user import User, UserRole
from app.routers.auth import get_current_user
from app.schemas.student_housing import (
    AcademicCycleCreate,
    AcademicCycleOut,
    StudentBedCreate,
    StudentBedOut,
)
from app.services.customer_features import resolve_customer_features
from app.services.menu_resolver import permission_allows_user


router = APIRouter(prefix="/api/properties", tags=["Student housing"])
FEATURE_KEY = "release.properties.student_housing"
MAX_CYCLES = 100
MAX_BEDS = 1000


def _student_property(db: Session, current_user: User, property_id: int) -> Property:
    if (
        current_user.organization_id is None
        or not current_user.is_active
        or current_user.deleted_at is not None
        or current_user.role not in {UserRole.ADMIN, UserRole.OWNER, UserRole.MANAGER}
        or not permission_allows_user(db, user=current_user, menu_key="PROPERTIES.ALL")
    ):
        raise HTTPException(status_code=403, detail="Property permission required.")

    decision = next(
        (
            item
            for item in resolve_customer_features(db, user=current_user)
            if item.key == FEATURE_KEY
        ),
        None,
    )
    if decision is None or not decision.allowed:
        raise HTTPException(status_code=404, detail="Student housing is not available.")

    prop = (
        db.query(Property)
        .filter(
            Property.id == property_id,
            Property.organization_id == current_user.organization_id,
            Property.is_active.is_(True),
            Property.deleted_at.is_(None),
        )
        .first()
    )
    if prop is None:
        raise HTTPException(status_code=404, detail="Property not found.")

    if current_user.role == UserRole.MANAGER and not (
        db.query(PropertyAssignment.id)
        .filter(
            PropertyAssignment.property_id == prop.id,
            PropertyAssignment.user_id == current_user.id,
            PropertyAssignment.is_active.is_(True),
            PropertyAssignment.deleted_at.is_(None),
        )
        .first()
    ):
        raise HTTPException(status_code=404, detail="Property not found.")
    return prop


def _require_write(current_user: User) -> None:
    if current_user.role not in {UserRole.ADMIN, UserRole.OWNER}:
        raise HTTPException(status_code=403, detail="Admin or owner access required.")


def _active_unit(db: Session, property_id: int, unit_id: int) -> Unit:
    unit = (
        db.query(Unit)
        .filter(
            Unit.id == unit_id,
            Unit.property_id == property_id,
            Unit.is_active.is_(True),
            Unit.deleted_at.is_(None),
        )
        .first()
    )
    if unit is None:
        raise HTTPException(status_code=404, detail="Unit not found.")
    return unit


def _cycle_out(row: StudentAcademicCycle) -> dict[str, object]:
    return {
        "id": row.id,
        "property_id": row.property_id,
        "name": row.name,
        "start_date": row.start_date,
        "end_date": row.end_date,
        "is_active": row.is_active,
        "created_at": row.created_at,
    }


def _bed_out(row: StudentBed) -> dict[str, object]:
    return {
        "id": row.id,
        "property_id": row.property_id,
        "unit_id": row.unit_id,
        "bed_label": row.bed_label,
        "is_active": row.is_active,
        "created_at": row.created_at,
    }


@router.get(
    "/{property_id}/student-housing/academic-cycles",
    response_model=list[AcademicCycleOut],
)
def list_academic_cycles(
    property_id: int,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    prop = _student_property(db, current_user, property_id)
    rows = (
        db.query(StudentAcademicCycle)
        .filter(
            StudentAcademicCycle.organization_id == prop.organization_id,
            StudentAcademicCycle.property_id == prop.id,
            StudentAcademicCycle.is_active.is_(True),
        )
        .order_by(StudentAcademicCycle.start_date.desc(), StudentAcademicCycle.id.desc())
        .limit(MAX_CYCLES + 1)
        .all()
    )
    if len(rows) > MAX_CYCLES:
        raise HTTPException(status_code=422, detail="Too many academic cycles.")
    response.headers["Cache-Control"] = "no-store"
    return [_cycle_out(row) for row in rows]


@router.post(
    "/{property_id}/student-housing/academic-cycles",
    response_model=AcademicCycleOut,
    status_code=status.HTTP_201_CREATED,
)
def create_academic_cycle(
    property_id: int,
    payload: AcademicCycleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    prop = _student_property(db, current_user, property_id)
    _require_write(current_user)
    row = StudentAcademicCycle(
        organization_id=prop.organization_id,
        property_id=prop.id,
        name=payload.name.strip(),
        start_date=payload.start_date,
        end_date=payload.end_date,
        created_by_id=current_user.id,
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Academic cycle already exists.")
    db.refresh(row)
    log_action(
        db,
        current_user,
        entity_type="property",
        entity_id=prop.id,
        action="student_academic_cycle_created",
        new_value={"cycle_id": row.id},
    )
    return _cycle_out(row)


@router.delete(
    "/{property_id}/student-housing/academic-cycles/{cycle_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def deactivate_academic_cycle(
    property_id: int,
    cycle_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    prop = _student_property(db, current_user, property_id)
    _require_write(current_user)
    row = (
        db.query(StudentAcademicCycle)
        .filter(
            StudentAcademicCycle.id == cycle_id,
            StudentAcademicCycle.organization_id == prop.organization_id,
            StudentAcademicCycle.property_id == prop.id,
            StudentAcademicCycle.is_active.is_(True),
        )
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Academic cycle not found.")
    row.is_active = False
    db.commit()
    log_action(
        db,
        current_user,
        entity_type="property",
        entity_id=prop.id,
        action="student_academic_cycle_deactivated",
        new_value={"cycle_id": row.id},
    )


@router.get(
    "/{property_id}/student-housing/beds",
    response_model=list[StudentBedOut],
)
def list_student_beds(
    property_id: int,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    prop = _student_property(db, current_user, property_id)
    rows = (
        db.query(StudentBed)
        .filter(
            StudentBed.organization_id == prop.organization_id,
            StudentBed.property_id == prop.id,
            StudentBed.is_active.is_(True),
        )
        .order_by(StudentBed.unit_id.asc(), StudentBed.bed_label.asc(), StudentBed.id.asc())
        .limit(MAX_BEDS + 1)
        .all()
    )
    if len(rows) > MAX_BEDS:
        raise HTTPException(status_code=422, detail="Too many student-housing beds.")
    response.headers["Cache-Control"] = "no-store"
    return [_bed_out(row) for row in rows]


@router.post(
    "/{property_id}/student-housing/beds",
    response_model=StudentBedOut,
    status_code=status.HTTP_201_CREATED,
)
def create_student_bed(
    property_id: int,
    payload: StudentBedCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    prop = _student_property(db, current_user, property_id)
    _require_write(current_user)
    _active_unit(db, prop.id, payload.unit_id)
    row = StudentBed(
        organization_id=prop.organization_id,
        property_id=prop.id,
        unit_id=payload.unit_id,
        bed_label=payload.bed_label.strip(),
        created_by_id=current_user.id,
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Bed label already exists for this unit.")
    db.refresh(row)
    log_action(
        db,
        current_user,
        entity_type="property",
        entity_id=prop.id,
        action="student_bed_created",
        new_value={"bed_id": row.id, "unit_id": row.unit_id},
    )
    return _bed_out(row)


@router.delete(
    "/{property_id}/student-housing/beds/{bed_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def deactivate_student_bed(
    property_id: int,
    bed_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    prop = _student_property(db, current_user, property_id)
    _require_write(current_user)
    row = (
        db.query(StudentBed)
        .filter(
            StudentBed.id == bed_id,
            StudentBed.organization_id == prop.organization_id,
            StudentBed.property_id == prop.id,
            StudentBed.is_active.is_(True),
        )
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Bed not found.")
    row.is_active = False
    db.commit()
    log_action(
        db,
        current_user,
        entity_type="property",
        entity_id=prop.id,
        action="student_bed_deactivated",
        new_value={"bed_id": row.id, "unit_id": row.unit_id},
    )
