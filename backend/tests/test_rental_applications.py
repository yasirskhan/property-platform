"""Application draft endpoints must not expose or write legacy sensitive fields."""
from __future__ import annotations

from datetime import date
import pytest
from fastapi import HTTPException, Response
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import init_db  # noqa: F401
from app.core.database import Base
from app.models.application import ApplicationPayment, ApplicationStatus, LeaseApplication
from app.models.audit_log import AuditLog
from app.models.property import Property, PropertyAssignment, Unit
from app.models.user import Organization, User, UserRole
from app.routers import rental_applications as api
from app.schemas.rental_application import RentalApplicationCreate, RentalApplicationEdit


def _db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _seed(db):
    o1, o2 = Organization(name="Applications One", slug="apps-one"), Organization(name="Applications Two", slug="apps-two")
    db.add_all([o1, o2]); db.flush()
    users = []
    for org, role, name in (
        (o1, UserRole.ADMIN, "Admin"), (o1, UserRole.MANAGER, "Manager"),
        (o1, UserRole.APPLICANT, "Applicant"), (o1, UserRole.APPLICANT, "ApplicantTwo"),
        (o2, UserRole.ADMIN, "OtherAdmin"), (o2, UserRole.APPLICANT, "ForeignApplicant"),
        (o1, UserRole.TENANT, "Tenant"),
    ):
        row = User(organization_id=org.id, first_name=name, last_name="Apps",
                   email=f"{name.lower()}@apps-test.example", hashed_password="x",
                   role=role, is_active=True)
        db.add(row); db.flush(); users.append(row)
    first = Property(organization_id=o1.id, name="First", address_line1="100 First St",
                     city="Cleveland", state="OH", zip_code="44113", country="USA", is_active=True)
    second = Property(organization_id=o1.id, name="Unassigned", address_line1="200 Second St",
                      city="Cleveland", state="OH", zip_code="44113", country="USA", is_active=True)
    other = Property(organization_id=o2.id, name="Foreign", address_line1="300 Foreign St",
                     city="Cleveland", state="OH", zip_code="44113", country="USA", is_active=True)
    db.add_all([first, second, other]); db.flush()
    unit = Unit(property_id=first.id, unit_number="2A", is_active=True, is_available=True)
    foreign_unit = Unit(property_id=other.id, unit_number="9Z", is_active=True)
    db.add_all([unit, foreign_unit])
    db.add(PropertyAssignment(property_id=first.id, user_id=users[1].id,
                              role=UserRole.MANAGER, is_active=True))
    db.commit()
    return (*users, first, second, other, unit, foreign_unit)


def _payload(property_id, unit_id=None):
    return RentalApplicationCreate(
        property_id=property_id, unit_id=unit_id, applicant_name="Applicant One",
        applicant_email="applicant@example.com", applicant_phone="555-0100",
        move_in_date=date(2027, 1, 1), lease_term_months=12,
        occupant_names=["Housemate"], pet_description="One cat",
    )


def test_applicant_creates_edits_submits_safe_draft_without_payment_or_ssn(monkeypatch):
    db, engine = _db()
    try:
        admin, manager, applicant, another, *_tail = _seed(db)
        first, _second, _other, unit, _foreign = _tail[-5:]
        monkeypatch.setattr(api, "permission_allows_user", lambda *a, **kw: True)
        made = api.create_rental_application(_payload(first.id, unit.id), db=db, current_user=applicant)
        assert made.status == "draft" and made.applicant_name == "Applicant One"
        assert "applicant_ssn" not in made.model_dump()
        assert "applicant_dob" not in made.model_dump()
        assert "screening_result" not in made.model_dump()
        record = db.query(LeaseApplication).one()
        assert record.applicant_ssn is None and record.applicant_dob is None
        assert record.screening_result is None and record.fee_amount is None
        assert db.query(ApplicationPayment).count() == 0
        updated = api.edit_rental_application(made.id, RentalApplicationEdit(
            applicant_name="Updated Person", applicant_email="updated@example.com",
            occupant_names=[], pet_description=None,
        ), db=db, current_user=applicant)
        assert updated.applicant_name == "Updated Person"
        submitted = api.submit_rental_application(made.id, db=db, current_user=applicant)
        assert submitted.status == "pending_payment"
        assert db.query(ApplicationPayment).count() == 0
        assert db.query(LeaseApplication).one().status == ApplicationStatus.PENDING_PAYMENT
        with pytest.raises(HTTPException) as exc:
            api.edit_rental_application(made.id, RentalApplicationEdit(
                applicant_name="Not allowed", applicant_email="no@example.com",
            ), db=db, current_user=applicant)
        assert exc.value.status_code == 409
        assert [a.action for a in db.query(AuditLog).filter_by(entity_type="lease_application").all()] == [
            "created", "updated", "submitted",
        ]
        for audit in db.query(AuditLog).filter_by(entity_type="lease_application").all():
            assert "updated@example.com" not in (audit.new_value or "")
            assert "555-0100" not in (audit.new_value or "")
    finally:
        db.close(); engine.dispose()


def test_cross_org_and_applicant_isolation_before_data_read(monkeypatch):
    db, engine = _db()
    try:
        admin, manager, applicant, another, other_admin, foreign_applicant, tenant, first, second, other, unit, foreign_unit = _seed(db)
        monkeypatch.setattr(api, "permission_allows_user", lambda *a, **kw: True)
        own = api.create_rental_application(_payload(first.id), db=db, current_user=applicant)
        for actor in (another, foreign_applicant):
            with pytest.raises(HTTPException) as exc:
                api.get_rental_application(own.id, Response(), db=db, current_user=actor)
            assert exc.value.status_code == 404
        with pytest.raises(HTTPException) as exc:
            api.create_rental_application(_payload(other.id), db=db, current_user=applicant)
        assert exc.value.status_code == 404
        with pytest.raises(HTTPException) as exc:
            api.create_rental_application(_payload(first.id, foreign_unit.id), db=db, current_user=applicant)
        assert exc.value.status_code == 404
        with pytest.raises(HTTPException) as exc:
            api.get_rental_application(own.id, Response(), db=db, current_user=other_admin)
        assert exc.value.status_code == 404
        assert [r.id for r in api.list_rental_applications(Response(), db=db, current_user=applicant)] == [own.id]
        assert api.list_rental_applications(Response(), db=db, current_user=foreign_applicant) == []
        with pytest.raises(HTTPException) as exc:
            api.create_rental_application(_payload(first.id), db=db, current_user=tenant)
        assert exc.value.status_code == 403
        with pytest.raises(HTTPException) as exc:
            api.create_rental_application(_payload(first.id), db=db, current_user=applicant)
        assert exc.value.status_code == 409
    finally:
        db.close(); engine.dispose()


def test_staff_scopes_and_live_permission_revocation(monkeypatch):
    db, engine = _db()
    try:
        admin, manager, applicant, _another, other_admin, _foreign_applicant, tenant, first, second, other, unit, _foreign_unit = _seed(db)
        monkeypatch.setattr(api, "permission_allows_user", lambda *a, **kw: True)
        first_app = api.create_rental_application(_payload(first.id), db=db, current_user=applicant)
        second_app = api.create_rental_application(_payload(second.id), db=db, current_user=applicant)
        assert len(api.list_rental_applications(Response(), db=db, current_user=admin)) == 2
        assert [x.id for x in api.list_rental_applications(Response(), db=db, current_user=manager)] == [first_app.id]
        with pytest.raises(HTTPException) as exc:
            api.get_rental_application(second_app.id, Response(), db=db, current_user=manager)
        assert exc.value.status_code == 404
        with pytest.raises(HTTPException) as exc:
            api.list_rental_applications(Response(), property_id=second.id, db=db, current_user=manager)
        assert exc.value.status_code == 404
        with pytest.raises(HTTPException) as exc:
            api.list_rental_applications(Response(), db=db, current_user=tenant)
        assert exc.value.status_code == 403
        monkeypatch.setattr(api, "permission_allows_user", lambda *a, **kw: False)
        for call in (
            lambda: api.list_rental_applications(Response(), db=db, current_user=admin),
            lambda: api.get_rental_application(first_app.id, Response(), db=db, current_user=manager),
        ):
            with pytest.raises(HTTPException) as exc:
                call()
            assert exc.value.status_code == 403
        monkeypatch.setattr(api, "permission_allows_user", lambda *a, **kw: True)
        admin.is_active = False; db.commit()
        with pytest.raises(HTTPException) as exc:
            api.list_rental_applications(Response(), db=db, current_user=admin)
        assert exc.value.status_code == 403
    finally:
        db.close(); engine.dispose()


def test_explicit_schema_refuses_ssn_payment_screening_and_extra_fields():
    from pydantic import ValidationError
    for field, value in (
        ("applicant_ssn", "123-45-6789"), ("applicant_dob", "2000-01-01"),
        ("screening_result", "secret"), ("fee_amount", "0"),
        ("paid", True), ("owner_id", 42),
    ):
        values = dict(property_id=1, applicant_name="Person", applicant_email="person@example.com", **{field: value})
        with pytest.raises(ValidationError):
            RentalApplicationCreate.model_validate(values)


def test_archived_property_wrong_unit_and_nonstaff_access_refused(monkeypatch):
    db, engine = _db()
    try:
        admin, manager, applicant, another, other_admin, foreign_applicant, tenant, first, second, other, unit, foreign_unit = _seed(db)
        monkeypatch.setattr(api, "permission_allows_user", lambda *a, **kw: True)
        first.is_active = False; db.commit()
        with pytest.raises(HTTPException) as exc:
            api.create_rental_application(_payload(first.id), db=db, current_user=applicant)
        assert exc.value.status_code == 404
        first.is_active = True; db.commit()
        unit.is_active = False; db.commit()
        with pytest.raises(HTTPException) as exc:
            api.create_rental_application(_payload(first.id, unit.id), db=db, current_user=applicant)
        assert exc.value.status_code == 404
        unit.is_active = True; db.commit()
        other_user = another
        other_user.is_active = False; db.commit()
        with pytest.raises(HTTPException) as exc:
            api.list_rental_applications(Response(), db=db, current_user=other_user)
        assert exc.value.status_code == 403
    finally:
        db.close(); engine.dispose()
