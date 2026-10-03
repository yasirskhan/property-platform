"""Standalone Charge detail, including paid/credit records without rent invoice inflation."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, Response
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import init_db  # noqa: F401
from app.core.database import Base
from app.models.charge import Charge
from app.models.gl_account import GLAccount
from app.models.lease import InvoiceStatus, Lease, LeaseStatus, RentInvoice
from app.models.property import Property, PropertyAssignment, Unit
from app.models.user import Organization, User, UserRole
from app.routers import reporting as router
from app.services import charge_detail_report as detail
from app.services.report_catalog import REPORT_CATALOG
from app.services.report_delivery import ReportDeliveryError, build_report_payload, report_csv_bytes

KEY = "transaction.charge_detail"


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _seed(db):
    one = Organization(name="Charge Detail One", slug="charge-detail-one")
    two = Organization(name="Charge Detail Two", slug="charge-detail-two")
    db.add_all([one, two]); db.flush()
    def person(org, role, name):
        user = User(organization_id=org.id, role=role,
                    first_name=name, last_name="Person",
                    email=f"{name}@charge-detail.example",
                    hashed_password="x", is_active=True)
        db.add(user); db.flush(); return user
    admin = person(one, UserRole.ADMIN, "Admin")
    manager = person(one, UserRole.MANAGER, "Manager")
    tenant = person(one, UserRole.TENANT, "=Tenant")
    outsider = person(two, UserRole.TENANT, "Foreign")
    def prop(org, name):
        row = Property(organization_id=org.id, name=name,
                       address_line1="100 Test Ave", city="Cleveland",
                       state="OH", zip_code="44113", is_active=True)
        db.add(row); db.flush(); return row
    assigned = prop(one, "Assigned")
    unassigned = prop(one, "Unassigned")
    foreign = prop(two, "Private")
    db.add(PropertyAssignment(property_id=assigned.id, user_id=manager.id,
                              role=UserRole.MANAGER, is_active=True))
    accounts = {}
    for org in (one, two):
        account = GLAccount(organization_id=org.id, gl_number="4010",
                            name="=Utility Fees" if org.id==one.id else "Foreign GL",
                            account_type="INCOME", is_active=True)
        db.add(account); db.flush(); accounts[org.id] = account
    def charge(org, user, property_, number, amount, paid, *, flag=False,
               active=True, deleted=False):
        row = Charge(organization_id=org.id, tenant_user_id=user.id,
                     property_id=property_.id if property_ else None,
                     charge_date=date.today()-timedelta(days=2),
                     gl_account_id=accounts[org.id].id, description=number,
                     amount=Decimal(amount), amount_paid=Decimal(paid),
                     is_paid=flag, is_active=active,
                     deleted_at=datetime.utcnow() if deleted else None)
        db.add(row); db.flush();return row
    partial = charge(one,tenant,assigned,"=Damages","80","30")
    paid = charge(one,tenant,assigned,"Paid","25","25",flag=True)
    credit = charge(one,tenant,assigned,"Overpayment","25","30",flag=True)
    second = charge(one,tenant,unassigned,"Utilities","120","0")
    orphan = charge(one,tenant,None,"Office","20","0")
    charge(two,outsider,foreign,"ForeignCharge","99999","0")
    charge(one,tenant,assigned,"Soft deleted","90","0",deleted=True)
    charge(one,tenant,assigned,"Inactive","90","0",active=False)
    unit = Unit(property_id=assigned.id,unit_number="A",is_active=True)
    db.add(unit); db.flush()
    lease = Lease(unit_id=unit.id,tenant_id=tenant.id,
                  start_date=date.today()-timedelta(days=90),
                  end_date=date.today()+timedelta(days=365),
                  monthly_rent=1000,security_deposit=500,status=LeaseStatus.ACTIVE)
    db.add(lease);db.flush()
    db.add(RentInvoice(lease_id=lease.id,
                       period_start=date.today()-timedelta(days=30),
                       period_end=date.today(),due_date=date.today(),
                       amount_due=Decimal("1000"),late_fee=Decimal("50"),
                       amount_paid=Decimal("0"),status=InvoiceStatus.PENDING))
    db.commit()
    return admin,manager,tenant,outsider,assigned,unassigned,foreign,accounts,partial,paid,credit,second,orphan


def _report(db, actor, **params):
    return build_report_payload(db,organization_id=actor.organization_id,
                                current_user=actor,report_key=KEY,parameters=params)


def test_full_charge_detail_scopes_paid_credit_and_no_rent_double_count(monkeypatch):
    db,engine = _session()
    try:
        admin,manager,tenant,outsider,assigned,unassigned,foreign,accounts,partial,paid,credit,second,orphan=_seed(db)
        monkeypatch.setattr(detail,"permission_allows_user",lambda *a,**kw:True)
        before = db.query(Charge).count()
        report=_report(db,admin)
        entries={r[0]:r for r in report.rows if isinstance(r[0],int)}
        assert set(entries)=={partial.id,paid.id,credit.id,second.id,orphan.id}
        assert entries[partial.id][8:11]==(Decimal("80"),Decimal("30"),Decimal("50"))
        assert entries[paid.id][10]==0
        assert entries[credit.id][10]==Decimal("-5")
        assert "CREDIT" in entries[credit.id][12]
        assert entries[orphan.id][3]=="Unallocated organization charge"
        assert report.rows[-1][8:11]==(Decimal("270"),Decimal("85"),Decimal("185"))
        csv=report_csv_bytes(report).decode("utf-8-sig")
        assert "'=Damages" in csv and "'=Utility Fees" in csv
        assert "99999" not in csv and "ForeignCharge" not in csv
        assert "1000" not in csv
        assert db.query(Charge).count()==before
        assert len(_report(db,admin,charge_id=partial.id).rows)==2
        assert _report(db,admin,date_from="2030-01-01").rows[-1][10]==0
    finally:
        db.close();engine.dispose()


def test_role_manager_property_and_foreign_mapping_fail_closed(monkeypatch):
    db,engine=_session()
    try:
        admin,manager,tenant,outsider,assigned,unassigned,foreign,accounts,partial,paid,credit,second,orphan=_seed(db)
        monkeypatch.setattr(detail,"permission_allows_user",lambda *a,**kw:True)
        assert {r[0] for r in _report(db,manager).rows if isinstance(r[0],int)}=={partial.id,paid.id,credit.id}
        for key in (second.id,orphan.id,999999):
            with pytest.raises(ReportDeliveryError,match="Charge not found"):
                _report(db,manager,charge_id=key)
        for prop in (unassigned,foreign):
            with pytest.raises(ReportDeliveryError,match="Property not found"):
                _report(db,manager,property_id=prop.id)
        with pytest.raises(ReportDeliveryError,match="Property not found"):
            _report(db,admin,property_id=foreign.id)
        with pytest.raises(ReportDeliveryError,match="Tenant not found"):
            _report(db,admin,tenant_id=outsider.id)
        with pytest.raises(ReportDeliveryError,match="permission"):
            _report(db,tenant)
        for params in ({"sql":"SELECT * FROM tax_profiles"},{"charge_id":-1},
                       {"date_from":"2026-10-01","date_to":"2026-09-01"},
                       {"charge_id":"invalid"}):
            with pytest.raises(ReportDeliveryError):
                _report(db,admin,**params)
        monkeypatch.setattr(detail,"permission_allows_user",
                            lambda db,*,user,menu_key:menu_key!="ACCOUNTING.GL_ACCOUNTS")
        with pytest.raises(ReportDeliveryError,match="permission"):
            _report(db,admin)
        monkeypatch.setattr(detail,"permission_allows_user",lambda *a,**kw:True)
        partial.gl_account_id=accounts[foreign.organization_id].id
        db.flush()
        with pytest.raises(ReportDeliveryError,match="GL account"):
            _report(db,admin)
        partial.gl_account_id=accounts[admin.organization_id].id
        partial.amount=Decimal("-2")
        db.flush()
        with pytest.raises(ReportDeliveryError,match="Invalid"):
            _report(db,admin)
    finally:
        db.rollback();db.close();engine.dispose()


def test_catalog_csv_preview_email_and_release_revocation(monkeypatch):
    db,engine=_session()
    try:
        admin,*_=_seed(db)
        monkeypatch.setattr(detail,"permission_allows_user",lambda *a,**kw:True)
        x=next(i for i in REPORT_CATALOG if i.key==KEY)
        assert x.href=="/dashboard/reporting/charge-detail" and x.presentation=="BUTTON"
        assert router.REPORT_PERMISSIONS[KEY]=="ACCOUNTING.CHARGES"
        monkeypatch.setattr(router,"permission_allows_user",lambda *a,**kw:True)
        monkeypatch.setattr(router,"resolve_customer_features",
                            lambda *a,**kw:[SimpleNamespace(key=router.EXPORT_FEATURE_KEY,allowed=True)])
        req=SimpleNamespace(query_params={})
        response=Response()
        preview=router.preview_charge_detail(req,response,db=db,current_user=admin)
        assert preview["total"]==6 and response.headers["cache-control"]=="no-store"
        exported=router.export_report_csv(KEY,req,db=db,current_user=admin)
        assert b"Recorded Description" in exported.body
        sent={}
        monkeypatch.setattr(router,"send_email",lambda **kw:sent.update(kw))
        ans=router.email_report(KEY,router.ReportEmailIn(
            recipient="accountant@example.com",parameters={}),
            db=db,current_user=admin)
        assert ans.sent and b"99999" not in sent["attachments"][0][1]
        monkeypatch.setattr(router,"resolve_customer_features",
                            lambda *a,**kw:[SimpleNamespace(key=router.EXPORT_FEATURE_KEY,allowed=False)])
        with pytest.raises(HTTPException) as exc:
            router.preview_charge_detail(req,Response(),db=db,current_user=admin)
        assert exc.value.status_code==404
        monkeypatch.setattr(router,"permission_allows_user",
                            lambda db,*,user,menu_key:menu_key=="REPORTING.ALL")
        with pytest.raises(HTTPException) as exc:
            router.export_report_csv(KEY,req,db=db,current_user=admin)
        assert exc.value.status_code==403
    finally:
        db.close();engine.dispose()
