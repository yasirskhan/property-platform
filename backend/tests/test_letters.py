from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, Response
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import init_db  # noqa: F401
from app.core.database import Base
from app.models.audit_log import AuditLog
from app.models.lease import Lease, LeaseStatus
from app.models.letter_template import LetterTemplate
from app.models.property import Property, PropertyAssignment, Unit
from app.models.user import Organization, User, UserRole
from app.routers import letters as router
from app.schemas.letter import LetterTemplateIn, LetterSendIn
from app.services import letters as engine


def _session():
    db_engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=db_engine)
    return sessionmaker(bind=db_engine, expire_on_commit=False)(), db_engine


def _seed(db):
    a = Organization(name="One Properties", slug="letters-one")
    b = Organization(name="Other Company", slug="letters-two")
    db.add_all([a, b])
    db.flush()
    users = []
    for org, role, email in [
        (a, UserRole.ADMIN, "letters-admin@example.com"),
        (a, UserRole.MANAGER, "letters-manager@example.com"),
        (a, UserRole.TENANT, "letters-tenant@example.com"),
        (b, UserRole.ADMIN, "letters-other-admin@example.com"),
        (b, UserRole.TENANT, "letters-other-tenant@example.com"),
    ]:
        person = User(organization_id=org.id, role=role, is_active=True,
                      email=email, first_name="Tenant" if role == UserRole.TENANT else "Staff",
                      last_name="Recipient", hashed_password="x")
        db.add(person)
        users.append(person)
    db.flush()
    def lease(org, tenant, name, number):
        prop = Property(organization_id=org.id, name=name, address_line1=name+" Road",
                        city="Cleveland", state="OH", zip_code="44113",
                        is_active=True)
        db.add(prop)
        db.flush()
        unit = Unit(property_id=prop.id, unit_number=number, is_active=True)
        db.add(unit)
        db.flush()
        record = Lease(unit_id=unit.id, tenant_id=tenant.id,
                       start_date=date(2026, 1, 1), end_date=date(2027, 1, 1),
                       monthly_rent=Decimal("1000.00"), security_deposit=Decimal("900.00"),
                       status=LeaseStatus.ACTIVE)
        db.add(record)
        db.flush()
        return prop, record
    p1, l1 = lease(a, users[2], "First", "2B")
    p2, l2 = lease(a, users[2], "Unassigned", "3C")
    po, lo = lease(b, users[4], "Private", "9Z")
    db.add(PropertyAssignment(property_id=p1.id, user_id=users[1].id,
                              role=UserRole.MANAGER, is_active=True))
    db.commit()
    return (*users, p1, p2, po, l1, l2, lo)


@pytest.fixture(autouse=True)
def allow(monkeypatch):
    monkeypatch.setattr(engine, "permission_allows_user", lambda *a, **kw: True)
    monkeypatch.setattr(router, "resolve_customer_features", lambda *a, **kw: [
        SimpleNamespace(key="release.reporting.export", allowed=True)
    ])


def _payload(category="CUSTOM"):
    return LetterTemplateIn(
        title="Welcome", category=category,
        subject="Welcome {{tenant_name}}",
        body="Hello {{tenant_name}}\n{{property_name}} | {{unit_number}}\n{{organization_name}}",
    )


def test_text_allowlist_no_templates_expressions_or_html():
    engine.validate_letter("Hi {{tenant_name}}", "Hello {{property_name}}")
    for bad in ("{{tenant.password}}", "{{__class__}}", "{{tenant_name|safe}}",
                "{{tenant_name", "Hello <script>x</script>", "<p>Hi</p>",
                "{{tax_id}}", "bad\x00data"):
        with pytest.raises(HTTPException) as exc:
            engine.validate_letter("Subject", bad)
        assert exc.value.status_code == 422


def test_crud_preview_scoping_manager_assignment_and_audit():
    db, e = _session()
    try:
        admin, manager, tenant, other, other_tenant, p1, p2, po, l1, l2, lo = _seed(db)
        created = router.create_letter(_payload(), Response(), db=db, current_user=admin)
        assert created.title == "Welcome"
        assert router.list_letters(Response(), db=db, current_user=admin)[0].id == created.id
        assert router.list_letters(Response(), db=db, current_user=other) == []
        for actor in (other, tenant):
            with pytest.raises(HTTPException):
                router.get_letter(created.id, Response(), db=db, current_user=actor)
        preview = router.preview_letter(created.id, l1.id, Response(), db=db, current_user=manager)
        assert "Tenant Recipient" in preview.body
        assert "First" in preview.body
        assert preview.recipient_email == tenant.email
        for lease in (l2, lo):
            with pytest.raises(HTTPException) as exc:
                router.preview_letter(created.id, lease.id, Response(), db=db, current_user=manager)
            assert exc.value.status_code == 404
        with pytest.raises(HTTPException):
            router.update_letter(created.id, _payload(), Response(), db=db, current_user=manager)
        edited = router.update_letter(
            created.id, LetterTemplateIn(title="Updated", category="CUSTOM",
                subject="Changed", body="Dear {{tenant_name}}"),
            Response(), db=db, current_user=admin)
        assert edited.title == "Updated"
        router.delete_letter(created.id, db=db, current_user=admin)
        assert router.list_letters(Response(), db=db, current_user=admin) == []
        with pytest.raises(HTTPException) as exc:
            router.preview_letter(created.id, l1.id, Response(), db=db, current_user=admin)
        assert exc.value.status_code == 404
        assert db.query(LetterTemplate).count() == 1
        assert {a.action for a in db.query(AuditLog).filter_by(entity_type="letter_template")} == {"created", "updated", "deactivated"}
    finally:
        db.close()
        e.dispose()


def test_3_day_notice_draft_requires_explicit_legal_approval_and_no_cross_org_delivery(monkeypatch):
    db, e = _session()
    try:
        admin, manager, tenant, other, other_tenant, p1, p2, po, l1, l2, lo = _seed(db)
        created = router.create_letter(_payload("THREE_DAY_NOTICE"), Response(), db=db, current_user=admin)
        reviewed = router.preview_letter(created.id, l1.id, Response(), db=db, current_user=admin)
        seen = []
        monkeypatch.setattr(router, "send_email", lambda **kw: seen.append(kw))
        for payload in (
            LetterSendIn(lease_id=l1.id, confirm_recipient=False,
                         confirm_content_reviewed=True, confirm_legal_review=True,
                         review_token=reviewed.review_token),
            LetterSendIn(lease_id=l1.id, confirm_recipient=True,
                         confirm_content_reviewed=True, confirm_legal_review=False,
                         review_token=reviewed.review_token),
        ):
            with pytest.raises(HTTPException) as exc:
                router.send_letter(created.id, payload, Response(), db=db, current_user=admin)
            assert exc.value.status_code == 422
        assert not seen
        with pytest.raises(HTTPException) as exc:
            router.send_letter(created.id, LetterSendIn(
                lease_id=lo.id, confirm_recipient=True,
                confirm_content_reviewed=True, confirm_legal_review=True,
                review_token=reviewed.review_token),
                Response(), db=db, current_user=admin)
        assert exc.value.status_code == 404
        assert not seen
        result = router.send_letter(created.id, LetterSendIn(
            lease_id=l1.id, confirm_recipient=True,
            confirm_content_reviewed=True, confirm_legal_review=True,
            review_token=reviewed.review_token),
            Response(), db=db, current_user=admin)
        assert result.sent and result.recipient_email == tenant.email
        assert len(seen) == 1 and seen[0]["to"] == tenant.email
        assert seen[0]["organization_id"] == admin.organization_id
        assert "Tenant Recipient" in seen[0]["body"]
        log = db.query(AuditLog).filter_by(entity_type="letter_template", action="letter_emailed").one()
        assert "tenant_email" not in (log.new_value or "")
    finally:
        db.close()
        e.dispose()


def test_permission_revocation_and_delivery_gate(monkeypatch):
    db, e = _session()
    try:
        admin, manager, tenant, other, other_tenant, p1, p2, po, l1, l2, lo = _seed(db)
        created = router.create_letter(_payload(), Response(), db=db, current_user=admin)
        monkeypatch.setattr(router, "resolve_customer_features", lambda *a, **kw: [
            SimpleNamespace(key="release.reporting.export", allowed=False)
        ])
        with pytest.raises(HTTPException) as exc:
            router.preview_letter(created.id, l1.id, Response(), db=db, current_user=admin)
        assert exc.value.status_code == 404
        monkeypatch.setattr(engine, "permission_allows_user",
                            lambda db, *, user, menu_key: menu_key == "REPORTING.ALL")
        with pytest.raises(HTTPException) as exc:
            router.list_letters(Response(), db=db, current_user=admin)
        assert exc.value.status_code == 403
        admin.is_active = False
        db.commit()
        with pytest.raises(HTTPException):
            router.list_letters(Response(), db=db, current_user=admin)
    finally:
        db.close()
        e.dispose()


def test_template_rejects_cross_org_and_unscoped_lease():
    db, e = _session()
    try:
        admin, manager, tenant, other, other_tenant, p1, p2, po, l1, l2, lo = _seed(db)
        created = router.create_letter(_payload(), Response(), db=db, current_user=admin)
        with pytest.raises(HTTPException) as exc:
            router.update_letter(created.id, _payload(), Response(), db=db, current_user=other)
        assert exc.value.status_code == 404
        assert "Private" not in router.preview_letter(
            created.id, l1.id, Response(), db=db, current_user=admin).body
    finally:
        db.close()
        e.dispose()



def test_email_requires_exact_current_preview_content_and_recipient(monkeypatch):
    db, e = _session()
    try:
        admin, manager, tenant, other, other_tenant, p1, p2, po, l1, l2, lo = _seed(db)
        created = router.create_letter(_payload(), Response(), db=db, current_user=admin)
        first = router.preview_letter(created.id, l1.id, Response(), db=db, current_user=admin)
        assert len(first.review_token) == 64
        sent = []
        monkeypatch.setattr(router, "send_email", lambda **kw: sent.append(kw))
        def send(token):
            return router.send_letter(created.id, LetterSendIn(
                lease_id=l1.id, confirm_recipient=True, confirm_content_reviewed=True,
                review_token=token), Response(), db=db, current_user=admin)
        router.update_letter(created.id, LetterTemplateIn(
            title="Welcome", category="CUSTOM", subject="Changed {{tenant_name}}",
            body="Hello {{tenant_name}}"), Response(), db=db, current_user=admin)
        with pytest.raises(HTTPException) as exc:
            send(first.review_token)
        assert exc.value.status_code == 409
        assert not sent
        new = router.preview_letter(created.id, l1.id, Response(), db=db, current_user=admin)
        assert first.review_token != new.review_token
        tenant.email = "letters-tenant-renamed@example.com"
        db.commit()
        with pytest.raises(HTTPException) as exc:
            send(new.review_token)
        assert exc.value.status_code == 409
        assert not sent
        current = router.preview_letter(created.id, l1.id, Response(), db=db, current_user=admin)
        assert send(current.review_token).recipient_email == tenant.email
        assert len(sent) == 1
        with pytest.raises(HTTPException) as exc:
            router.send_letter(created.id, LetterSendIn(
                lease_id=l2.id, confirm_recipient=True,
                confirm_content_reviewed=True, review_token=current.review_token),
                Response(), db=db, current_user=admin)
        assert exc.value.status_code == 409
    finally:
        db.close()
        e.dispose()


def test_preview_token_is_bound_to_reviewing_staff_user():
    db, e = _session()
    try:
        admin, manager, tenant, other, other_tenant, p1, p2, po, l1, l2, lo = _seed(db)
        created = router.create_letter(_payload(), Response(), db=db, current_user=admin)
        admin_token = router.preview_letter(
            created.id, l1.id, Response(), db=db, current_user=admin).review_token
        manager_token = router.preview_letter(
            created.id, l1.id, Response(), db=db, current_user=manager).review_token
        assert admin_token != manager_token
    finally:
        db.close()
        e.dispose()
