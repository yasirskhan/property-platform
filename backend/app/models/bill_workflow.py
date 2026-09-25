"""Recurring payable templates and positive-value vendor credits."""
from __future__ import annotations
from datetime import datetime
from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.orm import relationship
from app.core.database import Base

class RecurringBill(Base):
    __tablename__="recurring_bills"
    __table_args__=(Index("ix_recurring_bills_due","organization_id","is_active","next_post_date"),)
    id=Column(Integer,primary_key=True)
    organization_id=Column(Integer,ForeignKey("organizations.id",ondelete="CASCADE"),nullable=False,index=True)
    entry_type=Column(String(20),nullable=False,default="BILL",server_default="BILL",index=True)
    payee_name=Column(String(200),nullable=False)
    payee_user_id=Column(Integer,ForeignKey("users.id",ondelete="SET NULL"),nullable=True,index=True)
    start_date=Column(Date,nullable=False)
    end_date=Column(Date,nullable=True)
    bill_day=Column(Integer,nullable=False)
    due_day=Column(Integer,nullable=True)
    post_code=Column(String(40),nullable=True,index=True)
    next_post_date=Column(Date,nullable=False,index=True)
    last_posted_date=Column(Date,nullable=True)
    reference_number=Column(String(60),nullable=True)
    remarks=Column(Text,nullable=True)
    payable_gl_account_id=Column(Integer,ForeignKey("gl_accounts.id",ondelete="RESTRICT"),nullable=False,index=True)
    cash_gl_account_id=Column(Integer,ForeignKey("gl_accounts.id",ondelete="RESTRICT"),nullable=True,index=True)
    property_id=Column(Integer,ForeignKey("properties.id",ondelete="SET NULL"),nullable=True,index=True)
    unit_id=Column(Integer,ForeignKey("units.id",ondelete="SET NULL"),nullable=True,index=True)
    owner_id=Column(Integer,ForeignKey("users.id",ondelete="SET NULL"),nullable=True,index=True)
    is_active=Column(Boolean,nullable=False,default=True,server_default="1")
    created_by_id=Column(Integer,ForeignKey("users.id",ondelete="SET NULL"),nullable=True,index=True)
    created_at=Column(DateTime,nullable=False,default=datetime.utcnow)
    updated_at=Column(DateTime,nullable=False,default=datetime.utcnow,onupdate=datetime.utcnow)
    lines=relationship("RecurringBillLine",back_populates="recurring_bill",cascade="all, delete-orphan",order_by="RecurringBillLine.id")

class RecurringBillLine(Base):
    __tablename__="recurring_bill_lines"
    id=Column(Integer,primary_key=True)
    recurring_bill_id=Column(Integer,ForeignKey("recurring_bills.id",ondelete="CASCADE"),nullable=False,index=True)
    gl_account_id=Column(Integer,ForeignKey("gl_accounts.id",ondelete="RESTRICT"),nullable=False,index=True)
    property_id=Column(Integer,ForeignKey("properties.id",ondelete="SET NULL"),nullable=True,index=True)
    unit_id=Column(Integer,ForeignKey("units.id",ondelete="SET NULL"),nullable=True,index=True)
    description=Column(String(500),nullable=True)
    amount=Column(Numeric(14,2),nullable=False)
    created_at=Column(DateTime,nullable=False,default=datetime.utcnow)
    recurring_bill=relationship("RecurringBill",back_populates="lines")

class VendorCredit(Base):
    __tablename__="vendor_credits"
    id=Column(Integer,primary_key=True,index=True)
    organization_id=Column(Integer,ForeignKey("organizations.id",ondelete="CASCADE"),nullable=False,index=True)
    credit_number=Column(String(40),nullable=True,index=True)
    payee_name=Column(String(200),nullable=False)
    payee_user_id=Column(Integer,ForeignKey("users.id",ondelete="SET NULL"),nullable=True,index=True)
    credit_date=Column(Date,nullable=False,index=True)
    reference_number=Column(String(60),nullable=True)
    amount=Column(Numeric(14,2),nullable=False)
    property_id=Column(Integer,ForeignKey("properties.id",ondelete="SET NULL"),nullable=True,index=True)
    unit_id=Column(Integer,ForeignKey("units.id",ondelete="SET NULL"),nullable=True,index=True)
    owner_id=Column(Integer,ForeignKey("users.id",ondelete="SET NULL"),nullable=True,index=True)
    payable_gl_account_id=Column(Integer,ForeignKey("gl_accounts.id",ondelete="RESTRICT"),nullable=False,index=True)
    remarks=Column(Text,nullable=True)
    source_type=Column(String(40),nullable=True,index=True)
    source_id=Column(Integer,nullable=True)
    gl_transaction_id=Column(Integer,ForeignKey("gl_transactions.id",ondelete="SET NULL"),nullable=True,index=True)
    status=Column(String(20),nullable=False,default="POSTED",server_default="POSTED",index=True)
    is_reversed=Column(Boolean,nullable=False,default=False,server_default="0")
    reversal_of_id=Column(Integer,ForeignKey("vendor_credits.id",ondelete="SET NULL"),nullable=True)
    is_active=Column(Boolean,nullable=False,default=True,server_default="1",index=True)
    created_by_id=Column(Integer,ForeignKey("users.id",ondelete="SET NULL"),nullable=True)
    created_at=Column(DateTime,nullable=False,default=datetime.utcnow)
    updated_at=Column(DateTime,nullable=False,default=datetime.utcnow,onupdate=datetime.utcnow)
    lines=relationship("VendorCreditLine",back_populates="vendor_credit",cascade="all, delete-orphan",order_by="VendorCreditLine.id")

class VendorCreditLine(Base):
    __tablename__="vendor_credit_lines"
    id=Column(Integer,primary_key=True)
    vendor_credit_id=Column(Integer,ForeignKey("vendor_credits.id",ondelete="CASCADE"),nullable=False,index=True)
    organization_id=Column(Integer,ForeignKey("organizations.id",ondelete="CASCADE"),nullable=False,index=True)
    gl_account_id=Column(Integer,ForeignKey("gl_accounts.id",ondelete="RESTRICT"),nullable=False,index=True)
    property_id=Column(Integer,ForeignKey("properties.id",ondelete="SET NULL"),nullable=True,index=True)
    unit_id=Column(Integer,ForeignKey("units.id",ondelete="SET NULL"),nullable=True,index=True)
    description=Column(String(500),nullable=True)
    amount=Column(Numeric(14,2),nullable=False)
    created_at=Column(DateTime,nullable=False,default=datetime.utcnow)
    vendor_credit=relationship("VendorCredit",back_populates="lines")
