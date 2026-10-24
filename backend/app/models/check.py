"""Bank-account-backed checks and bill allocations."""
from __future__ import annotations
from datetime import datetime
from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from app.core.database import Base

class Check(Base):
    __tablename__ = "checks"
    __table_args__ = (UniqueConstraint("organization_id","check_number",name="uq_checks_org_number"),)
    id=Column(Integer,primary_key=True,index=True)
    organization_id=Column(Integer,ForeignKey("organizations.id",ondelete="CASCADE"),nullable=False,index=True)
    bank_account_id=Column(Integer,ForeignKey("bank_accounts.id",ondelete="RESTRICT"),nullable=False,index=True)
    check_number=Column(String(40),nullable=True,index=True)
    check_date=Column(Date,nullable=False,index=True)
    payee_name=Column(String(200),nullable=False,index=True)
    memo=Column(Text,nullable=True)
    amount=Column(Numeric(14,2),nullable=False)
    status=Column(String(20),nullable=False,default="ISSUED",server_default="ISSUED",index=True)
    gl_transaction_id=Column(Integer,ForeignKey("gl_transactions.id",ondelete="SET NULL"),nullable=True,index=True)
    void_gl_transaction_id=Column(Integer,ForeignKey("gl_transactions.id",ondelete="SET NULL"),nullable=True,index=True)
    void_reason=Column(Text,nullable=True)
    voided_at=Column(DateTime,nullable=True)
    voided_by_id=Column(Integer,ForeignKey("users.id",ondelete="SET NULL"),nullable=True)
    created_by_id=Column(Integer,ForeignKey("users.id",ondelete="SET NULL"),nullable=True)
    created_at=Column(DateTime,nullable=False,default=datetime.utcnow)
    updated_at=Column(DateTime,nullable=False,default=datetime.utcnow,onupdate=datetime.utcnow)
    bank_account=relationship("BankAccount")
    allocations=relationship("CheckBillAllocation",back_populates="check",cascade="all, delete-orphan",order_by="CheckBillAllocation.id")
    gl_transaction=relationship("GLTransaction",foreign_keys=[gl_transaction_id])
    void_gl_transaction=relationship("GLTransaction",foreign_keys=[void_gl_transaction_id])

class CheckBillAllocation(Base):
    __tablename__="check_bill_allocations"
    __table_args__=(UniqueConstraint("check_id","bill_id",name="uq_check_bill_allocation"),)
    id=Column(Integer,primary_key=True,index=True)
    check_id=Column(Integer,ForeignKey("checks.id",ondelete="CASCADE"),nullable=False,index=True)
    bill_id=Column(Integer,ForeignKey("bills.id",ondelete="RESTRICT"),nullable=False,index=True)
    amount=Column(Numeric(14,2),nullable=False)
    created_at=Column(DateTime,nullable=False,default=datetime.utcnow)
    check=relationship("Check",back_populates="allocations")
    bill=relationship("Bill")
