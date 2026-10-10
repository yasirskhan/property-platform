from __future__ import annotations
from datetime import date
from decimal import Decimal
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from app.core.database import Base
from app.models.bill import Bill
from app.models.bill_line import BillLine
from app.models.bill_workflow import RecurringBill, RecurringBillLine, VendorCredit, VendorCreditLine
from app.models.gl_account import GLAccount, GLAccountPostingRestriction
from app.models.gl_entry import GLEntry
from app.models.gl_transaction import GLTransaction
from app.models.property import Property, Unit
from app.models.release_gate import ReleaseGate, ReleaseGateOrganization
from app.models.user import Organization, User, UserRole
from app.schemas.bill import BillLineIn
from app.schemas.bill_workflow import RecurringBillCreateIn, VendorCreditCreateIn
import app.services.bill_workflows as workflows

TEST_TABLES=[Organization.__table__,User.__table__,Property.__table__,Unit.__table__,GLAccount.__table__,GLAccountPostingRestriction.__table__,ReleaseGate.__table__,ReleaseGateOrganization.__table__,GLTransaction.__table__,GLEntry.__table__,Bill.__table__,BillLine.__table__,RecurringBill.__table__,RecurringBillLine.__table__,VendorCredit.__table__,VendorCreditLine.__table__]

@pytest.fixture()
def db()->Session:
    engine=create_engine("sqlite+pysqlite:///:memory:",connect_args={"check_same_thread":False},poolclass=StaticPool)
    Base.metadata.create_all(engine,tables=TEST_TABLES)
    s=sessionmaker(bind=engine,autoflush=False,expire_on_commit=False)()
    try: yield s
    finally:
        s.close(); Base.metadata.drop_all(engine,tables=list(reversed(TEST_TABLES))); engine.dispose()

def seed(db:Session,slug:str="bill-workflow"):
    org=Organization(name="Bill Workflow",slug=slug); db.add(org); db.flush()
    user=User(email=f"{slug}@example.com",hashed_password="unused",first_name="Bill",last_name="Admin",role=UserRole.ADMIN,organization_id=org.id,is_active=True,is_verified=True)
    ap=GLAccount(organization_id=org.id,gl_number="2100",name="AP",account_type="LIABILITY",is_active=True)
    expense=GLAccount(organization_id=org.id,gl_number="6100",name="Repairs",account_type="EXPENSE",is_active=True)
    cash=GLAccount(organization_id=org.id,gl_number="1150",name="Cash",account_type="ASSET",is_active=True)
    db.add_all([user,ap,expense,cash]); db.commit(); return org,user,ap,expense,cash

def line(expense_id:int,amount:str="100.00")->BillLineIn:
    return BillLineIn(gl_account_id=expense_id,description="Monthly service",amount=Decimal(amount))

@pytest.mark.accounting
def test_recurring_bill_posts_due_months_once_with_post_code(db:Session,monkeypatch)->None:
    org,user,_ap,expense,cash=seed(db)
    schedule=workflows.create_recurring_bill(db,organization_id=org.id,created_by=user,payload=RecurringBillCreateIn(entry_type="BILL",payee_name="Landscaper",start_date=date(2026,1,31),bill_day=31,due_day=5,post_code="LAND",cash_gl_account_id=cash.id,lines=[line(expense.id)]))
    monkeypatch.setattr(workflows,"recurring_bills_enabled_for_org",lambda _db,*,organization_id:True)
    result=workflows.post_due_recurring_bills(db,as_of=date(2026,2,28),organization_id=org.id)
    assert result=={"posted_bills":2,"posted_credits":0,"skipped_disabled":0,"failed":0}
    bills=db.query(Bill).filter(Bill.source_type=="recurring_bill",Bill.source_id==schedule.id).order_by(Bill.bill_date).all()
    assert [x.bill_date for x in bills]==[date(2026,1,31),date(2026,2,28)]
    assert [x.due_date for x in bills]==[date(2026,2,5),date(2026,3,5)]
    assert schedule.post_code=="LAND"
    second=workflows.post_due_recurring_bills(db,as_of=date(2026,2,28),organization_id=org.id)
    assert second["posted_bills"]==0
    assert db.query(Bill).filter(Bill.source_type=="recurring_bill",Bill.source_id==schedule.id).count()==2

@pytest.mark.accounting
def test_recurring_credit_creates_positive_vendor_credit_not_negative_bill(db:Session,monkeypatch)->None:
    org,user,ap,expense,_cash=seed(db)
    schedule=workflows.create_recurring_bill(db,organization_id=org.id,created_by=user,payload=RecurringBillCreateIn(entry_type="CREDIT",payee_name="Supplier",start_date=date(2026,3,15),bill_day=15,post_code="REBATE",lines=[line(expense.id,"75.00")]))
    monkeypatch.setattr(workflows,"recurring_bills_enabled_for_org",lambda _db,*,organization_id:True)
    result=workflows.post_due_recurring_bills(db,as_of=date(2026,3,15),organization_id=org.id)
    assert result["posted_credits"]==1
    assert db.query(Bill).filter(Bill.source_id==schedule.id).count()==0
    credit=db.query(VendorCredit).filter(VendorCredit.source_type=="recurring_bill",VendorCredit.source_id==schedule.id).one()
    assert Decimal(credit.amount)==Decimal("75.00")
    entries=db.query(GLEntry).filter(GLEntry.transaction_id==credit.gl_transaction_id).all()
    by_account={x.gl_account_id:x for x in entries}
    assert Decimal(by_account[ap.id].debit)==Decimal("75.00")
    assert Decimal(by_account[expense.id].credit)==Decimal("75.00")

@pytest.mark.accounting
def test_manual_post_limits_to_selected_schedule(db:Session,monkeypatch)->None:
    org,user,_ap,expense,_cash=seed(db)
    selected=workflows.create_recurring_bill(db,organization_id=org.id,created_by=user,payload=RecurringBillCreateIn(entry_type="BILL",payee_name="Selected",start_date=date(2026,4,1),bill_day=1,lines=[line(expense.id)]))
    other=workflows.create_recurring_bill(db,organization_id=org.id,created_by=user,payload=RecurringBillCreateIn(entry_type="BILL",payee_name="Other",start_date=date(2026,4,1),bill_day=1,lines=[line(expense.id)]))
    monkeypatch.setattr(workflows,"recurring_bills_enabled_for_org",lambda _db,*,organization_id:True)
    monkeypatch.setattr(workflows,"manual_bill_post_enabled_for_org",lambda _db,*,organization_id:True)
    result=workflows.post_due_recurring_bills(db,as_of=date(2026,4,1),organization_id=org.id,schedule_ids=[selected.id],created_by=user,require_manual_gate=True)
    assert result["posted_bills"]==1
    assert db.query(Bill).filter(Bill.source_id==selected.id).count()==1
    assert db.query(Bill).filter(Bill.source_id==other.id).count()==0

@pytest.mark.accounting
def test_vendor_credit_rejects_cross_org_account(db:Session)->None:
    org,user,_ap,_expense,_cash=seed(db,"primary")
    _o,_u,_a,other_expense,_c=seed(db,"other")
    with pytest.raises(Exception,match="not found in your organization"):
        workflows.post_vendor_credit(db,organization_id=org.id,created_by=user,payload=VendorCreditCreateIn(payee_name="Bad Supplier",credit_date=date(2026,5,1),lines=[line(other_expense.id)]))
