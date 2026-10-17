"""Phase 4.10 student-housing workflows.

Academic cycles, bed inventory, by-the-bed leases and guarantor tracking remain
explicitly scoped. Student-bed leases use the existing central Lease lifecycle.
Guarantor records track staff workflow only and do not establish legal liability.
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.audit import log_action
from app.core.database import get_db
from app.models.lease import Lease, LeaseStatus
from app.models.property import (
    Property,
    PropertyAssignment,
    StudentAcademicCycle,
    StudentBed,
    StudentGuarantor,
    Unit,
)
from app.models.user import User, UserRole
from app.routers.auth import get_current_user
from app.routers.leases import _find_occupancy_conflict
from app.schemas.student_housing import (
    AcademicCycleCreate,
    AcademicCycleOut,
    StudentBedCreate,
    StudentBedLeaseCreate,
    StudentBedLeaseOut,
    StudentBedOut,
    StudentGuarantorCreate,
    StudentGuarantorOut,
    StudentHousingContextOut,
)
from app.services.customer_features import resolve_customer_features
from app.services.menu_resolver import permission_allows_user


router = APIRouter(prefix="/api/properties", tags=["Student housing"])
FEATURE_KEY = "release.properties.student_housing"
MAX_CYCLES = 100
MAX_BEDS = 1000
MAX_BED_LEASES = 1000
MAX_GUARANTORS = 1000
OPEN_LEASE_STATUSES = (
    LeaseStatus.DRAFT,
    LeaseStatus.PENDING_SIGNATURE,
    LeaseStatus.ACTIVE,
)
GUARANTOR_DRAFT = "DRAFT"
GUARANTOR_REQUESTED = "REQUESTED"
GUARANTOR_RECEIVED = "DOCUMENT_RECEIVED"
GUARANTOR_CANCELLED = "CANCELLED"


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


def _active_bed(
    db: Session,
    *,
    organization_id: int,
    property_id: int,
    bed_id: int,
) -> StudentBed:
    row = (
        db.query(StudentBed)
        .filter(
            StudentBed.id == bed_id,
            StudentBed.organization_id == organization_id,
            StudentBed.property_id == property_id,
            StudentBed.is_active.is_(True),
        )
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Student bed not found.")
    _active_unit(db, property_id, row.unit_id)
    return row


def _active_cycle(
    db: Session,
    *,
    organization_id: int,
    property_id: int,
    cycle_id: int,
) -> StudentAcademicCycle:
    row = (
        db.query(StudentAcademicCycle)
        .filter(
            StudentAcademicCycle.id == cycle_id,
            StudentAcademicCycle.organization_id == organization_id,
            StudentAcademicCycle.property_id == property_id,
            StudentAcademicCycle.is_active.is_(True),
        )
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Academic cycle not found.")
    return row


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


def _student_lease(
    db: Session,
    *,
    organization_id: int,
    property_id: int,
    lease_id: int,
) -> Lease:
    row = (
        db.query(Lease)
        .join(Unit, Unit.id == Lease.unit_id)
        .filter(
            Lease.id == lease_id,
            Lease.student_bed_id.isnot(None),
            Unit.property_id == property_id,
        )
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Student bed lease not found.")
    prop = db.get(Property, property_id)
    if prop is None or prop.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Student bed lease not found.")
    return row


def _bed_lease_out(db: Session, lease: Lease) -> dict[str, object]:
    bed = db.get(StudentBed, lease.student_bed_id)
    cycle = db.get(StudentAcademicCycle, lease.student_academic_cycle_id)
    tenant = db.get(User, lease.tenant_id)
    if bed is None or cycle is None or tenant is None:
        raise HTTPException(
            status_code=409,
            detail="Student bed lease source references are incomplete.",
        )
    return {
        "id": lease.id,
        "property_id": bed.property_id,
        "unit_id": lease.unit_id,
        "bed_id": bed.id,
        "bed_label": bed.bed_label,
        "tenant_id": tenant.id,
        "tenant_name": f"{tenant.first_name} {tenant.last_name}".strip(),
        "tenant_email": tenant.email,
        "academic_cycle_id": cycle.id,
        "academic_cycle_name": cycle.name,
        "start_date": lease.start_date,
        "end_date": lease.end_date,
        "monthly_rent": lease.monthly_rent,
        "security_deposit": lease.security_deposit,
        "due_day": lease.due_day,
        "status": lease.status.value if hasattr(lease.status, "value") else str(lease.status),
        "signed_by_tenant": bool(lease.signed_by_tenant),
        "signed_by_manager": bool(lease.signed_by_manager),
        "created_at": lease.created_at,
    }


def _guarantor_out(row: StudentGuarantor) -> dict[str, object]:
    return {
        "id": row.id,
        "property_id": row.property_id,
        "lease_id": row.lease_id,
        "full_name": row.full_name,
        "email": row.email,
        "phone": row.phone,
        "relationship_to_tenant": row.relationship_to_tenant,
        "status": row.status,
        "requested_at": row.requested_at,
        "received_at": row.received_at,
        "cancelled_at": row.cancelled_at,
        "created_at": row.created_at,
    }


def _guarantor(
    db: Session,
    *,
    organization_id: int,
    property_id: int,
    guarantor_id: int,
) -> StudentGuarantor:
    row = (
        db.query(StudentGuarantor)
        .filter(
            StudentGuarantor.id == guarantor_id,
            StudentGuarantor.organization_id == organization_id,
            StudentGuarantor.property_id == property_id,
        )
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Guarantor workflow record not found.")
    return row


@router.get(
    "/{property_id}/student-housing/context",
    response_model=StudentHousingContextOut,
)
def get_student_housing_context(
    property_id: int,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    prop = _student_property(db, current_user, property_id)
    units = (
        db.query(Unit)
        .filter(
            Unit.property_id == prop.id,
            Unit.is_active.is_(True),
            Unit.deleted_at.is_(None),
        )
        .order_by(Unit.unit_number.asc(), Unit.id.asc())
        .limit(MAX_BEDS + 1)
        .all()
    )
    if len(units) > MAX_BEDS:
        raise HTTPException(status_code=422, detail="Too many units for Student Housing.")

    tenants = []
    if current_user.role in {UserRole.ADMIN, UserRole.OWNER}:
        tenant_rows = (
            db.query(User)
            .filter(
                User.organization_id == prop.organization_id,
                User.role == UserRole.TENANT,
                User.is_active.is_(True),
                User.deleted_at.is_(None),
            )
            .order_by(User.last_name.asc(), User.first_name.asc(), User.id.asc())
            .limit(1001)
            .all()
        )
        if len(tenant_rows) > 1000:
            raise HTTPException(status_code=422, detail="Too many tenants for Student Housing.")
        tenants = [
            {
                "id": row.id,
                "name": f"{row.first_name} {row.last_name}".strip(),
                "email": row.email,
            }
            for row in tenant_rows
        ]

    response.headers["Cache-Control"] = "no-store"
    return {
        "units": [
            {"id": row.id, "unit_number": row.unit_number}
            for row in units
        ],
        "tenants": tenants,
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
    row = _active_cycle(
        db,
        organization_id=prop.organization_id,
        property_id=prop.id,
        cycle_id=cycle_id,
    )
    linked = (
        db.query(Lease.id)
        .filter(
            Lease.student_academic_cycle_id == row.id,
            Lease.status.in_(OPEN_LEASE_STATUSES),
        )
        .first()
    )
    if linked is not None:
        raise HTTPException(
            status_code=409,
            detail="Academic cycle has an open student bed lease and cannot be deactivated.",
        )
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
    row = _active_bed(
        db,
        organization_id=prop.organization_id,
        property_id=prop.id,
        bed_id=bed_id,
    )
    linked = (
        db.query(Lease.id)
        .filter(
            Lease.student_bed_id == row.id,
            Lease.status.in_(OPEN_LEASE_STATUSES),
        )
        .first()
    )
    if linked is not None:
        raise HTTPException(
            status_code=409,
            detail="Bed has an open student lease and cannot be deactivated.",
        )
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


@router.get(
    "/{property_id}/student-housing/bed-leases",
    response_model=list[StudentBedLeaseOut],
)
def list_student_bed_leases(
    property_id: int,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    prop = _student_property(db, current_user, property_id)
    rows = (
        db.query(Lease)
        .join(Unit, Unit.id == Lease.unit_id)
        .filter(
            Unit.property_id == prop.id,
            Lease.student_bed_id.isnot(None),
        )
        .order_by(Lease.created_at.desc(), Lease.id.desc())
        .limit(MAX_BED_LEASES + 1)
        .all()
    )
    if len(rows) > MAX_BED_LEASES:
        raise HTTPException(status_code=422, detail="Too many student bed leases.")
    response.headers["Cache-Control"] = "no-store"
    return [_bed_lease_out(db, row) for row in rows]


@router.post(
    "/{property_id}/student-housing/bed-leases",
    response_model=StudentBedLeaseOut,
    status_code=status.HTTP_201_CREATED,
)
def create_student_bed_lease(
    property_id: int,
    payload: StudentBedLeaseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    prop = _student_property(db, current_user, property_id)
    _require_write(current_user)
    bed = _active_bed(
        db,
        organization_id=prop.organization_id,
        property_id=prop.id,
        bed_id=payload.bed_id,
    )
    cycle = _active_cycle(
        db,
        organization_id=prop.organization_id,
        property_id=prop.id,
        cycle_id=payload.academic_cycle_id,
    )
    tenant = (
        db.query(User)
        .filter(
            User.id == payload.tenant_id,
            User.organization_id == prop.organization_id,
            User.role == UserRole.TENANT,
            User.is_active.is_(True),
            User.deleted_at.is_(None),
        )
        .first()
    )
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found.")
    if payload.start_date < cycle.start_date or payload.end_date > cycle.end_date:
        raise HTTPException(
            status_code=422,
            detail="Student bed lease dates must stay within the selected academic cycle.",
        )

    conflict = _find_occupancy_conflict(
        db,
        unit_id=bed.unit_id,
        student_bed_id=bed.id,
    )
    if conflict is not None:
        raise HTTPException(
            status_code=409,
            detail="Bed or unit already has a conflicting open lease.",
        )

    lease = Lease(
        unit_id=bed.unit_id,
        tenant_id=tenant.id,
        student_bed_id=bed.id,
        student_academic_cycle_id=cycle.id,
        start_date=payload.start_date,
        end_date=payload.end_date,
        monthly_rent=payload.monthly_rent,
        security_deposit=payload.security_deposit,
        due_day=payload.due_day,
        status=LeaseStatus.DRAFT,
        notes=payload.notes,
    )
    db.add(lease)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Student bed lease could not be created because its source changed.",
        )
    db.refresh(lease)
    log_action(
        db,
        current_user,
        entity_type="lease",
        entity_id=lease.id,
        action="student_bed_lease_created",
        new_value={
            "property_id": prop.id,
            "bed_id": bed.id,
            "academic_cycle_id": cycle.id,
        },
    )
    return _bed_lease_out(db, lease)


@router.get(
    "/{property_id}/student-housing/guarantors",
    response_model=list[StudentGuarantorOut],
)
def list_student_guarantors(
    property_id: int,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    prop = _student_property(db, current_user, property_id)
    rows = (
        db.query(StudentGuarantor)
        .filter(
            StudentGuarantor.organization_id == prop.organization_id,
            StudentGuarantor.property_id == prop.id,
        )
        .order_by(StudentGuarantor.created_at.desc(), StudentGuarantor.id.desc())
        .limit(MAX_GUARANTORS + 1)
        .all()
    )
    if len(rows) > MAX_GUARANTORS:
        raise HTTPException(status_code=422, detail="Too many guarantor workflow records.")
    response.headers["Cache-Control"] = "no-store"
    return [_guarantor_out(row) for row in rows]


@router.post(
    "/{property_id}/student-housing/bed-leases/{lease_id}/guarantors",
    response_model=StudentGuarantorOut,
    status_code=status.HTTP_201_CREATED,
)
def create_student_guarantor(
    property_id: int,
    lease_id: int,
    payload: StudentGuarantorCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    prop = _student_property(db, current_user, property_id)
    _require_write(current_user)
    _student_lease(
        db,
        organization_id=prop.organization_id,
        property_id=prop.id,
        lease_id=lease_id,
    )
    normalized_email = str(payload.email).strip().lower()
    duplicate = (
        db.query(StudentGuarantor.id)
        .filter(
            StudentGuarantor.lease_id == lease_id,
            func.lower(StudentGuarantor.email) == normalized_email,
        )
        .first()
    )
    if duplicate is not None:
        raise HTTPException(
            status_code=409,
            detail="This guarantor email is already tracked for the student lease.",
        )
    row = StudentGuarantor(
        organization_id=prop.organization_id,
        property_id=prop.id,
        lease_id=lease_id,
        full_name=payload.full_name.strip(),
        email=normalized_email,
        phone=payload.phone.strip() if payload.phone else None,
        relationship_to_tenant=(
            payload.relationship_to_tenant.strip()
            if payload.relationship_to_tenant
            else None
        ),
        status=GUARANTOR_DRAFT,
        created_by_id=current_user.id,
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Guarantor workflow record already exists.")
    db.refresh(row)
    log_action(
        db,
        current_user,
        entity_type="lease",
        entity_id=lease_id,
        action="student_guarantor_created",
        new_value={"guarantor_id": row.id, "status": row.status},
    )
    return _guarantor_out(row)


@router.post(
    "/{property_id}/student-housing/guarantors/{guarantor_id}/mark-requested",
    response_model=StudentGuarantorOut,
)
def mark_guarantor_requested(
    property_id: int,
    guarantor_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    prop = _student_property(db, current_user, property_id)
    _require_write(current_user)
    row = _guarantor(
        db,
        organization_id=prop.organization_id,
        property_id=prop.id,
        guarantor_id=guarantor_id,
    )
    if row.status == GUARANTOR_CANCELLED:
        raise HTTPException(status_code=409, detail="Cancelled guarantor workflow cannot be requested.")
    if row.status == GUARANTOR_DRAFT:
        row.status = GUARANTOR_REQUESTED
        row.requested_at = datetime.utcnow()
        db.commit()
        db.refresh(row)
        log_action(
            db,
            current_user,
            entity_type="lease",
            entity_id=row.lease_id,
            action="student_guarantor_marked_requested",
            new_value={"guarantor_id": row.id, "status": row.status},
        )
    return _guarantor_out(row)


@router.post(
    "/{property_id}/student-housing/guarantors/{guarantor_id}/record-received",
    response_model=StudentGuarantorOut,
)
def record_guarantor_document_received(
    property_id: int,
    guarantor_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    prop = _student_property(db, current_user, property_id)
    _require_write(current_user)
    row = _guarantor(
        db,
        organization_id=prop.organization_id,
        property_id=prop.id,
        guarantor_id=guarantor_id,
    )
    if row.status == GUARANTOR_DRAFT:
        raise HTTPException(
            status_code=409,
            detail="Mark the guarantor request as externally requested before recording receipt.",
        )
    if row.status == GUARANTOR_CANCELLED:
        raise HTTPException(status_code=409, detail="Cancelled guarantor workflow cannot receive documents.")
    if row.status != GUARANTOR_RECEIVED:
        row.status = GUARANTOR_RECEIVED
        row.received_at = datetime.utcnow()
        db.commit()
        db.refresh(row)
        log_action(
            db,
            current_user,
            entity_type="lease",
            entity_id=row.lease_id,
            action="student_guarantor_document_received",
            new_value={"guarantor_id": row.id, "status": row.status},
        )
    return _guarantor_out(row)


@router.post(
    "/{property_id}/student-housing/guarantors/{guarantor_id}/cancel",
    response_model=StudentGuarantorOut,
)
def cancel_guarantor_workflow(
    property_id: int,
    guarantor_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    prop = _student_property(db, current_user, property_id)
    _require_write(current_user)
    row = _guarantor(
        db,
        organization_id=prop.organization_id,
        property_id=prop.id,
        guarantor_id=guarantor_id,
    )
    if row.status == GUARANTOR_RECEIVED:
        raise HTTPException(
            status_code=409,
            detail="Received guarantor documents are retained as workflow history.",
        )
    if row.status != GUARANTOR_CANCELLED:
        row.status = GUARANTOR_CANCELLED
        row.cancelled_at = datetime.utcnow()
        db.commit()
        db.refresh(row)
        log_action(
            db,
            current_user,
            entity_type="lease",
            entity_id=row.lease_id,
            action="student_guarantor_cancelled",
            new_value={"guarantor_id": row.id, "status": row.status},
        )
    return _guarantor_out(row)
