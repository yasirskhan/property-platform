"""Scoped applicant-authored drafts and staff read-only application queue.

This intentionally does not implement SSN collection, fees, screening,
approval or lease activation. Historical legacy sensitive columns
are neither read nor serialized.
"""
from __future__ import annotations

import json
from cryptography.fernet import Fernet, InvalidToken

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.config import settings
from app.models.application_private_details import ApplicationPrivateDetails
from app.schemas.application_private_details import PrivateApplicationIn, PrivateApplicationOut
from app.models.application import ApplicationStatus, LeaseApplication
from app.models.property import Property, PropertyAssignment, Unit
from app.models.user import User, UserRole
from app.routers.auth import get_current_user
from app.schemas.rental_application import (
    ApplicantDetails, RentalApplicationCreate, RentalApplicationEdit,
    RentalApplicationOut,
)
from app.services.audit import append_audit_log
from app.services.menu_resolver import permission_allows_user


router = APIRouter(prefix="/api/leasing/applications", tags=["Rental Applications"])
_STAFF_ROLES = {UserRole.ADMIN, UserRole.OWNER, UserRole.MANAGER}


def _user_role(user: User) -> UserRole:
    return user.role


def _require_active(user: User) -> int:
    if user.organization_id is None or not user.is_active or user.deleted_at is not None:
        raise HTTPException(status_code=403, detail="Application access required.")
    return int(user.organization_id)


def _staff_access(db: Session, user: User, *, property_id: int | None = None) -> int:
    org_id = _require_active(user)
    if user.role not in _STAFF_ROLES or not permission_allows_user(
        db, user=user, menu_key="LEASING.APPLICATIONS",
    ):
        raise HTTPException(status_code=403, detail="Application permission required.")
    if property_id is not None and user.role == UserRole.MANAGER:
        assignment = db.query(PropertyAssignment.id).filter(
            PropertyAssignment.property_id == property_id,
            PropertyAssignment.user_id == user.id,
            PropertyAssignment.is_active.is_(True),
            PropertyAssignment.deleted_at.is_(None),
        ).first()
        if assignment is None:
            raise HTTPException(status_code=404, detail="Application not found.")
    return org_id


def _property(db: Session, user: User, property_id: int, *, for_draft: bool = False) -> Property:
    org_id = _require_active(user)
    prop = db.query(Property).filter(
        Property.id == property_id, Property.organization_id == org_id,
    ).first()
    if prop is None:
        raise HTTPException(status_code=404, detail="Property not found.")
    if for_draft and (not prop.is_active or prop.deleted_at is not None):
        raise HTTPException(status_code=404, detail="Property not accepting applications.")
    return prop


def _row(db: Session, user: User, application_id: int) -> LeaseApplication:
    org_id = _require_active(user)
    row = db.query(LeaseApplication).join(
        Property, Property.id == LeaseApplication.property_id,
    ).filter(
        LeaseApplication.id == application_id,
        Property.organization_id == org_id,
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Application not found.")
    if user.role == UserRole.APPLICANT:
        if row.applicant_user_id != user.id:
            raise HTTPException(status_code=404, detail="Application not found.")
    else:
        _staff_access(db, user, property_id=row.property_id)
    return row


def _read_json_names(raw: str | None) -> list[str]:
    try:
        value = json.loads(raw or "[]")
        return [str(s)[:150] for s in value if isinstance(s, str)] if isinstance(value, list) else []
    except (ValueError, TypeError):
        return []


def _out(row: LeaseApplication) -> RentalApplicationOut:
    # Do not materialize or read applicant_ssn, applicant_dob, screening_result.
    return RentalApplicationOut(
        id=row.id, property_id=row.property_id, unit_id=row.unit_id,
        applicant_user_id=row.applicant_user_id, status=row.status.value,
        applicant_name=(_read_json_names(row.applicant_names) or ["Applicant"])[0],
        applicant_email=row.applicant_email or "",
        applicant_phone=row.applicant_phone,
        move_in_date=row.move_in_date, lease_term_months=row.lease_term_months,
        occupant_names=_read_json_names(row.occupant_names),
        pet_description=_read_pets(row.pet_details),
        created_at=row.created_at, updated_at=row.updated_at,
    )


def _read_pets(raw: str | None) -> str | None:
    try:
        value = json.loads(raw or "{}")
        return value.get("description") if isinstance(value, dict) and isinstance(value.get("description"), str) else None
    except (ValueError, TypeError):
        return None


def _fill(row: LeaseApplication, payload: ApplicantDetails) -> None:
    row.applicant_names = json.dumps([payload.applicant_name])
    row.applicant_email = str(payload.applicant_email)
    row.applicant_phone = payload.applicant_phone
    row.move_in_date = payload.move_in_date
    row.lease_term_months = payload.lease_term_months
    row.occupant_names = json.dumps(payload.occupant_names)
    row.pet_details = json.dumps({"description": payload.pet_description or ""})
    # Deliberately NEVER write existing applicant_ssn / DOB / screening / fees.


@router.get("", response_model=list[RentalApplicationOut])
def list_rental_applications(
    response: Response, property_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = _require_active(current_user)
    response.headers["Cache-Control"] = "no-store"
    query = db.query(LeaseApplication).join(
        Property, Property.id == LeaseApplication.property_id,
    ).filter(Property.organization_id == org_id)
    if current_user.role == UserRole.APPLICANT:
        query = query.filter(LeaseApplication.applicant_user_id == current_user.id)
    else:
        _staff_access(db, current_user, property_id=property_id)
        if current_user.role == UserRole.MANAGER:
            query = query.join(
                PropertyAssignment, PropertyAssignment.property_id == Property.id,
            ).filter(
                PropertyAssignment.user_id == current_user.id,
                PropertyAssignment.is_active.is_(True),
                PropertyAssignment.deleted_at.is_(None),
            )
    if property_id is not None:
        _property(db, current_user, property_id)
        query = query.filter(LeaseApplication.property_id == property_id)
    rows = query.order_by(LeaseApplication.created_at.desc(), LeaseApplication.id.desc()).limit(201).all()
    if len(rows) > 200:
        raise HTTPException(status_code=422, detail="Filter applications by property.")
    return [_out(row) for row in rows]


@router.get("/{application_id}", response_model=RentalApplicationOut)
def get_rental_application(
    application_id: int, response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    response.headers["Cache-Control"] = "no-store"
    return _out(_row(db, current_user, application_id))


@router.post("", response_model=RentalApplicationOut, status_code=201)
def create_rental_application(
    payload: RentalApplicationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = _require_active(current_user)
    if current_user.role != UserRole.APPLICANT:
        raise HTTPException(status_code=403, detail="Only applicants can start an application.")
    _property(db, current_user, payload.property_id, for_draft=True)
    if payload.unit_id is not None:
        unit = db.query(Unit).filter(
            Unit.id == payload.unit_id, Unit.property_id == payload.property_id,
            Unit.is_active.is_(True), Unit.deleted_at.is_(None),
        ).first()
        if unit is None:
            raise HTTPException(status_code=404, detail="Unit not found.")
    duplicate = db.query(LeaseApplication.id).filter(
        LeaseApplication.applicant_user_id == current_user.id,
        LeaseApplication.property_id == payload.property_id,
        LeaseApplication.status.in_([ApplicationStatus.DRAFT, ApplicationStatus.PENDING_PAYMENT]),
    ).first()
    if duplicate is not None:
        raise HTTPException(status_code=409, detail="An open application already exists for this property.")
    row = LeaseApplication(
        property_id=payload.property_id, unit_id=payload.unit_id,
        applicant_user_id=current_user.id, submitted_by_id=current_user.id,
        status=ApplicationStatus.DRAFT,
    )
    _fill(row, payload)
    db.add(row); db.flush()
    append_audit_log(
        db, user_id=current_user.id, organization_id=org_id,
        entity_type="lease_application", entity_id=row.id, action="created",
        new_value={"property_id": row.property_id, "status": "draft"},
    )
    db.commit(); db.refresh(row)
    return _out(row)


@router.put("/{application_id}", response_model=RentalApplicationOut)
def edit_rental_application(
    application_id: int, payload: RentalApplicationEdit,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = _row(db, current_user, application_id)
    if current_user.role != UserRole.APPLICANT or row.status != ApplicationStatus.DRAFT:
        raise HTTPException(status_code=409, detail="Only your own draft application can be edited.")
    _fill(row, payload); db.flush()
    append_audit_log(
        db, user_id=current_user.id, organization_id=current_user.organization_id,
        entity_type="lease_application", entity_id=row.id, action="updated",
        new_value={"status": "draft"},
    )
    db.commit(); db.refresh(row)
    return _out(row)


@router.post("/{application_id}/submit", response_model=RentalApplicationOut)
def submit_rental_application(
    application_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = _row(db, current_user, application_id)
    if current_user.role != UserRole.APPLICANT or row.status != ApplicationStatus.DRAFT:
        raise HTTPException(status_code=409, detail="Only your own draft application can be submitted.")
    row.status = ApplicationStatus.PENDING_PAYMENT
    db.flush()
    append_audit_log(
        db, user_id=current_user.id, organization_id=current_user.organization_id,
        entity_type="lease_application", entity_id=row.id, action="submitted",
        new_value={"status": "pending_payment"},
    )
    db.commit(); db.refresh(row)
    return _out(row)


def _private_fernet() -> Fernet:
    """Fail closed; private application data needs its own provisioned key."""
    secret = settings.APPLICATION_ENCRYPTION_KEY
    if not secret or secret in (settings.ENCRYPTION_KEY, settings.TAX_PROFILE_ENCRYPTION_KEY):
        raise HTTPException(status_code=503, detail="Private application encryption is not configured.")
    try:
        return Fernet(secret.encode("utf-8"))
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=503, detail="Private application encryption is unavailable.") from exc


def _private_payload(row: ApplicationPrivateDetails, key: Fernet) -> PrivateApplicationOut:
    try:
        plaintext = key.decrypt(row.encrypted_payload.encode("utf-8"))
        body = json.loads(plaintext)
        data = PrivateApplicationIn.model_validate(body)
    except (InvalidToken, TypeError, ValueError, UnicodeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=503, detail="Private application data cannot be decrypted.") from exc
    return PrivateApplicationOut(
        application_id=row.application_id, configured=True,
        details=data, updated_at=row.updated_at,
    )


@router.get("/{application_id}/private-details", response_model=PrivateApplicationOut)
def get_private_application_details(
    application_id: int, response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _row(db, current_user, application_id)  # applicant self OR scoped staff
    response.headers["Cache-Control"] = "no-store"
    key = _private_fernet()
    record = db.query(ApplicationPrivateDetails).filter(
        ApplicationPrivateDetails.application_id == application_id,
        ApplicationPrivateDetails.organization_id == current_user.organization_id,
    ).first()
    if record is None:
        return PrivateApplicationOut(application_id=application_id, configured=False)
    return _private_payload(record, key)


@router.put("/{application_id}/private-details", response_model=PrivateApplicationOut)
def save_private_application_details(
    application_id: int, payload: PrivateApplicationIn, response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    app = _row(db, current_user, application_id)
    if current_user.role != UserRole.APPLICANT or app.status != ApplicationStatus.DRAFT:
        raise HTTPException(status_code=403, detail="Only the applicant can edit their own draft.")
    response.headers["Cache-Control"] = "no-store"
    key = _private_fernet()
    ciphertext = key.encrypt(payload.model_dump_json().encode("utf-8")).decode("ascii")
    record = db.query(ApplicationPrivateDetails).filter(
        ApplicationPrivateDetails.application_id == app.id,
        ApplicationPrivateDetails.organization_id == current_user.organization_id,
    ).first()
    created = record is None
    if record is None:
        record = ApplicationPrivateDetails(
            organization_id=current_user.organization_id,
            application_id=app.id, created_by_id=current_user.id,
        )
        db.add(record)
    record.encrypted_payload = ciphertext
    record.updated_by_id = current_user.id
    db.flush()
    append_audit_log(
        db, user_id=current_user.id, organization_id=current_user.organization_id,
        entity_type="application_private_details", entity_id=record.id,
        action="created" if created else "updated",
        new_value={"application_id": app.id, "configured": True},
    )
    db.commit(); db.refresh(record)
    return _private_payload(record, key)


