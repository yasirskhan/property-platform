"""No TIN, taxpayer name or address may escape encrypted tax profiles."""
from __future__ import annotations

import json
from datetime import date

import pytest
from cryptography.fernet import Fernet
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import init_db  # noqa: F401
from app.core.config import settings
from app.core.database import Base
from app.models.audit_log import AuditLog
from app.models.tax_profile import TaxProfile
from app.models.user import Organization, User, UserRole
from app.schemas.tax_profile import TaxProfileUpsertIn
from app.services import tax_profiles as service


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _users(db):
    first = Organization(name="Tax Org One", slug="tax-org-one")
    second = Organization(name="Tax Org Two", slug="tax-org-two")
    db.add_all([first, second])
    db.flush()
    users = []
    for org, role, email in (
        (first, UserRole.ADMIN, "tax-admin@example.com"),
        (first, UserRole.OWNER, "tax-owner@example.com"),
        (first, UserRole.VENDOR, "tax-vendor@example.com"),
        (second, UserRole.ADMIN, "tax-other-admin@example.com"),
        (second, UserRole.OWNER, "tax-other-owner@example.com"),
        (first, UserRole.MANAGER, "tax-manager@example.com"),
    ):
        user = User(
            organization_id=org.id, first_name="Tax", last_name="Recipient",
            email=email, hashed_password="x", is_active=True, role=role,
        )
        db.add(user)
        users.append(user)
    db.commit()
    return users


def _input(subject_type, subject_id, **updates):
    base = dict(
        subject_type=subject_type, subject_id=subject_id,
        legal_name="Private Legal Recipient", tax_classification="INDIVIDUAL",
        tin_type="SSN", tin="123-45-6789",
        address_line1="42 Confidential Ave", city="Cleveland",
        state="OH", postal_code="44113", country="USA",
        w9_on_file=subject_type != "ORGANIZATION",
        w9_received_on=date(2026, 9, 26) if subject_type != "ORGANIZATION" else None,
    )
    base.update(updates)
    return TaxProfileUpsertIn(**base)


@pytest.fixture
def key(monkeypatch):
    secret = Fernet.generate_key().decode()
    monkeypatch.setattr(settings, "TAX_PROFILE_ENCRYPTION_KEY", secret)
    monkeypatch.setattr(service, "permission_allows_user", lambda *a, **kw: True)
    return secret


def test_encrypted_w9_tracking_scope_audit_redaction(key):
    db, engine = _session()
    try:
        admin, owner, _, other_admin, _, _ = _users(db)
        saved = service.upsert_tax_profile(db, current_user=admin,
                                           payload=_input("OWNER", owner.id))
        assert saved.tin_last4 == "6789"
        assert saved.w9_on_file and saved.w9_received_on == date(2026, 9, 26)
        assert "tin" not in saved.model_dump()
        assert "legal_name" not in saved.model_dump()
        row = db.query(TaxProfile).one()
        for secret in ("123456789", "Private Legal Recipient", "42 Confidential Ave"):
            assert secret not in row.encrypted_payload
        assert json.loads(Fernet(key.encode()).decrypt(row.encrypted_payload.encode()))["tin"] == "123456789"
        history = db.query(AuditLog).all()
        assert len(history) == 1
        assert history[0].organization_id == admin.organization_id
        for secret in ("123456789", "6789", "Private Legal Recipient", "42 Confidential Ave"):
            assert secret not in (history[0].new_value or "")
            assert secret not in (history[0].old_value or "")
        assert len(service.list_tax_profiles(db, current_user=admin)) == 1
        assert service.list_tax_profiles(db, current_user=other_admin) == []
    finally:
        db.close()
        engine.dispose()


def test_organization_payer_and_vendor_profiles(key):
    db, engine = _session()
    try:
        admin, owner, vendor, _, _, _ = _users(db)
        org_profile = service.upsert_tax_profile(
            db, current_user=admin,
            payload=_input("ORGANIZATION", admin.organization_id,
                           tin_type="EIN", tax_classification="C_CORP"),
        )
        vendor_profile = service.upsert_tax_profile(
            db, current_user=admin, payload=_input("VENDOR", vendor.id),
        )
        assert org_profile.subject_id == admin.organization_id
        assert vendor_profile.subject_id == vendor.id
        again = service.upsert_tax_profile(
            db, current_user=admin, payload=_input("OWNER", owner.id),
        )
        changed = service.upsert_tax_profile(
            db, current_user=admin, payload=_input(
                "OWNER", owner.id, tin="111-22-3333", w9_on_file=False, w9_received_on=None),
        )
        assert again.id == changed.id and changed.tin_last4 == "3333"
        assert db.query(TaxProfile).count() == 3
    finally:
        db.close()
        engine.dispose()


def test_access_and_cross_org_subject_probes_fail_closed(key):
    db, engine = _session()
    try:
        admin, owner, vendor, other_admin, other_owner, manager = _users(db)
        for actor, payload in (
            (admin, _input("OWNER", other_owner.id)),
            (admin, _input("VENDOR", other_owner.id)),
            (admin, _input("ORGANIZATION", other_admin.organization_id)),
        ):
            with pytest.raises(HTTPException) as exc:
                service.upsert_tax_profile(db, current_user=actor, payload=payload)
            assert exc.value.status_code == 404
        for actor in (owner, vendor, manager):
            with pytest.raises(HTTPException) as exc:
                service.list_tax_profiles(db, current_user=actor)
            assert exc.value.status_code == 403
        with pytest.raises(HTTPException) as exc:
            service.upsert_tax_profile(db, current_user=manager,
                                       payload=_input("OWNER", owner.id))
        assert exc.value.status_code == 403
    finally:
        db.close()
        engine.dispose()


def test_tax_key_missing_or_shared_with_smtp_key_refuses_storage(key, monkeypatch):
    db, engine = _session()
    try:
        admin, owner, *_ = _users(db)
        monkeypatch.setattr(settings, "TAX_PROFILE_ENCRYPTION_KEY", "")
        with pytest.raises(HTTPException) as exc:
            service.upsert_tax_profile(db, current_user=admin,
                                       payload=_input("OWNER", owner.id))
        assert exc.value.status_code == 503
        assert db.query(TaxProfile).count() == 0
        monkeypatch.setattr(settings, "TAX_PROFILE_ENCRYPTION_KEY", settings.ENCRYPTION_KEY)
        with pytest.raises(HTTPException) as exc:
            service.list_tax_profiles(db, current_user=admin)
        assert exc.value.status_code == 503
        assert db.query(TaxProfile).count() == 0
    finally:
        db.close()
        engine.dispose()


def test_tin_and_paper_w9_validations(key):
    db, engine = _session()
    try:
        admin, owner, *_ = _users(db)
        for raw in ("", "1234567", "12345678X", "1234567890"):
            with pytest.raises(HTTPException) as exc:
                service.upsert_tax_profile(db, current_user=admin,
                                           payload=_input("OWNER", owner.id, tin=raw))
            assert exc.value.status_code == 422
        with pytest.raises(ValueError):
            _input("OWNER", owner.id, w9_on_file=True, w9_received_on=None)
        with pytest.raises(ValueError):
            _input("ORGANIZATION", admin.organization_id, w9_on_file=True,
                   w9_received_on=date(2026, 9, 26))
        assert db.query(TaxProfile).count() == 0
    finally:
        db.close()
        engine.dispose()


def test_permission_revocation_and_ciphertext_tampering(key, monkeypatch):
    db, engine = _session()
    try:
        admin, owner, *_ = _users(db)
        service.upsert_tax_profile(db, current_user=admin,
                                   payload=_input("OWNER", owner.id))
        monkeypatch.setattr(service, "permission_allows_user", lambda *a, **kw: False)
        with pytest.raises(HTTPException) as exc:
            service.list_tax_profiles(db, current_user=admin)
        assert exc.value.status_code == 403
        monkeypatch.setattr(service, "permission_allows_user", lambda *a, **kw: True)
        row = db.query(TaxProfile).one()
        row.encrypted_payload = row.encrypted_payload[:-3] + "abc"
        db.commit()
        with pytest.raises(HTTPException) as exc:
            service.list_tax_profiles(db, current_user=admin)
        assert exc.value.status_code == 503
    finally:
        db.close()
        engine.dispose()



def test_tax_profile_http_routes_never_cache_sensitive_status(key):
    from fastapi import Response
    from app.routers import tax_profiles as routes

    db, engine = _session()
    try:
        admin, owner, *_ = _users(db)
        result = Response()
        saved = routes.save_profile(_input("OWNER", owner.id), result,
                                    db=db, current_user=admin)
        assert result.headers.get("cache-control") == "no-store"
        assert saved.tin_last4 == "6789"
        read_response = Response()
        listed = routes.list_profiles(read_response, db=db, current_user=admin)
        assert read_response.headers.get("cache-control") == "no-store"
        assert listed[0].id == saved.id
        assert "tin" not in listed[0].model_dump()
    finally:
        db.close()
        engine.dispose()


def test_1099_preparation_link_does_not_advertise_irs_submission():
    from app.services.report_catalog import REPORT_CATALOG
    from app.services.report_delivery import REPORT_PERMISSIONS

    item = next(item for item in REPORT_CATALOG if item.key == "tax.1099_preparation")
    assert item.href == "/dashboard/reporting/1099"
    assert "filing not enabled" in (item.description or "")
    assert "tax.1099_preparation" not in REPORT_PERMISSIONS
