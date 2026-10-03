"""Ledger-sourced security deposit liability detail and authorization boundaries."""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, Response
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import init_db  # noqa: F401
from app.core.database import Base
from app.models.accounting_key_account import AccountingKeyAccount
from app.models.gl_account import GLAccount
from app.models.gl_entry import GLEntry
from app.models.gl_transaction import GLTransaction
from app.models.property import Property, PropertyAssignment, Unit
from app.models.user import Organization, User, UserRole
from app.routers import reporting as router
from app.services.report_catalog import REPORT_CATALOG
from app.services.report_delivery import ReportDeliveryError, build_report_payload, report_csv_bytes


REPORT_KEY = "tenant.security_deposit_funds_detail"


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _seed(db):
    org = Organization(name="Deposits Org", slug="deposits-org")
    foreign_org = Organization(name="Foreign Deposits", slug="foreign-deposits")
    db.add_all([org, foreign_org])
    db.flush()
    def person(organization, role, name):
        user = User(
            organization_id=organization.id,
            first_name=name, last_name="Person",
            email=f"{name.lower()}@deposit-example.test",
            hashed_password="x", role=role, is_active=True,
        )
        db.add(user)
        db.flush()
        return user
    admin = person(org, UserRole.ADMIN, "Admin")
    manager = person(org, UserRole.MANAGER, "Manager")
    tenant = person(org, UserRole.TENANT, "Tenant")
    def property_(organization, name):
        prop = Property(
            organization_id=organization.id, name=name,
            address_line1="100 Test Ave", city="Cleveland", state="OH",
            zip_code="44113", is_active=True,
        )
        db.add(prop)
        db.flush()
        return prop
    assigned = property_(org, "=Formula Property")
    unassigned = property_(org, "Unassigned")
    foreign = property_(foreign_org, "Foreign")
    db.add(PropertyAssignment(
        property_id=assigned.id, user_id=manager.id,
        role=UserRole.MANAGER, is_active=True,
    ))
    db.flush()
    unit = Unit(property_id=assigned.id, unit_number="A", is_active=True)
    db.add(unit)
    db.flush()
    def account(organization, code, name, kind):
        item = GLAccount(
            organization_id=organization.id, gl_number=code,
            name=name, account_type=kind, is_active=True,
        )
        db.add(item)
        db.flush()
        return item
    security = account(org, "2101", "Security Deposits", "LIABILITY")
    owner_held = account(org, "2180", "Owner Held Deposits", "LIABILITY")
    cash = account(org, "1150", "Operating Cash", "ASSET")
    foreign_security = account(foreign_org, "2101", "Foreign Deposits", "LIABILITY")
    db.add(AccountingKeyAccount(
        organization_id=org.id, key_type="DEPOSIT_LIABILITY",
        gl_account_id=owner_held.id,
    ))
    db.flush()

    def movement(acct, *, property_id, unit_id=None, amount=100,
                 increase=True, when=None, organization_id=None):
        oid = organization_id if organization_id is not None else org.id
        txn = GLTransaction(
            organization_id=oid, transaction_date=when or date.today(),
            transaction_type="JOURNAL_ENTRY", reference_number="REF-1",
        )
        db.add(txn)
        db.flush()
        entry = GLEntry(
            organization_id=oid, transaction_id=txn.id, gl_account_id=acct.id,
            property_id=property_id, unit_id=unit_id,
            debit=Decimal(0 if increase else amount),
            credit=Decimal(amount if increase else 0),
        )
        db.add(entry)
        # Add the cash-side counter-entry so fixtures preserve balanced GL.
        db.add(GLEntry(
            organization_id=oid, transaction_id=txn.id,
            gl_account_id=cash.id if oid == org.id else foreign_security.id,
            property_id=property_id,
            debit=Decimal(amount if increase else 0),
            credit=Decimal(0 if increase else amount),
        ))
        db.flush()
        return entry, txn
    original, original_txn = movement(
        security, property_id=assigned.id, unit_id=unit.id,
        amount=1000, when=date.today() - timedelta(days=10),
    )
    reversal, reversal_txn = movement(
        security, property_id=assigned.id, unit_id=unit.id,
        amount=200, increase=False, when=date.today() - timedelta(days=2),
    )
    original_txn.is_reversed = True  # Historical original remains included.
    reversal_txn.reversal_of_id = original_txn.id
    owner_entry, _ = movement(owner_held, property_id=assigned.id, amount=350)
    unassigned_entry, _ = movement(security, property_id=unassigned.id, amount=75)
    unallocated_entry, _ = movement(security, property_id=None, amount=40)
    future_entry, _ = movement(security, property_id=assigned.id,
                               amount=999, when=date.today() + timedelta(days=1))
    foreign_entry, _ = movement(
        foreign_security, property_id=foreign.id, amount=8888,
        organization_id=foreign_org.id,
    )
    db.commit()
    return {
        "admin": admin, "manager": manager, "tenant": tenant,
        "assigned": assigned, "unassigned": unassigned, "foreign": foreign,
        "original": original, "reversal": reversal, "owner": owner_entry,
        "unassigned_entry": unassigned_entry, "unallocated": unallocated_entry,
        "future": future_entry, "foreign_entry": foreign_entry,
    }


def _report(db, user, **params):
    return build_report_payload(
        db, organization_id=user.organization_id, report_key=REPORT_KEY,
        parameters=params, current_user=user,
    )


def test_liability_credits_debits_reversal_custom_account_and_org_scope():
    db, engine = _session()
    try:
        s = _seed(db)
        payload = _report(db, s["admin"])
        ids = {row[5] for row in payload.rows}
        assert ids == {s[k].id for k in (
            "original", "reversal", "owner", "unassigned_entry", "unallocated",
        )}
        assert sum((row[9] for row in payload.rows), Decimal(0)) == Decimal("1265")
        assert payload.rows[0][9] == Decimal("1000")
        assert any(row[9] == Decimal("-200") for row in payload.rows)
        assert any(row[3] == "2180" for row in payload.rows)
        assert any(row[10] == "Unallocated; review" and row[11] == ""
                   for row in payload.rows)
        assert all(row[5] != s["future"].id for row in payload.rows)
        assert all(row[5] != s["foreign_entry"].id for row in payload.rows)
        csv_text = report_csv_bytes(payload).decode("utf-8-sig")
        assert "'=Formula Property" in csv_text
        assert "Foreign Deposits" not in csv_text
        assert "8888" not in csv_text
        # A historical cutoff excludes a reversal posted after the date.
        historical = _report(db, s["admin"], as_of=(date.today() - timedelta(days=5)).isoformat())
        assert {row[5] for row in historical.rows} == {s["original"].id}
        assert sum((row[9] for row in historical.rows), Decimal(0)) == Decimal("1000")
    finally:
        db.close()
        engine.dispose()


def test_manager_can_only_see_assigned_tagged_liabilities():
    db, engine = _session()
    try:
        s = _seed(db)
        visible = _report(db, s["manager"])
        assert {r[5] for r in visible.rows} == {
            s["original"].id, s["reversal"].id, s["owner"].id,
        }
        assert sum((r[9] for r in visible.rows), Decimal(0)) == Decimal("1150")
        for prop in (s["unassigned"], s["foreign"]):
            with pytest.raises(ReportDeliveryError, match="Property not found"):
                _report(db, s["manager"], property_id=prop.id)
        own = _report(db, s["manager"], property_id=s["assigned"].id)
        assert len(own.rows) == 3
        with pytest.raises(ReportDeliveryError, match="Property not found"):
            _report(db, s["admin"], property_id=s["foreign"].id)
    finally:
        db.close()
        engine.dispose()


def test_invalid_filters_actor_scope_and_nonstaff_fail_closed():
    db, engine = _session()
    try:
        s = _seed(db)
        for parameters in (
            {"sql": "select * from gl_entries"},
            {"property_id": "0"}, {"property_id": "invalid"},
            {"as_of": "invalid"},
            {"as_of": (date.today() + timedelta(days=1)).isoformat()},
        ):
            with pytest.raises(ReportDeliveryError):
                _report(db, s["admin"], **parameters)
        with pytest.raises(ReportDeliveryError):
            _report(db, s["tenant"])
        with pytest.raises(ReportDeliveryError):
            build_report_payload(
                db, organization_id=s["admin"].organization_id,
                report_key=REPORT_KEY, parameters={},
            )
        with pytest.raises(ReportDeliveryError):
            build_report_payload(
                db, organization_id=s["foreign"].organization_id,
                report_key=REPORT_KEY, parameters={}, current_user=s["admin"],
            )
        s["admin"].is_active = False
        db.commit()
        with pytest.raises(ReportDeliveryError):
            _report(db, s["admin"])
    finally:
        db.close()
        engine.dispose()


def test_catalog_preview_csv_email_and_permission_revocation(monkeypatch):
    db, engine = _session()
    try:
        s = _seed(db)
        admin = s["admin"]
        item = next(x for x in REPORT_CATALOG if x.key == REPORT_KEY)
        assert item.tier == "STANDARD" and item.href == "/dashboard/reporting/security-deposits"
        assert router.REPORT_PERMISSIONS[REPORT_KEY] == "ACCOUNTING.GL_ACCOUNTS"
        monkeypatch.setattr(router, "permission_allows_user", lambda *a, **kw: True)
        monkeypatch.setattr(
            router, "resolve_customer_features",
            lambda *a, **kw: [
                SimpleNamespace(key=router.EXPORT_FEATURE_KEY, allowed=True)
            ],
        )
        response = Response()
        request = SimpleNamespace(query_params={})
        preview = router.preview_security_deposit_funds(
            request, response, db=db, current_user=admin,
        )
        assert preview["total"] == 5
        assert response.headers["cache-control"] == "no-store"
        exported = router.export_report_csv(REPORT_KEY, request, db=db, current_user=admin)
        assert b"Liability Credit" in exported.body
        sent = {}
        monkeypatch.setattr(router, "send_email", lambda **kw: sent.update(kw))
        emailed = router.email_report(
            REPORT_KEY,
            router.ReportEmailIn(recipient="recipient@example.com", parameters={}),
            db=db, current_user=admin,
        )
        assert emailed.sent
        assert sent["organization_id"] == admin.organization_id
        assert b"Liability Credit" in sent["attachments"][0][1]
        monkeypatch.setattr(
            router, "resolve_customer_features",
            lambda *a, **kw: [
                SimpleNamespace(key=router.EXPORT_FEATURE_KEY, allowed=False)
            ],
        )
        with pytest.raises(HTTPException) as exc:
            router.preview_security_deposit_funds(
                request, Response(), db=db, current_user=admin,
            )
        assert exc.value.status_code == 404
        monkeypatch.setattr(
            router, "resolve_customer_features",
            lambda *a, **kw: [
                SimpleNamespace(key=router.EXPORT_FEATURE_KEY, allowed=True)
            ],
        )
        monkeypatch.setattr(
            router, "permission_allows_user",
            lambda db, *, user, menu_key: menu_key == "REPORTING.ALL",
        )
        with pytest.raises(HTTPException) as exc:
            router.export_report_csv(REPORT_KEY, request, db=db, current_user=admin)
        assert exc.value.status_code == 403
    finally:
        db.close()
        engine.dispose()
