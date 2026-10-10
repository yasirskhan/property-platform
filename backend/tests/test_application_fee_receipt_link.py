"""Staff receipt settlement is a link to existing GL, not new cash movement."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import init_db  # noqa: F401
from app.core.database import Base
from app.models.application import ApplicationPayment, ApplicationStatus, LeaseApplication
from app.models.application_fee_attempt import ApplicationFeeAttempt
from app.models.audit_log import AuditLog
from app.models.bank_account import BankAccount
from app.models.gl_account import GLAccount
from app.models.gl_entry import GLEntry
from app.models.gl_transaction import GLTransaction
from app.models.property import Property, Unit
from app.models.receipt import Receipt
from app.models.user import Organization, User, UserRole
from app.routers import rental_applications as api
from app.schemas.application_fee import ApplicationFeeRecordReceiptIn
from app.schemas.receipt import ReceiptCreateIn
from app.services.receipt_posting import post_receipt, reverse_receipt
from app.services.gl_posting import PostingError


def _db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _seed(db):
    org, foreign = Organization(name="Receipt Match", slug="receipt-match"), Organization(name="Foreign Receipt", slug="foreign-receipt")
    db.add_all([org, foreign]); db.flush()
    users = []
    for o, role, email in [
        (org, UserRole.ADMIN, "match-admin@example.com"),
        (org, UserRole.APPLICANT, "match-applicant@example.com"),
        (org, UserRole.MANAGER, "match-manager@example.com"),
        (foreign, UserRole.ADMIN, "match-foreign@example.com"),
    ]:
        u = User(organization_id=o.id, role=role, email=email, first_name="First",
                 last_name="Applicant", hashed_password="x", is_active=True)
        db.add(u); db.flush(); users.append(u)
    prop = Property(organization_id=org.id, name="Match", address_line1="100 Match St",
                    city="Cleveland", state="OH", zip_code="44113", country="USA", is_active=True)
    db.add(prop); db.flush()
    unit = Unit(property_id=prop.id, unit_number="2B", application_fee=Decimal("65.50"), is_active=True)
    db.add(unit); db.flush()
    cash = GLAccount(organization_id=org.id, gl_number="1150", name="Rental Trust",
                     account_type="ASSET", is_active=True)
    fee = GLAccount(organization_id=org.id, gl_number="4420", name="Application Income",
                    account_type="INCOME", is_active=True)
    db.add_all([cash, fee]); db.flush()
    app = LeaseApplication(property_id=prop.id, unit_id=unit.id,
        applicant_user_id=users[1].id, applicant_names='["First Applicant"]',
        status=ApplicationStatus.PENDING_PAYMENT)
    db.add(app); db.flush()
    attempt = ApplicationFeeAttempt(
        organization_id=org.id, application_id=app.id, applicant_user_id=users[1].id,
        unit_id=unit.id, idempotency_key="match-app-fee-key-00001",
        amount_cents=6550, currency="USD", status="PREPARED",
    )
    db.add(attempt); db.commit()
    return users, prop, unit, cash, fee, app, attempt


def _receipt(db, staff, prop, unit, app, amount="65.50", reference=None, payer="First Applicant"):
    return post_receipt(
        db=db, organization_id=staff.organization_id,
        payload=ReceiptCreateIn(
            type="APPLICATION_FEE", receipt_date=date(2026, 9, 27),
            amount=Decimal(amount), cash_gl_account_id=None,
            received_from=payer, reference_number=reference or f"APP-{app.id}",
            property_id=prop.id, unit_id=unit.id,
        ), created_by=staff,
    )


def _confirm(db, app, receipt, staff):
    return api.record_application_fee_receipt(
        app.id, ApplicationFeeRecordReceiptIn(
            receipt_id=receipt.id, attested_received_and_matched=True,
        ), db=db, current_user=staff,
    )


@pytest.fixture
def authorized(monkeypatch):
    monkeypatch.setattr(api, "permission_allows_user", lambda *args, **kwargs: True)
    monkeypatch.setattr(api, "resolve_customer_features", lambda *args, **kwargs: [
        type("Decision", (), {"key": "release.accounting.receipts.application_fee", "allowed": True})(),
    ])


def test_existing_gl_receipt_links_once_and_reversal_restores_pending(authorized):
    db, engine = _db()
    try:
        users, prop, unit, cash, fee, app, attempt = _seed(db)
        staff = users[0]
        receipt = _receipt(db, staff, prop, unit, app)
        old_gl_count = db.query(GLTransaction).count()
        old_entry_count = db.query(GLEntry).count()
        result = _confirm(db, app, receipt, staff)
        assert result.status == "paid"
        assert db.query(GLTransaction).count() == old_gl_count
        assert db.query(GLEntry).count() == old_entry_count
        payment = db.query(ApplicationPayment).one()
        assert payment.status == "paid" and payment.receipt_id == receipt.id
        assert payment.amount == Decimal("65.50")
        assert payment.stripe_payment_intent_id is None
        db.refresh(attempt)
        assert attempt.status == "ACCOUNTED"
        with pytest.raises(HTTPException) as exc:
            _confirm(db, app, receipt, staff)
        assert exc.value.status_code == 409
        reverse_receipt(db, original=receipt, reversal_date=date(2026, 9, 27),
                        memo="Returned funds", created_by=staff)
        db.refresh(app); db.refresh(attempt); db.refresh(payment)
        assert app.status == ApplicationStatus.PENDING_PAYMENT
        assert app.fee_amount is None and attempt.status == "REVERSED"
        assert payment.status == "reversed" and payment.receipt_id == receipt.id
        assert db.query(GLTransaction).count() == old_gl_count + 1
        assert db.query(ApplicationPayment).count() == 1
        new_receipt = _receipt(db, staff, prop, unit, app)
        again = _confirm(db, app, new_receipt, staff)
        assert again.status == "paid"
        assert db.query(ApplicationPayment).count() == 2
        assert db.query(ApplicationPayment).filter_by(status="paid").count() == 1
    finally:
        db.close(); engine.dispose()


def test_staff_scope_permission_and_feature_revocation_fail_closed(authorized, monkeypatch):
    db, engine = _db()
    try:
        users, prop, unit, cash, fee, app, attempt = _seed(db)
        admin, applicant, manager, foreign = users
        receipt = _receipt(db, admin, prop, unit, app)
        for actor in (applicant, manager, foreign):
            with pytest.raises(HTTPException) as exc:
                _confirm(db, app, receipt, actor)
            assert exc.value.status_code in (403, 404)
        monkeypatch.setattr(api, "permission_allows_user",
                            lambda _db, *, user, menu_key: menu_key != "ACCOUNTING.RECEIVABLES")
        with pytest.raises(HTTPException) as exc:
            _confirm(db, app, receipt, admin)
        assert exc.value.status_code == 403
        monkeypatch.setattr(api, "permission_allows_user", lambda *a, **k: True)
        monkeypatch.setattr(api, "resolve_customer_features", lambda *a, **k: [])
        with pytest.raises(HTTPException) as exc:
            _confirm(db, app, receipt, admin)
        assert exc.value.status_code == 404
        assert db.query(ApplicationPayment).count() == 0
        assert app.status == ApplicationStatus.PENDING_PAYMENT
    finally:
        db.close(); engine.dispose()


def test_wrong_receipts_and_existing_payment_cannot_be_reused(authorized):
    db, engine = _db()
    try:
        users, prop, unit, cash, fee, app, attempt = _seed(db)
        admin = users[0]
        receipt = _receipt(db, admin, prop, unit, app)
        receipt.reference_number = "BAD"; db.commit()
        with pytest.raises(HTTPException) as exc:
            _confirm(db, app, receipt, admin)
        assert exc.value.status_code == 422
        receipt.reference_number = f"APP-{app.id}"
        receipt.received_from = "Other Payer"; db.commit()
        with pytest.raises(HTTPException) as exc:
            _confirm(db, app, receipt, admin)
        assert exc.value.status_code == 422
        receipt.received_from = "First Applicant"
        receipt.amount = Decimal("55.00"); db.commit()
        with pytest.raises(HTTPException) as exc:
            _confirm(db, app, receipt, admin)
        assert exc.value.status_code == 422
        receipt.amount = Decimal("65.50")
        receipt.is_reversed = True; db.commit()
        with pytest.raises(HTTPException) as exc:
            _confirm(db, app, receipt, admin)
        assert exc.value.status_code == 422
        receipt.is_reversed = False
        receipt.type = "OTHER"; db.commit()
        with pytest.raises(HTTPException) as exc:
            _confirm(db, app, receipt, admin)
        assert exc.value.status_code == 422
        receipt.type = "APPLICATION_FEE"; db.commit()
        _confirm(db, app, receipt, admin)
        # Cannot reuse even after reversing: unique FK/link persists.
        reverse_receipt(db, original=receipt, reversal_date=date(2026, 9, 27),
                        memo=None, created_by=admin)
        with pytest.raises(HTTPException) as exc:
            _confirm(db, app, receipt, admin)
        assert exc.value.status_code in (409, 422)
        assert db.query(AuditLog).filter_by(action="fee_receipt_reversed").count() == 1
    finally:
        db.close(); engine.dispose()


def test_failed_gl_reversal_does_not_unpay_application(authorized):
    db, engine = _db()
    try:
        users, prop, unit, cash, fee, app, attempt = _seed(db)
        admin = users[0]
        receipt = _receipt(db, admin, prop, unit, app)
        _confirm(db, app, receipt, admin)
        org = db.get(Organization, admin.organization_id)
        org.locked_through_date = date(2026, 9, 27); db.commit()
        with pytest.raises(PostingError):
            reverse_receipt(db, original=receipt, reversal_date=date(2026, 9, 27),
                            memo=None, created_by=admin)
        db.refresh(app)
        payment = db.query(ApplicationPayment).one()
        db.refresh(payment); db.refresh(attempt)
        assert app.status == ApplicationStatus.PAID
        assert payment.status == "paid"
        assert attempt.status == "ACCOUNTED"
        assert db.query(GLTransaction).count() == 1
    finally:
        db.close(); engine.dispose()
