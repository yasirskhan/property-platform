from __future__ import annotations
from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, Field
from typing import Optional

class CheckAllocationIn(BaseModel):
    bill_id:int
    amount:Decimal=Field(...,gt=0)
class CheckIssueIn(BaseModel):
    bank_account_id:int
    check_date:date
    check_number:Optional[str]=Field(None,max_length=40)
    memo:Optional[str]=None
    allocations:list[CheckAllocationIn]=Field(...,min_length=1)
class CheckVoidIn(BaseModel):
    void_date:date
    reason:Optional[str]=None
class CheckMemoIn(BaseModel):
    memo:Optional[str]=None
class EligibleBillOut(BaseModel):
    id:int; bill_number:Optional[str]=None; payee_name:str; bill_date:date; due_date:Optional[date]=None; amount:Decimal; amount_paid:Decimal; outstanding:Decimal; property_id:Optional[int]=None
class CheckBankAccountOut(BaseModel):
    id:int; name:str; account_type:str; gl_account_id:int
class CheckAllocationOut(BaseModel):
    id:int; bill_id:int; bill_number:Optional[str]=None; amount:Decimal
class CheckOut(BaseModel):
    id:int; organization_id:int; bank_account_id:int; bank_account_name:Optional[str]=None; check_number:Optional[str]=None; check_date:date; payee_name:str; memo:Optional[str]=None; amount:Decimal; status:str; gl_transaction_id:Optional[int]=None; void_gl_transaction_id:Optional[int]=None; void_reason:Optional[str]=None; voided_at:Optional[datetime]=None; created_by_id:Optional[int]=None; created_at:datetime; updated_at:datetime; allocations:list[CheckAllocationOut]=[]
class CheckListOut(BaseModel):
    items:list[CheckOut]; total:int
