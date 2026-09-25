from __future__ import annotations
from datetime import date
from decimal import Decimal
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.core.database import Base
from app.models.bank_account import BankAccount
from app.models.bill import Bill
from app.models.bill_line import BillLine
from app.models.check import Check, CheckBillAllocation
from app.models.gl_account import GLAccount, GLAccountPostingRestriction
from app.models.gl_entry import GLEntry
from app.models.gl_transaction import GLTransaction
from app.models.organization_feature_setting import OrganizationFeatureSetting
from app.models.release_gate import ReleaseGate, ReleaseGateOrganization
from app.models.user import Organization, User, UserRole
from app.schemas.bill import BillCreateIn, BillLineIn
from app.schemas.check import CheckAllocationIn, CheckIssueIn
from app.services.bill_posting import post_bill
from app.services.checks import issue_check, void_check
TABLES=[Organization.__table__,User.__table__,GLAccount.__table__,GLAccountPostingRestriction.__table__,ReleaseGate.__table__,ReleaseGateOrganization.__table__,OrganizationFeatureSetting.__table__,GLTransaction.__table__,GLEntry.__table__,BankAccount.__table__,Bill.__table__,BillLine.__table__,Check.__table__,CheckBillAllocation.__table__]
@pytest.fixture()
def db():
    engine=create_engine("sqlite+pysqlite:///:memory:",connect_args={"check_same_thread":False},poolclass=StaticPool);Base.metadata.create_all(engine,tables=TABLES);s=sessionmaker(bind=engine,expire_on_commit=False)()
    try:yield s
    finally:s.close();engine.dispose()
def seed(db,slug="checks"):
    org=Organization(name="Checks",slug=slug);db.add(org);db.flush();user=User(email=f"{slug}@example.com",hashed_password="x",first_name="C",last_name="Admin",role=UserRole.ADMIN,organization_id=org.id,is_active=True,is_verified=True);ap=GLAccount(organization_id=org.id,gl_number="2100",name="AP",account_type="LIABILITY",is_active=True);exp=GLAccount(organization_id=org.id,gl_number="6100",name="Repairs",account_type="EXPENSE",is_active=True);cash=GLAccount(organization_id=org.id,gl_number="1150",name="Trust",account_type="ASSET",is_active=True);db.add_all([user,ap,exp,cash]);db.flush();bank=BankAccount(organization_id=org.id,name="Client Trust",gl_account_id=cash.id,account_type="OPERATING",is_active=True,created_by_id=user.id);db.add(bank);db.commit();return org,user,ap,exp,cash,bank
def make_bill(db,org,user,exp):return post_bill(db=db,organization_id=org.id,created_by=user,payload=BillCreateIn(payee_name="Vendor",bill_date=date(2026,9,1),lines=[BillLineIn(gl_account_id=exp.id,amount=Decimal("100.00"))]))
@pytest.mark.accounting
def test_issue_and_void_check_updates_bill_and_gl_atomically(db):
    org,user,_ap,exp,_cash,bank=seed(db);b=make_bill(db,org,user,exp);c=issue_check(db,organization_id=org.id,created_by=user,payload=CheckIssueIn(bank_account_id=bank.id,check_date=date(2026,9,10),memo="September",allocations=[CheckAllocationIn(bill_id=b.id,amount=Decimal("60.00"))]));db.refresh(b);assert c.status=="ISSUED";assert Decimal(b.amount_paid)==Decimal("60.00");assert b.status=="PARTIAL";txn=db.get(GLTransaction,c.gl_transaction_id);assert txn.transaction_type=="CHECK";void_check(db,check=c,void_date=date(2026,9,11),reason="Printer jam",created_by=user);db.refresh(b);db.refresh(txn);assert c.status=="VOID";assert Decimal(b.amount_paid)==0;assert b.status=="UNPAID";assert txn.is_reversed
@pytest.mark.accounting
def test_check_rejects_cross_org_bill(db):
    org,user,_ap,_exp,_cash,bank=seed(db,"one");other,other_user,_a,other_exp,_c,_b=seed(db,"two");foreign=make_bill(db,other,other_user,other_exp)
    with pytest.raises(Exception,match="not found in your organization"):issue_check(db,organization_id=org.id,created_by=user,payload=CheckIssueIn(bank_account_id=bank.id,check_date=date(2026,9,10),allocations=[CheckAllocationIn(bill_id=foreign.id,amount=Decimal("10.00"))]))
