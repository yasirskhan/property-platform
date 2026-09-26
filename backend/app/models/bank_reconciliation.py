"""Durable bank reconciliation snapshots and imported statement lines."""
from __future__ import annotations
from datetime import datetime
from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from app.core.database import Base

class BankReconciliation(Base):
    __tablename__="bank_reconciliations"
    id=Column(Integer,primary_key=True,index=True)
    organization_id=Column(Integer,ForeignKey("organizations.id",ondelete="CASCADE"),nullable=False,index=True)
    bank_account_id=Column(Integer,ForeignKey("bank_accounts.id",ondelete="RESTRICT"),nullable=False,index=True)
    statement_date=Column(Date,nullable=False,index=True)
    beginning_balance=Column(Numeric(14,2),nullable=False,default=0)
    ending_statement_balance=Column(Numeric(14,2),nullable=False)
    status=Column(String(20),nullable=False,default="OPEN",server_default="OPEN",index=True)
    finished_at=Column(DateTime,nullable=True)
    finished_by_id=Column(Integer,ForeignKey("users.id",ondelete="SET NULL"),nullable=True)
    created_by_id=Column(Integer,ForeignKey("users.id",ondelete="SET NULL"),nullable=True)
    created_at=Column(DateTime,nullable=False,default=datetime.utcnow)
    updated_at=Column(DateTime,nullable=False,default=datetime.utcnow,onupdate=datetime.utcnow)
    bank_account=relationship("BankAccount")
    items=relationship("BankReconciliationItem",back_populates="reconciliation",cascade="all, delete-orphan",order_by="BankReconciliationItem.transaction_date, BankReconciliationItem.id")
    statement_lines=relationship("BankStatementLine",back_populates="reconciliation",cascade="all, delete-orphan",order_by="BankStatementLine.posted_date, BankStatementLine.id")

class BankReconciliationItem(Base):
    __tablename__="bank_reconciliation_items"
    __table_args__=(UniqueConstraint("reconciliation_id","source_type","source_id",name="uq_bank_recon_source"),)
    id=Column(Integer,primary_key=True,index=True)
    reconciliation_id=Column(Integer,ForeignKey("bank_reconciliations.id",ondelete="CASCADE"),nullable=False,index=True)
    organization_id=Column(Integer,ForeignKey("organizations.id",ondelete="CASCADE"),nullable=False,index=True)
    source_type=Column(String(30),nullable=False,index=True)
    source_id=Column(Integer,nullable=False,index=True)
    transaction_date=Column(Date,nullable=False,index=True)
    description=Column(String(500),nullable=True)
    reference_number=Column(String(80),nullable=True)
    signed_amount=Column(Numeric(14,2),nullable=False)
    cleared=Column(Boolean,nullable=False,default=False,server_default="0",index=True)
    created_at=Column(DateTime,nullable=False,default=datetime.utcnow)
    reconciliation=relationship("BankReconciliation",back_populates="items")

class BankStatementLine(Base):
    __tablename__="bank_statement_lines"
    id=Column(Integer,primary_key=True,index=True)
    reconciliation_id=Column(Integer,ForeignKey("bank_reconciliations.id",ondelete="CASCADE"),nullable=False,index=True)
    organization_id=Column(Integer,ForeignKey("organizations.id",ondelete="CASCADE"),nullable=False,index=True)
    posted_date=Column(Date,nullable=False,index=True)
    amount=Column(Numeric(14,2),nullable=False)
    payee=Column(String(300),nullable=True)
    memo=Column(Text,nullable=True)
    reference_number=Column(String(100),nullable=True)
    matched_item_id=Column(Integer,ForeignKey("bank_reconciliation_items.id",ondelete="SET NULL"),nullable=True,index=True)
    created_at=Column(DateTime,nullable=False,default=datetime.utcnow)
    reconciliation=relationship("BankReconciliation",back_populates="statement_lines")
    matched_item=relationship("BankReconciliationItem")
