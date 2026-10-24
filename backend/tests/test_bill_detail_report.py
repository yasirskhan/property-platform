"""Verified posted Bill/GL line breakdown, scoped and accounting-read-only."""
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
from app.models.bill import Bill
from app.models.bill_line import BillLine
from app.models.gl_account import GLAccount
from app.models.gl_transaction import GLTransaction
from app.models.user import Organization, User, UserRole
from app.routers import reporting as router
from app.services import bill_detail_report as detail
from app.services.report_catalog import REPORT_CATALOG
from app.services.report_delivery import ReportDeliveryError, build_report_payload, report_csv_bytes

KEY = "transaction.bill_detail"


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _seed(db):
    one = Organization(name="Detail Org One", slug="detail-org-one")
    other = Organization(name="Detail Org Two", slug="detail-org-two")
    db.add_all([one, other]); db.flush()
    def person(org, role, name):
        user = User(organization_id=org.id, role=role, first_name=name,
                    last_name="Bill", email=f"{name}@bill-detail.example",
                    hashed_password="x", is_active=True)
        db.add(user); db.flush(); return user
    admin = person(one, UserRole.ADMIN, "Admin")
    manager = person(one, UserRole.MANAGER, "Manager")
    foreign_admin = person(other, UserRole.ADMIN, "Foreign")
    def account(org, number, name, type_):
        item = GLAccount(organization_id=org.id, gl_number=number,
                         name=name, account_type=type_)
        db.add(item); db.flush(); return item
    ap = account(one, "2100", "Accounts Payable", "LIABILITY")
    expenses = account(one, "6100", "=Plumbing Expense", "EXPENSE")
    other_account = account(other, "2100", "Foreign Accounts Payable", "LIABILITY")
    other_expense = account(other, "6100", "Foreign Expense", "EXPENSE")
    today = date.today()
    def bill(org, name, payable, lines, amount, paid, status="UNPAID",
             reversed=False, active=True, posted=True, bill_date=today):
        gl = None
        if posted:
            gl = GLTransaction(organization_id=org.id,
                               transaction_date=bill_date, transaction_type="BILL",
                               is_reversed=False)
            db.add(gl); db.flush()
        item = Bill(
            organization_id=org.id, payee_name="=Vendor" if name=="PARTIAL" else name,
            bill_number=name, reference_number=name+"-REF", bill_date=bill_date,
            due_date=today, payable_gl_account_id=payable.id,
            gl_transaction_id=gl.id if gl else None, amount=Decimal(amount),
            amount_paid=Decimal(paid), status=status, is_reversed=reversed,
            is_active=active,
        )
        db.add(item); db.flush()
        for number, acct, line_amount in lines:
            db.add(BillLine(
                organization_id=org.id, bill_id=item.id, gl_account_id=acct.id,
                description=number, amount=Decimal(line_amount),
            ))
        db.flush()
        return item
    partial = bill(one, "PARTIAL", ap,
                   [("Line A",expenses,"60"),("Line B",expenses,"40")],
                   "100","25",status="PARTIAL")
    paid = bill(one,"PAID",ap,[("Paid line",expenses,"80")],"80","80",status="PAID")
    bill(one,"VOID",ap,[("Void",expenses,"20")],"20","0",status="VOID")
    bill(one,"REVERSED",ap,[("Reverse",expenses,"20")],"20","0",reversed=True)
    bill(one,"UNPOSTED",ap,[("Draft",expenses,"20")],"20","0",posted=False)
    bill(other,"OTHER",other_account,[("Secret",other_expense,"99999")],
         "99999","0")
    db.commit()
    return admin,manager,foreign_admin,partial,paid,ap,expenses,other_account,other_expense


def _report(db, actor, **params):
    return build_report_payload(
        db, organization_id=actor.organization_id, current_user=actor,
        report_key=KEY, parameters=params,
    )


def test_posted_bill_headers_line_totals_scope_csv_and_no_writes(monkeypatch):
    db, engine = _session()
    try:
        admin, manager, foreign, partial, paid, *_ = _seed(db)
        monkeypatch.setattr(detail, "permission_allows_user", lambda *a, **k: True)
        before = db.query(GLTransaction).count()
        data = _report(db, admin)
        assert len(data.rows) == 5
        headers = [r for r in data.rows if r[0]=="BILL"]
        lines = [r for r in data.rows if r[0]=="LINE"]
        assert len(headers)==2 and len(lines)==3
        assert headers[0][1]==partial.id
        assert headers[0][12:] == (Decimal("100"), Decimal("25"), Decimal("75"))
        assert [r[11] for r in lines[:2]]==[Decimal("60"),Decimal("40")]
        assert all(r[12:]==("","","") for r in lines)
        assert headers[1][1] == paid.id and headers[1][-1] == 0
        text = report_csv_bytes(data).decode("utf-8-sig")
        assert "'=Vendor" in text and "'=Plumbing Expense" in text
        for forbidden in ("99999","Foreign Expense","UNPOSTED","REVERSED","VOID"):
            assert forbidden not in text
        assert db.query(GLTransaction).count()==before
        assert len(_report(db, admin, bill_id=partial.id).rows)==3
        assert _report(db, admin, date_from="2029-01-01").rows == ()
    finally:
        db.close();engine.dispose()


def test_invalid_org_roles_gl_line_and_status_metadata_fail_closed(monkeypatch):
    db, engine = _session()
    try:
        admin, manager, foreign, partial, paid, ap, expenses, foreign_ap, foreign_exp = _seed(db)
        monkeypatch.setattr(detail, "permission_allows_user", lambda *a, **k: True)
        with pytest.raises(ReportDeliveryError,match="permission"):
            _report(db,manager)
        assert len(_report(db,foreign).rows)==2
        for params in ({"bill_id":-1},{"bill_id":"nope"},{"bill_id":999999},
                       {"date_from":"2026-10-01","date_to":"2026-09-01"},
                       {"sql":"SELECT * FROM tax_profiles"}):
            with pytest.raises(ReportDeliveryError):
                _report(db,admin,**params)
        monkeypatch.setattr(detail,"permission_allows_user",
                            lambda db,*,user,menu_key:menu_key!="ACCOUNTING.GL_ACCOUNTS")
        with pytest.raises(ReportDeliveryError,match="permission"):
            _report(db,admin)
        monkeypatch.setattr(detail,"permission_allows_user",lambda *a,**kw:True)
        partial.payable_gl_account_id=foreign_ap.id
        db.flush()
        with pytest.raises(ReportDeliveryError,match="mapping"):
            _report(db,admin)
        partial.payable_gl_account_id=ap.id
        db.flush()
        part=db.query(BillLine).filter(BillLine.bill_id==partial.id).order_by(BillLine.id).first()
        part.gl_account_id=foreign_exp.id
        db.flush()
        with pytest.raises(ReportDeliveryError,match="mapping"):
            _report(db,admin)
        part.gl_account_id=expenses.id
        part.amount=Decimal("1")
        db.flush()
        with pytest.raises(ReportDeliveryError,match="line sum"):
            _report(db,admin)
        part.amount=Decimal("60")
        partial.amount_paid=Decimal("150")
        db.flush()
        with pytest.raises(ReportDeliveryError,match="Invalid"):
            _report(db,admin)
    finally:
        db.rollback();db.close();engine.dispose()


def test_catalog_preview_csv_email_revocation(monkeypatch):
    db, engine=_session()
    try:
        admin,*_= _seed(db)
        monkeypatch.setattr(detail,"permission_allows_user",lambda *a,**kw:True)
        item=next(x for x in REPORT_CATALOG if x.key==KEY)
        assert item.href=="/dashboard/reporting/bill-detail"
        assert item.presentation=="BUTTON"
        assert router.REPORT_PERMISSIONS[KEY]=="ACCOUNTING.PAYABLES"
        monkeypatch.setattr(router,"permission_allows_user",lambda *a,**kw:True)
        monkeypatch.setattr(router,"resolve_customer_features",
                            lambda *a,**kw:[SimpleNamespace(key=router.EXPORT_FEATURE_KEY,allowed=True)])
        request=SimpleNamespace(query_params={})
        response=Response()
        preview=router.preview_bill_detail(request,response,db=db,current_user=admin)
        assert preview["total"]==5
        assert response.headers["cache-control"]=="no-store"
        csv=router.export_report_csv(KEY,request,db=db,current_user=admin)
        assert b"Recorded Payee" in csv.body
        sent={}
        monkeypatch.setattr(router,"send_email",lambda **kw:sent.update(kw))
        out=router.email_report(
            KEY,router.ReportEmailIn(recipient="accountant@example.com",
                                     parameters={}),db=db,current_user=admin)
        assert out.sent and b"99999" not in sent["attachments"][0][1]
        monkeypatch.setattr(router,"resolve_customer_features",
                            lambda *a,**kw:[SimpleNamespace(key=router.EXPORT_FEATURE_KEY,allowed=False)])
        with pytest.raises(HTTPException) as exc:
            router.preview_bill_detail(request,Response(),db=db,current_user=admin)
        assert exc.value.status_code==404
        monkeypatch.setattr(router,"permission_allows_user",
                            lambda db,*,user,menu_key:menu_key=="REPORTING.ALL")
        with pytest.raises(HTTPException) as exc:
            router.export_report_csv(KEY,request,db=db,current_user=admin)
        assert exc.value.status_code==403
    finally:
        db.close();engine.dispose()
