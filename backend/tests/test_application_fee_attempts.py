"""Server-only fee snapshot and applicant idempotency tests."""
from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi import HTTPException, Response
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import init_db  # noqa: F401
from app.core.database import Base
from app.models.application import ApplicationPayment, ApplicationStatus, LeaseApplication
from app.models.application_fee_attempt import ApplicationFeeAttempt
from app.models.audit_log import AuditLog
from app.models.property import Property, Unit
from app.models.user import Organization, User, UserRole
from app.routers import rental_applications as api
from app.schemas.application_fee import ApplicationFeePrepareIn


def _db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _seed(db):
    org1 = Organization(name="Fee Prepare One", slug="fee-prepare-one")
    org2 = Organization(name="Fee Prepare Two", slug="fee-prepare-two")
    db.add_all([org1, org2]); db.flush()
    applicant = User(organization_id=org1.id, email="fees-applicant@example.com", first_name="First",
                     last_name="Applicant", role=UserRole.APPLICANT, is_active=True, hashed_password="x")
    other = User(organization_id=org1.id, email="fees-other@example.com", first_name="Other",
                 last_name="Applicant", role=UserRole.APPLICANT, is_active=True, hashed_password="x")
    foreign = User(organization_id=org2.id, email="fees-foreign@example.com", first_name="Foreign",
                   last_name="Applicant", role=UserRole.APPLICANT, is_active=True, hashed_password="x")
    admin = User(organization_id=org1.id, email="fees-admin@example.com", first_name="Admin",
                 last_name="One", role=UserRole.ADMIN, is_active=True, hashed_password="x")
    p1 = Property(organization_id=org1.id, name="First", address_line1="100 First",
                  city="Cleveland", state="OH", zip_code="44113", country="USA", is_active=True)
    p2 = Property(organization_id=org2.id, name="Other", address_line1="100 Other",
                  city="Cleveland", state="OH", zip_code="44113", country="USA", is_active=True)
    db.add_all([applicant, other, foreign, admin, p1, p2]); db.flush()
    unit = Unit(property_id=p1.id, unit_number="1A", application_fee=Decimal("65.50"), is_active=True)
    db.add(unit); db.flush()
    app = LeaseApplication(property_id=p1.id, unit_id=unit.id,
                           applicant_user_id=applicant.id,
                           status=ApplicationStatus.PENDING_PAYMENT)
    db.add(app); db.commit()
    return applicant, other, foreign, admin, p1, p2, unit, app


def _payload(key="same-idempotency-key-0001"):
    return ApplicationFeePrepareIn(idempotency_key=key)


def test_reservation_idempotency_fixed_price_and_no_financial_side_effect(monkeypatch):
    db, engine = _db()
    try:
        applicant, other, foreign, admin, p1, p2, unit, app = _seed(db)
        monkeypatch.setattr(api, "permission_allows_user", lambda *a, **k: True)
        attempt = api.prepare_application_fee(app.id, _payload(), db=db, current_user=applicant)
        assert attempt.amount_cents == 6550 and attempt.currency == "USD"
        assert attempt.status == "PREPARED" and attempt.checkout_available is False
        same = api.prepare_application_fee(app.id, _payload(), db=db, current_user=applicant)
        assert same.attempt_id == attempt.attempt_id
        assert db.query(ApplicationFeeAttempt).count() == 1
        assert db.query(AuditLog).filter_by(entity_type="application_fee_attempt").count() == 1
        assert db.query(ApplicationPayment).count() == 0
        db.refresh(app)
        assert app.status == ApplicationStatus.PENDING_PAYMENT and app.fee_amount is None
        with pytest.raises(HTTPException) as exc:
            api.prepare_application_fee(app.id, _payload("a-different-idempotency-key-02"),
                                        db=db, current_user=applicant)
        assert exc.value.status_code == 409
        unit.application_fee = Decimal("75.50"); db.commit()
        with pytest.raises(HTTPException) as exc:
            api.prepare_application_fee(app.id, _payload(), db=db, current_user=applicant)
        assert exc.value.status_code == 409
        assert db.query(ApplicationPayment).count() == 0
    finally:
        db.close(); engine.dispose()


def test_prepare_rejects_foreign_staff_draft_unpriced_and_zero_fee(monkeypatch):
    db, engine = _db()
    try:
        applicant, other, foreign, admin, p1, p2, unit, app = _seed(db)
        monkeypatch.setattr(api, "permission_allows_user", lambda *a, **k: True)
        for actor in (other, foreign, admin):
            with pytest.raises(HTTPException) as exc:
                api.prepare_application_fee(app.id, _payload(), db=db, current_user=actor)
            assert exc.value.status_code in (403, 404, 409)
        app.status = ApplicationStatus.DRAFT; db.commit()
        with pytest.raises(HTTPException) as exc:
            api.prepare_application_fee(app.id, _payload(), db=db, current_user=applicant)
        assert exc.value.status_code == 409
        app.status = ApplicationStatus.PENDING_PAYMENT
        unit.application_fee = None; db.commit()
        with pytest.raises(HTTPException) as exc:
            api.prepare_application_fee(app.id, _payload(), db=db, current_user=applicant)
        assert exc.value.status_code == 422
        unit.application_fee = Decimal("0"); db.commit()
        with pytest.raises(HTTPException) as exc:
            api.prepare_application_fee(app.id, _payload(), db=db, current_user=applicant)
        assert exc.value.status_code == 422
        unit.is_active = False; db.commit()
        with pytest.raises(HTTPException) as exc:
            api.prepare_application_fee(app.id, _payload(), db=db, current_user=applicant)
        assert exc.value.status_code == 404
        assert db.query(ApplicationFeeAttempt).count() == 0
    finally:
        db.close(); engine.dispose()


def test_price_is_never_client_supplied_and_attempts_are_not_generic_attachments(monkeypatch):
    from app.services.entity_notes import resolve_note_target
    db, engine = _db()
    try:
        applicant, other, foreign, admin, p1, p2, unit, app = _seed(db)
        monkeypatch.setattr(api, "permission_allows_user", lambda *a, **k: True)
        with pytest.raises(ValidationError):
            ApplicationFeePrepareIn.model_validate({"idempotency_key": "same-idempotency-key-0001", "amount_cents": 1})
        with pytest.raises(ValidationError):
            ApplicationFeePrepareIn.model_validate({"idempotency_key": "123"})
        attempt = api.prepare_application_fee(app.id, _payload(), db=db, current_user=applicant)
        with pytest.raises(HTTPException) as exc:
            resolve_note_target(db, current_user=admin, entity_type="application_fee_attempts",
                                entity_id=attempt.attempt_id)
        assert exc.value.status_code == 404
        assert db.query(ApplicationPayment).count() == 0
    finally:
        db.close(); engine.dispose()
