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



def test_internal_register_masked_csv_org_scope_audit_and_formula_escape(ctx, monkeypatch):
    from app.services.report_delivery import report_csv_bytes
    db, admin = ctx["db"], ctx["admin"]
    monkeypatch.setattr(routes, "_require_export_feature", lambda *args: None)
    prepared = service.prepare_review(
        db, current_user=admin,
        payload=nec(ctx, source_reference="=HYPERLINK(\"https://example.com\")"),
    )
    service.mark_reviewed(db, current_user=admin, record_id=prepared.id)
    service.approve_review(db, current_user=admin, record_id=prepared.id,
                           payload=approval())
    # A separate organization's record is never exported to this admin.
    other = service.prepare_review(
        db, current_user=ctx["other_admin"],
        payload=nec(
            ctx, idempotency_key="foreign-1099-register", payer_profile_id=ctx["other_payer"].id,
            recipient_profile_id=ctx["other_vendor_profile"].id,
            source_reference="FOREIGN ORG PRIVATE",
        ),
    )
    assert other.id != prepared.id
    reply = routes.export_internal_register(tax_year=2026, db=db, current_user=admin)
    content = reply.body.decode("utf-8-sig")
    assert reply.headers["cache-control"] == "no-store"
    assert reply.headers["x-content-type-options"] == "nosniff"
    assert "not-for-irs" in reply.headers["content-disposition"]
    assert "NOT FOR IRS SUBMISSION" in content
    assert "APPROVED" in content
    assert "****3333" in content and "****4444" in content
    assert "'=HYPERLINK" in content
    assert "FOREIGN ORG PRIVATE" not in content
    for secret in ("111223333", "222334444", "444556666", "555667777"):
        assert secret not in content
    assert "Manual tax-year review" not in content  # Source note deliberately excluded.
    row = db.query(AuditLog).filter(AuditLog.entity_type == "tax_1099_register").one()
    assert row.organization_id == admin.organization_id
    assert json.loads(row.new_value)["irs_submission"] is False
    assert "4444" not in (row.new_value or "")
    empty = routes.export_internal_register(tax_year=2025, db=db, current_user=admin)
    assert b"NOT FOR IRS SUBMISSION" not in empty.body  # Header-only, no fabricated record.


def test_internal_register_fails_closed_without_export_feature_or_permission(ctx, monkeypatch):
    db, admin = ctx["db"], ctx["admin"]
    service.prepare_review(db, current_user=admin, payload=nec(ctx))
    with pytest.raises(HTTPException) as exc:
        routes.export_internal_register(tax_year=2026, db=db, current_user=admin)
    assert exc.value.status_code == 404  # Release feature is absent in fixture.
    monkeypatch.setattr(routes, "_require_export_feature", lambda *args: None)
    with pytest.raises(HTTPException) as exc:
        routes.export_internal_register(tax_year=2026, db=db, current_user=ctx["vendor"])
    assert exc.value.status_code == 403
    with pytest.raises(HTTPException) as exc:
        service.internal_register(db, current_user=admin, tax_year=2019)
    assert exc.value.status_code == 422
    assert db.query(AuditLog).filter(AuditLog.entity_type == "tax_1099_register").count() == 0



def _changed_vendor_profile(ctx, **overrides):
    from app.schemas.tax_profile import TaxProfileUpsertIn
    data = dict(
        subject_type="VENDOR", subject_id=ctx["vendor"].id,
        legal_name="Verified Vendor", tax_classification="INDIVIDUAL",
        tin_type="SSN", tin="222334445",
        address_line1="10 Revised Street", city="Cleveland",
        state="OH", postal_code="44113", country="USA",
        w9_on_file=True, w9_received_on=date(2026, 9, 25),
    )
    data.update(overrides)
    return TaxProfileUpsertIn(**data)


def test_profile_correction_invalidates_review_and_requires_reapproval(ctx):
    db, admin = ctx["db"], ctx["admin"]
    item = service.prepare_review(db, current_user=admin, payload=nec(ctx))
    reviewed = service.mark_reviewed(db, current_user=admin, record_id=item.id)
    assert reviewed.profile_changed_since_review is False
    recipient = ctx["vendor_profile"]
    before = recipient.profile_revision
    tax_profiles.upsert_tax_profile(
        db, current_user=admin, payload=_changed_vendor_profile(ctx),
    )
    db.refresh(recipient)
    assert recipient.profile_revision == before + 1
    assert service.list_reviews(db, current_user=admin)[0].profile_changed_since_review is True
    with pytest.raises(HTTPException) as exc:
        service.approve_review(db, current_user=admin, record_id=item.id,
                               payload=approval())
    assert exc.value.status_code == 409

    rereviewed = service.mark_reviewed(db, current_user=admin, record_id=item.id)
    assert rereviewed.status == "REVIEWED"
    assert rereviewed.profile_changed_since_review is False
    approved = service.approve_review(
        db, current_user=admin, record_id=item.id, payload=approval(),
    )
    assert approved.status == "APPROVED"
    assert approved.profile_changed_since_review is False
    tax_profiles.upsert_tax_profile(
        db, current_user=admin,
        payload=_changed_vendor_profile(ctx, tin="222334446"),
    )
    locked = service.list_reviews(db, current_user=admin)[0]
    assert locked.status == "APPROVED"
    assert locked.profile_changed_since_review is True
    exported = service.internal_register(db, current_user=admin, tax_year=2026)
    assert "RE-REVIEW REQUIRED" in str(exported.rows)
    assert "222334446" not in str(exported.rows)
    # Old approval is immutable; submit an explicitly new corrected review.
    assert service.mark_reviewed(db, current_user=admin, record_id=item.id).profile_changed_since_review
    logs = db.query(AuditLog).filter(
        AuditLog.entity_type == "tax_1099_review",
        AuditLog.action == "re_reviewed",
    ).all()
    assert len(logs) == 1


def test_identical_profile_save_does_not_stale_review(ctx):
    db, admin = ctx["db"], ctx["admin"]
    recipient = ctx["vendor_profile"]
    item = service.prepare_review(db, current_user=admin, payload=nec(ctx))
    service.mark_reviewed(db, current_user=admin, record_id=item.id)
    payload = _changed_vendor_profile(ctx)
    tax_profiles.upsert_tax_profile(db, current_user=admin, payload=payload)
    db.refresh(recipient)
    revision = recipient.profile_revision
    assert service.list_reviews(db, current_user=admin)[0].profile_changed_since_review
    # Submitting identical normalized taxpayer data and W-9 metadata
    # changes ciphertext but not its substantive version.
    tax_profiles.upsert_tax_profile(db, current_user=admin, payload=payload)
    db.refresh(recipient)
    assert recipient.profile_revision == revision


def test_new_signed_w9_after_approval_requires_new_review(ctx):
    from app.services.tax_w9 import archive_signed_w9

    db, admin = ctx["db"], ctx["admin"]
    item = service.prepare_review(db, current_user=admin, payload=nec(ctx))
    service.mark_reviewed(db, current_user=admin, record_id=item.id)
    service.approve_review(db, current_user=admin, record_id=item.id,
                           payload=approval())
    original_revision = ctx["vendor_profile"].profile_revision
    archive_signed_w9(
        db, current_user=admin, tax_profile_id=ctx["vendor_profile"].id,
        contents=b"%PDF-1.7\\n1 0 obj\\n<<>>\\nendobj\\n%%EOF\\n",
        received_on=date(2026, 9, 25), signed_original_confirmed=True,
    )
    db.refresh(ctx["vendor_profile"])
    assert ctx["vendor_profile"].profile_revision == original_revision + 1
    assert service.list_reviews(db, current_user=admin)[0].profile_changed_since_review


def test_key_rotation_does_not_invalidate_semantically_identical_approved_data(ctx, monkeypatch):
    from app.services.tax_key_rotation import rotate_org_tax_keys
    from app.schemas.tax_rotation import TaxRotationIn

    db, admin = ctx["db"], ctx["admin"]
    item = service.prepare_review(db, current_user=admin, payload=nec(ctx))
    service.mark_reviewed(db, current_user=admin, record_id=item.id)
    service.approve_review(db, current_user=admin, record_id=item.id,
                           payload=approval())
    before = ctx["vendor_profile"].profile_revision
    original_key = settings.TAX_PROFILE_ENCRYPTION_KEY
    monkeypatch.setattr(settings, "TAX_PROFILE_ENCRYPTION_KEY",
                        Fernet.generate_key().decode())
    monkeypatch.setattr(settings, "TAX_PROFILE_PREVIOUS_KEYS_JSON",
                        json.dumps([original_key]))
    result = rotate_org_tax_keys(
        db, current_user=admin, payload=TaxRotationIn(limit=10),
    )
    db.refresh(ctx["vendor_profile"])
    assert result.profiles_rewrapped >= 2
    assert ctx["vendor_profile"].profile_revision == before
    assert not service.list_reviews(db, current_user=admin)[0].profile_changed_since_review


def test_legacy_approved_records_without_revision_snapshot_fail_closed(ctx):
    from app.models.tax_1099_review import Tax1099Review

    db, admin = ctx["db"], ctx["admin"]
    item = service.prepare_review(db, current_user=admin, payload=nec(ctx))
    service.mark_reviewed(db, current_user=admin, record_id=item.id)
    service.approve_review(db, current_user=admin, record_id=item.id,
                           payload=approval())
    db.query(Tax1099Review).filter_by(id=item.id).update({
        Tax1099Review.reviewed_payer_revision: None,
    })
    db.commit()
    historical = service.list_reviews(db, current_user=admin)[0]
    assert historical.status == "APPROVED"
    assert historical.profile_changed_since_review



def _full_tax_profile(ctx, subject, tin, w9=False):
    from app.schemas.tax_profile import TaxProfileUpsertIn
    return TaxProfileUpsertIn(
        subject_type=subject.subject_type, subject_id=subject.subject_id,
        legal_name="Taxpayer Legal Name", tax_classification="INDIVIDUAL",
        tin_type="SSN" if subject.subject_type != "ORGANIZATION" else "EIN",
        tin=tin, address_line1="123 Private Street", city="Cleveland",
        state="OH", postal_code="44113", country="USA",
        w9_on_file=w9, w9_received_on=date(2026, 9, 25) if w9 else None,
    )


def test_preflight_never_fabricates_filing_or_exposes_taxpayer_data(ctx):
    db, admin = ctx["db"], ctx["admin"]
    item = service.prepare_review(db, current_user=admin, payload=nec(ctx))
    service.mark_reviewed(db, current_user=admin, record_id=item.id)
    service.approve_review(db, current_user=admin, record_id=item.id,
                           payload=approval())

    # Older paper profiles with only TIN/classification cannot pass
    # payer/recipient identity and address completeness validation.
    reply = Response()
    incomplete = routes.check_provider_preflight(
        item.id, reply, db=db, current_user=admin,
    )
    assert reply.headers["cache-control"] == "no-store"
    assert incomplete.ready_for_provider_handoff is False
    assert incomplete.filing_enabled is False
    assert incomplete.submission_status == "NOT_SUBMITTED"
    assert len(incomplete.blockers) == 2
    assert "Payer" in incomplete.blockers[0]
    assert "Recipient" in incomplete.blockers[1]
    for secret in ("111223333", "222334444", "123 Private Street"):
        assert secret not in incomplete.model_dump_json()

    # Update both profiles, then create a new explicitly reviewed record.
    tax_profiles.upsert_tax_profile(
        db, current_user=admin,
        payload=_full_tax_profile(ctx, ctx["payer"], "111223333"),
    )
    tax_profiles.upsert_tax_profile(
        db, current_user=admin,
        payload=_full_tax_profile(ctx, ctx["vendor_profile"], "222334444", w9=True),
    )
    assert service.preflight_review(
        db, current_user=admin, record_id=item.id,
    ).ready_for_provider_handoff is False  # stale immutable approval
    corrected = service.prepare_review(
        db, current_user=admin,
        payload=nec(ctx, idempotency_key="preflight-updated-2026"),
    )
    service.mark_reviewed(db, current_user=admin, record_id=corrected.id)
    service.approve_review(db, current_user=admin, record_id=corrected.id,
                           payload=approval())
    ready = service.preflight_review(
        db, current_user=admin, record_id=corrected.id,
    )
    assert ready.ready_for_provider_handoff
    assert ready.blockers == []
    assert not ready.filing_enabled
    assert ready.submission_status == "NOT_SUBMITTED"
    for secret in ("111223333", "222334444", "123 Private Street"):
        assert secret not in ready.model_dump_json()
    events = db.query(AuditLog).filter(
        AuditLog.entity_type == "tax_1099_review",
        AuditLog.action == "preflight_checked",
    ).all()
    assert len(events) == 3
    for event in events:
        assert "111223333" not in (event.new_value or "")
        assert "222334444" not in (event.new_value or "")
        assert "Taxpayer Legal Name" not in (event.new_value or "")


def test_provider_preflight_scope_and_revocation(ctx, monkeypatch):
    db, admin = ctx["db"], ctx["admin"]
    item = service.prepare_review(db, current_user=admin, payload=nec(ctx))
    for actor, wanted in ((ctx["other_admin"], 404), (ctx["vendor"], 403)):
        with pytest.raises(HTTPException) as exc:
            service.preflight_review(db, current_user=actor, record_id=item.id)
        assert exc.value.status_code == wanted
    monkeypatch.setattr(tax_profiles, "permission_allows_user", lambda *a, **kw: False)
    with pytest.raises(HTTPException) as exc:
        service.preflight_review(db, current_user=admin, record_id=item.id)
    assert exc.value.status_code == 403
    assert db.query(AuditLog).filter(AuditLog.action == "preflight_checked").count() == 0


def test_provider_preflight_requires_signed_w9_even_after_manual_approval(ctx):
    db, admin = ctx["db"], ctx["admin"]
    item = service.prepare_review(db, current_user=admin, payload=nec(ctx))
    service.mark_reviewed(db, current_user=admin, record_id=item.id)
    service.approve_review(db, current_user=admin, record_id=item.id,
                           payload=approval())
    db.query(TaxW9Document).filter(
        TaxW9Document.tax_profile_id == ctx["vendor_profile"].id,
    ).delete()
    db.commit()
    preflight = service.preflight_review(
        db, current_user=admin, record_id=item.id,
    )
    assert not preflight.ready_for_provider_handoff
    assert any("signed paper W-9" in text for text in preflight.blockers)



def test_unencrypted_1099_source_rejects_new_tax_ids_and_masks_historical_text(ctx):
    from app.models.tax_1099_review import Tax1099Review

    db, admin = ctx["db"], ctx["admin"]
    for bad in (
        {"source_reference": "Check SSN 123-45-6789"},
        {"source_note": "Payee EIN 12-3456789"},
        {"source_reference": "123456789"},
    ):
        with pytest.raises(HTTPException) as exc:
            service.prepare_review(db, current_user=admin,
                                   payload=nec(ctx, **bad))
        assert exc.value.status_code == 422
        assert "123456789" not in str(exc.value.detail)
        assert "12-3456789" not in str(exc.value.detail)
    assert db.query(Tax1099Review).count() == 0

    prepared = service.prepare_review(db, current_user=admin, payload=nec(ctx))
    with pytest.raises(HTTPException) as exc:
        service.update_prepared(
            db, current_user=admin, record_id=prepared.id,
            payload=Tax1099UpdateIn(**nec(
                ctx, source_note="Private EIN 12-3456789",
            ).model_dump(exclude={"idempotency_key"})),
        )
    assert exc.value.status_code == 422

    # A legacy/externally restored record predates the new validation;
    # never render its free text unredacted, even in the internal CSV.
    row = db.query(Tax1099Review).filter_by(id=prepared.id).one()
    row.source_reference = "Check SSN 123-45-6789"
    row.source_note = "Private EIN 12-3456789"
    db.commit()
    listed = service.list_reviews(db, current_user=admin)[0]
    assert "123-45-6789" not in listed.model_dump_json()
    assert "12-3456789" not in listed.model_dump_json()
    assert "[REDACTED TAX ID]" in listed.source_reference
    report = service.internal_register(db, current_user=admin, tax_year=2026)
    from app.services.report_delivery import report_csv_bytes
    encoded = report_csv_bytes(report).decode("utf-8-sig")
    assert "123-45-6789" not in encoded and "12-3456789" not in encoded
    assert "[REDACTED TAX ID]" in encoded
    with pytest.raises(HTTPException) as exc:
        service.mark_reviewed(db, current_user=admin, record_id=prepared.id)
    assert exc.value.status_code == 422
    blockers = service.preflight_review(
        db, current_user=admin, record_id=prepared.id,
    ).blockers
    assert any("unencrypted source" in reason for reason in blockers)


def test_competing_current_approved_returns_are_blocked_before_handoff(ctx):
    db, admin = ctx["db"], ctx["admin"]
    # Complete payer and recipient profiles, retaining signed W-9 evidence.
    tax_profiles.upsert_tax_profile(
        db, current_user=admin,
        payload=_full_tax_profile(ctx, ctx["payer"], "111223333"),
    )
    tax_profiles.upsert_tax_profile(
        db, current_user=admin,
        payload=_full_tax_profile(ctx, ctx["vendor_profile"], "222334444", w9=True),
    )
    ids = []
    for key, reference in (
        ("competing-1099-0001", "Check #1042 and reviewed annual total"),
        ("competing-1099-0002", "Check #1043 and reviewed annual total"),
    ):
        prepared = service.prepare_review(
            db, current_user=admin,
            payload=nec(ctx, idempotency_key=key, source_reference=reference),
        )
        service.mark_reviewed(db, current_user=admin, record_id=prepared.id)
        service.approve_review(db, current_user=admin, record_id=prepared.id,
                               payload=approval())
        ids.append(prepared.id)
    for record_id in ids:
        result = service.preflight_review(
            db, current_user=admin, record_id=record_id,
        )
        assert result.review_status == "APPROVED"
        assert not result.ready_for_provider_handoff
        assert result.submission_status == "NOT_SUBMITTED"
        assert any("Competing current" in reason for reason in result.blockers)

    # A corrected profile invalidates old approvals, so a newly
    # reviewed and approved replacement must NOT be blocked by them.
    tax_profiles.upsert_tax_profile(
        db, current_user=admin,
        payload=_full_tax_profile(
            ctx, ctx["vendor_profile"], "222334445", w9=True,
        ),
    )
    replacement = service.prepare_review(
        db, current_user=admin,
        payload=nec(ctx, idempotency_key="competing-1099-correction",
                    source_reference="Corrected annual statement"),
    )
    service.mark_reviewed(db, current_user=admin, record_id=replacement.id)
    service.approve_review(db, current_user=admin, record_id=replacement.id,
                           payload=approval())
    result = service.preflight_review(
        db, current_user=admin, record_id=replacement.id,
    )
    assert result.ready_for_provider_handoff
    assert result.blockers == []
    assert not result.filing_enabled



def test_avalara_sandbox_dry_run_is_disabled_by_default(ctx, monkeypatch):
    from app.schemas.tax_1099_review import Tax1099ProviderDryRunIn
    from app.services import tax_1099_provider as provider

    db, admin = ctx["db"], ctx["admin"]
    called = []
    monkeypatch.setattr(provider.requests, "post", lambda *a, **k: called.append((a, k)))
    with pytest.raises(HTTPException) as exc:
        provider.validate_avalara_sandbox_dry_run(
            db, current_user=admin, record_id=999,
            payload=Tax1099ProviderDryRunIn(confirm_external_tax_data_sandbox=True),
        )
    assert exc.value.status_code == 503
    assert called == []


def _ready_nec_for_provider(ctx):
    db, admin = ctx["db"], ctx["admin"]
    tax_profiles.upsert_tax_profile(
        db, current_user=admin,
        payload=_full_tax_profile(ctx, ctx["payer"], "111223333"),
    )
    tax_profiles.upsert_tax_profile(
        db, current_user=admin,
        payload=_full_tax_profile(ctx, ctx["vendor_profile"], "222334444", w9=True),
    )
    item = service.prepare_review(
        db, current_user=admin,
        payload=nec(ctx, idempotency_key="provider-sandbox-nec-2026"),
    )
    service.mark_reviewed(db, current_user=admin, record_id=item.id)
    service.approve_review(db, current_user=admin, record_id=item.id, payload=approval())
    return item


def test_avalara_sandbox_dry_run_never_schedules_or_returns_provider_body(ctx, monkeypatch):
    from types import SimpleNamespace
    from app.schemas.tax_1099_review import Tax1099ProviderDryRunIn
    from app.services import tax_1099_provider as provider

    db, admin = ctx["db"], ctx["admin"]
    item = _ready_nec_for_provider(ctx)
    monkeypatch.setattr(settings, "TAX_1099_PROVIDER", "avalara_sandbox")
    monkeypatch.setattr(settings, "AVALARA_1099_CLIENT_ID", "sandbox-client")
    monkeypatch.setattr(settings, "AVALARA_1099_CLIENT_SECRET", "sandbox-secret")
    monkeypatch.setattr(settings, "AVALARA_1099_ISSUER_ID", "sandbox-issuer")
    monkeypatch.setattr(settings, "AVALARA_1099_API_VERSION", "2.0.0")

    calls = []
    class Fake:
        def __init__(self, status, body):
            self.status_code = status
            self.text = body
            self._body = body
        def json(self):
            return json.loads(self._body)

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        if url == provider.TOKEN_URL:
            return Fake(200, json.dumps({"access_token": "redacted-token"}))
        return Fake(200, json.dumps({
            "tin": "222334444", "recipientName": "DO NOT RETURN",
            "validation": "accepted",
        }))

    monkeypatch.setattr(provider.requests, "post", fake_post)
    result = provider.validate_avalara_sandbox_dry_run(
        db, current_user=admin, record_id=item.id,
        payload=Tax1099ProviderDryRunIn(confirm_external_tax_data_sandbox=True),
    )
    assert result.validated is True
    assert result.submission_status == "NOT_SUBMITTED"
    assert result.filing_enabled is False and result.dry_run is True
    serialized = result.model_dump_json()
    assert "222334444" not in serialized and "DO NOT RETURN" not in serialized
    assert len(calls) == 2
    token_url, token_args = calls[0]
    assert token_url == provider.TOKEN_URL
    assert token_args["data"]["client_secret"] == "sandbox-secret"
    form_url, form_args = calls[1]
    assert form_url.endswith("/1099/forms/$bulk-upsert")
    assert form_args["params"] == {"dryRun": "true"}
    form = form_args["json"]["forms"][0]
    assert form["type"] == "1099-NEC"
    assert form["issuerId"] == "sandbox-issuer"
    assert form["tin"] == "222334444"
    assert form["nonemployeeCompensation"] == 2500.0
    assert form["federalEfileDate"] is None
    assert form["stateEfileDate"] is None
    assert form["recipientEdeliveryDate"] is None
    assert form["postalMail"] is False
    assert form["tinMatch"] is False
    assert form["addressVerification"] is False
    audit = db.query(AuditLog).filter(
        AuditLog.entity_type == "tax_1099_review",
        AuditLog.action == "provider_sandbox_dry_run",
    ).one()
    assert "222334444" not in (audit.new_value or "")
    assert "sandbox-secret" not in (audit.new_value or "")


def test_avalara_sandbox_misc_rents_dry_run_uses_verified_field_and_never_schedules(ctx, monkeypatch):
    from app.schemas.tax_1099_review import Tax1099ProviderDryRunIn
    from app.services import tax_1099_provider as provider

    db, admin = ctx["db"], ctx["admin"]
    tax_profiles.upsert_tax_profile(
        db, current_user=admin,
        payload=_full_tax_profile(ctx, ctx["payer"], "111223333"),
    )
    tax_profiles.upsert_tax_profile(
        db, current_user=admin,
        payload=_full_tax_profile(ctx, ctx["owner_profile"], "333445555", w9=True),
    )
    item = service.prepare_review(
        db, current_user=admin,
        payload=nec(
            ctx, idempotency_key="provider-sandbox-misc-2026",
            form_type="1099-MISC", income_category="RENTS",
            recipient_profile_id=ctx["owner_profile"].id,
        ),
    )
    service.mark_reviewed(db, current_user=admin, record_id=item.id)
    service.approve_review(db, current_user=admin, record_id=item.id, payload=approval())
    monkeypatch.setattr(settings, "TAX_1099_PROVIDER", "avalara_sandbox")
    monkeypatch.setattr(settings, "AVALARA_1099_CLIENT_ID", "sandbox-client")
    monkeypatch.setattr(settings, "AVALARA_1099_CLIENT_SECRET", "sandbox-secret")
    monkeypatch.setattr(settings, "AVALARA_1099_ISSUER_ID", "sandbox-issuer")
    monkeypatch.setattr(settings, "AVALARA_1099_API_VERSION", "2.0.0")

    calls = []
    class Fake:
        def __init__(self, status, body):
            self.status_code = status
            self._body = body
            self.text = body
        def json(self):
            return json.loads(self._body)

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        if url == provider.TOKEN_URL:
            return Fake(200, json.dumps({"access_token": "redacted-token"}))
        return Fake(200, json.dumps({
            "tin": "333445555", "recipientName": "DO NOT RETURN",
            "validation": "accepted",
        }))

    monkeypatch.setattr(provider.requests, "post", fake_post)
    result = provider.validate_avalara_sandbox_dry_run(
        db, current_user=admin, record_id=item.id,
        payload=Tax1099ProviderDryRunIn(confirm_external_tax_data_sandbox=True),
    )
    assert result.validated is True
    assert result.submission_status == "NOT_SUBMITTED"
    assert result.filing_enabled is False
    raw = result.model_dump_json()
    assert "333445555" not in raw and "DO NOT RETURN" not in raw
    assert len(calls) == 2
    form_args = calls[1][1]
    assert form_args["params"] == {"dryRun": "true"}
    assert form_args["json"]["type"] == "1099-MISC"
    form = form_args["json"]["forms"][0]
    assert form["type"] == "1099-MISC"
    assert form["rents"] == 2500.0
    assert "nonemployeeCompensation" not in form
    assert form["federalEfileDate"] is None
    assert form["stateEfileDate"] is None
    assert form["recipientEdeliveryDate"] is None
    assert form["postalMail"] is False
    assert form["tinMatch"] is False
    assert form["addressVerification"] is False
    audit = db.query(AuditLog).filter(
        AuditLog.entity_type == "tax_1099_review",
        AuditLog.action == "provider_sandbox_dry_run",
    ).one()
    assert "333445555" not in (audit.new_value or "")
    assert "sandbox-secret" not in (audit.new_value or "")



def test_provider_status_is_redacted_scoped_and_no_store(ctx, monkeypatch):
    from fastapi import Response
    from app.routers import tax_1099_reviews as review_routes
    from app.services import tax_1099_provider as provider

    db, admin = ctx["db"], ctx["admin"]
    response = Response()
    disabled = review_routes.read_provider_status(response, db=db, current_user=admin)
    assert response.headers["cache-control"] == "no-store"
    assert disabled.provider == "DISABLED"
    assert disabled.configured is False
    assert disabled.filing_enabled is False
    assert disabled.supported_forms == []

    monkeypatch.setattr(settings, "TAX_1099_PROVIDER", "avalara_sandbox")
    monkeypatch.setattr(settings, "AVALARA_1099_CLIENT_ID", "private-client")
    monkeypatch.setattr(settings, "AVALARA_1099_CLIENT_SECRET", "private-secret")
    monkeypatch.setattr(settings, "AVALARA_1099_ISSUER_ID", "private-issuer")
    monkeypatch.setattr(settings, "AVALARA_1099_API_VERSION", "2.0.0")
    enabled = provider.provider_status(db, current_user=admin)
    assert enabled.provider == "AVALARA_SANDBOX"
    assert enabled.configured is True
    assert enabled.supported_forms == ["1099-NEC", "1099-MISC"]
    raw = enabled.model_dump_json()
    for secret in ("private-client", "private-secret", "private-issuer"):
        assert secret not in raw

    with pytest.raises(HTTPException) as exc:
        provider.provider_status(db, current_user=ctx["vendor"])
    assert exc.value.status_code == 403
