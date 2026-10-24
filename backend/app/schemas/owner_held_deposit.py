"""Schemas for Owner Held Security Deposits."""
from datetime import datetime
from pydantic import BaseModel


class DepositKeyAccountIn(BaseModel):
    gl_account_id: int


class DepositGLAccountOut(BaseModel):
    gl_account_id: int
    gl_number: str
    name: str
    offset_account: str | None = None


class DepositKeyAccountOut(DepositGLAccountOut):
    id: int
    organization_id: int
    created_at: datetime


class OwnerHeldDepositSetupOut(BaseModel):
    operating_cash_gl_number: str
    key_accounts: list[DepositKeyAccountOut]
    eligible_accounts: list[DepositGLAccountOut]
