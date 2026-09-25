"""Schemas for recurring bills, manual posting, and vendor credits."""
from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Optional
from pydantic import BaseModel, Field, field_validator
from app.schemas.bill import BillLineIn

class RecurringBillCreateIn(BaseModel):
    entry_type: Literal["BILL","CREDIT"]="BILL"
    payee_name: str=Field(...,min_length=1,max_length=200)
    payee_user_id: Optional[int]=None
    start_date: date
    end_date: Optional[date]=None
    bill_day: int=Field(...,ge=1,le=31)
    due_day: Optional[int]=Field(None,ge=1,le=31)
    post_code: Optional[str]=Field(None,max_length=40)
    reference_number: Optional[str]=Field(None,max_length=60)
    remarks: Optional[str]=None
    payable_gl_account_id: Optional[int]=None
    cash_gl_account_id: Optional[int]=None
    property_id: Optional[int]=None
    unit_id: Optional[int]=None
    owner_id: Optional[int]=None
    lines: list[BillLineIn]=Field(...,min_length=1)
    @field_validator("end_date")
    @classmethod
    def validate_end_date(cls,value,info):
        start=info.data.get("start_date")
        if value is not None and start is not None and value<start: raise ValueError("end_date cannot be before start_date")
        return value

class RecurringBillLineOut(BaseModel):
    id:int; gl_account_id:int; property_id:Optional[int]=None; unit_id:Optional[int]=None; description:Optional[str]=None; amount:Decimal
    class Config: from_attributes=True
class RecurringBillOut(BaseModel):
    id:int; organization_id:int; entry_type:str; payee_name:str; payee_user_id:Optional[int]=None
    start_date:date; end_date:Optional[date]=None; bill_day:int; due_day:Optional[int]=None; post_code:Optional[str]=None
    next_post_date:date; last_posted_date:Optional[date]=None; reference_number:Optional[str]=None; remarks:Optional[str]=None
    payable_gl_account_id:int; cash_gl_account_id:Optional[int]=None; property_id:Optional[int]=None; unit_id:Optional[int]=None; owner_id:Optional[int]=None
    is_active:bool; created_by_id:Optional[int]=None; created_at:datetime; updated_at:datetime; lines:list[RecurringBillLineOut]=[]
    class Config: from_attributes=True
class RecurringBillPostIn(BaseModel):
    as_of:date; schedule_ids:list[int]=Field(default_factory=list)
class RecurringBillPostResult(BaseModel):
    posted_bills:int; posted_credits:int; skipped_disabled:int; failed:int
class VendorCreditCreateIn(BaseModel):
    payee_name:str=Field(...,min_length=1,max_length=200); payee_user_id:Optional[int]=None; credit_date:date
    reference_number:Optional[str]=Field(None,max_length=60); credit_number:Optional[str]=Field(None,max_length=40)
    payable_gl_account_id:Optional[int]=None; property_id:Optional[int]=None; unit_id:Optional[int]=None; owner_id:Optional[int]=None
    remarks:Optional[str]=None; source_type:Optional[str]=Field(None,max_length=40); source_id:Optional[int]=None
    lines:list[BillLineIn]=Field(...,min_length=1)
class VendorCreditLineOut(BaseModel):
    id:int; gl_account_id:int; property_id:Optional[int]=None; unit_id:Optional[int]=None; description:Optional[str]=None; amount:Decimal
    class Config: from_attributes=True
class VendorCreditOut(BaseModel):
    id:int; organization_id:int; credit_number:Optional[str]=None; payee_name:str; payee_user_id:Optional[int]=None; credit_date:date
    reference_number:Optional[str]=None; amount:Decimal; property_id:Optional[int]=None; unit_id:Optional[int]=None; owner_id:Optional[int]=None
    payable_gl_account_id:int; remarks:Optional[str]=None; source_type:Optional[str]=None; source_id:Optional[int]=None
    gl_transaction_id:Optional[int]=None; status:str; is_reversed:bool; is_active:bool; created_by_id:Optional[int]=None
    created_at:datetime; updated_at:datetime; lines:list[VendorCreditLineOut]=[]
    class Config: from_attributes=True
