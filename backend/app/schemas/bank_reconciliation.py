from __future__ import annotations
from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, Field
from typing import Optional

class ReconciliationStartIn(BaseModel):
    statement_date:date
    ending_statement_balance:Decimal

class ReconciliationSelectionIn(BaseModel):
    cleared_item_ids:list[int]

class QIFImportIn(BaseModel):
    content:str=Field(...,min_length=1,max_length=2_000_000)

class ReconciliationItemOut(BaseModel):
    id:int;source_type:str;source_id:int;transaction_date:date;description:Optional[str]=None;reference_number:Optional[str]=None;signed_amount:Decimal;cleared:bool

class StatementLineOut(BaseModel):
    id:int;posted_date:date;amount:Decimal;payee:Optional[str]=None;memo:Optional[str]=None;reference_number:Optional[str]=None;matched_item_id:Optional[int]=None

class ReconciliationOut(BaseModel):
    id:int;organization_id:int;bank_account_id:int;bank_account_name:Optional[str]=None;statement_date:date;beginning_balance:Decimal;ending_statement_balance:Decimal;cleared_balance:Decimal;difference:Decimal;balanced:bool;status:str;finished_at:Optional[datetime]=None;items:list[ReconciliationItemOut]=[];statement_lines:list[StatementLineOut]=[]

class QIFImportOut(BaseModel):
    imported:int
    matched:int
    reconciliation:ReconciliationOut
