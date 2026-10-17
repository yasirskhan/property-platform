"""Encrypted rental questionnaire: tenant/staff scope, ciphertext and audit-only metadata."""
from __future__ import annotations

from decimal import Decimal
import json

import pytest
from cryptography.fernet import Fernet
from fastapi import HTTPException, Response
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from pydantic import ValidationError

import init_db  # noqa: F401
from app.core.config import settings
from app.core.database import Base
from app.models.application import ApplicationStatus, LeaseApplication
from app.models.application_private_details import ApplicationPrivateDetails
from app.models.audit_log import AuditLog
from app.models.property import Property, PropertyAssignment
from app.models.user import Organization, User, UserRole
from app.routers import rental_applications as api
from app.schemas.application_private_details import PrivateApplicationIn
from app.services.entity_notes import resolve_note_target


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _seed(db):
    org1, org2 = Organization(name="Encrypted Apps One", slug="enc-apps-one"), Organization(name="Encrypted Apps Two", slug="enc-apps-two")
    db.add_all([org1, org2]); db.flush()
    users = []
    for org, role, name in (
        (org1, UserRole.ADMIN, "Admin"), (org1, UserRole.MANAGER, "Manager"),
        (org1, UserRole.APPLICANT, "Applicant"), (org1, UserRole.APPLICANT, "Other"),
        (org2, UserRole.ADMIN, "ForeignAdmin"), (org2, UserRole.APPLICANT, "ForeignApplicant"),
    ):
        user = User(organization_id=org.id, role=role, first_name=name, last_name="Private",
                    email=f"{name.lower()}@private-tests.example", hashed_password="x", is_active=True)
        db.add(user); db.flush(); users.append(user)
    prop1 = Property(organization_id=org1.id, name="Assigned",
                     address_line1="100 Local St", city="Cleveland", state="OH",
                     zip_code="44113", country="USA", is_active=True)
    prop2 = Property(organization_id=org1.id, name="Unassigned",
                     address_line1="200 Local St", city="Cleveland", state="OH",
                     zip_code="44113", country="USA", is_active=True)
    prop3 = Property(organization_id=org2.id, name="Foreign",
                     address_line1="300 Remote St", city="Cleveland", state="OH",
                     zip_code="44113", country="USA", is_active=True)
    db.add_all([prop1, prop2, prop3]); db.flush()
    db.add(PropertyAssignment(property_id=prop1.id, user_id=users[1].id,
                              role=UserRole.MANAGER, is_active=True))
    first = LeaseApplication(property_id=prop1.id, applicant_user_id=users[2].id,
                             submitted_by_id=users[2].id, status=ApplicationStatus.DRAFT)
    second = LeaseApplication(property_id=prop2.id, applicant_user_id=users[2].id,
                              submitted_by_id=users[2].id, status=ApplicationStatus.DRAFT)
    foreign = LeaseApplication(property_id=prop3.id, applicant_user_id=users[5].id,
                               submitted_by_id=users[5].id, status=ApplicationStatus.DRAFT)
    db.add_all([first, second, foreign]); db.commit()
    return (*users, first, second, foreign)


def _payload(**changes):
    values = dict(
        current_address=dict(address_line1="42 Private Way", city="Cleveland",
                             state="OH", postal_code="44113", country="USA"),
        previous_addresses=[dict(address_line1="88 Old Address", city="Akron",
                                 state="OH", postal_code="44301", country="USA")],
        employer_name="Private Employer", employment_title="Designer",
        gross_monthly_income=Decimal("4567.89"),
    )
    values.update(changes)
    return PrivateApplicationIn(**values)


@pytest.fixture
def key(monkeypatch):
    secret = Fernet.generate_key().decode()
    monkeypatch.setattr(settings, "APPLICATION_ENCRYPTION_KEY", secret)
    monkeypatch.setattr(api, "permission_allows_user", lambda *a, **kw: True)
    return secret


def test_questionnaire_ciphertext_and_allowed_read_permissions(key):
    db, engine = _session()
    try:
        admin, manager, applicant, another, foreign_admin, foreign_applicant, own, unassigned, foreign = _seed(db)
        resp = Response()
        saved = api.save_private_application_details(own.id, _payload(), resp, db=db, current_user=applicant)
        assert resp.headers["cache-control"] == "no-store"
        assert saved.configured and saved.details.current_address.address_line1 == "42 Private Way"
        row = db.query(ApplicationPrivateDetails).one()
        assert row.organization_id == applicant.organization_id
        assert row.application_id == own.id
        for sensitive in ("42 Private Way", "88 Old Address", "4567.89", "Private Employer"):
            assert sensitive not in row.encrypted_payload
        decoded = json.loads(Fernet(key.encode()).decrypt(row.encrypted_payload.encode()))
        assert decoded["current_address"]["address_line1"] == "42 Private Way"
        assert api.get_private_application_details(own.id, Response(), db=db, current_user=admin).configured
        assert api.get_private_application_details(own.id, Response(), db=db, current_user=manager).details.employer_name == "Private Employer"
        audit = db.query(AuditLog).filter_by(entity_type="application_private_details").all()
        assert len(audit) == 1
        for item in audit:
            assert "Private Employer" not in (item.new_value or "")
            assert "42 Private Way" not in (item.new_value or "")
        assert db.query(ApplicationPrivateDetails).count() == 1
    finally:
        db.close(); engine.dispose()


def test_subject_org_manager_and_role_isolation(key):
    db, engine = _session()
    try:
        admin, manager, applicant, another, foreign_admin, foreign_applicant, own, unassigned, foreign = _seed(db)
        api.save_private_application_details(own.id, _payload(), Response(), db=db, current_user=applicant)
        for actor in (another, foreign_admin, foreign_applicant):
            with pytest.raises(HTTPException) as exc:
                api.get_private_application_details(own.id, Response(), db=db, current_user=actor)
            assert exc.value.status_code == 404
        with pytest.raises(HTTPException) as exc:
            api.get_private_application_details(unassigned.id, Response(), db=db, current_user=manager)
        assert exc.value.status_code == 404
        with pytest.raises(HTTPException) as exc:
            api.save_private_application_details(own.id, _payload(), Response(), db=db, current_user=manager)
        assert exc.value.status_code == 403
        with pytest.raises(HTTPException) as exc:
            api.save_private_application_details(foreign.id, _payload(), Response(), db=db, current_user=applicant)
        assert exc.value.status_code == 404
        applicant.is_active = False; db.commit()
        with pytest.raises(HTTPException) as exc:
            api.get_private_application_details(own.id, Response(), db=db, current_user=applicant)
        assert exc.value.status_code == 403
    finally:
        db.close(); engine.dispose()


def test_unconfigured_key_and_tampered_ciphertext_fail_closed(monkeypatch, key):
    db, engine = _session()
    try:
        admin, manager, applicant, another, foreign_admin, foreign_applicant, own, unassigned, foreign = _seed(db)
        monkeypatch.setattr(settings, "APPLICATION_ENCRYPTION_KEY", "")
        for action in (
            lambda: api.get_private_application_details(own.id, Response(), db=db, current_user=applicant),
            lambda: api.save_private_application_details(own.id, _payload(), Response(), db=db, current_user=applicant),
        ):
            with pytest.raises(HTTPException) as exc:
                action()
            assert exc.value.status_code == 503
        assert db.query(ApplicationPrivateDetails).count() == 0
        monkeypatch.setattr(settings, "APPLICATION_ENCRYPTION_KEY", key)
        api.save_private_application_details(own.id, _payload(), Response(), db=db, current_user=applicant)
        record = db.query(ApplicationPrivateDetails).one()
        record.encrypted_payload = "invalid-base64-ciphertext"
        db.commit()
        with pytest.raises(HTTPException) as exc:
            api.get_private_application_details(own.id, Response(), db=db, current_user=admin)
        assert exc.value.status_code == 503
    finally:
        db.close(); engine.dispose()


def test_submitted_draft_locked_and_no_sensitive_fields_in_schema(key):
    db, engine = _session()
    try:
        admin, manager, applicant, another, foreign_admin, foreign_applicant, own, unassigned, foreign = _seed(db)
        payload = _payload()
        api.save_private_application_details(own.id, payload, Response(), db=db, current_user=applicant)
        own.status = ApplicationStatus.PENDING_PAYMENT; db.commit()
        with pytest.raises(HTTPException) as exc:
            api.save_private_application_details(own.id, payload, Response(), db=db, current_user=applicant)
        assert exc.value.status_code == 403
        assert api.get_private_application_details(own.id, Response(), db=db, current_user=applicant).details.gross_monthly_income == Decimal("4567.89")
        for forbidden in ("applicant_ssn", "applicant_dob", "bank_account", "screening_result", "ssn", "tin"):
            with pytest.raises(ValidationError):
                PrivateApplicationIn.model_validate({
                    **payload.model_dump(mode="json"), forbidden: "SECRET-1234",
                })
        with pytest.raises(ValidationError):
            PrivateApplicationIn.model_validate({
                **payload.model_dump(mode="json"),
                "previous_addresses": [payload.current_address.model_dump()] * 4,
            })
    finally:
        db.close(); engine.dispose()


def test_private_table_denied_in_generic_notes_and_attachments(key):
    db, engine = _session()
    try:
        admin, manager, applicant, another, foreign_admin, foreign_applicant, own, unassigned, foreign = _seed(db)
        api.save_private_application_details(own.id, _payload(), Response(), db=db, current_user=applicant)
        with pytest.raises(HTTPException) as exc:
            resolve_note_target(db, current_user=admin, entity_type="application_private_details", entity_id=1)
        assert exc.value.status_code == 404
    finally:
        db.close(); engine.dispose()


def test_authorization_revoked_on_menu_change(key, monkeypatch):
    db, engine = _session()
    try:
        admin, manager, applicant, another, foreign_admin, foreign_applicant, own, unassigned, foreign = _seed(db)
        api.save_private_application_details(own.id, _payload(), Response(), db=db, current_user=applicant)
        monkeypatch.setattr(api, "permission_allows_user", lambda *a, **kw: False)
        with pytest.raises(HTTPException) as exc:
            api.get_private_application_details(own.id, Response(), db=db, current_user=admin)
        assert exc.value.status_code == 403
        assert api.get_private_application_details(own.id, Response(), db=db, current_user=applicant).configured
    finally:
        db.close(); engine.dispose()
