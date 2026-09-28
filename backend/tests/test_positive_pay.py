"""Positive-pay preflight never claims bank file acceptance or changes checks/GL."""
from __future__ import annotations
from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace
import pytest
from fastapi import HTTPException, Response
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import init_db  # noqa: F401
from app.core.database import Base
from app.models.user import Organization, User, UserRole
from app.models.gl_account import GLAccount
from app.models.bank_account import BankAccount
from app.models.gl_transaction import GLTransaction
from app.models.check import Check
from app.routers import positive_pay as api
from app.services import positive_pay as service, check_register_report as register


def _db():
    engine=create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine,expire_on_commit=False)(),engine


def _seed(db):
    org=Organization(name="Positive Pay One",slug="positive-pay-one")
    foreign_org=Organization(name="Positive Pay Two",slug="positive-pay-two")
    db.add_all([org,foreign_org]);db.flush()
    actors=[]
    for o,role,name in ((org,UserRole.ADMIN,"admin"),(org,UserRole.MANAGER,"manager"),
                        (foreign_org,UserRole.ADMIN,"foreign")):
        u=User(organization_id=o.id,role=role,first_name=name,last_name="Check",
               email=f"positive-{name}@example.com",hashed_password="x",is_active=True)
        db.add(u);actors.append(u)
    db.flush()
    banks=[]
    for o,name in ((org,"Local"),(foreign_org,"Foreign")):
        gl=GLAccount(organization_id=o.id,gl_number="1150",name="Cash",
                     account_type="ASSET",is_active=True)
        db.add(gl);db.flush()
        b=BankAccount(organization_id=o.id,name=name,gl_account_id=gl.id,
                      account_type="OPERATING",routing_number="011000015",
                      account_number="PRIVATE-ACCOUNT-123",is_active=True)
        db.add(b);db.flush();banks.append(b)
    today=date(2026,9,27)
    rows=[]
    for org_, bank_, status, check_num, payee, amount in (
        (org,banks[0],"ISSUED","000010","=Sensitive Supplier","125.50"),
        (org,banks[0],"VOID","000011","=Void Payee","25"),
        (org,banks[0],"ISSUED",None,"Missing Number","10"),
        (foreign_org,banks[1],"ISSUED","999999","Secret Vendor","9000"),
    ):
        check=Check(organization_id=org_.id,bank_account_id=bank_.id,
                    check_date=today,check_number=check_num,payee_name=payee,
                    amount=Decimal(amount),status=status)
        db.add(check);db.flush()
        issue=GLTransaction(organization_id=org_.id,transaction_date=today,
                            transaction_type="CHECK",source_type="check",
                            source_id=check.id,is_reversed=status=="VOID")
        db.add(issue);db.flush();check.gl_transaction_id=issue.id
        if status=="VOID":
            reverse=GLTransaction(organization_id=org_.id,
                transaction_date=today,transaction_type="REVERSAL",
                source_type="check_void",source_id=check.id,
                reversal_of_id=issue.id)
            db.add(reverse);db.flush()
            check.void_gl_transaction_id=reverse.id
            check.voided_at=datetime.utcnow()
        rows.append(check)
    db.commit()
    return actors,banks,rows


@pytest.fixture(autouse=True)
def permitted(monkeypatch):
    monkeypatch.setattr(service,"permission_allows_user",lambda *a,**k:True)
    monkeypatch.setattr(register,"permission_allows_user",lambda *a,**k:True)
    monkeypatch.setattr(service,"resolve_customer_features",lambda *a,**k:[
        SimpleNamespace(key=service.FEATURE_KEY,allowed=True)])


def test_positive_pay_issue_void_and_missing_number_are_bounded_and_read_only():
    db,engine=_db()
    try:
        (admin,manager,foreign),(bank,other),rows=_seed(db)
        before=db.query(GLTransaction).count()
        response=Response()
        preview=api.positive_pay_preflight(bank.id,response,db=db,current_user=admin)
        assert response.headers["cache-control"]=="no-store"
        assert preview["total"]==3 and preview["issued"]==2 and preview["voided"]==1
        assert preview["needs_review"]==1
        assert [x["check_number"] for x in preview["items"]]==["000010","000011",""]
        assert preview["items"][-1]["review_flags"]==["Missing recorded check number"]
        assert preview["bank_file_export_available"] is False
        assert preview["submission_status"]=="NOT_SUBMITTED"
        assert "PRIVATE-ACCOUNT-123" not in str(preview)
        assert "Secret Vendor" not in str(preview)
        assert db.query(GLTransaction).count()==before
        assert len(service.preflight_positive_pay(
            db,bank_id=bank.id,current_user=admin,
            date_from=date(2026,9,27),date_to=date(2026,9,27))["items"])==3
    finally:
        db.close();engine.dispose()


def test_positive_pay_scope_release_and_menu_permission_fail_closed(monkeypatch):
    db,engine=_db()
    try:
        (admin,manager,foreign),(bank,other),rows=_seed(db)
        for actor,account in ((admin,other),(foreign,bank),(manager,bank)):
            with pytest.raises(HTTPException) as exc:
                service.preflight_positive_pay(db,bank_id=account.id,current_user=actor)
            assert exc.value.status_code in {403,404}
        monkeypatch.setattr(service,"resolve_customer_features",lambda *a,**k:[
            SimpleNamespace(key=service.FEATURE_KEY,allowed=False)])
        with pytest.raises(HTTPException) as exc:
            service.preflight_positive_pay(db,bank_id=bank.id,current_user=admin)
        assert exc.value.status_code==404
        monkeypatch.setattr(service,"resolve_customer_features",lambda *a,**k:[
            SimpleNamespace(key=service.FEATURE_KEY,allowed=True)])
        monkeypatch.setattr(register,"permission_allows_user",lambda db,*,user,menu_key:menu_key!="ACCOUNTING.PAYABLES")
        with pytest.raises(HTTPException) as exc:
            service.preflight_positive_pay(db,bank_id=bank.id,current_user=admin)
        assert exc.value.status_code==422
    finally:
        db.close();engine.dispose()


def test_positive_pay_rejects_missing_or_reversed_posting_and_invalid_dates():
    db,engine=_db()
    try:
        (admin,manager,foreign),(bank,other),rows=_seed(db)
        with pytest.raises(HTTPException) as exc:
            service.preflight_positive_pay(db,bank_id=bank.id,current_user=admin,
                date_from=date(2026,9,28),date_to=date(2026,9,27))
        assert exc.value.status_code==422
        issued=rows[0]
        txn=db.query(GLTransaction).filter(GLTransaction.id==issued.gl_transaction_id).one()
        txn.is_reversed=True
        db.flush()
        with pytest.raises(HTTPException) as exc:
            service.preflight_positive_pay(db,bank_id=bank.id,current_user=admin)
        assert exc.value.status_code==422
        assert db.query(GLTransaction).count()==5
    finally:
        db.rollback();db.close();engine.dispose()
