"""1099 review workflow never derives amounts or exposes full taxpayer IDs."""
from __future__ import annotations

import json
from datetime import date
from decimal import Decimal

import pytest
from cryptography.fernet import Fernet
from fastapi import HTTPException, Response
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import init_db  # noqa: F401
from app.core.config import settings
from app.core.database import Base
from app.models.audit_log import AuditLog
from app.models.tax_profile import TaxProfile
from app.models.tax_w9_document import TaxW9Document
from app.models.user import Organization, User, UserRole
from app.routers import tax_1099_reviews as routes
from app.schemas.tax_1099_review import (
    Tax1099ApprovalIn, Tax1099PrepareIn, Tax1099UpdateIn,
)
from app.services import tax_1099_reviews as service
from app.services import tax_profiles
from app.services.entity_notes import _model_for_table


@pytest.fixture
def ctx(monkeypatch):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine, expire_on_commit=False)()
    key = Fernet.generate_key().decode()
    monkeypatch.setattr(settings, "TAX_PROFILE_ENCRYPTION_KEY", key)
    monkeypatch.setattr(settings, "TAX_PROFILE_PREVIOUS_KEYS_JSON", "[]")
    monkeypatch.setattr(tax_profiles, "permission_allows_user", lambda *a, **kw: True)

    org = Organization(name="1099 Review Org", slug="review-org")
    other = Organization(name="Other 1099 Org", slug="review-other")
    db.add_all([org, other])
    db.flush()

    def user(scope, role, email):
        row = User(
            organization_id=scope.id, role=role, email=email,
            hashed_password="x", first_name="Tax", last_name=role.value,
            is_active=True,
        )
        db.add(row); db.flush(); return row

    admin = user(org, UserRole.ADMIN, "review-admin@example.com")
    vendor = user(org, UserRole.VENDOR, "review-vendor@example.com")
    owner = user(org, UserRole.OWNER, "review-owner@example.com")
    other_admin = user(other, UserRole.ADMIN, "review-other-admin@example.com")
    other_vendor = user(other, UserRole.VENDOR, "review-other-vendor@example.com")

    cipher = Fernet(key.encode())
    def profile(scope, typ, subject_id, tin):
        row = TaxProfile(
            organization_id=scope.id, subject_type=typ, subject_id=subject_id,
            encrypted_payload=cipher.encrypt(json.dumps({
                "tin": tin, "tax_classification": "INDIVIDUAL",
            }).encode()).decode(),
            w9_on_file=typ != "ORGANIZATION",
            w9_received_on=date(2026, 9, 25) if typ != "ORGANIZATION" else None,
        )
        db.add(row); db.flush(); return row

    payer = profile(org, "ORGANIZATION", org.id, "111223333")
    vendor_profile = profile(org, "VENDOR", vendor.id, "222334444")
    owner_profile = profile(org, "OWNER", owner.id, "333445555")
    other_payer = profile(other, "ORGANIZATION", other.id, "444556666")
    other_vendor_profile = profile(other, "VENDOR", other_vendor.id, "555667777")
    db.add_all([
        TaxW9Document(
            organization_id=org.id, tax_profile_id=vendor_profile.id,
            encrypted_pdf=cipher.encrypt(b"%PDF-1.7\n%%EOF\n"),
            size_bytes=16, received_on=date(2026, 9, 25), uploaded_by_id=admin.id,
        ),
        TaxW9Document(
            organization_id=org.id, tax_profile_id=owner_profile.id,
            encrypted_pdf=cipher.encrypt(b"%PDF-1.7\n%%EOF\n"),
            size_bytes=16, received_on=date(2026, 9, 25), uploaded_by_id=admin.id,
        ),
    ])
    db.commit()
    yield {
        "db": db, "engine": engine, "admin": admin, "vendor": vendor,
        "owner": owner, "other_admin": other_admin, "payer": payer,
        "vendor_profile": vendor_profile, "owner_profile": owner_profile,
        "other_payer": other_payer, "other_vendor_profile": other_vendor_profile,
    }
    db.close(); engine.dispose()


def nec(ctx, **changes):
    values = dict(
        idempotency_key="prep-nec-2026-0001", tax_year=2026,
        form_type="1099-NEC", income_category="NONEMPLOYEE_COMPENSATION",
        payer_profile_id=ctx["payer"].id,
        recipient_profile_id=ctx["vendor_profile"].id,
        amount=Decimal("2500.00"), source_type="CHECK",
        source_reference="Check register review #1042",
        source_note="Manual tax-year review; do not derive from GL.",
    )
    values.update(changes)
    return Tax1099PrepareIn(**values)


def approval():
    return Tax1099ApprovalIn(
        source_review_confirmed=True,
        threshold_review_confirmed=True,
        recipient_review_confirmed=True,
    )


def test_prepare_review_approve_lock_and_redacted_output(ctx):
    db, admin = ctx["db"], ctx["admin"]
    prepared = service.prepare_review(db, current_user=admin, payload=nec(ctx))
    assert prepared.status == "PREPARED"
    assert prepared.recipient_tin_last4 == "4444"
    assert prepared.payer_tin_last4 == "3333"
    assert "tin" not in prepared.model_dump()
    reviewed = service.mark_reviewed(db, current_user=admin, record_id=prepared.id)
    assert reviewed.status == "REVIEWED" and reviewed.w9_evidence_present
    approved = service.approve_review(
        db, current_user=admin, record_id=prepared.id, payload=approval())
    assert approved.status == "APPROVED"
    assert approved.source_review_confirmed
    assert approved.threshold_review_confirmed
    assert approved.recipient_review_confirmed

    with pytest.raises(HTTPException) as exc:
        service.update_prepared(
            db, current_user=admin, record_id=prepared.id,
            payload=Tax1099UpdateIn(**nec(ctx).model_dump(exclude={"idempotency_key"})),
        )
    assert exc.value.status_code == 409
    assert service.mark_reviewed(db, current_user=admin, record_id=prepared.id).status == "APPROVED"
    assert service.approve_review(db, current_user=admin, record_id=prepared.id,
                                  payload=approval()).status == "APPROVED"

    logs = db.query(AuditLog).filter(AuditLog.entity_type == "tax_1099_review").all()
    assert [row.action for row in logs] == ["prepared", "reviewed", "approved"]
    for log in logs:
        text = f"{log.old_value} {log.new_value}"
        assert "222334444" not in text
        assert "Manual tax-year review" not in text


def test_idempotency_conflict_and_same_payload_retry(ctx):
    db, admin = ctx["db"], ctx["admin"]
    first = service.prepare_review(db, current_user=admin, payload=nec(ctx))
    second = service.prepare_review(db, current_user=admin, payload=nec(ctx))
    assert second.id == first.id
    with pytest.raises(HTTPException) as exc:
        service.prepare_review(db, current_user=admin,
                               payload=nec(ctx, amount=Decimal("2501.00")))
    assert exc.value.status_code == 409
    assert db.query(__import__("app.models.tax_1099_review", fromlist=["Tax1099Review"]).Tax1099Review).count() == 1


def test_form_recipient_scope_and_taxpayer_profiles_are_explicit(ctx):
    db, admin = ctx["db"], ctx["admin"]
    misc = nec(
        ctx, idempotency_key="prep-misc-2026-0001",
        form_type="1099-MISC", income_category="RENTS",
        recipient_profile_id=ctx["owner_profile"].id,
    )
    assert service.prepare_review(db, current_user=admin, payload=misc).recipient_subject_type == "OWNER"

    for bad in (
        nec(ctx, idempotency_key="bad-owner-nec", recipient_profile_id=ctx["owner_profile"].id),
        nec(ctx, idempotency_key="bad-other-recipient", recipient_profile_id=ctx["other_vendor_profile"].id),
        nec(ctx, idempotency_key="bad-other-payer", payer_profile_id=ctx["other_payer"].id),
    ):
        with pytest.raises(HTTPException) as exc:
            service.prepare_review(db, current_user=admin, payload=bad)
        assert exc.value.status_code in {404, 422}


def test_review_requires_actual_archived_w9_not_metadata_only(ctx):
    db, admin = ctx["db"], ctx["admin"]
    db.query(TaxW9Document).filter(
        TaxW9Document.tax_profile_id == ctx["vendor_profile"].id).delete()
    db.commit()
    prepared = service.prepare_review(db, current_user=admin, payload=nec(ctx))
    with pytest.raises(HTTPException) as exc:
        service.mark_reviewed(db, current_user=admin, record_id=prepared.id)
    assert exc.value.status_code == 422
    assert "Archived signed W-9 evidence" in exc.value.detail


def test_approval_requires_all_manual_review_attestations(ctx):
    db, admin = ctx["db"], ctx["admin"]
    prepared = service.prepare_review(db, current_user=admin, payload=nec(ctx))
    service.mark_reviewed(db, current_user=admin, record_id=prepared.id)
    with pytest.raises(ValueError):
        Tax1099ApprovalIn(
            source_review_confirmed=True,
            threshold_review_confirmed=False,
            recipient_review_confirmed=True,
        )
    with pytest.raises(HTTPException) as exc:
        service.approve_review(db, current_user=admin, record_id=999999, payload=approval())
    assert exc.value.status_code == 404


def test_org_scope_no_store_and_no_filing_endpoint(ctx):
    db, admin = ctx["db"], ctx["admin"]
    response = Response()
    created = routes.create_review(nec(ctx), response, db=db, current_user=admin)
    assert response.headers["cache-control"] == "no-store"
    read_response = Response()
    rows = routes.read_reviews(read_response, db=db, current_user=admin, tax_year=2026)
    assert read_response.headers["cache-control"] == "no-store"
    assert [row.id for row in rows] == [created.id]
    assert service.list_reviews(
        db, current_user=ctx["other_admin"], tax_year=2026
    ) == []
    with pytest.raises(HTTPException) as exc:
        service.update_prepared(
            db, current_user=ctx["other_admin"], record_id=created.id,
            payload=Tax1099UpdateIn(**nec(ctx).model_dump(exclude={"idempotency_key"})),
        )
    assert exc.value.status_code == 404
    assert not hasattr(routes, "submit")
    assert not hasattr(routes, "file_return")
    with pytest.raises(HTTPException) as exc:
        service.list_reviews(db, current_user=admin, tax_year=1900)
    assert exc.value.status_code == 422


def test_tax_review_table_is_not_generic_note_or_attachment_target(ctx):
    with pytest.raises(HTTPException) as exc:
        _model_for_table("tax_1099_reviews")
    assert exc.value.status_code == 404
