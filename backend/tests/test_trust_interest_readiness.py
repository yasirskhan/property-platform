"""Trust interest review status cannot silently become an allocation or posting."""
from __future__ import annotations
from types import SimpleNamespace
import pytest
from fastapi import HTTPException, Response
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import init_db  # noqa: F401
from app.core.database import Base
from app.models.bank_account import BankAccount
from app.models.gl_account import GLAccount
from app.models.gl_transaction import GLTransaction
from app.models.trust_interest import TrustInterestReadiness
from app.models.audit_log import AuditLog
from app.models.user import Organization, User, UserRole
from app.routers import trust_interest as api
from app.schemas.trust_interest import TrustInterestInput


def _db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _seed(db):
    first, second = Organization(name="Interest One", slug="interest-one"), Organization(name="Interest Two", slug="interest-two")
    db.add_all([first, second]); db.flush()
    users = []
    for org, role, name in (
        (first, UserRole.ADMIN, "admin"), (first, UserRole.OWNER, "owner"),
        (first, UserRole.MANAGER, "manager"), (first, UserRole.TENANT, "tenant"),
        (second, UserRole.ADMIN, "foreign"),
    ):
        row = User(organization_id=org.id, role=role, first_name=name, last_name="Interest",
                   email=f"interest-{name}@example.com", hashed_password="x", is_active=True)
        db.add(row); users.append(row)
    db.flush()
    banks=[]
    for org, number, account_type in ((first, "1150", "OPERATING"), (first, "1160", "ESCROW"), (second, "1150", "OPERATING")):
        gl = GLAccount(organization_id=org.id, gl_number=number,
                       name="Trust Cash", account_type="ASSET", is_active=True)
        db.add(gl); db.flush()
        bank = BankAccount(organization_id=org.id, name="Trust",
                           account_type=account_type, gl_account_id=gl.id,
                           routing_number="012345678", account_number="SUPER-SECRET",
                           is_active=True)
        db.add(bank); banks.append(bank)
    db.commit()
    return users, banks


@pytest.fixture(autouse=True)
def gate(monkeypatch):
    from app.services import trust_interest as service
    monkeypatch.setattr(service, "permission_allows_user", lambda *a, **kw: True)
    monkeypatch.setattr(service, "resolve_customer_features", lambda *a, **kw: [
        SimpleNamespace(key=service.FEATURE_KEY, allowed=True),
    ])


def test_interest_scope_no_bank_numbers_or_ledger_changes():
    db, engine = _db()
    try:
        (admin, owner, manager, tenant, foreign), (bank, escrow, outside) = _seed(db)
        response=Response()
        empty=api.get_interest_readiness(bank.id,response,db=db,current_user=admin)
        assert response.headers["cache-control"]=="no-store"
        assert not empty.configured and empty.proposed_recipient=="UNDETERMINED"
        saved=api.put_interest_readiness(
            bank.id, TrustInterestInput(jurisdiction="OH", proposed_recipient="TENANT",
                                       basis_reference="Staff-checked policy citation"),
            Response(),db=db,current_user=admin)
        assert saved.configured and saved.legal_review_required is True
        assert saved.interest_allocation_enabled is False and saved.interest_posting_enabled is False
        assert "SUPER-SECRET" not in saved.model_dump_json()
        assert "012345678" not in saved.model_dump_json()
        assert "Staff-checked" not in saved.model_dump_json()
        assert db.query(TrustInterestReadiness).count()==1
        assert db.query(GLTransaction).count()==0
        assert api.get_interest_readiness(bank.id,Response(),db=db,current_user=owner).configured
        for actor,bank_id in ((admin,outside.id),(foreign,bank.id),(manager,bank.id),(tenant,bank.id)):
            with pytest.raises(HTTPException) as exc:
                api.get_interest_readiness(bank_id,Response(),db=db,current_user=actor)
            assert exc.value.status_code in {403,404}
        audit=db.query(AuditLog).one()
        assert "Staff-checked" not in (audit.new_value or "")
    finally:
        db.close(); engine.dispose()


def test_interest_input_review_reference_required_and_updates_remain_read_only():
    db, engine=_db()
    try:
        (admin, owner, manager, tenant, foreign), (bank, escrow, outside)=_seed(db)
        with pytest.raises(ValueError):
            TrustInterestInput(jurisdiction="OH",proposed_recipient="STATE")
        first=api.put_interest_readiness(
            escrow.id,TrustInterestInput(),Response(),db=db,current_user=admin)
        second=api.put_interest_readiness(
            escrow.id,TrustInterestInput(jurisdiction="OH",proposed_recipient="OTHER",
                                          basis_reference="External legal review needed"),
            Response(),db=db,current_user=admin)
        assert first.bank_account_id==second.bank_account_id
        assert db.query(TrustInterestReadiness).count()==1
        assert db.query(GLTransaction).count()==0
        assert db.query(AuditLog).count()==2
    finally:
        db.close();engine.dispose()


def test_interest_gate_permissions_and_inactive_bank_fail_closed(monkeypatch):
    from app.services import trust_interest as service
    db,engine=_db()
    try:
        (admin,owner,manager,tenant,foreign),(bank,escrow,outside)=_seed(db)
        monkeypatch.setattr(service,"resolve_customer_features",lambda *a,**k:[
            SimpleNamespace(key=service.FEATURE_KEY,allowed=False),
        ])
        with pytest.raises(HTTPException) as exc:
            api.get_interest_readiness(bank.id,Response(),db=db,current_user=admin)
        assert exc.value.status_code==404
        monkeypatch.setattr(service,"resolve_customer_features",lambda *a,**k:[
            SimpleNamespace(key=service.FEATURE_KEY,allowed=True),
        ])
        monkeypatch.setattr(service,"permission_allows_user",lambda *a,**k:False)
        with pytest.raises(HTTPException) as exc:
            api.get_interest_readiness(bank.id,Response(),db=db,current_user=admin)
        assert exc.value.status_code==403
        monkeypatch.setattr(service,"permission_allows_user",lambda *a,**k:True)
        bank.is_active=False;db.commit()
        with pytest.raises(HTTPException) as exc:
            api.put_interest_readiness(bank.id,TrustInterestInput(),Response(),db=db,current_user=admin)
        assert exc.value.status_code==404
        admin.is_active=False;db.commit()
        with pytest.raises(HTTPException) as exc:
            api.get_interest_readiness(escrow.id,Response(),db=db,current_user=admin)
        assert exc.value.status_code==403
        assert db.query(TrustInterestReadiness).count()==0
    finally:
        db.close();engine.dispose()
