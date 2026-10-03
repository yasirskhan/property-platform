from __future__ import annotations
from datetime import date
from decimal import Decimal
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.core.database import Base
from app.models.bank_account import BankAccount
from app.models.bank_reconciliation import BankReconciliation,BankReconciliationItem,BankStatementLine
from app.models.check import Check
from app.models.deposit import Deposit
from app.models.gl_account import GLAccount
from app.models.gl_entry import GLEntry
from app.models.gl_transaction import GLTransaction
from app.models.user import Organization,User,UserRole
from app.services.bank_reconciliation import finish_reconciliation,import_qif,set_cleared_items,start_reconciliation
from app.services.gl_posting import PostingError
TABLES=[Organization.__table__,User.__table__,GLAccount.__table__,BankAccount.__table__,GLTransaction.__table__,GLEntry.__table__,Deposit.__table__,Check.__table__,BankReconciliation.__table__,BankReconciliationItem.__table__,BankStatementLine.__table__]
@pytest.fixture()
def db():
 e=create_engine("sqlite+pysqlite:///:memory:",connect_args={"check_same_thread":False},poolclass=StaticPool);Base.metadata.create_all(e,tables=TABLES);s=sessionmaker(bind=e,expire_on_commit=False)()
 try:yield s
 finally:s.close();e.dispose()
def seed(db):
 org=Organization(name="Recon",slug="recon");db.add(org);db.flush();u=User(email="recon@example.com",hashed_password="x",first_name="R",last_name="A",role=UserRole.ADMIN,organization_id=org.id,is_active=True,is_verified=True);cash=GLAccount(organization_id=org.id,gl_number="1150",name="Trust",account_type="ASSET",is_active=True);db.add_all([u,cash]);db.flush();bank=BankAccount(organization_id=org.id,name="Trust",gl_account_id=cash.id,account_type="OPERATING",is_active=True,created_by_id=u.id);db.add(bank);db.flush();dep=Deposit(organization_id=org.id,bank_gl_account_id=cash.id,deposit_date=date(2026,9,2),deposit_number="D-1",total=Decimal("100"),is_active=True,created_by_id=u.id);chk=Check(organization_id=org.id,bank_account_id=bank.id,check_number="1",check_date=date(2026,9,3),payee_name="Vendor",amount=Decimal("40"),status="ISSUED",created_by_id=u.id);db.add_all([dep,chk]);db.commit();return org,u,bank
@pytest.mark.accounting
def test_reconciliation_balances_and_finishes(db):
 org,u,bank=seed(db);r=start_reconciliation(db,organization_id=org.id,bank_account=bank,statement_date=date(2026,9,30),ending_balance=Decimal("60"),created_by=u);db.refresh(r);assert len(r.items)==2;set_cleared_items(db,reconciliation=r,item_ids=[x.id for x in r.items]);db.refresh(r);finish_reconciliation(db,reconciliation=r,user=u);assert r.status=="RECONCILED"
@pytest.mark.accounting
def test_finish_rejects_difference_and_qif_exact_match_clears(db):
 org,u,bank=seed(db);r=start_reconciliation(db,organization_id=org.id,bank_account=bank,statement_date=date(2026,9,30),ending_balance=Decimal("100"),created_by=u)
 with pytest.raises(PostingError,match="not balanced"):finish_reconciliation(db,reconciliation=r,user=u)
 count,matched=import_qif(db,reconciliation=r,content="D9/2/26\nT100.00\nPDeposit\n^\n");assert(count,matched)==(1,1);db.refresh(r);assert sum(1 for x in r.items if x.cleared)==1
