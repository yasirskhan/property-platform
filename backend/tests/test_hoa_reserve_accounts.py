"""HOA reserve mappings are read-only book references, not reserve transfers."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, Response
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import init_db  # noqa: F401
from app.core.database import Base
from app.models.audit_log import AuditLog
from app.models.bank_account import BankAccount
from app.models.charge import Charge
from app.models.gl_account import GLAccount
from app.models.gl_entry import GLEntry
from app.models.gl_transaction import GLTransaction
from app.models.hoa_reserve_account import HOAReserveAccount
from app.models.lease import Lease, RentInvoice
from app.models.property import Property, PropertyAssignment
from app.models.user import Organization, User, UserRole
from app.routers import hoa_associations as hoa
from app.routers import hoa_reserve_accounts as api
from app.schemas.hoa_association import HOAAssociationIn
from app.schemas.hoa_reserve_account import HOAReserveIn
from app.services.entity_notes import _model_for_table


@pytest.fixture(autouse=True)
def grants(monkeypatch):
    monkeypatch.setattr(hoa, "permission_allows_user", lambda *a, **kw: True)
    monkeypatch.setattr(hoa, "resolve_customer_features", lambda *a, **kw: [
        SimpleNamespace(key=hoa.FEATURE_KEY, allowed=True)
    ])
    monkeypatch.setattr(api, "permission_allows_user", lambda *a, **kw: True)


def _db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _seed(db):
    org = Organization(name="HOA Reserve A", slug="hoa-reserve-a")
    other = Organization(name="HOA Reserve B", slug="hoa-reserve-b")
    db.add_all([org, other]); db.flush()
    users = []
    for o, role, label in (
        (org, UserRole.ADMIN, "admin"), (org, UserRole.OWNER, "owner"),
        (org, UserRole.MANAGER, "manager"), (org, UserRole.TENANT, "tenant"),
        (other, UserRole.ADMIN, "foreign"),
    ):
        user = User(
            organization_id=o.id, role=role, first_name=label,
            last_name="Reserve", email=f"hoa-reserve-{label}@example.test",
            hashed_password="x", is_active=True,
        )
        db.add(user); users.append(user)
    db.flush()
    props = []
    for scope, label in (
        (org, "Assigned"), (org, "Other property"), (other, "Foreign"),
    ):
        prop = Property(
            organization_id=scope.id, name=label, address_line1="1 Main",
            city="Cleveland", state="OH", zip_code="44113", is_active=True,
        )
        db.add(prop); props.append(prop)
    db.flush()
    db.add(PropertyAssignment(
        property_id=props[0].id, user_id=users[2].id,
        role=UserRole.MANAGER, is_active=True,
    ))
    cash = GLAccount(
        organization_id=org.id, gl_number="1188",
        name="Recorded reserve cash GL", account_type="ASSET",
        include_on_cash_flow=True, is_active=True,
    )
    offset = GLAccount(
        organization_id=org.id, gl_number="3900",
        name="Offset for test", account_type="EQUITY", is_active=True,
    )
    another = GLAccount(
        organization_id=org.id, gl_number="1199",
        name="Other reserve cash GL", account_type="ASSET",
        include_on_cash_flow=True, is_active=True,
    )
    foreign_gl = GLAccount(
        organization_id=other.id, gl_number="1188",
        name="Other org cash", account_type="ASSET",
        include_on_cash_flow=True, is_active=True,
    )
    db.add_all([cash, offset, another, foreign_gl]); db.flush()
    bank = BankAccount(
        organization_id=org.id, name="Staff reserve bank",
        gl_account_id=cash.id, account_type="ESCROW",
        bank_name="Sensitive bank provider", routing_number="123456789",
        account_number="12345678901234", is_active=True,
    )
    wrong = BankAccount(
        organization_id=org.id, name="Different cash bank",
        gl_account_id=another.id, account_type="OPERATING",
        routing_number="00001111", account_number="SECRETACCOUNT",
        is_active=True,
    )
    db.add_all([bank, wrong])
    db.commit()
    assoc = hoa.create_association(
        HOAAssociationIn(name="Recorded HOA", property_ids=[props[0].id, props[1].id]),
        db=db, current_user=users[0],
    )
    return users, props, assoc, cash, offset, another, foreign_gl, bank, wrong


def _post_fixture(db, *, org_id, cash, offset, prop_id, debit, credit, d=date(2026, 9, 1), reversal=False):
    """Create representative already-posted balanced GL for READ tests only."""
    tr = GLTransaction(
        organization_id=org_id, transaction_date=d,
        transaction_type="REVERSAL" if reversal else "JOURNAL_ENTRY",
        is_reversed=False,
    )
    db.add(tr); db.flush()
    amount = Decimal(str(debit or credit))
    db.add_all([
        GLEntry(
            organization_id=org_id, transaction_id=tr.id,
            gl_account_id=cash.id, property_id=prop_id,
            debit=Decimal(str(debit)), credit=Decimal(str(credit)),
        ),
        GLEntry(
            organization_id=org_id, transaction_id=tr.id,
            gl_account_id=offset.id, property_id=prop_id,
            debit=Decimal(str(credit)), credit=Decimal(str(debit)),
        ),
    ])
    db.commit()


def _payload(prop, cash, bank=None):
    return HOAReserveIn(
        property_id=prop.id, gl_account_id=cash.id,
        bank_account_id=bank.id if bank is not None else None,
    )


def _finances(db):
    return (
        db.query(Charge).count(), db.query(Lease).count(),
        db.query(RentInvoice).count(), db.query(GLTransaction).count(),
        db.query(GLEntry).count(),
    )


def test_reserve_mapping_and_actual_book_balances_are_not_legal_reserves():
    db, engine = _db()
    try:
        (admin, owner, manager, tenant, foreign), (assigned, other_prop, outside), assoc, cash, offset, another, foreign_gl, bank, wrong = _seed(db)
        _post_fixture(db, org_id=admin.organization_id, cash=cash, offset=offset,
                      prop_id=assigned.id, debit="1000.00", credit="0.00")
        _post_fixture(db, org_id=admin.organization_id, cash=cash, offset=offset,
                      prop_id=None, debit="75.00", credit="0.00")
        _post_fixture(db, org_id=admin.organization_id, cash=cash, offset=offset,
                      prop_id=other_prop.id, debit="40.00", credit="0.00")
        _post_fixture(db, org_id=admin.organization_id, cash=cash, offset=offset,
                      prop_id=assigned.id, debit="0.00", credit="20.00",
                      d=date(2026, 9, 2), reversal=True)
        before = _finances(db)
        settings = api.put_reserve(
            assoc.id, _payload(assigned, cash, bank),
            db=db, current_user=admin,
        )
        assert settings.status == "STAFF_MAPPED_UNVERIFIED"
        assert settings.posting_enabled is False
        assert settings.gl_number == "1188"
        assert settings.bank_display_name == bank.name
        assert bank.routing_number not in str(settings.model_dump())
        assert bank.account_number not in str(settings.model_dump())
        read = api.get_reserve(
            assoc.id, Response(), assigned.id, db=db, current_user=manager,
        )
        assert read.id == settings.id
        options = api.reserve_options(
            assoc.id, Response(), assigned.id, db=db, current_user=owner,
        )
        assert [v.gl_account_id for v in options] == [cash.id]
        assert bank.account_number not in str([x.model_dump() for x in options])
        response = Response()
        result = api.reserve_book(
            assoc.id, response, assigned.id, date(2026, 9, 2),
            db=db, current_user=owner,
        )
        assert response.headers["cache-control"] == "no-store"
        assert result.account_wide_book_balance == Decimal("1095.00")
        assert result.property_tagged_book_balance == Decimal("980.00")
        assert result.unallocated_or_other_property_balance == Decimal("115.00")
        assert result.attribution_status == "OTHER_OR_UNTAGGED_POSTINGS_PRESENT"
        assert result.bank_statement_reconciled is False
        assert result.legal_reserve_ownership_verified is False
        early = api.reserve_book(
            assoc.id, Response(), assigned.id, date(2026, 8, 31),
            db=db, current_user=admin,
        )
        assert early.account_wide_book_balance == Decimal("0")
        with pytest.raises(HTTPException) as denied:
            api.reserve_book(
                assoc.id, Response(), assigned.id, date(2026, 9, 2),
                db=db, current_user=manager,
            )
        assert denied.value.status_code == 403
        assert _finances(db) == before
        assert "123456789" not in str(result.model_dump())
        assert "SECRETACCOUNT" not in str(result.model_dump())
        assert db.query(AuditLog).filter(AuditLog.entity_type=="hoa_reserve_account").count() == 1
    finally:
        db.close(); engine.dispose()


def test_reserve_mismatch_scope_duplicate_and_actor_revocation(monkeypatch):
    db, engine = _db()
    try:
        (admin, owner, manager, tenant, foreign), (assigned, other_prop, outside), assoc, cash, offset, another, foreign_gl, bank, wrong = _seed(db)
        for prop, gl, b in (
            (outside, cash, bank), (assigned, foreign_gl, None),
            (assigned, offset, None), (assigned, cash, wrong),
        ):
            with pytest.raises(HTTPException):
                api.put_reserve(assoc.id, _payload(prop, gl, b),
                                db=db, current_user=admin)
        for actor in (manager, tenant, foreign):
            with pytest.raises(HTTPException):
                api.put_reserve(assoc.id, _payload(assigned, cash, bank),
                                db=db, current_user=actor)
        first = api.put_reserve(
            assoc.id, _payload(assigned, cash, bank), db=db, current_user=admin,
        )
        with pytest.raises(HTTPException) as e:
            api.put_reserve(assoc.id, _payload(other_prop, cash),
                            db=db, current_user=owner)
        assert e.value.status_code == 409
        with pytest.raises(HTTPException) as e:
            api.put_reserve(assoc.id, _payload(assigned, another),
                            db=db, current_user=owner)
        assert e.value.status_code == 409
        for actor, prop in ((manager, other_prop), (foreign, assigned)):
            with pytest.raises(HTTPException):
                api.get_reserve(assoc.id, Response(), prop.id,
                                db=db, current_user=actor)
        monkeypatch.setattr(api, "permission_allows_user",
                            lambda db, *, user, menu_key: menu_key != "ACCOUNTING.GL_ACCOUNTS")
        with pytest.raises(HTTPException) as e:
            api.get_reserve(assoc.id, Response(), assigned.id,
                            db=db, current_user=admin)
        assert e.value.status_code == 403
        monkeypatch.setattr(api, "permission_allows_user", lambda *a, **k: True)
        monkeypatch.setattr(hoa, "resolve_customer_features", lambda *a, **k: [])
        with pytest.raises(HTTPException) as e:
            api.get_reserve(assoc.id, Response(), assigned.id,
                            db=db, current_user=admin)
        assert e.value.status_code == 404
        assert db.get(HOAReserveAccount, first.id).is_active
        assert db.query(Charge).count() == db.query(GLTransaction).count() == 0
        with pytest.raises(HTTPException) as e:
            _model_for_table("hoa_reserve_accounts")
        assert e.value.status_code == 404
    finally:
        db.rollback(); db.close(); engine.dispose()


def test_reserve_unlink_archives_mapping_and_relink_requires_revalidation():
    db, engine = _db()
    try:
        (admin, owner, manager, tenant, foreign), (assigned, other_prop, outside), assoc, cash, offset, another, foreign_gl, bank, wrong = _seed(db)
        saved = api.put_reserve(
            assoc.id, _payload(assigned, cash, bank), db=db, current_user=admin,
        )
        hoa.update_association(
            assoc.id, HOAAssociationIn(
                name="Recorded HOA", property_ids=[other_prop.id],
            ), db=db, current_user=owner,
        )
        assert db.get(HOAReserveAccount, saved.id).is_active is False
        hoa.update_association(
            assoc.id, HOAAssociationIn(
                name="Recorded HOA", property_ids=[assigned.id, other_prop.id],
            ), db=db, current_user=owner,
        )
        assert api.get_reserve(
            assoc.id, Response(), assigned.id, db=db, current_user=admin,
        ) is None
        restored = api.put_reserve(
            assoc.id, _payload(assigned, cash, bank), db=db, current_user=owner,
        )
        assert restored.id == saved.id and restored.posting_enabled is False
        bank.is_active = False
        db.flush()
        old = api.get_reserve(
            assoc.id, Response(), assigned.id, db=db, current_user=owner,
        )
        assert old.mapping_status == "ARCHIVED_MAPPING_NEEDS_REVIEW"
        with pytest.raises(HTTPException):
            api.put_reserve(
                assoc.id, _payload(assigned, cash, bank),
                db=db, current_user=admin,
            )
        assert db.query(Charge).count() == db.query(GLTransaction).count() == 0
    finally:
        db.rollback(); db.close(); engine.dispose()
