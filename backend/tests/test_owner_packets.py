from __future__ import annotations

import json
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
from app.models.owner_statement import OwnerPacketSettings, OwnerStatement
from app.models.property import Property, PropertyAssignment
from app.models.user import Organization, User, UserRole
from app.routers import owner_packets as router
from app.schemas.owner_packet import OwnerPacketSendIn
from app.services import owner_packets as service


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _seed(db):
    a = Organization(name="Packet Org One", slug="packets-one")
    b = Organization(name="Packet Org Two", slug="packets-two")
    db.add_all([a, b]); db.flush()
    users = []
    for org, role, email in (
        (a, UserRole.ADMIN, "packet-admin@example.com"),
        (a, UserRole.MANAGER, "packet-manager@example.com"),
        (a, UserRole.OWNER, "packet-owner@example.com"),
        (b, UserRole.ADMIN, "packet-other-admin@example.com"),
        (b, UserRole.OWNER, "packet-other-owner@example.com"),
    ):
        user = User(organization_id=org.id, role=role, email=email,
                    first_name="Packet", last_name="Recipient",
                    is_active=True, hashed_password="x")
        db.add(user); users.append(user)
    db.flush()
    props = []
    for org, name in ((a, "=First Property"), (a, "Second"), (b, "Private")):
        row = Property(organization_id=org.id, name=name,
                       address_line1="100 Packet Ave", city="Cleveland",
                       state="OH", zip_code="44113", is_active=True)
        db.add(row); db.flush(); props.append(row)
    db.add(PropertyAssignment(property_id=props[0].id, user_id=users[1].id,
                              role=UserRole.MANAGER, is_active=True))
    def statement(org, owner, prop):
        frozen = [{
            "property_id": prop.id, "property_name": prop.name,
            "ownership_pct": "100", "beginning_cash": "100.00",
            "ending_cash": "175.00", "income": "100.00", "expense": "25.00",
            "net": "75.00", "required_reserves": "50.00",
            "prepaid_rent": "10.00", "available_cash": "115.00",
            "transactions": [{
                "date": "2026-08-12", "description": "=Formula",
                "income": "100.00", "expense": "0.00",
                "running_balance": "175.00",
            }],
        }]
        row = OwnerStatement(organization_id=org.id, owner_id=owner.id,
                             period_start=date(2026, 8, 1), period_end=date(2026, 8, 31),
                             property_data=json.dumps(frozen), is_active=True)
        db.add(row); db.flush()
        return row
    first = statement(a, users[2], props[0])
    other = statement(b, users[4], props[2])
    db.add(OwnerPacketSettings(organization_id=a.id,
        included_reports=json.dumps(["OWNER_STATEMENT", "PROPERTY_CASH_SUMMARY"]),
        cover_message="Your frozen statement is enclosed.", email_owner=True))
    db.commit()
    return (*users, *props, first, other)


@pytest.fixture(autouse=True)
def permissions(monkeypatch):
    monkeypatch.setattr(service, "permission_allows_user", lambda *a, **kw: True)
    monkeypatch.setattr(service, "resolve_customer_features", lambda *a, **kw: [
        SimpleNamespace(key=name, allowed=True) for name in (
            service.FEATURE_CUSTOMIZER, service.FEATURE_EXPORT, service.FEATURE_CASH
        )
    ])


def test_scoped_frozen_csv_packet_with_formula_escaping_and_current_owner():
    db, engine = _session()
    try:
        admin, manager, owner, other_admin, other_owner, prop, second, private, first, foreign = _seed(db)
        packet = service.build_packet(db, actor=admin, statement_id=first.id)
        assert packet.preview.recipient_email == owner.email
        assert packet.preview.email_enabled
        assert packet.preview.attachment_format == "CSV"
        assert len(packet.files) == 2
        assert all(kind == "text/csv" for _, _, kind in packet.files)
        assert b"'=Formula" in packet.files[0][1]
        assert b"'=First Property" in packet.files[1][1]
        assert b"115.00" in packet.files[1][1]
        assert b"Private" not in b"".join(content for _, content, _ in packet.files)
        assert len(packet.preview.review_token) == 64
        assert service.build_packet(db, actor=manager, statement_id=first.id).preview.owner_id == owner.id
        for actor, statement_id in ((admin, foreign.id), (other_admin, first.id),
                                    (owner, first.id)):
            with pytest.raises(HTTPException):
                service.build_packet(db, actor=actor, statement_id=statement_id)
    finally:
        db.close(); engine.dispose()


def test_manager_must_have_every_snapshot_property_assignment():
    db, engine = _session()
    try:
        admin, manager, owner, other_admin, other_owner, prop, second, private, first, foreign = _seed(db)
        frozen = json.loads(first.property_data)
        frozen.append({**frozen[0], "property_id": second.id, "property_name": second.name})
        first.property_data = json.dumps(frozen)
        db.commit()
        with pytest.raises(HTTPException) as exc:
            service.build_packet(db, actor=manager, statement_id=first.id)
        assert exc.value.status_code == 404
        assert len(service.build_packet(db, actor=admin, statement_id=first.id).files) == 2
    finally:
        db.close(); engine.dispose()


def test_confirmed_email_rechecks_settings_recipient_and_signed_preview(monkeypatch):
    db, engine = _session()
    try:
        admin, manager, owner, other_admin, other_owner, prop, second, private, first, foreign = _seed(db)
        seen = []
        monkeypatch.setattr(router, "send_email", lambda **kw: seen.append(kw))
        preview = router.preview_owner_packet(first.id, Response(), db=db, current_user=admin)
        for value in (
            OwnerPacketSendIn(confirm_recipient=False, confirm_snapshot_reviewed=True,
                              review_token=preview.review_token),
            OwnerPacketSendIn(confirm_recipient=True, confirm_snapshot_reviewed=False,
                              review_token=preview.review_token),
        ):
            with pytest.raises(HTTPException) as exc:
                router.email_owner_packet(first.id, value, Response(), db=db, current_user=admin)
            assert exc.value.status_code == 422
        assert not seen
        owner.email = "packet-owner-renamed@example.com"
        db.commit()
        with pytest.raises(HTTPException) as exc:
            router.email_owner_packet(first.id, OwnerPacketSendIn(
                confirm_recipient=True, confirm_snapshot_reviewed=True,
                review_token=preview.review_token), Response(), db=db, current_user=admin)
        assert exc.value.status_code == 409
        current = router.preview_owner_packet(first.id, Response(), db=db, current_user=admin)
        done = router.email_owner_packet(first.id, OwnerPacketSendIn(
            confirm_recipient=True, confirm_snapshot_reviewed=True,
            review_token=current.review_token), Response(), db=db, current_user=admin)
        assert done.sent and done.recipient_email == owner.email
        assert len(seen) == 1 and seen[0]["to"] == owner.email
        assert len(seen[0]["attachments"]) == 2
        audit = db.query(AuditLog).filter_by(entity_type="owner_packet").one()
        assert audit.action == "emailed"
        assert owner.email not in (audit.new_value or "")
        assert "175.00" not in (audit.new_value or "")
    finally:
        db.close(); engine.dispose()


def test_no_delivery_if_owner_email_disabled_or_feature_revoked(monkeypatch):
    db, engine = _session()
    try:
        admin, manager, owner, other_admin, other_owner, prop, second, private, first, foreign = _seed(db)
        saved = db.get(OwnerPacketSettings, admin.organization_id)
        saved.email_owner = False
        db.commit()
        before = service.build_packet(db, actor=admin, statement_id=first.id)
        assert not before.preview.email_enabled
        with pytest.raises(HTTPException) as exc:
            router.email_owner_packet(first.id, OwnerPacketSendIn(
                confirm_recipient=True, confirm_snapshot_reviewed=True,
                review_token=before.preview.review_token), Response(), db=db, current_user=admin)
        assert exc.value.status_code == 403
        monkeypatch.setattr(service, "resolve_customer_features", lambda *a, **kw: [
            SimpleNamespace(key=service.FEATURE_CUSTOMIZER, allowed=True),
            SimpleNamespace(key=service.FEATURE_EXPORT, allowed=False),
            SimpleNamespace(key=service.FEATURE_CASH, allowed=True),
        ])
        with pytest.raises(HTTPException) as exc:
            service.build_packet(db, actor=admin, statement_id=first.id)
        assert exc.value.status_code == 404
        monkeypatch.setattr(service, "permission_allows_user",
                            lambda db, *, user, menu_key: menu_key == "REPORTING.ALL")
        with pytest.raises(HTTPException) as exc:
            service.build_packet(db, actor=admin, statement_id=first.id)
        assert exc.value.status_code == 403
    finally:
        db.close(); engine.dispose()


def test_configuration_change_or_corruption_fail_closed():
    db, engine = _session()
    try:
        admin, manager, owner, other_admin, other_owner, prop, second, private, first, foreign = _seed(db)
        previous = service.build_packet(db, actor=admin, statement_id=first.id).preview.review_token
        row = db.get(OwnerPacketSettings, admin.organization_id)
        row.included_reports = json.dumps(["OWNER_STATEMENT"])
        db.commit()
        fresh = service.build_packet(db, actor=admin, statement_id=first.id)
        assert fresh.preview.review_token != previous
        assert len(fresh.files) == 1
        row.included_reports = json.dumps(["INJECTED_REPORT"])
        db.commit()
        with pytest.raises(HTTPException) as exc:
            service.build_packet(db, actor=admin, statement_id=first.id)
        assert exc.value.status_code == 422
    finally:
        db.close(); engine.dispose()
