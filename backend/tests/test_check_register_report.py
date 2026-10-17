"""Check register verifies current issue/void GL markers but not bank clearing."""
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
from app.models.bank_account import BankAccount
from app.models.check import Check
from app.models.gl_account import GLAccount
from app.models.gl_transaction import GLTransaction
from app.models.user import Organization, User, UserRole
from app.routers import reporting as router
from app.services import check_register_report as register
from app.services.report_catalog import REPORT_CATALOG
from app.services.report_delivery import ReportDeliveryError, build_report_payload, report_csv_bytes

KEY = "transaction.check_register"


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _seed(db):
    first = Organization(name="Check Register One", slug="check-register-one")
    second = Organization(name="Check Register Two", slug="check-register-two")
    db.add_all([first, second]); db.flush()
    def user(org, role, name):
        row = User(organization_id=org.id, role=role, first_name=name,
                   last_name="Checks", email=f"{name}@checks.example",
                   hashed_password="x", is_active=True)
        db.add(row);db.flush();return row
    admin=user(first,UserRole.ADMIN,"Admin")
    manager=user(first,UserRole.MANAGER,"Manager")
    foreign_admin=user(second,UserRole.ADMIN,"Foreign")
    def bank(org):
        gl=GLAccount(organization_id=org.id,gl_number="1150",
                     name="Cash",account_type="ASSET",is_active=True)
        db.add(gl);db.flush()
        row=BankAccount(
            organization_id=org.id,name="=Client Trust" if org==first else "Foreign Bank",
            gl_account_id=gl.id,account_type="OPERATING",
            account_number="9876543210",routing_number="111000111",
            is_active=True,
        )
        db.add(row);db.flush()
        return row,gl
    bank_one,gl_one=bank(first)
    bank_two,gl_two=bank(second)
    today=date.today()
    def check(org,bank,name,number,amount,status="ISSUED"):
        row=Check(
            organization_id=org.id,bank_account_id=bank.id,
            check_number=number,check_date=today,payee_name=name,
            amount=Decimal(amount),status=status,
        )
        db.add(row);db.flush()
        txn=GLTransaction(
            organization_id=org.id,transaction_date=today,
            transaction_type="CHECK",source_type="check",
            source_id=row.id,is_reversed=status=="VOID",
        )
        db.add(txn);db.flush()
        row.gl_transaction_id=txn.id
        if status=="VOID":
            reversal=GLTransaction(
                organization_id=org.id,transaction_date=today,
                transaction_type="REVERSAL",source_type="check_void",
                source_id=row.id,reversal_of_id=txn.id,
            )
            db.add(reversal);db.flush()
            row.void_gl_transaction_id=reversal.id
            row.voided_at=datetime.utcnow()
        db.flush()
        return row,txn
    issued,original=check(first,bank_one,"=Invoice Supplier","C-0001","100")
    voided,void_original=check(first,bank_one,"Vendor Two","C-0002","35",status="VOID")
    foreign,foreign_txn=check(second,bank_two,"Secret Vendor","F-99","99999")
    db.commit()
    return admin,manager,foreign_admin,bank_one,bank_two,gl_one,gl_two,issued,voided,foreign,original,void_original


def _report(db,actor,**params):
    return build_report_payload(db,organization_id=actor.organization_id,
                                current_user=actor,report_key=KEY,parameters=params)


def test_issued_void_rows_clearing_disclaimer_and_bank_secrets_never_export(monkeypatch):
    db,engine=_session()
    try:
        admin,manager,foreign_admin,bank_one,bank_two,gl_one,gl_two,issued,voided,foreign,original,void_original=_seed(db)
        monkeypatch.setattr(register,"permission_allows_user",lambda *a,**kw:True)
        before=db.query(GLTransaction).count()
        report=_report(db,admin)
        assert len(report.rows)==2
        assert report.rows[0][0]==issued.id
        assert report.rows[0][5]=="ISSUED"
        assert report.rows[0][8]=="" and report.rows[0][9]==""
        assert report.rows[1][0]==voided.id
        assert report.rows[1][5]=="VOID" and report.rows[1][8]==voided.void_gl_transaction_id
        assert "not verified cleared" in report.title.lower()
        csv=report_csv_bytes(report).decode("utf-8-sig")
        assert "'=Invoice Supplier" in csv and "'=Client Trust" in csv
        for secret in ("9876543210","111000111","99999","Secret Vendor","Foreign Bank"):
            assert secret not in csv
        assert db.query(GLTransaction).count()==before
        assert len(_report(db,admin,bank_id=bank_one.id).rows)==2
        assert len(_report(db,admin,status="VOID").rows)==1
    finally:
        db.close();engine.dispose()


def test_org_role_filters_and_invalid_gl_or_reversal_refused(monkeypatch):
    db,engine=_session()
    try:
        admin,manager,foreign_admin,bank_one,bank_two,gl_one,gl_two,issued,voided,foreign,original,void_original=_seed(db)
        monkeypatch.setattr(register,"permission_allows_user",lambda *a,**kw:True)
        with pytest.raises(ReportDeliveryError,match="permission"):
            _report(db,manager)
        assert len(_report(db,foreign_admin).rows)==1
        for params in ({"check_id":foreign.id},{"bank_id":bank_two.id},
                       {"status":"CLEARED"},{"check_id":-1},
                       {"date_from":"2026-10-01","date_to":"2026-09-01"},
                       {"sql":"SELECT * FROM tax_profiles"}):
            with pytest.raises(ReportDeliveryError):
                _report(db,admin,**params)
        monkeypatch.setattr(register,"permission_allows_user",
                            lambda db,*,user,menu_key:menu_key!="ACCOUNTING.PAYABLES")
        with pytest.raises(ReportDeliveryError,match="permission"):
            _report(db,admin)
        monkeypatch.setattr(register,"permission_allows_user",lambda *a,**kw:True)
        issued.bank_account_id=bank_two.id;db.flush()
        with pytest.raises(ReportDeliveryError,match="bank mapping"):
            _report(db,admin)
        issued.bank_account_id=bank_one.id
        bank_one.gl_account_id=gl_two.id;db.flush()
        with pytest.raises(ReportDeliveryError,match="cash GL"):
            _report(db,admin)
        bank_one.gl_account_id=gl_one.id
        issued.status="VOID";db.flush()
        with pytest.raises(ReportDeliveryError,match="Void check"):
            _report(db,admin)
        issued.status="ISSUED"
        original.is_reversed=True;db.flush()
        with pytest.raises(ReportDeliveryError,match="Issued check"):
            _report(db,admin)
    finally:
        db.rollback();db.close();engine.dispose()


def test_catalog_preview_export_email_and_revocation(monkeypatch):
    db,engine=_session()
    try:
        admin,*_=_seed(db)
        monkeypatch.setattr(register,"permission_allows_user",lambda *a,**kw:True)
        item=next(row for row in REPORT_CATALOG if row.key==KEY)
        assert item.href=="/dashboard/reporting/check-register" and item.presentation=="BUTTON"
        assert router.REPORT_PERMISSIONS[KEY]=="ACCOUNTING.BANK_ACCOUNTS"
        monkeypatch.setattr(router,"permission_allows_user",lambda *a,**kw:True)
        monkeypatch.setattr(router,"resolve_customer_features",
                            lambda *a,**kw:[SimpleNamespace(key=router.EXPORT_FEATURE_KEY,allowed=True)])
        req=SimpleNamespace(query_params={})
        response=Response()
        data=router.preview_check_register(req,response,db=db,current_user=admin)
        assert data["total"]==2 and response.headers["cache-control"]=="no-store"
        result=router.export_report_csv(KEY,req,db=db,current_user=admin)
        assert b"Recorded Payee" in result.body
        sent={}
        monkeypatch.setattr(router,"send_email",lambda **kw:sent.update(kw))
        done=router.email_report(KEY,router.ReportEmailIn(
            recipient="finance@example.com",parameters={}),
            db=db,current_user=admin)
        assert done.sent
        assert b"9876543210" not in sent["attachments"][0][1]
        monkeypatch.setattr(router,"resolve_customer_features",
                            lambda *a,**kw:[SimpleNamespace(key=router.EXPORT_FEATURE_KEY,allowed=False)])
        with pytest.raises(HTTPException) as exc:
            router.preview_check_register(req,Response(),db=db,current_user=admin)
        assert exc.value.status_code==404
        monkeypatch.setattr(router,"permission_allows_user",
                            lambda db,*,user,menu_key:menu_key=="REPORTING.ALL")
        with pytest.raises(HTTPException) as exc:
            router.export_report_csv(KEY,req,db=db,current_user=admin)
        assert exc.value.status_code==403
    finally:
        db.close();engine.dispose()
