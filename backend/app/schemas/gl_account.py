# ============================================================
# gl_account.py (schemas)
# ------------------------------------------------------------
# Pydantic shapes for the GL accounts API.
# ============================================================

from datetime import datetime
from typing import Optional, List, Dict
from decimal import Decimal
from pydantic import BaseModel, Field


# ------------------------------------------------------------
# Create / Update
# ------------------------------------------------------------

class GLAccountCreate(BaseModel):
    gl_number: str = Field(..., min_length=1, max_length=20)
    name: str = Field(..., min_length=1, max_length=255)
    account_type: str = Field(..., min_length=1, max_length=20)
    sub_account_of: Optional[int] = None
    offset_account: Optional[str] = Field(None, max_length=20)
    subject_to_mgmt_fees: bool = False
    include_on_cash_flow: bool = True
    must_clear: bool = False


class GLAccountUpdate(BaseModel):
    # Every field optional — send only what changed.
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    account_type: Optional[str] = Field(None, min_length=1, max_length=20)
    sub_account_of: Optional[int] = None
    offset_account: Optional[str] = Field(None, max_length=20)
    subject_to_mgmt_fees: Optional[bool] = None
    include_on_cash_flow: Optional[bool] = None
    must_clear: Optional[bool] = None


# ------------------------------------------------------------
# Out
# ------------------------------------------------------------

class GLAccountOut(BaseModel):
    id: int
    organization_id: int
    gl_number: str
    name: str
    account_type: str
    sub_account_of: Optional[int] = None
    offset_account: Optional[str] = None
    subject_to_mgmt_fees: bool
    include_on_cash_flow: bool
    must_clear: bool
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ------------------------------------------------------------
# List response — grouped by type for the frontend
# ------------------------------------------------------------

class GLAccountGroup(BaseModel):
    account_type: str          # ASSET | LIABILITY | EQUITY | INCOME | EXPENSE
    accounts: List[GLAccountOut]


class GLAccountListOut(BaseModel):
    groups: List[GLAccountGroup]
    total: int

class GLAccountPostingPermissionRow(BaseModel):
    gl_account_id: int
    gl_number: str
    name: str
    permissions: Dict[str, bool]

class GLAccountPostingPermissionMatrixOut(BaseModel):
    roles: List[str]
    rows: List[GLAccountPostingPermissionRow]

class GLAccountPostingPermissionMatrixUpdate(BaseModel):
    values: Dict[int, Dict[str, bool]]

class GLAccountRecalculationOut(BaseModel):
    source: str
    account_count: int
    entry_count: int
    total_debits: Decimal
    total_credits: Decimal
    net_balance: Decimal
    is_balanced: bool
    recalculated_at: datetime
