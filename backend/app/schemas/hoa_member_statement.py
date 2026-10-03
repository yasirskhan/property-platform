"""Actual posted association-member assessment balances, no new posting."""
from datetime import date
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel

class HOAMemberStatementPaymentOut(BaseModel):
    id: int
    amount: Decimal
    received_on: date
    status: Literal["POSTED", "REVERSED"]
    receipt_id: int
    reversal_receipt_id: int | None

class HOAMemberStatementChargeOut(BaseModel):
    id: int
    proposal_id: int
    amount: Decimal
    amount_paid: Decimal
    outstanding: Decimal
    due_on: date
    status: Literal["OPEN", "PAID", "REVERSED"]
    gl_transaction_id: int
    reversal_transaction_id: int | None
    payments: list[HOAMemberStatementPaymentOut]

class HOAMemberStatementOut(BaseModel):
    member_user_id: int
    total_assessed: Decimal
    total_paid: Decimal
    outstanding: Decimal
    charges: list[HOAMemberStatementChargeOut]
