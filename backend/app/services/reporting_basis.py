"""Reporting-only accounting-basis resolver."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.accounting_settings import AccountingSettings

ACCRUAL = "ACCRUAL"
CASH = "CASH"

def get_accounting_basis(db: Session, *, organization_id: int) -> str:
    settings = db.get(AccountingSettings, organization_id)
    basis = str(settings.accounting_basis if settings else ACCRUAL).upper()
    return CASH if basis == CASH else ACCRUAL
